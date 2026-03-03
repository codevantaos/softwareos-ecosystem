/**
 * Message Router — routes normalized messages to AI backend and manages sessions.
 *
 * Redis-backed conversation state per user/channel.
 * Uses ECO_* environment variables for configuration.
 *
 * URI: softwareos-base://platforms/im-integration/shared/router
 */

import Redis from "ioredis";
import pino from "pino";
import type { NormalizedMessage, OutboundMessage, Channel } from "./normalizer";

const logger = pino({
  level: process.env.ECO_LOG_LEVEL || "info",
  name: "eco-im-router",
});

interface SessionState {
  userId: string;
  channel: Channel;
  conversationId: string;
  messageCount: number;
  lastMessageAt: string;
  context: Record<string, unknown>;
}

export class MessageRouter {
  private redis: Redis;
  private sessionTTL: number;
  private apiUrl: string;
  private serviceToken: string;

  constructor(
    redisUrl: string = process.env.ECO_REDIS_URL || "redis://localhost:6379",
    sessionTTL = parseInt(process.env.ECO_IM_SESSION_TTL || "3600", 10)
  ) {
    this.redis = new Redis(redisUrl, {
      maxRetriesPerRequest: 3,
      lazyConnect: true,
      enableOfflineQueue: true,
      retryStrategy(times: number) {
        if (times > 5) return null;
        return Math.min(times * 200, 2000);
      },
    });
    this.sessionTTL = sessionTTL;
    this.apiUrl = process.env.ECO_API_URL || "http://localhost:3000";
    this.serviceToken = process.env.ECO_SERVICE_TOKEN || "";

    this.redis.on("error", (err) => {
      logger.warn({ msg: "Redis connection error", error: err.message });
    });
  }

  async route(message: NormalizedMessage): Promise<OutboundMessage> {
    let session: SessionState;

    try {
      session = await this.getOrCreateSession(message);
    } catch (err) {
      // Redis failure: create ephemeral session
      logger.warn({
        msg: "Redis unavailable, using ephemeral session",
        error: (err as Error).message,
      });
      session = {
        userId: message.userId,
        channel: message.channel,
        conversationId: crypto.randomUUID(),
        messageCount: 0,
        lastMessageAt: new Date().toISOString(),
        context: {},
      };
    }

    logger.info({
      msg: "Routing message",
      channel: message.channel,
      userId: message.userId,
      conversationId: session.conversationId,
      messageCount: session.messageCount,
    });

    // Forward to AI backend
    const aiResponse = await this.forwardToAI(message, session);

    // Update session (best-effort)
    session.messageCount++;
    session.lastMessageAt = new Date().toISOString();
    try {
      await this.saveSession(session);
    } catch {
      // Non-fatal
    }

    return {
      channel: message.channel,
      userId: message.userId,
      text: aiResponse,
      metadata: { conversationId: session.conversationId },
    };
  }

  private async getOrCreateSession(
    message: NormalizedMessage
  ): Promise<SessionState> {
    const key = `eco:session:${message.channel}:${message.userId}`;
    const existing = await this.redis.get(key);

    if (existing) {
      return JSON.parse(existing);
    }

    const session: SessionState = {
      userId: message.userId,
      channel: message.channel,
      conversationId: crypto.randomUUID(),
      messageCount: 0,
      lastMessageAt: new Date().toISOString(),
      context: {},
    };

    await this.saveSession(session);
    return session;
  }

  private async saveSession(session: SessionState): Promise<void> {
    const key = `eco:session:${session.channel}:${session.userId}`;
    await this.redis.setex(key, this.sessionTTL, JSON.stringify(session));
  }

  private async forwardToAI(
    message: NormalizedMessage,
    session: SessionState
  ): Promise<string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Request-Source": "eco-im-router",
      "X-Channel": message.channel,
      "X-Conversation-Id": session.conversationId,
    };

    if (this.serviceToken) {
      headers["Authorization"] = `Bearer ${this.serviceToken}`;
    }

    try {
      const res = await fetch(`${this.apiUrl}/api/v1/ai/generate`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          prompt: message.text,
          model_id: "default",
          max_tokens: 1024,
          temperature: 0.7,
          top_p: 0.9,
          params: {
            channel: message.channel,
            conversationId: session.conversationId,
            userId: message.userId,
            messageId: message.id,
          },
        }),
        signal: AbortSignal.timeout(30000),
      });

      if (res.ok) {
        const data = (await res.json()) as Record<string, any>;
        return data.result || data.content || "Processing your request...";
      }

      logger.warn({
        msg: "AI service returned non-OK",
        status: res.status,
        channel: message.channel,
      });
      return "I'm having trouble processing your request. Please try again.";
    } catch (err) {
      logger.error({
        msg: "Failed to reach AI service",
        error: (err as Error).message,
        channel: message.channel,
      });
      return "Service temporarily unavailable. Please try again later.";
    }
  }

  async destroy(): Promise<void> {
    try {
      await this.redis.quit();
    } catch {
      // Already disconnected
    }
  }
}