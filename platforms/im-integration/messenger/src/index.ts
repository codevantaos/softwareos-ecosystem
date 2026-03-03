/**
 * softwareos-base Facebook Messenger Adapter
 *
 * Production-grade adapter for Facebook Messenger Platform.
 * Uses shared normalizer for message parsing, shared router for
 * AI backend routing with Redis session management.
 *
 * Features:
 * - HMAC-SHA256 signature verification
 * - Webhook verification challenge handling
 * - Sender actions (typing_on/typing_off)
 * - Mark seen before processing
 * - Echo message filtering
 * - Structured JSON logging
 * - Graceful shutdown
 * - Health + metrics endpoints
 *
 * URI: softwareos-base://platforms/im-integration/messenger
 */

import express from "express";
import crypto from "crypto";
import pino from "pino";
import { normalizeMessenger, type NormalizedMessage } from "../../shared/normalizer";
import { MessageRouter } from "../../shared/router";

// ─── Configuration ───────────────────────────────────────────────────

const PORT = parseInt(process.env.ECO_MESSENGER_PORT || "3004", 10);
const VERIFY_TOKEN = process.env.ECO_MESSENGER_VERIFY_TOKEN || "";
const PAGE_ACCESS_TOKEN = process.env.ECO_MESSENGER_PAGE_ACCESS_TOKEN || "";
const APP_SECRET = process.env.ECO_MESSENGER_APP_SECRET || "";
const GRAPH_API = "https://graph.facebook.com/v18.0/me";

const logger = pino({
  level: process.env.ECO_LOG_LEVEL || "info",
  name: "eco-messenger-adapter",
});

const messageRouter = new MessageRouter(
  process.env.ECO_REDIS_URL || "redis://localhost:6379"
);

// ─── Metrics ─────────────────────────────────────────────────────────

const metrics = {
  messages_received: 0,
  messages_sent: 0,
  echoes_ignored: 0,
  signature_failures: 0,
  api_errors: 0,
  started_at: new Date().toISOString(),
};

// ─── Signature Verification ──────────────────────────────────────────

function verifySignature(body: Buffer, signature: string): boolean {
  if (!APP_SECRET) return true;
  if (!signature) return false;
  const expected =
    "sha256=" +
    crypto.createHmac("sha256", APP_SECRET).update(body).digest("hex");
  try {
    return crypto.timingSafeEqual(
      Buffer.from(signature),
      Buffer.from(expected)
    );
  } catch {
    return false;
  }
}

// ─── Messenger API Helpers ───────────────────────────────────────────

async function sendSenderAction(
  recipientId: string,
  action: "typing_on" | "typing_off" | "mark_seen"
): Promise<void> {
  try {
    await fetch(`${GRAPH_API}/messages?access_token=${PAGE_ACCESS_TOKEN}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recipient: { id: recipientId },
        sender_action: action,
      }),
      signal: AbortSignal.timeout(5000),
    });
  } catch {
    // Non-critical
  }
}

export async function sendMessengerReply(
  recipientId: string,
  text: string
): Promise<boolean> {
  try {
    const resp = await fetch(
      `${GRAPH_API}/messages?access_token=${PAGE_ACCESS_TOKEN}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          recipient: { id: recipientId },
          message: { text },
          messaging_type: "RESPONSE",
        }),
        signal: AbortSignal.timeout(15000),
      }
    );

    if (!resp.ok) {
      const errBody = await resp.text().catch(() => "");
      logger.error({
        msg: "Messenger send failed",
        status: resp.status,
        body: errBody,
      });
      metrics.api_errors++;
      return false;
    }

    metrics.messages_sent++;
    return true;
  } catch (err) {
    logger.error({
      msg: "Messenger send error",
      error: (err as Error).message,
    });
    metrics.api_errors++;
    return false;
  }
}

// ─── Message Extraction ──────────────────────────────────────────────

interface MessagingEvent {
  sender: { id: string };
  recipient: { id: string };
  timestamp: number;
  message?: {
    mid: string;
    text?: string;
    is_echo?: boolean;
    attachments?: any[];
  };
  postback?: { payload: string };
}

function extractTextEvents(body: Record<string, any>): MessagingEvent[] {
  const events: MessagingEvent[] = [];

  for (const entry of body?.entry || []) {
    for (const event of entry?.messaging || []) {
      // Skip echo messages (sent by the page itself)
      if (event.message?.is_echo) {
        metrics.echoes_ignored++;
        continue;
      }

      // Only process text messages
      if (event.message?.text) {
        events.push(event);
      }
    }
  }

  return events;
}

// ─── Express App ─────────────────────────────────────────────────────

const app = express();

// Raw body for signature verification
app.use(
  "/webhook/messenger",
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

// ─── Webhook Verification ────────────────────────────────────────────

app.get("/webhook/messenger", (req, res) => {
  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];

  if (mode === "subscribe" && token === VERIFY_TOKEN) {
    logger.info({ msg: "Messenger webhook verified" });
    res.status(200).send(challenge);
  } else {
    logger.warn({ msg: "Messenger webhook verification failed" });
    res.sendStatus(403);
  }
});

// ─── Webhook Handler ─────────────────────────────────────────────────

app.post("/webhook/messenger", async (req, res) => {
  const signature = req.headers["x-hub-signature-256"] as string;
  const rawBody = (req as any)._rawBody;

  if (rawBody && !verifySignature(rawBody, signature || "")) {
    metrics.signature_failures++;
    logger.warn({ msg: "Invalid Messenger signature" });
    res.sendStatus(401);
    return;
  }

  // Acknowledge immediately per Facebook requirements
  res.sendStatus(200);

  const events = extractTextEvents(req.body);
  metrics.messages_received += events.length;

  for (const event of events) {
    const normalized: NormalizedMessage = normalizeMessenger(req.body);

    logger.info({
      msg: "Processing Messenger message",
      userId: normalized.userId,
      messageId: normalized.id,
      uri: normalized.uri,
    });

    // Mark seen + typing indicator
    await sendSenderAction(event.sender.id, "mark_seen");
    await sendSenderAction(event.sender.id, "typing_on");

    try {
      const response = await messageRouter.route(normalized);

      // Stop typing
      await sendSenderAction(event.sender.id, "typing_off");

      await sendMessengerReply(event.sender.id, response.text);

      logger.info({
        msg: "Messenger reply sent",
        userId: normalized.userId,
        conversationId: response.metadata?.conversationId,
      });
    } catch (err) {
      logger.error({
        msg: "Messenger processing failed",
        userId: normalized.userId,
        error: (err as Error).message,
      });

      await sendSenderAction(event.sender.id, "typing_off");
      await sendMessengerReply(
        event.sender.id,
        "Sorry, I encountered an error. Please try again."
      );
    }
  }
});

// ─── Health & Metrics ────────────────────────────────────────────────

app.get("/health", (_req, res) =>
  res.json({
    status: "healthy",
    channel: "messenger",
    version: "2.0.0",
    api: process.env.ECO_API_URL || "http://localhost:3000",
    page_token: PAGE_ACCESS_TOKEN ? "configured" : "missing",
    uri: "softwareos-base://platforms/im-integration/messenger/health",
    timestamp: new Date().toISOString(),
  })
);

app.get("/metrics", (_req, res) =>
  res.json({
    ...metrics,
    uri: "softwareos-base://platforms/im-integration/messenger/metrics",
    timestamp: new Date().toISOString(),
  })
);

// ─── Graceful Shutdown ───────────────────────────────────────────────

let server: ReturnType<typeof app.listen>;

function shutdown(signal: string) {
  logger.info({ msg: `Received ${signal}, shutting down Messenger adapter` });
  server?.close(() => {
    messageRouter.destroy().then(() => process.exit(0));
  });
  setTimeout(() => process.exit(1), 10000);
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));

server = app.listen(PORT, () => {
  logger.info({
    msg: "Messenger adapter started",
    port: PORT,
    uri: "softwareos-base://platforms/im-integration/messenger",
  });
});

export { app };