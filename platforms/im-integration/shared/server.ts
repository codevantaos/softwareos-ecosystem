/**
 * IM Integration Webhook Server — unified entry point for all channels.
 *
 * Each channel has its own webhook path validated with platform secrets.
 * Shared logic handles normalization, routing, session management,
 * and channel-specific reply delivery.
 *
 * This server can run as a single process handling all 4 channels,
 * or each channel adapter can run independently.
 *
 * URI: softwareos-base://platforms/im-integration/shared/server
 */

import express from "express";
import pino from "pino";
import crypto from "crypto";
import { normalize, type Channel, type NormalizedMessage } from "./normalizer";
import { MessageRouter } from "./router";

const logger = pino({
  level: process.env.ECO_LOG_LEVEL || "info",
  name: "eco-im-server",
});

const app = express();
const router = new MessageRouter();

app.use(express.json());

// ─── Channel Reply Senders ───────────────────────────────────────────

type ReplySender = (userId: string, text: string, metadata?: Record<string, any>) => Promise<boolean>;

const WHATSAPP_GRAPH_API = "https://graph.facebook.com/v18.0";
const LINE_REPLY_API = "https://api.line.me/v2/bot/message/reply";
const LINE_PUSH_API = "https://api.line.me/v2/bot/message/push";
const MESSENGER_GRAPH_API = "https://graph.facebook.com/v18.0/me/messages";

async function sendWhatsApp(userId: string, text: string): Promise<boolean> {
  const token = process.env.ECO_WHATSAPP_ACCESS_TOKEN;
  const phoneId = process.env.ECO_WHATSAPP_PHONE_NUMBER_ID;
  if (!token || !phoneId) return false;

  try {
    const resp = await fetch(`${WHATSAPP_GRAPH_API}/${phoneId}/messages`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        messaging_product: "whatsapp",
        recipient_type: "individual",
        to: userId,
        type: "text",
        text: { preview_url: false, body: text },
      }),
      signal: AbortSignal.timeout(15000),
    });
    return resp.ok;
  } catch {
    return false;
  }
}

async function sendTelegram(userId: string, text: string): Promise<boolean> {
  const token = process.env.ECO_TELEGRAM_BOT_TOKEN;
  if (!token) return false;

  try {
    const resp = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: userId, text, parse_mode: "Markdown" }),
      signal: AbortSignal.timeout(15000),
    });
    return resp.ok;
  } catch {
    return false;
  }
}

async function sendLINE(userId: string, text: string, metadata?: Record<string, any>): Promise<boolean> {
  const token = process.env.ECO_LINE_CHANNEL_ACCESS_TOKEN;
  if (!token) return false;

  // Try reply token first if available
  const replyToken = metadata?.replyToken as string | undefined;
  if (replyToken) {
    try {
      const resp = await fetch(LINE_REPLY_API, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ replyToken, messages: [{ type: "text", text }] }),
        signal: AbortSignal.timeout(10000),
      });
      if (resp.ok) return true;
    } catch {
      // Fall through to push
    }
  }

  // Push fallback
  try {
    const resp = await fetch(LINE_PUSH_API, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ to: userId, messages: [{ type: "text", text }] }),
      signal: AbortSignal.timeout(10000),
    });
    return resp.ok;
  } catch {
    return false;
  }
}

async function sendMessenger(userId: string, text: string): Promise<boolean> {
  const token = process.env.ECO_MESSENGER_PAGE_ACCESS_TOKEN;
  if (!token) return false;

  try {
    const resp = await fetch(`${MESSENGER_GRAPH_API}?access_token=${token}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recipient: { id: userId },
        message: { text },
        messaging_type: "RESPONSE",
      }),
      signal: AbortSignal.timeout(15000),
    });
    return resp.ok;
  } catch {
    return false;
  }
}

const SENDERS: Record<Channel, ReplySender> = {
  whatsapp: sendWhatsApp,
  telegram: sendTelegram,
  line: sendLINE,
  messenger: sendMessenger,
};

// ─── Metrics ─────────────────────────────────────────────────────────

const metrics = {
  total_received: 0,
  total_sent: 0,
  total_errors: 0,
  by_channel: { whatsapp: 0, telegram: 0, line: 0, messenger: 0 },
  started_at: new Date().toISOString(),
};

// ─── Webhook Verification Helpers ────────────────────────────────────

function verifyWhatsAppSignature(req: express.Request): boolean {
  const signature = req.headers["x-hub-signature-256"] as string;
  if (!signature) return false;
  const secret = process.env.ECO_WHATSAPP_APP_SECRET || "";
  if (!secret) return true;
  const hash =
    "sha256=" +
    crypto.createHmac("sha256", secret).update(JSON.stringify(req.body)).digest("hex");
  try {
    return crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(hash));
  } catch {
    return false;
  }
}

function verifyTelegramSecret(req: express.Request): boolean {
  const token = req.params.token;
  return token === process.env.ECO_TELEGRAM_BOT_TOKEN;
}

function verifyLINESignature(req: express.Request): boolean {
  const signature = req.headers["x-line-signature"] as string;
  if (!signature) return false;
  const secret = process.env.ECO_LINE_CHANNEL_SECRET || "";
  if (!secret) return true;
  const hash = crypto
    .createHmac("sha256", secret)
    .update(JSON.stringify(req.body))
    .digest("base64");
  return signature === hash;
}

function verifyMessengerSignature(req: express.Request): boolean {
  const signature = req.headers["x-hub-signature-256"] as string;
  if (!signature) return false;
  const secret = process.env.ECO_MESSENGER_APP_SECRET || "";
  if (!secret) return true;
  const hash =
    "sha256=" +
    crypto.createHmac("sha256", secret).update(JSON.stringify(req.body)).digest("hex");
  try {
    return crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(hash));
  } catch {
    return false;
  }
}

// ─── Unified Webhook Handler ─────────────────────────────────────────

async function handleWebhook(
  channel: Channel,
  req: express.Request,
  res: express.Response
) {
  try {
    const message: NormalizedMessage = normalize(channel, req.body);
    metrics.total_received++;
    metrics.by_channel[channel]++;

    if (!message.text) {
      res.status(200).json({ status: "ignored", reason: "no_text" });
      return;
    }

    const response = await router.route(message);

    logger.info({
      msg: "Message processed",
      channel,
      userId: message.userId,
      conversationId: response.metadata?.conversationId,
      uri: message.uri,
    });

    // Deliver reply via channel-specific sender
    const sender = SENDERS[channel];
    const sent = await sender(message.userId, response.text, message.metadata);

    if (sent) {
      metrics.total_sent++;
    } else {
      metrics.total_errors++;
      logger.warn({ msg: "Reply delivery failed", channel, userId: message.userId });
    }

    res.status(200).json({
      status: "ok",
      responseText: response.text,
      delivered: sent,
    });
  } catch (err) {
    metrics.total_errors++;
    logger.error({
      msg: "Webhook processing failed",
      channel,
      error: (err as Error).message,
    });
    res.status(500).json({ error: "processing_failed" });
  }
}

// ─── WhatsApp ────────────────────────────────────────────────────────

app.get("/webhook/whatsapp", (req, res) => {
  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];
  if (mode === "subscribe" && token === process.env.ECO_WHATSAPP_VERIFY_TOKEN) {
    res.status(200).send(challenge);
  } else {
    res.status(403).send("Forbidden");
  }
});

app.post("/webhook/whatsapp", (req, res) => {
  if (!verifyWhatsAppSignature(req)) {
    res.status(401).json({ error: "invalid_signature" });
    return;
  }
  handleWebhook("whatsapp", req, res);
});

// ─── Telegram ────────────────────────────────────────────────────────

app.post("/webhook/telegram/:token", (req, res) => {
  if (!verifyTelegramSecret(req)) {
    res.status(401).json({ error: "invalid_token" });
    return;
  }
  handleWebhook("telegram", req, res);
});

// ─── LINE ────────────────────────────────────────────────────────────

app.post("/webhook/line", (req, res) => {
  if (!verifyLINESignature(req)) {
    res.status(401).json({ error: "invalid_signature" });
    return;
  }
  handleWebhook("line", req, res);
});

// ─── Messenger ───────────────────────────────────────────────────────

app.get("/webhook/messenger", (req, res) => {
  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];
  if (mode === "subscribe" && token === process.env.ECO_MESSENGER_VERIFY_TOKEN) {
    res.status(200).send(challenge);
  } else {
    res.status(403).send("Forbidden");
  }
});

app.post("/webhook/messenger", (req, res) => {
  if (!verifyMessengerSignature(req)) {
    res.status(401).json({ error: "invalid_signature" });
    return;
  }
  handleWebhook("messenger", req, res);
});

// ─── Health & Metrics ────────────────────────────────────────────────

app.get("/health", (_req, res) => {
  res.status(200).json({
    status: "healthy",
    service: "im-integration",
    version: "2.0.0",
    uri: "softwareos-base://platforms/im-integration/health",
    channels: ["whatsapp", "telegram", "line", "messenger"],
    timestamp: new Date().toISOString(),
  });
});

app.get("/metrics", (_req, res) => {
  res.status(200).json({
    ...metrics,
    uri: "softwareos-base://platforms/im-integration/metrics",
    timestamp: new Date().toISOString(),
  });
});

// ─── Start & Shutdown ────────────────────────────────────────────────

const port = parseInt(process.env.ECO_IM_PORT || process.env.PORT || "4000", 10);
let server: ReturnType<typeof app.listen>;

function shutdown(signal: string) {
  logger.info({ msg: `Received ${signal}, shutting down IM server` });
  server?.close(() => {
    router.destroy().then(() => process.exit(0));
  });
  setTimeout(() => process.exit(1), 10000);
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));

server = app.listen(port, () => {
  logger.info({
    msg: "IM Integration server started",
    port,
    uri: "softwareos-base://platforms/im-integration",
  });
});

export { app, SENDERS };