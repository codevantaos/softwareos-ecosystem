/**
 * softwareos-base LINE Messaging API Adapter
 *
 * Production-grade adapter for LINE Messaging API.
 * Uses shared normalizer for message parsing, shared router for
 * AI backend routing with Redis session management.
 *
 * Features:
 * - HMAC-SHA256 signature verification (base64)
 * - Reply token management with expiry awareness
 * - Push message fallback when reply token expires
 * - Structured JSON logging
 * - Graceful shutdown
 * - Health + metrics endpoints
 *
 * URI: softwareos-base://platforms/im-integration/line
 */

import express from "express";
import crypto from "crypto";
import pino from "pino";
import { normalizeLINE, type NormalizedMessage } from "../../shared/normalizer";
import { MessageRouter } from "../../shared/router";

// ─── Configuration ───────────────────────────────────────────────────

const PORT = parseInt(process.env.ECO_LINE_PORT || "3003", 10);
const CHANNEL_SECRET = process.env.ECO_LINE_CHANNEL_SECRET || "";
const CHANNEL_ACCESS_TOKEN = process.env.ECO_LINE_CHANNEL_ACCESS_TOKEN || "";
const LINE_REPLY_API = "https://api.line.me/v2/bot/message/reply";
const LINE_PUSH_API = "https://api.line.me/v2/bot/message/push";

const logger = pino({
  level: process.env.ECO_LOG_LEVEL || "info",
  name: "eco-line-adapter",
});

const messageRouter = new MessageRouter(
  process.env.ECO_REDIS_URL || "redis://localhost:6379"
);

// ─── Metrics ─────────────────────────────────────────────────────────

const metrics = {
  messages_received: 0,
  messages_sent: 0,
  reply_token_used: 0,
  push_fallback_used: 0,
  signature_failures: 0,
  api_errors: 0,
  events_ignored: 0,
  started_at: new Date().toISOString(),
};

// ─── Signature Verification ──────────────────────────────────────────

function verifySignature(body: Buffer, signature: string): boolean {
  if (!CHANNEL_SECRET) return true;
  if (!signature) return false;
  const expected = crypto
    .createHmac("SHA256", CHANNEL_SECRET)
    .update(body)
    .digest("base64");
  try {
    return crypto.timingSafeEqual(
      Buffer.from(signature),
      Buffer.from(expected)
    );
  } catch {
    return false;
  }
}

// ─── LINE API Helpers ────────────────────────────────────────────────

export async function sendLineReply(
  replyToken: string,
  text: string
): Promise<boolean> {
  try {
    const resp = await fetch(LINE_REPLY_API, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${CHANNEL_ACCESS_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        replyToken,
        messages: [{ type: "text", text }],
      }),
      signal: AbortSignal.timeout(10000),
    });

    if (!resp.ok) {
      const errBody = await resp.text().catch(() => "");
      logger.warn({
        msg: "LINE reply failed",
        status: resp.status,
        body: errBody,
      });
      return false;
    }

    metrics.reply_token_used++;
    metrics.messages_sent++;
    return true;
  } catch (err) {
    logger.error({
      msg: "LINE reply error",
      error: (err as Error).message,
    });
    metrics.api_errors++;
    return false;
  }
}

export async function sendLinePush(
  userId: string,
  text: string
): Promise<boolean> {
  try {
    const resp = await fetch(LINE_PUSH_API, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${CHANNEL_ACCESS_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        to: userId,
        messages: [{ type: "text", text }],
      }),
      signal: AbortSignal.timeout(10000),
    });

    if (!resp.ok) {
      logger.warn({ msg: "LINE push failed", status: resp.status });
      metrics.api_errors++;
      return false;
    }

    metrics.push_fallback_used++;
    metrics.messages_sent++;
    return true;
  } catch (err) {
    logger.error({
      msg: "LINE push error",
      error: (err as Error).message,
    });
    metrics.api_errors++;
    return false;
  }
}

// ─── Event Processing ────────────────────────────────────────────────

interface LineEvent {
  type: string;
  source?: { type: string; userId?: string; groupId?: string; roomId?: string };
  replyToken?: string;
  message?: { id: string; type: string; text?: string };
  timestamp?: number;
}

function extractTextEvents(body: Record<string, any>): LineEvent[] {
  const events: LineEvent[] = [];
  for (const event of body?.events || []) {
    if (event.type === "message" && event.message?.type === "text") {
      events.push(event);
    } else {
      metrics.events_ignored++;
    }
  }
  return events;
}

// ─── Express App ─────────────────────────────────────────────────────

const app = express();

// Raw body for signature verification
app.use(
  "/webhook/line",
  express.raw({ type: "application/json" }),
  (req, _res, next) => {
    if (Buffer.isBuffer(req.body)) {
      (req as any)._rawBody = req.body;
      req.body = JSON.parse(req.body.toString());
    }
    next();
  }
);

app.use(express.json());

// ─── Webhook Handler ─────────────────────────────────────────────────

app.post("/webhook/line", async (req, res) => {
  const signature = req.headers["x-line-signature"] as string;
  const rawBody = (req as any)._rawBody;

  if (rawBody && !verifySignature(rawBody, signature || "")) {
    metrics.signature_failures++;
    logger.warn({ msg: "Invalid LINE signature" });
    res.sendStatus(401);
    return;
  }

  // Acknowledge immediately per LINE requirements
  res.sendStatus(200);

  const events = extractTextEvents(req.body);
  metrics.messages_received += events.length;

  for (const event of events) {
    const normalized: NormalizedMessage = normalizeLINE(req.body);

    logger.info({
      msg: "Processing LINE message",
      userId: normalized.userId,
      messageId: normalized.id,
      uri: normalized.uri,
    });

    try {
      const response = await messageRouter.route(normalized);

      // Try reply token first, fall back to push
      const replyToken = event.replyToken || "";
      let sent = false;

      if (replyToken) {
        sent = await sendLineReply(replyToken, response.text);
      }

      if (!sent && normalized.userId) {
        sent = await sendLinePush(normalized.userId, response.text);
      }

      if (sent) {
        logger.info({
          msg: "LINE reply sent",
          userId: normalized.userId,
          conversationId: response.metadata?.conversationId,
        });
      } else {
        logger.error({
          msg: "Failed to send LINE reply via both reply and push",
          userId: normalized.userId,
        });
      }
    } catch (err) {
      logger.error({
        msg: "LINE processing failed",
        userId: normalized.userId,
        error: (err as Error).message,
      });

      if (event.replyToken) {
        await sendLineReply(
          event.replyToken,
          "Sorry, I encountered an error. Please try again."
        );
      }
    }
  }
});

// ─── Health & Metrics ────────────────────────────────────────────────

app.get("/health", (_req, res) =>
  res.json({
    status: "healthy",
    channel: "line",
    version: "2.0.0",
    api: process.env.ECO_API_URL || "http://localhost:3000",
    channel_secret: CHANNEL_SECRET ? "configured" : "missing",
    uri: "softwareos-base://platforms/im-integration/line/health",
    timestamp: new Date().toISOString(),
  })
);

app.get("/metrics", (_req, res) =>
  res.json({
    ...metrics,
    uri: "softwareos-base://platforms/im-integration/line/metrics",
    timestamp: new Date().toISOString(),
  })
);

// ─── Graceful Shutdown ───────────────────────────────────────────────

let server: ReturnType<typeof app.listen>;

function shutdown(signal: string) {
  logger.info({ msg: `Received ${signal}, shutting down LINE adapter` });
  server?.close(() => {
    messageRouter.destroy().then(() => process.exit(0));
  });
  setTimeout(() => process.exit(1), 10000);
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));

server = app.listen(PORT, () => {
  logger.info({
    msg: "LINE adapter started",
    port: PORT,
    uri: "softwareos-base://platforms/im-integration/line",
  });
});

export { app };