/**
 * softwareos-base Cloudflare Worker — Webhook Router
 *
 * Production-grade edge webhook router for IM platforms
 * (WhatsApp, Telegram, LINE, Messenger).
 *
 * Features:
 * - HMAC signature verification per channel
 * - Request deduplication via KV (idempotency)
 * - Per-IP sliding-window rate limiting via KV
 * - Structured JSON logging
 * - Retry with exponential backoff + dead-letter KV
 * - Per-channel payload normalization before forwarding
 * - CORS preflight handling
 * - /health and /metrics endpoints
 * - Error classification (4xx client vs 5xx upstream)
 *
 * URI: softwareos-base://backend/cloudflare/webhook-router
 */

// ─── Environment Bindings ────────────────────────────────────────────

interface Env {
  ECO_API_URL: string;
  ECO_WEBHOOK_SECRET: string;
  WHATSAPP_VERIFY_TOKEN: string;
  TELEGRAM_SECRET_TOKEN: string;
  LINE_CHANNEL_SECRET: string;
  MESSENGER_VERIFY_TOKEN: string;
  MESSENGER_APP_SECRET: string;
  WEBHOOK_KV: KVNamespace;
  RATE_LIMIT_PER_MINUTE: string;
  DEAD_LETTER_TTL_SECONDS: string;
  DEDUP_TTL_SECONDS: string;
}

// ─── Types ───────────────────────────────────────────────────────────

type Channel = "whatsapp" | "telegram" | "line" | "messenger";

interface NormalizedWebhookPayload {
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

interface LogEntry {
  level: "info" | "warn" | "error";
  msg: string;
  channel?: string;
  ip?: string;
  status?: number;
  latency_ms?: number;
  idempotency_key?: string;
  error?: string;
  timestamp: string;
  service: "webhook-router";
  uri: string;
}

interface MetricsState {
  requests_total: number;
  requests_by_channel: Record<string, number>;
  signature_failures: number;
  rate_limited: number;
  dedup_hits: number;
  upstream_errors: number;
  upstream_successes: number;
  dead_letters: number;
  last_reset: string;
}

// ─── Constants ───────────────────────────────────────────────────────

const VERSION = "2.0.0";
const DEFAULT_RATE_LIMIT = 120;
const DEFAULT_DEDUP_TTL = 300;
const DEFAULT_DEAD_LETTER_TTL = 86400;
const MAX_RETRIES = 2;
const RETRY_BASE_MS = 500;
const UPSTREAM_TIMEOUT_MS = 15_000;

// ─── In-memory metrics (per-isolate, reset on cold start) ────────────

let metrics: MetricsState = {
  requests_total: 0,
  requests_by_channel: { whatsapp: 0, telegram: 0, line: 0, messenger: 0 },
  signature_failures: 0,
  rate_limited: 0,
  dedup_hits: 0,
  upstream_errors: 0,
  upstream_successes: 0,
  dead_letters: 0,
  last_reset: new Date().toISOString(),
};

// ─── Logging ─────────────────────────────────────────────────────────

function log(entry: Omit<LogEntry, "timestamp" | "service" | "uri">): void {
  const full: LogEntry = {
    ...entry,
    timestamp: new Date().toISOString(),
    service: "webhook-router",
    uri: "softwareos-base://cloudflare/webhook-router/log",
  };
  if (entry.level === "error") {
    console.error(JSON.stringify(full));
  } else {
    console.log(JSON.stringify(full));
  }
}

// ─── Crypto Helpers ──────────────────────────────────────────────────

async function hmacSha256(secret: string, data: string): Promise<string> {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, encoder.encode(data));
  return Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function sha256Hex(data: string): Promise<string> {
  const encoder = new TextEncoder();
  const hash = await crypto.subtle.digest("SHA-256", encoder.encode(data));
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}

// ─── Signature Verification ──────────────────────────────────────────

async function verifyWhatsApp(
  request: Request,
  env: Env,
  body: string
): Promise<boolean> {
  const signature = request.headers.get("X-Hub-Signature-256");
  if (!signature) return false;
  const expected = await hmacSha256(env.ECO_WEBHOOK_SECRET, body);
  return timingSafeEqual(signature, `sha256=${expected}`);
}

async function verifyTelegram(
  request: Request,
  env: Env,
  _body: string
): Promise<boolean> {
  const token = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
  if (!token || !env.TELEGRAM_SECRET_TOKEN) return false;
  return timingSafeEqual(token, env.TELEGRAM_SECRET_TOKEN);
}

async function verifyLine(
  request: Request,
  env: Env,
  body: string
): Promise<boolean> {
  const signature = request.headers.get("X-Line-Signature");
  if (!signature || !env.LINE_CHANNEL_SECRET) return false;
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(env.LINE_CHANNEL_SECRET),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, encoder.encode(body));
  const expected = btoa(String.fromCharCode(...new Uint8Array(sig)));
  return timingSafeEqual(signature, expected);
}

async function verifyMessenger(
  request: Request,
  env: Env,
  body: string
): Promise<boolean> {
  const signature = request.headers.get("X-Hub-Signature-256");
  if (!signature || !env.MESSENGER_APP_SECRET) return false;
  const expected = await hmacSha256(env.MESSENGER_APP_SECRET, body);
  return timingSafeEqual(signature, `sha256=${expected}`);
}

type VerifyFn = (req: Request, env: Env, body: string) => Promise<boolean>;

const VERIFIERS: Record<Channel, VerifyFn> = {
  whatsapp: verifyWhatsApp,
  telegram: verifyTelegram,
  line: verifyLine,
  messenger: verifyMessenger,
};

// ─── Channel Resolution ──────────────────────────────────────────────

function resolveChannel(pathname: string): Channel | null {
  if (pathname.startsWith("/webhook/whatsapp")) return "whatsapp";
  if (pathname.startsWith("/webhook/telegram")) return "telegram";
  if (pathname.startsWith("/webhook/line")) return "line";
  if (pathname.startsWith("/webhook/messenger")) return "messenger";
  return null;
}

// ─── Rate Limiting (KV-backed sliding window) ────────────────────────

async function checkRateLimit(
  env: Env,
  ip: string
): Promise<{ allowed: boolean; remaining: number }> {
  const limit = parseInt(env.RATE_LIMIT_PER_MINUTE || String(DEFAULT_RATE_LIMIT), 10);
  if (!env.WEBHOOK_KV) return { allowed: true, remaining: limit };

  const windowKey = `rl:${ip}:${Math.floor(Date.now() / 60000)}`;
  const current = parseInt((await env.WEBHOOK_KV.get(windowKey)) || "0", 10);

  if (current >= limit) {
    return { allowed: false, remaining: 0 };
  }

  await env.WEBHOOK_KV.put(windowKey, String(current + 1), { expirationTtl: 120 });
  return { allowed: true, remaining: limit - current - 1 };
}

// ─── Request Deduplication (KV-backed) ───────────────────────────────

async function isDuplicate(
  env: Env,
  idempotencyKey: string
): Promise<boolean> {
  if (!env.WEBHOOK_KV) return false;

  const dedupTtl = parseInt(env.DEDUP_TTL_SECONDS || String(DEFAULT_DEDUP_TTL), 10);
  const key = `dedup:${idempotencyKey}`;
  const existing = await env.WEBHOOK_KV.get(key);

  if (existing) return true;

  await env.WEBHOOK_KV.put(key, "1", { expirationTtl: dedupTtl });
  return false;
}

// ─── Dead Letter Queue (KV-backed) ──────────────────────────────────

async function writeDeadLetter(
  env: Env,
  payload: NormalizedWebhookPayload,
  error: string
): Promise<void> {
  if (!env.WEBHOOK_KV) return;

  const ttl = parseInt(env.DEAD_LETTER_TTL_SECONDS || String(DEFAULT_DEAD_LETTER_TTL), 10);
  const key = `dlq:${payload.channel}:${payload.idempotency_key}`;
  await env.WEBHOOK_KV.put(
    key,
    JSON.stringify({
      payload,
      error,
      failed_at: new Date().toISOString(),
    }),
    { expirationTtl: ttl }
  );
  metrics.dead_letters++;
}

// ─── Payload Normalization ───────────────────────────────────────────

function normalizeWhatsApp(raw: Record<string, any>): Partial<NormalizedWebhookPayload> {
  const entry = raw.entry?.[0];
  const change = entry?.changes?.[0]?.value;
  const msg = change?.messages?.[0];
  const contact = change?.contacts?.[0];
  const msgId = msg?.id || crypto.randomUUID();

  return {
    event_type: msg?.type === "text" ? "message" : (msg?.type || "unknown"),
    sender_id: msg?.from || "",
    chat_id: msg?.from || "",
    text: msg?.text?.body || "",
    message_id: msgId,
    timestamp: msg?.timestamp
      ? new Date(parseInt(msg.timestamp, 10) * 1000).toISOString()
      : new Date().toISOString(),
  };
}

function normalizeTelegram(raw: Record<string, any>): Partial<NormalizedWebhookPayload> {
  const msg = raw.message || raw.edited_message || raw.channel_post;
  const msgId = String(msg?.message_id || crypto.randomUUID());

  return {
    event_type: raw.edited_message ? "message_edit" : "message",
    sender_id: String(msg?.from?.id || ""),
    chat_id: String(msg?.chat?.id || ""),
    text: msg?.text || "",
    message_id: msgId,
    timestamp: msg?.date
      ? new Date(msg.date * 1000).toISOString()
      : new Date().toISOString(),
  };
}

function normalizeLINE(raw: Record<string, any>): Partial<NormalizedWebhookPayload> {
  const event = raw.events?.[0];
  const msgId = event?.message?.id || crypto.randomUUID();

  return {
    event_type: event?.type || "message",
    sender_id: event?.source?.userId || "",
    chat_id: event?.source?.groupId || event?.source?.roomId || event?.source?.userId || "",
    text: event?.message?.text || "",
    message_id: String(msgId),
    timestamp: event?.timestamp
      ? new Date(event.timestamp).toISOString()
      : new Date().toISOString(),
  };
}

function normalizeMessenger(raw: Record<string, any>): Partial<NormalizedWebhookPayload> {
  const entry = raw.entry?.[0];
  const messaging = entry?.messaging?.[0];
  const msg = messaging?.message;
  const msgId = msg?.mid || crypto.randomUUID();

  return {
    event_type: msg?.is_echo ? "echo" : "message",
    sender_id: messaging?.sender?.id || "",
    chat_id: messaging?.sender?.id || "",
    text: msg?.text || "",
    message_id: msgId,
    timestamp: messaging?.timestamp
      ? new Date(messaging.timestamp).toISOString()
      : new Date().toISOString(),
  };
}

const NORMALIZERS: Record<Channel, (raw: Record<string, any>) => Partial<NormalizedWebhookPayload>> = {
  whatsapp: normalizeWhatsApp,
  telegram: normalizeTelegram,
  line: normalizeLINE,
  messenger: normalizeMessenger,
};

async function buildPayload(
  channel: Channel,
  body: string
): Promise<NormalizedWebhookPayload> {
  let raw: Record<string, any>;
  try {
    raw = JSON.parse(body);
  } catch {
    raw = {};
  }

  const normalizer = NORMALIZERS[channel];
  const normalized = normalizer(raw);
  const idempotencyKey = await sha256Hex(`${channel}:${normalized.message_id || body}`);

  return {
    channel,
    event_type: normalized.event_type || "unknown",
    sender_id: normalized.sender_id || "",
    chat_id: normalized.chat_id || "",
    text: normalized.text || "",
    message_id: normalized.message_id || "",
    timestamp: normalized.timestamp || new Date().toISOString(),
    raw,
    signature_valid: true,
    idempotency_key: idempotencyKey,
    uri: `softwareos-base://im/${channel}/webhook/${normalized.message_id || "unknown"}`,
    urn: `urn:softwareos-base:im:${channel}:webhook:${normalized.sender_id || "anon"}:${normalized.message_id || "unknown"}`,
  };
}

// ─── Upstream Forwarding with Retry ──────────────────────────────────

async function forwardToUpstream(
  env: Env,
  payload: NormalizedWebhookPayload
): Promise<Response> {
  const apiUrl = env.ECO_API_URL || "https://api.softwareos-base.com";
  const url = `${apiUrl}/api/v1/im/webhook`;

  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Webhook-Channel": payload.channel,
          "X-Webhook-Signature-Valid": "true",
          "X-Webhook-Idempotency-Key": payload.idempotency_key,
          "X-Webhook-Message-Id": payload.message_id,
          "X-Webhook-Sender-Id": payload.sender_id,
          "X-Request-Source": "eco-webhook-router",
          "User-Agent": `softwareos-base-WebhookRouter/${VERSION}`,
        },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      });

      if (resp.ok) {
        metrics.upstream_successes++;
        const respBody = await resp.text();
        return new Response(respBody, {
          status: resp.status,
          headers: {
            "Content-Type": "application/json",
            "X-Webhook-Processed": "true",
            "X-Webhook-Idempotency-Key": payload.idempotency_key,
          },
        });
      }

      if (resp.status >= 400 && resp.status < 500) {
        metrics.upstream_errors++;
        const errBody = await resp.text();
        return new Response(errBody, {
          status: resp.status,
          headers: { "Content-Type": "application/json" },
        });
      }

      lastError = new Error(`upstream ${resp.status}: ${resp.statusText}`);
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
    }

    if (attempt < MAX_RETRIES) {
      await new Promise((r) => setTimeout(r, RETRY_BASE_MS * Math.pow(2, attempt)));
    }
  }

  metrics.upstream_errors++;

  await writeDeadLetter(env, payload, lastError?.message || "unknown");

  log({
    level: "error",
    msg: "Upstream forwarding failed after retries, written to dead-letter",
    channel: payload.channel,
    idempotency_key: payload.idempotency_key,
    error: lastError?.message,
  });

  return new Response(
    JSON.stringify({
      error: "upstream_error",
      message: "Webhook accepted but upstream processing failed. Queued for retry.",
      channel: payload.channel,
      idempotency_key: payload.idempotency_key,
    }),
    { status: 202, headers: { "Content-Type": "application/json" } }
  );
}

// ─── Verification Challenge Handlers ─────────────────────────────────

async function handleVerificationChallenge(
  request: Request,
  channel: Channel,
  env: Env
): Promise<Response | null> {
  if (request.method !== "GET") return null;

  const url = new URL(request.url);

  if (channel === "whatsapp" || channel === "messenger") {
    const mode = url.searchParams.get("hub.mode");
    const token = url.searchParams.get("hub.verify_token");
    const challenge = url.searchParams.get("hub.challenge");
    const expected =
      channel === "whatsapp"
        ? env.WHATSAPP_VERIFY_TOKEN
        : env.MESSENGER_VERIFY_TOKEN;

    if (mode === "subscribe" && token && expected && timingSafeEqual(token, expected) && challenge) {
      log({ level: "info", msg: "Verification challenge passed", channel });
      return new Response(challenge, {
        status: 200,
        headers: { "Content-Type": "text/plain" },
      });
    }

    log({ level: "warn", msg: "Verification challenge failed", channel });
    return new Response(
      JSON.stringify({ error: "forbidden", message: "Verification failed" }),
      { status: 403, headers: { "Content-Type": "application/json" } }
    );
  }

  return null;
}

// ─── CORS ────────────────────────────────────────────────────────────

function corsHeaders(): Record<string, string> {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Hub-Signature-256, X-Line-Signature, X-Telegram-Bot-Api-Secret-Token",
    "Access-Control-Max-Age": "86400",
  };
}

function handleCORS(): Response {
  return new Response(null, { status: 204, headers: corsHeaders() });
}

// ─── Response Helpers ────────────────────────────────────────────────

function jsonResponse(body: Record<string, unknown>, status: number, extra?: Record<string, string>): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...corsHeaders(),
      ...(extra || {}),
    },
  });
}

// ─── Main Handler ────────────────────────────────────────────────────

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const startTime = Date.now();
    const url = new URL(request.url);
    const ip = request.headers.get("CF-Connecting-IP") || request.headers.get("X-Forwarded-For") || "unknown";

    metrics.requests_total++;

    // CORS preflight
    if (request.method === "OPTIONS") {
      return handleCORS();
    }

    // Health check
    if (url.pathname === "/health") {
      return jsonResponse(
        {
          status: "healthy",
          service: "webhook-router",
          version: VERSION,
          uri: "softwareos-base://cloudflare/webhook-router/health",
          timestamp: new Date().toISOString(),
          channels: ["whatsapp", "telegram", "line", "messenger"],
          kv_available: !!env.WEBHOOK_KV,
        },
        200
      );
    }

    // Metrics endpoint
    if (url.pathname === "/metrics") {
      return jsonResponse(
        {
          ...metrics,
          uri: "softwareos-base://cloudflare/webhook-router/metrics",
          timestamp: new Date().toISOString(),
        },
        200
      );
    }

    // Resolve channel
    const channel = resolveChannel(url.pathname);
    if (!channel) {
      return jsonResponse(
        { error: "not_found", message: `No route for ${url.pathname}` },
        404
      );
    }

    metrics.requests_by_channel[channel] = (metrics.requests_by_channel[channel] || 0) + 1;

    // Rate limiting
    const rateResult = await checkRateLimit(env, ip);
    if (!rateResult.allowed) {
      metrics.rate_limited++;
      log({ level: "warn", msg: "Rate limited", channel, ip });
      return jsonResponse(
        { error: "rate_limited", message: "Too many requests", retry_after_seconds: 60 },
        429,
        { "Retry-After": "60", "X-RateLimit-Remaining": "0" }
      );
    }

    // GET verification challenges (WhatsApp, Messenger)
    const challengeResp = await handleVerificationChallenge(request, channel, env);
    if (challengeResp) return challengeResp;

    // Only POST for webhook payloads
    if (request.method !== "POST") {
      return jsonResponse(
        { error: "method_not_allowed", message: "Only POST is accepted for webhooks" },
        405
      );
    }

    // Read body
    let body: string;
    try {
      body = await request.text();
    } catch {
      return jsonResponse(
        { error: "bad_request", message: "Failed to read request body" },
        400
      );
    }

    if (!body || body.length === 0) {
      return jsonResponse(
        { error: "bad_request", message: "Empty request body" },
        400
      );
    }

    // Verify signature
    const verifier = VERIFIERS[channel];
    const signatureValid = await verifier(request, env, body);

    if (!signatureValid) {
      metrics.signature_failures++;
      log({ level: "warn", msg: "Signature verification failed", channel, ip });
      return jsonResponse(
        { error: "unauthorized", message: "Invalid webhook signature", channel },
        401
      );
    }

    // Build normalized payload
    const payload = await buildPayload(channel, body);

    // Deduplication check
    const duplicate = await isDuplicate(env, payload.idempotency_key);
    if (duplicate) {
      metrics.dedup_hits++;
      log({
        level: "info",
        msg: "Duplicate webhook ignored",
        channel,
        idempotency_key: payload.idempotency_key,
      });
      return jsonResponse(
        {
          status: "duplicate",
          message: "Webhook already processed",
          idempotency_key: payload.idempotency_key,
        },
        200
      );
    }

    // Forward to upstream API
    log({
      level: "info",
      msg: "Forwarding webhook",
      channel,
      ip,
      idempotency_key: payload.idempotency_key,
    });

    const response = await forwardToUpstream(env, payload);

    const latencyMs = Date.now() - startTime;
    log({
      level: response.status < 400 ? "info" : "warn",
      msg: "Webhook processed",
      channel,
      ip,
      status: response.status,
      latency_ms: latencyMs,
      idempotency_key: payload.idempotency_key,
    });

    // Append CORS + timing headers to upstream response
    const finalHeaders = new Headers(response.headers);
    for (const [k, v] of Object.entries(corsHeaders())) {
      finalHeaders.set(k, v);
    }
    finalHeaders.set("X-Response-Time", `${latencyMs}ms`);
    finalHeaders.set("X-RateLimit-Remaining", String(rateResult.remaining));

    return new Response(response.body, {
      status: response.status,
      headers: finalHeaders,
    });
  },
};