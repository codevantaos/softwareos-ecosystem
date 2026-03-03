/**
 * softwareos-base — AI Job Poller
 * URI: softwareos-base://backend/api/services/job-poller
 *
 * Polls pending/running AI jobs from Supabase, checks upstream AI service
 * for completion, updates DB, and pushes status via Socket.IO.
 *
 * Lifecycle:
 *   start() → interval loop → poll() → for each job → checkAndUpdate()
 *   stop()  → clears interval
 */

import { Server as SocketIOServer } from "socket.io";
import * as db from "./supabase";
import * as aiProxy from "./ai-proxy";

// ── Configuration ────────────────────────────────────────────────────────────

const POLL_INTERVAL_MS = parseInt(process.env.ECO_JOB_POLL_INTERVAL_MS || "3000", 10);
const POLL_BATCH_SIZE = parseInt(process.env.ECO_JOB_POLL_BATCH_SIZE || "20", 10);
const STALE_JOB_TIMEOUT_MS = parseInt(process.env.ECO_JOB_STALE_TIMEOUT_MS || "300000", 10);

// ── State ────────────────────────────────────────────────────────────────────

let _timer: ReturnType<typeof setInterval> | null = null;
let _io: SocketIOServer | null = null;
let _polling = false;

// ── Public API ───────────────────────────────────────────────────────────────

export function start(io: SocketIOServer): void {
  if (_timer) return;
  _io = io;
  _timer = setInterval(() => {
    poll().catch(() => {});
  }, POLL_INTERVAL_MS);
}

export function stop(): void {
  if (_timer) {
    clearInterval(_timer);
    _timer = null;
  }
  _io = null;
}

export function isRunning(): boolean {
  return _timer !== null;
}

// ── Core Poll Loop ───────────────────────────────────────────────────────────

async function poll(): Promise<void> {
  if (_polling) return;
  _polling = true;

  try {
    const jobs = await db.getPendingJobs(POLL_BATCH_SIZE);

    for (const job of jobs) {
      try {
        await checkAndUpdate(job);
      } catch {
        // Individual job failure does not stop the batch
      }
    }
  } finally {
    _polling = false;
  }
}

// ── Per-Job Check ────────────────────────────────────────────────────────────

async function checkAndUpdate(job: db.AiJobRow): Promise<void> {
  const createdMs = new Date(job.created_at).getTime();
  const now = Date.now();

  // Mark stale jobs as failed
  if (now - createdMs > STALE_JOB_TIMEOUT_MS) {
    await db.updateAiJob(job.id, {
      status: "failed",
      error: "Job timed out after " + Math.round(STALE_JOB_TIMEOUT_MS / 1000) + "s",
      completed_at: new Date().toISOString(),
    });
    emitJobEvent(job.user_id, job.id, "failed", null, "Job timed out");
    return;
  }

  // Query upstream AI service for job status
  let upstream: {
    id: string;
    status: string;
    result: string | null;
    error: string | null;
    engine: string | null;
    latency_ms: number | null;
  };

  try {
    upstream = await aiProxy.getJobStatus(job.id);
  } catch {
    // AI service unreachable — skip this cycle, will retry next poll
    return;
  }

  // No status change
  if (upstream.status === job.status) {
    if (upstream.status === "running") {
      emitJobEvent(job.user_id, job.id, "running", null, null);
    }
    return;
  }

  // Status changed — update DB
  const updates: Partial<db.AiJobRow> = {
    status: upstream.status,
  };

  if (upstream.engine) updates.engine = upstream.engine;
  if (upstream.latency_ms != null) updates.latency_ms = upstream.latency_ms;

  if (upstream.status === "completed") {
    updates.result = upstream.result;
    updates.completed_at = new Date().toISOString();
  }

  if (upstream.status === "failed") {
    updates.error = upstream.error || "Unknown upstream error";
    updates.completed_at = new Date().toISOString();
  }

  await db.updateAiJob(job.id, updates);

  // Push WebSocket event
  emitJobEvent(
    job.user_id,
    job.id,
    upstream.status,
    upstream.status === "completed" ? upstream.result : null,
    upstream.status === "failed" ? (upstream.error || "Unknown error") : null
  );

  // Record governance event for completed jobs
  if (upstream.status === "completed" || upstream.status === "failed") {
    await db.insertGovernanceRecord({
      action: `ai_job_${upstream.status}`,
      resource_type: "ai_job",
      resource_id: job.id,
      actor_id: job.user_id,
      details: {
        model_id: job.model_id,
        engine: upstream.engine,
        latency_ms: upstream.latency_ms,
        status: upstream.status,
      },
      compliance_tags: ["ai-inference"],
      uri: `softwareos-base://ai/job/${job.id}`,
    }).catch(() => {});
  }
}

// ── WebSocket Emit ───────────────────────────────────────────────────────────

function emitJobEvent(
  userId: string,
  jobId: string,
  status: string,
  result: string | null,
  error: string | null
): void {
  if (!_io) return;

  const payload = {
    jobId,
    status,
    result,
    error,
    timestamp: Date.now(),
  };

  // Emit to user-specific room (user joins room on WS connect)
  _io.to(`user:${userId}`).emit("ai:job:progress", payload);

  if (status === "completed") {
    _io.to(`user:${userId}`).emit("ai:job:complete", payload);
  }
}