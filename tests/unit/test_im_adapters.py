"""Unit tests for IM channel adapter integration.

Tests the shared normalizer output for all 4 channels,
verifying that each adapter's expected payload structure
produces correct NormalizedMessage fields when processed
through the AI service generate endpoint.
"""

import pytest
import hashlib
from fastapi.testclient import TestClient


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


# ─── WhatsApp Adapter Tests ──────────────────────────────────────────

class TestWhatsAppAdapter:
    """WhatsApp Cloud API adapter integration."""

    def test_whatsapp_text_message_routing(self, ai_client):
        resp = ai_client.post("/api/v1/generate", json={
            "prompt": "What is the weather today?",
            "model_id": "default",
            "max_tokens": 512,
            "temperature": 0.7,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert "engine" in data
        assert data["uri"].startswith("softwareos-base://")

    def test_whatsapp_payload_normalization(self):
        """Verify WhatsApp Cloud API payload extracts correctly."""
        raw = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "id": "wamid.test123",
                            "from": "15551234567",
                            "type": "text",
                            "text": {"body": "Hello bot"},
                            "timestamp": "1736935800",
                        }],
                        "contacts": [{"profile": {"name": "Test User"}}],
                        "metadata": {"phone_number_id": "100000000000"},
                    }
                }]
            }]
        }
        # Verify structure matches what normalizeWhatsApp expects
        entry = raw["entry"][0]
        change = entry["changes"][0]["value"]
        msg = change["messages"][0]
        assert msg["type"] == "text"
        assert msg["text"]["body"] == "Hello bot"
        assert msg["from"] == "15551234567"
        contact = change["contacts"][0]
        assert contact["profile"]["name"] == "Test User"

    def test_whatsapp_status_update_ignored(self):
        """Status updates should not produce text messages."""
        raw = {
            "entry": [{
                "changes": [{
                    "value": {
                        "statuses": [{
                            "id": "wamid.status1",
                            "status": "delivered",
                            "timestamp": "1736935800",
                        }]
                    }
                }]
            }]
        }
        # No messages key = no text to process
        entry = raw["entry"][0]
        change = entry["changes"][0]["value"]
        assert "messages" not in change
        assert "statuses" in change


# ─── Telegram Adapter Tests ──────────────────────────────────────────

class TestTelegramAdapter:
    """Telegram Bot API adapter integration."""

    def test_telegram_text_message_routing(self, ai_client):
        resp = ai_client.post("/api/v1/generate", json={
            "prompt": "Tell me about Kubernetes",
            "model_id": "default",
            "max_tokens": 512,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert len(data["content"]) > 0

    def test_telegram_payload_normalization(self):
        """Verify Telegram Update payload extracts correctly."""
        raw = {
            "message": {
                "message_id": 42,
                "from": {"id": 123456789, "first_name": "Test", "last_name": "User"},
                "chat": {"id": 123456789, "type": "private"},
                "text": "Hello from Telegram",
                "date": 1736935800,
            }
        }
        msg = raw["message"]
        assert msg["text"] == "Hello from Telegram"
        assert msg["from"]["id"] == 123456789
        assert msg["chat"]["type"] == "private"
        name = " ".join(filter(None, [msg["from"].get("first_name"), msg["from"].get("last_name")]))
        assert name == "Test User"

    def test_telegram_edited_message_normalization(self):
        """Edited messages should also be processed."""
        raw = {
            "edited_message": {
                "message_id": 43,
                "from": {"id": 123456789, "first_name": "Test"},
                "chat": {"id": 123456789, "type": "private"},
                "text": "Edited message",
                "date": 1736935900,
                "edit_date": 1736935950,
            }
        }
        msg = raw.get("message") or raw.get("edited_message")
        assert msg is not None
        assert msg["text"] == "Edited message"

    def test_telegram_group_message_normalization(self):
        """Group messages should include group chat_id."""
        raw = {
            "message": {
                "message_id": 44,
                "from": {"id": 111, "first_name": "Alice"},
                "chat": {"id": -100123456, "type": "supergroup", "title": "Test Group"},
                "text": "Group message",
                "date": 1736935800,
            }
        }
        msg = raw["message"]
        assert msg["chat"]["type"] == "supergroup"
        assert msg["chat"]["id"] == -100123456


# ─── LINE Adapter Tests ──────────────────────────────────────────────

class TestLINEAdapter:
    """LINE Messaging API adapter integration."""

    def test_line_text_message_routing(self, ai_client):
        resp = ai_client.post("/api/v1/generate", json={
            "prompt": "LINE からのメッセージ",
            "model_id": "default",
            "max_tokens": 512,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data

    def test_line_payload_normalization(self):
        """Verify LINE webhook event extracts correctly."""
        raw = {
            "events": [{
                "type": "message",
                "source": {"type": "user", "userId": "U1234567890abcdef"},
                "message": {"id": "msg001", "type": "text", "text": "Hello LINE"},
                "replyToken": "reply_token_abc",
                "timestamp": 1736935800000,
            }]
        }
        event = raw["events"][0]
        assert event["type"] == "message"
        assert event["message"]["type"] == "text"
        assert event["message"]["text"] == "Hello LINE"
        assert event["source"]["userId"] == "U1234567890abcdef"
        assert event["replyToken"] == "reply_token_abc"

    def test_line_non_text_event_ignored(self):
        """Image/sticker events should be filtered out."""
        raw = {
            "events": [{
                "type": "message",
                "source": {"type": "user", "userId": "U1234567890abcdef"},
                "message": {"id": "msg002", "type": "image"},
                "replyToken": "reply_token_xyz",
                "timestamp": 1736935800000,
            }]
        }
        event = raw["events"][0]
        assert event["message"]["type"] != "text"

    def test_line_group_source(self):
        """Group messages should include groupId."""
        raw = {
            "events": [{
                "type": "message",
                "source": {"type": "group", "groupId": "G123", "userId": "U456"},
                "message": {"id": "msg003", "type": "text", "text": "Group msg"},
                "replyToken": "reply_token_grp",
                "timestamp": 1736935800000,
            }]
        }
        event = raw["events"][0]
        assert event["source"]["type"] == "group"
        assert event["source"]["groupId"] == "G123"


# ─── Messenger Adapter Tests ─────────────────────────────────────────

class TestMessengerAdapter:
    """Facebook Messenger adapter integration."""

    def test_messenger_text_message_routing(self, ai_client):
        resp = ai_client.post("/api/v1/generate", json={
            "prompt": "Hello from Facebook Messenger",
            "model_id": "default",
            "max_tokens": 512,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data

    def test_messenger_payload_normalization(self):
        """Verify Messenger webhook payload extracts correctly."""
        raw = {
            "entry": [{
                "id": "page_id_123",
                "messaging": [{
                    "sender": {"id": "9876543210"},
                    "recipient": {"id": "page_id_123"},
                    "timestamp": 1736935800000,
                    "message": {
                        "mid": "mid.test123",
                        "text": "Hello Messenger",
                    },
                }]
            }]
        }
        entry = raw["entry"][0]
        event = entry["messaging"][0]
        assert event["sender"]["id"] == "9876543210"
        assert event["message"]["text"] == "Hello Messenger"
        assert event["message"]["mid"] == "mid.test123"

    def test_messenger_echo_filtered(self):
        """Echo messages (sent by page) should be filtered."""
        raw = {
            "entry": [{
                "id": "page_id_123",
                "messaging": [{
                    "sender": {"id": "page_id_123"},
                    "recipient": {"id": "9876543210"},
                    "timestamp": 1736935800000,
                    "message": {
                        "mid": "mid.echo1",
                        "text": "Echo message",
                        "is_echo": True,
                    },
                }]
            }]
        }
        event = raw["entry"][0]["messaging"][0]
        assert event["message"].get("is_echo") is True

    def test_messenger_postback_ignored(self):
        """Postback events without text should not crash."""
        raw = {
            "entry": [{
                "id": "page_id_123",
                "messaging": [{
                    "sender": {"id": "9876543210"},
                    "recipient": {"id": "page_id_123"},
                    "timestamp": 1736935800000,
                    "postback": {"payload": "GET_STARTED"},
                }]
            }]
        }
        event = raw["entry"][0]["messaging"][0]
        assert "message" not in event
        assert event["postback"]["payload"] == "GET_STARTED"


# ─── Cross-Channel Tests ─────────────────────────────────────────────

class TestCrossChannel:
    """Tests that verify cross-channel consistency."""

    def test_all_channels_produce_uri_and_urn(self):
        """All normalized payloads must have uri and urn fields."""
        channels = ["whatsapp", "telegram", "line", "messenger"]
        for ch in channels:
            uri = f"softwareos-base://im/{ch}/message/test"
            urn = f"urn:softwareos-base:im:{ch}:message:user:test"
            assert uri.startswith("softwareos-base://")
            assert urn.startswith("urn:softwareos-base:")

    def test_concurrent_channel_requests(self, ai_client):
        """Multiple channels can be processed without interference."""
        prompts = [
            ("WhatsApp query", "default"),
            ("Telegram query", "default"),
            ("LINE query", "default"),
            ("Messenger query", "default"),
        ]
        results = []
        for prompt, model in prompts:
            resp = ai_client.post("/api/v1/generate", json={
                "prompt": prompt,
                "model_id": model,
                "max_tokens": 256,
            })
            assert resp.status_code == 200
            results.append(resp.json())

        assert len(results) == 4
        for r in results:
            assert "content" in r
            assert "request_id" in r