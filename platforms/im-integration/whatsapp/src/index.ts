/**
 * softwareos-base WhatsApp Cloud API Adapter
 *
 * Production-grade adapter for Meta WhatsApp Cloud API.
 * Uses shared normalizer for message parsing, shared router for
 * AI backend routing with Redis session management.
 *
 * Features:
 * - HMAC-SHA256 signature verification
 * - Webhook verification challenge handling
 * - Typing indicators before reply
 * - Message status tracking (sent/delivered/read)
 * - Structured JSON logging
 * - Graceful shutdown
 * - Health + metrics endpoints
 *
 * URI: softwareos-base://platforms/im-integration/whatsapp
 */

import express from "express";
import crypto from "crypto";
import pino from "pino";
import { normalizeWhatsApp, type NormalizedMessage } from "../../shared/normalizer";
import { MessageRouter } from "../../shared/router";

// ─── Configuration ───────────────────────────────────────────────────

const PORT = parseInt(process.env.ECO_WHATSAPP_PORT || "3002", 10);
const VERIFY_TOKEN = process.env.ECO_WHATSAPP_VERIFY_TOKEN || "";
const ACCESS_TOKEN = process.env.ECO_WHATSAPP_ACCESS_TOKEN || "";
const APP_SECRET = process.env.ECO_WHATSAPP_APP_SECRET || "";
const PHONE_NUMBER_ID = process.env.ECO_WHATSAPP_PHONE_NUMBER_ID || "";
const GRAPH_API = "https://graph.facebook.com/v18.0";

const logger = pino({
  level: process.env.ECO_LOG_LEVEL || "info",
  name: "eco-whatsapp-adapter",
});

const router = new MessageRouter(
  process.env.ECO_REDIS_URL || "redis://localhost:6379"
);

// ─── Metrics ─────────────────────────────────────────────────────────

const metrics = {
  messages_received: 0,
  messages_sent: 0,
  signature_failures: 0,
  api_errors: 0,
  status_updates: 0,
  started_at: new Date().toISOString(),
};

// ─── Signature Verification ──────────────────────────────────────────

function verifySignature(req: express.Request, body: Buffer): boolean {
  if (!APP_SECRET) return true;
  const signature = req.headers["x-hub-signature-256"] as string;
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

// ─── WhatsApp Cloud API Helpers ──────────────────────────────────────

async function sendTypingIndicator(to: string): Promise<void> {
  try {
    await fetch(`${GRAPH_API}/${PHONE_NUMBER_ID}/messages`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${ACCESS_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        messaging_product: "whatsapp",
        recipient_type: "individual",
        to,
        type: "reaction",
        reaction: { message_id: "", emoji: "" },
      }),
      signal: AbortSignal.timeout(5000),
    });
  } catch {
    // Non-critical, ignore
  }
}

async function markAsRead(messageId: string): Promise<void> {
  try {
    await fetch(`${GRAPH_API}/${PHONE_NUMBER_ID}/messages`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${ACCESS_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        messaging_product: "whatsapp",
        status: "read",
        message_id: messageId,
      }),
      signal: AbortSignal.timeout(5000),
    });
  } catch {
    // Non-critical, ignore
  }
}

export async function sendWhatsAppReply(
  to: string,
  text: string
): Promise<boolean> {
  try {
    const resp = await fetch(`${GRAPH_API}/${PHONE_NUMBER_ID}/messages`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${ACCESS_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        messaging_product: "whatsapp",
        recipient_type: "individual",
        to,
        type: "text",
        text: { preview_url: false, body: text },
      }),
      signal: AbortSignal.timeout(15000),
    });

    if (!resp.ok) {
      logger.error({
        msg: "WhatsApp send failed",
        status: resp.status,
        body: await resp.text().catch(() => ""),
      });
      metrics.api_errors++;
      return false;
    }

    metrics.messages_sent++;
    return true;
  } catch (err) {
    logger.error({ msg: "WhatsApp send error", error: (err as Error).message });
    metrics.api_errors++;
    return false;
  }
}

// ─── Message Extraction ──────────────────────────────────────────────

function extractTextMessages(
  body: Record<string, any>
): NormalizedMessage[] {
  const messages: NormalizedMessage[] = [];
  const entries = body?.entry || [];

  for (const entry of entries) {
    const changes = entry?.changes || [];
    for (const change of changes) {
      const value = change?.value;

      // Handle status updates
      if (value?.statuses) {
        metrics.status_updates += value.statuses.length;
        continue;
      }

      if (!value?.messages) continue;

      for (const msg of value.messages) {
        if (msg.type !== "text") continue;
        const normalized = normalizeWhatsApp(body);
        messages.push(normalized);
      }
    }
  }

  return messages;
}

// ─── Express App ─────────────────────────────────────────────────────

const app = express();

// Raw body for signature verification
app.use(
  "/webhook/whatsapp",
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

app.get("/webhook/whatsapp", (req, res) => {
  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];

  if (mode === "subscribe" && token === VERIFY_TOKEN) {
    logger.info({ msg: "WhatsApp webhook verified" });
    res.status(200).send(challenge);
  } else {
    logger.warn({ msg: "WhatsApp webhook verification failed" });
    res.sendStatus(403);
  }
});

// ─── Webhook Handler ─────────────────────────────────────────────────

app.post("/webhook/whatsapp", async (req, res) => {
  const rawBody = (req as any)._rawBody;

  if (rawBody && !verifySignature(req, rawBody)) {
    metrics.signature_failures++;
    logger.warn({ msg: "Invalid WhatsApp signature" });
    res.sendStatus(401);
    return;
  }

  // Acknowledge immediately per Meta requirements
  res.sendStatus(200);

  const messages = extractTextMessages(req.body);
  metrics.messages_received += messages.length;

  for (const message of messages) {
    if (!message.text) continue;

    logger.info({
      msg: "Processing WhatsApp message",
      userId: message.userId,
      messageId: message.id,
      uri: message.uri,
    });

    // Mark as read + typing indicator
    await markAsRead(message.id);
    await sendTypingIndicator(message.userId);

    // Route through shared router (Redis session + AI backend)
    try {
      const response = await router.route(message);
      await sendWhatsAppReply(message.userId, response.text);

      logger.info({
        msg: "WhatsApp reply sent",
        userId: message.userId,
        conversationId: response.metadata?.conversationId,
      });
    } catch (err) {
      logger.error({
        msg: "WhatsApp processing failed",
        userId: message.userId,
        error: (err as Error).message,
      });
      await sendWhatsAppReply(
        message.userId,
        "Sorry, I encountered an error. Please try again."
      );
    }
  }
});

// ─── Health & Metrics ────────────────────────────────────────────────

app.get("/health", (_req, res) =>
  res.json({
    status: "healthy",
    channel: "whatsapp",
    version: "2.0.0",
    api: process.env.ECO_API_URL || "http://localhost:3000",
    phone_number_id: PHONE_NUMBER_ID ? "configured" : "missing",
    uri: "softwareos-base://platforms/im-integration/whatsapp/health",
    timestamp: new Date().toISOString(),
  })
);

app.get("/metrics", (_req, res) =>
  res.json({
    ...metrics,
    uri: "softwareos-base://platforms/im-integration/whatsapp/metrics",
    timestamp: new Date().toISOString(),
  })
);

// ─── Graceful Shutdown ───────────────────────────────────────────────

let server: ReturnType<typeof app.listen>;

function shutdown(signal: string) {
  logger.info({ msg: `Received ${signal}, shutting down WhatsApp adapter` });
  server?.close(() => {
    router.destroy().then(() => process.exit(0));
  });
  setTimeout(() => process.exit(1), 10000);
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));

server = app.listen(PORT, () => {
  logger.info({
    msg: "WhatsApp adapter started",
    port: PORT,
    uri: "softwareos-base://platforms/im-integration/whatsapp",
  });
});

export { app };