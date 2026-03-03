/**
 * softwareos-base — IM Webhook Routes
 * URI: softwareos-base://backend/api/routes/im-webhook
 *
 * Receives normalized webhook payloads forwarded by the Cloudflare
 * webhook-router worker. Routes messages to AI service via ai-proxy,
 * persists conversation state, and returns responses for channel adapters.
 */

import { Router, Request, Response, NextFunction } from "express";
import { v1 as uuidv1 } from "uuid";
import * as aiProxy from "../services/ai-proxy";
import * as db from "../services/supabase";
import pino from "pino";

const logger = pino({ level: process.env.ECO_LOG_LEVEL || "info" });

export const imWebhookRouter = Router();

// ─── Types ───────────────────────────────────────────────────────────

type Channel = "whatsapp" | "telegram" | "line" | "messenger";

interface IncomingWebhookPayload {
  channel: Channel;
  event_type: string;
  sender_id: string;
  chat_id: string;
  text: string;
  message_id: string;
  timestamp: string;
  raw: unknown;
  signature_valid: boolean;
  idempotency_key: string;
  uri: string;
  urn: string;
}

interface WebhookResponse {
  status: string;
  channel: Channel;
  message_id: string;
  reply_text: string;
  conversation_id: string;
  idempotency_key: string;
  latency_ms: number;
  uri: string;
  urn: string;
}

const VALID_CHANNELS: Set<string> = new Set(["whatsapp", "telegram", "line", "messenger"]);

// ─── POST /api/v1/im/webhook — Main webhook ingestion ────────────────

imWebhookRouter.post("/webhook", async (req: Request, res: Response, next: NextFunction): Promise<void> => {
  const startTime = Date.now();

  try {
    const payload = req.body as IncomingWebhookPayload;

    // Validate required fields
    if (!payload.channel || !VALID_CHANNELS.has(payload.channel)) {
      res.status(400).json({
        error: "validation_error",
        message: `Invalid or missing channel. Expected one of: ${[...VALID_CHANNELS].join(", ")}`,
      });
      return;
    }

    if (!payload.signature_valid) {
      res.status(401).json({
        error: "unauthorized",
        message: "Webhook signature not verified",
      });
      return;
    }

    // Also accept channel from header (Cloudflare worker sets this)
    const headerChannel = req.headers["x-webhook-channel"] as string | undefined;
    if (headerChannel && headerChannel !== payload.channel) {
      res.status(400).json({
        error: "validation_error",
        message: "Channel mismatch between header and payload",
      });
      return;
    }

    // Skip non-text events (status updates, read receipts, etc.)
    if (!payload.text || payload.text.trim().length === 0) {
      res.status(200).json({
        status: "ignored",
        reason: "no_text_content",
        channel: payload.channel,
        message_id: payload.message_id,
      });
      return;
    }

    const conversationId = uuidv1();
    const jobId = uuidv1();

    logger.info({
      msg: "Processing IM webhook",
      channel: payload.channel,
      sender_id: payload.sender_id,
      message_id: payload.message_id,
      idempotency_key: payload.idempotency_key,
    });

    // Persist AI job for tracking
    try {
      await db.createAiJob({
        user_id: `im:${payload.channel}:${payload.sender_id}`,
        prompt: payload.text,
        model_id: "default",
        model_params: {
          temperature: 0.7,
          top_p: 0.9,
          max_tokens: 1024,
          stream: false,
          channel: payload.channel,
          conversation_id: conversationId,
        },
        uri: `softwareos-base://ai/job/${jobId}`,
        urn: `urn:softwareos-base:ai:job:${jobId}`,
      });
    } catch (dbErr) {
      // Non-fatal: log but continue processing
      logger.warn({
        msg: "Failed to persist AI job",
        error: (dbErr as Error).message,
        channel: payload.channel,
      });
    }

    // Route to AI service
    let replyText: string;
    try {
      const aiResponse = await aiProxy.generate({
        prompt: payload.text,
        model_id: "default",
        max_tokens: 1024,
        temperature: 0.7,
        top_p: 0.9,
      });
      replyText = aiResponse.content || "No response generated.";
    } catch (aiErr) {
      logger.error({
        msg: "AI service error for IM webhook",
        error: (aiErr as Error).message,
        channel: payload.channel,
      });
      replyText = "I'm having trouble processing your request. Please try again shortly.";
    }

    const latencyMs = Date.now() - startTime;

    const response: WebhookResponse = {
      status: "ok",
      channel: payload.channel,
      message_id: payload.message_id,
      reply_text: replyText,
      conversation_id: conversationId,
      idempotency_key: payload.idempotency_key || "",
      latency_ms: latencyMs,
      uri: `softwareos-base://im/${payload.channel}/response/${payload.message_id}`,
      urn: `urn:softwareos-base:im:${payload.channel}:response:${payload.sender_id}:${payload.message_id}`,
    };

    logger.info({
      msg: "IM webhook processed",
      channel: payload.channel,
      sender_id: payload.sender_id,
      latency_ms: latencyMs,
    });

    res.status(200).json(response);
  } catch (err) {
    next(err);
  }
});

// ─── GET /api/v1/im/health — IM subsystem health ────────────────────

imWebhookRouter.get("/health", (_req: Request, res: Response): void => {
  res.status(200).json({
    status: "healthy",
    service: "im-webhook",
    version: "1.0.0",
    channels: ["whatsapp", "telegram", "line", "messenger"],
    uri: "softwareos-base://backend/api/im-webhook/health",
    timestamp: new Date().toISOString(),
  });
});