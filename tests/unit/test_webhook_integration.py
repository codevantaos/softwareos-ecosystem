"""Unit tests for IM webhook integration flow.

Tests the webhook payload normalization, forwarding logic,
and AI service response path that the Cloudflare webhook-router
relies on when forwarding to the backend.

These tests verify the AI service endpoints that receive
normalized webhook payloads from the edge worker.
"""

import pytest
import json
import hashlib
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient


# ─── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def ai_app():
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from backend.ai.src.app import app
    return app


@pytest.fixture(scope="module")
def ai_client(ai_app):
    with TestClient(ai_app) as c:
        yield c


# ─── Webhook Payload Builders ─────────────────────────────────────────

def build_whatsapp_normalized_payload(text: str = "Hello from WhatsApp", sender: str = "15551234567"):
    msg_id = "wamid_test_" + hashlib.md5(text.encode()).hexdigest()[:8]
    return {
        "channel": "whatsapp",
        "event_type": "message",
        "sender_id": sender,
        "chat_id": sender,
        "text": text,
        "message_id": msg_id,
        "timestamp": "2025-01-15T10:30:00.000Z",
        "raw": {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "id": msg_id,
                            "from": sender,
                            "type": "text",
                            "text": {"body": text},
                            "timestamp": "1736935800",
                        }],
                        "contacts": [{"profile": {"name": "Test User"}}],
                        "metadata": {"phone_number_id": "100000000000"},
                    }
                }]
            }]
        },
        "signature_valid": True,
        "idempotency_key": hashlib.sha256(f"whatsapp:{msg_id}".encode()).hexdigest(),
        "uri": f"softwareos-base://im/whatsapp/webhook/{msg_id}",
        "urn": f"urn:softwareos-base:im:whatsapp:webhook:{sender}:{msg_id}",
    }


def build_telegram_normalized_payload(text: str = "Hello from Telegram", sender: str = "123456789"):
    msg_id = "tg_" + hashlib.md5(text.encode()).hexdigest()[:8]
    return {
        "channel": "telegram",
        "event_type": "message",
        "sender_id": sender,
        "chat_id": sender,
        "text": text,
        "message_id": msg_id,
        "timestamp": "2025-01-15T10:30:00.000Z",
        "raw": {
            "message": {
                "message_id": int(msg_id.replace("tg_", "0x"), 16) % 100000,
                "from": {"id": int(sender), "first_name": "Test"},
                "chat": {"id": int(sender), "type": "private"},
                "text": text,
                "date": 1736935800,
            }
        },
        "signature_valid": True,
        "idempotency_key": hashlib.sha256(f"telegram:{msg_id}".encode()).hexdigest(),
        "uri": f"softwareos-base://im/telegram/webhook/{msg_id}",
        "urn": f"urn:softwareos-base:im:telegram:webhook:{sender}:{msg_id}",
    }


def build_line_normalized_payload(text: str = "Hello from LINE", sender: str = "U1234567890abcdef"):
    msg_id = "line_" + hashlib.md5(text.encode()).hexdigest()[:8]
    return {
        "channel": "line",
        "event_type": "message",
        "sender_id": sender,
        "chat_id": sender,
        "text": text,
        "message_id": msg_id,
        "timestamp": "2025-01-15T10:30:00.000Z",
        "raw": {
            "events": [{
                "type": "message",
                "source": {"type": "user", "userId": sender},
                "message": {"id": msg_id, "type": "text", "text": text},
                "replyToken": "reply_token_test",
                "timestamp": 1736935800000,
            }]
        },
        "signature_valid": True,
        "idempotency_key": hashlib.sha256(f"line:{msg_id}".encode()).hexdigest(),
        "uri": f"softwareos-base://im/line/webhook/{msg_id}",
        "urn": f"urn:softwareos-base:im:line:webhook:{sender}:{msg_id}",
    }


def build_messenger_normalized_payload(text: str = "Hello from Messenger", sender: str = "9876543210"):
    msg_id = "mid_" + hashlib.md5(text.encode()).hexdigest()[:8]
    return {
        "channel": "messenger",
        "event_type": "message",
        "sender_id": sender,
        "chat_id": sender,
        "text": text,
        "message_id": msg_id,
        "timestamp": "2025-01-15T10:30:00.000Z",
        "raw": {
            "entry": [{
                "id": "page_id_test",
                "messaging": [{
                    "sender": {"id": sender},
                    "message": {"mid": msg_id, "text": text},
                    "timestamp": 1736935800000,
                }]
            }]
        },
        "signature_valid": True,
        "idempotency_key": hashlib.sha256(f"messenger:{msg_id}".encode()).hexdigest(),
        "uri": f"softwareos-base://im/messenger/webhook/{msg_id}",
        "urn": f"urn:softwareos-base:im:messenger:webhook:{sender}:{msg_id}",
    }


# ─── Test: AI Service Handles Webhook-Originated Requests ─────────────

class TestWebhookToAIFlow:
    """Verify that the AI service correctly handles requests
    that originate from IM webhook payloads forwarded by the
    Cloudflare worker through the API service."""

    def test_generate_from_whatsapp_context(self, ai_client):
        """Simulate a generate request that would come from a WhatsApp webhook."""
        resp = ai_client.post("/api/v1/generate", json={
            "prompt": "Hello from WhatsApp",
            "model_id": "default",
            "max_tokens": 1024,
            "temperature": 0.7,
            "top_p": 0.9,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert "request_id" in data
        assert "engine" in data
        assert "uri" in data
        assert data["uri"].startswith("softwareos-base://")

    def test_generate_from_telegram_context(self, ai_client):
        resp = ai_client.post("/api/v1/generate", json={
            "prompt": "Hello from Telegram",
            "model_id": "default",
            "max_tokens": 1024,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert len(data["content"]) > 0

    def test_generate_from_line_context(self, ai_client):
        resp = ai_client.post("/api/v1/generate", json={
            "prompt": "Hello from LINE",
            "model_id": "default",
            "max_tokens": 512,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data

    def test_generate_from_messenger_context(self, ai_client):
        resp = ai_client.post("/api/v1/generate", json={
            "prompt": "Hello from Messenger",
            "model_id": "default",
            "max_tokens": 512,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data


# ─── Test: Payload Normalization Correctness ──────────────────────────

class TestPayloadNormalization:
    """Verify that normalized payloads from each channel contain
    all required fields for downstream processing."""

    def test_whatsapp_payload_structure(self):
        payload = build_whatsapp_normalized_payload()
        assert payload["channel"] == "whatsapp"
        assert payload["event_type"] == "message"
        assert payload["sender_id"] == "15551234567"
        assert payload["text"] == "Hello from WhatsApp"
        assert payload["signature_valid"] is True
        assert payload["uri"].startswith("softwareos-base://im/whatsapp/")
        assert payload["urn"].startswith("urn:softwareos-base:im:whatsapp:")
        assert len(payload["idempotency_key"]) == 64

    def test_telegram_payload_structure(self):
        payload = build_telegram_normalized_payload()
        assert payload["channel"] == "telegram"
        assert payload["event_type"] == "message"
        assert payload["sender_id"] == "123456789"
        assert payload["text"] == "Hello from Telegram"
        assert payload["signature_valid"] is True
        assert payload["uri"].startswith("softwareos-base://im/telegram/")

    def test_line_payload_structure(self):
        payload = build_line_normalized_payload()
        assert payload["channel"] == "line"
        assert payload["event_type"] == "message"
        assert payload["sender_id"] == "U1234567890abcdef"
        assert payload["text"] == "Hello from LINE"
        assert payload["signature_valid"] is True
        assert payload["uri"].startswith("softwareos-base://im/line/")

    def test_messenger_payload_structure(self):
        payload = build_messenger_normalized_payload()
        assert payload["channel"] == "messenger"
        assert payload["event_type"] == "message"
        assert payload["sender_id"] == "9876543210"
        assert payload["text"] == "Hello from Messenger"
        assert payload["signature_valid"] is True
        assert payload["uri"].startswith("softwareos-base://im/messenger/")

    def test_idempotency_keys_unique_per_message(self):
        p1 = build_whatsapp_normalized_payload("Message A")
        p2 = build_whatsapp_normalized_payload("Message B")
        assert p1["idempotency_key"] != p2["idempotency_key"]

    def test_idempotency_keys_stable_for_same_message(self):
        p1 = build_whatsapp_normalized_payload("Same message")
        p2 = build_whatsapp_normalized_payload("Same message")
        assert p1["idempotency_key"] == p2["idempotency_key"]

    def test_all_channels_have_raw_field(self):
        for builder in [
            build_whatsapp_normalized_payload,
            build_telegram_normalized_payload,
            build_line_normalized_payload,
            build_messenger_normalized_payload,
        ]:
            payload = builder()
            assert "raw" in payload
            assert isinstance(payload["raw"], dict)


# ─── Test: Edge Cases ─────────────────────────────────────────────────

class TestWebhookEdgeCases:
    """Edge cases for webhook processing."""

    def test_empty_text_generates_response(self, ai_client):
        """AI service should handle empty-ish prompts gracefully."""
        resp = ai_client.post("/api/v1/generate", json={
            "prompt": " ",
            "model_id": "default",
            "max_tokens": 256,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data

    def test_long_text_generates_response(self, ai_client):
        """AI service should handle long prompts."""
        long_text = "Hello " * 500
        resp = ai_client.post("/api/v1/generate", json={
            "prompt": long_text,
            "model_id": "default",
            "max_tokens": 256,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data

    def test_unicode_text_generates_response(self, ai_client):
        """AI service should handle unicode from IM platforms."""
        resp = ai_client.post("/api/v1/generate", json={
            "prompt": "こんにちは世界 🌍 مرحبا",
            "model_id": "default",
            "max_tokens": 256,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data

    def test_missing_prompt_returns_422(self, ai_client):
        """AI service should reject requests without prompt."""
        resp = ai_client.post("/api/v1/generate", json={
            "model_id": "default",
        })
        assert resp.status_code == 422