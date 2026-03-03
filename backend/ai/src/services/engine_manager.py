"""Engine Manager — Orchestrates inference engine lifecycle, routing, and health.

Initializes all 7 engine adapters with connection pools and circuit breakers.
Provides unified generate/stream interface with automatic failover.

URI: softwareos-base://backend/ai/services/engine_manager
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from .circuit_breaker import CircuitBreaker, CircuitState
from .connection_pool import ConnectionPool

logger = logging.getLogger(__name__)

# Engine endpoint defaults (overridden by ECO_* env vars at runtime)
DEFAULT_ENGINE_ENDPOINTS: Dict[str, str] = {
    "vllm": "http://localhost:8100",
    "tgi": "http://localhost:8101",
    "ollama": "http://localhost:11434",
    "sglang": "http://localhost:8102",
    "tensorrt": "http://localhost:8103",
    "deepspeed": "http://localhost:8104",
    "lmdeploy": "http://localhost:8105",
}

# Model → preferred engine mapping
MODEL_ENGINE_MAP: Dict[str, str] = {
    "llama-3.1-8b-instruct": "vllm",
    "llama-3.1-70b-instruct": "vllm",
    "qwen2.5-72b-instruct": "vllm",
    "qwen2.5-coder-32b-instruct": "sglang",
    "deepseek-r1": "vllm",
    "mistral-7b-instruct": "ollama",
}


class EngineHealth:
    """Tracks per-engine health metrics."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.is_available: bool = False
        self.last_check: float = 0.0
        self.latency_ms: float = 0.0
        self.total_requests: int = 0
        self.total_errors: int = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "available": self.is_available,
            "latency_ms": round(self.latency_ms, 2),
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
        }


class EngineManager:
    """Manages all inference engine adapters with connection pooling and circuit breaking."""

    def __init__(
        self,
        endpoints: Optional[Dict[str, str]] = None,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
    ) -> None:
        self._endpoints = endpoints or DEFAULT_ENGINE_ENDPOINTS
        self._pool = ConnectionPool()
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._health: Dict[str, EngineHealth] = {}

        for name in self._endpoints:
            self._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
            )
            self._health[name] = EngineHealth(name)

    async def initialize(self) -> None:
        """Probe all engines and establish connection pools."""
        logger.info("EngineManager: initializing %d engines", len(self._endpoints))
        tasks = [self._probe_engine(name) for name in self._endpoints]
        await asyncio.gather(*tasks, return_exceptions=True)
        available = sum(1 for h in self._health.values() if h.is_available)
        logger.info(
            "EngineManager: %d/%d engines available", available, len(self._endpoints)
        )

    async def _probe_engine(self, name: str) -> None:
        """Health-check a single engine."""
        url = self._endpoints[name]
        client = self._pool.get_client(name, url)
        health = self._health[name]
        start = time.monotonic()
        try:
            # Most engines expose /health or /v1/models
            for path in ["/health", "/v1/models", "/"]:
                try:
                    resp = await client.get(path, timeout=5.0)
                    if resp.status_code < 500:
                        health.is_available = True
                        health.latency_ms = (time.monotonic() - start) * 1000
                        health.last_check = time.time()
                        logger.info(
                            "Engine %s: available at %s (%.1fms)",
                            name,
                            url,
                            health.latency_ms,
                        )
                        return
                except Exception:
                    continue
            health.is_available = False
            logger.info("Engine %s: not available at %s", name, url)
        except Exception as exc:
            health.is_available = False
            logger.debug("Engine %s probe failed: %s", name, exc)

    def resolve_engine(self, model_id: str) -> str:
        """Resolve model_id to best available engine name."""
        # Direct mapping
        preferred = MODEL_ENGINE_MAP.get(model_id)
        if preferred and self._is_engine_usable(preferred):
            return preferred

        # Partial match
        for mid, eng in MODEL_ENGINE_MAP.items():
            if model_id in mid or mid in model_id:
                if self._is_engine_usable(eng):
                    return eng

        # Fallback: first usable engine
        for name in self._endpoints:
            if self._is_engine_usable(name):
                return name

        # Last resort: return vllm even if circuit is open
        return "vllm"

    def _is_engine_usable(self, name: str) -> bool:
        breaker = self._breakers.get(name)
        if not breaker:
            return False
        return breaker.state != CircuitState.OPEN

    async def generate(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Route generation request to appropriate engine with failover."""
        engine_name = self.resolve_engine(model_id)
        candidates = [engine_name] + [
            n for n in self._endpoints if n != engine_name and self._is_engine_usable(n)
        ]

        last_error: Optional[Exception] = None
        for name in candidates:
            breaker = self._breakers[name]
            if not breaker.allow_request():
                continue

            health = self._health[name]
            health.total_requests += 1
            start = time.monotonic()

            try:
                result = await self._call_engine(
                    name, model_id, prompt, max_tokens, temperature, top_p, **kwargs
                )
                elapsed = (time.monotonic() - start) * 1000
                health.latency_ms = elapsed
                breaker.record_success()
                result["engine"] = name
                result["latency_ms"] = round(elapsed, 2)
                return result
            except Exception as exc:
                health.total_errors += 1
                breaker.record_failure()
                last_error = exc
                logger.warning(
                    "Engine %s failed for model %s: %s — trying next",
                    name,
                    model_id,
                    exc,
                )

        # All engines failed — return degraded response
        logger.error(
            "All engines failed for model %s. Last error: %s", model_id, last_error
        )
        return {
            "content": f"[degraded] All inference engines unavailable for {model_id}. "
            f"Last error: {last_error}",
            "model_id": model_id,
            "engine": "none",
            "finish_reason": "error",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "latency_ms": 0,
        }

    async def _call_engine(
        self,
        engine_name: str,
        model_id: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute inference call against a specific engine."""
        url = self._endpoints[engine_name]
        client = self._pool.get_client(engine_name, url)

        # OpenAI-compatible payload (works for vLLM, TGI, SGLang, LMDeploy)
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": False,
        }

        # Engine-specific path adjustments
        path = "/v1/chat/completions"
        if engine_name == "ollama":
            path = "/api/chat"
            payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}],
                "options": {"temperature": temperature, "top_p": top_p, "num_predict": max_tokens},
                "stream": False,
            }
        elif engine_name == "deepspeed":
            path = "/generate"
            payload = {"prompt": prompt, "max_tokens": max_tokens, "temperature": temperature}

        resp = await client.post(path, json=payload)
        resp.raise_for_status()
        data = resp.json()

        # Normalize response across engine formats
        content = ""
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        if "choices" in data and data["choices"]:
            msg = data["choices"][0].get("message", {})
            content = msg.get("content", "")
            if "usage" in data:
                usage = data["usage"]
        elif "message" in data:
            # Ollama format
            content = data["message"].get("content", "")
        elif "text" in data:
            # DeepSpeed format
            content = data["text"]
        else:
            content = str(data)

        return {
            "content": content,
            "model_id": model_id,
            "finish_reason": "stop",
            "usage": usage,
        }

    async def shutdown(self) -> None:
        """Clean shutdown — close all connection pools."""
        logger.info("EngineManager: shutting down")
        await self._pool.close_all()

    def get_health(self) -> Dict[str, Any]:
        """Return health status of all engines."""
        return {
            "engines": {n: h.to_dict() for n, h in self._health.items()},
            "circuits": {n: b.to_dict() for n, b in self._breakers.items()},
            "pool": self._pool.to_dict(),
        }

    def list_available_engines(self) -> List[str]:
        return [n for n, h in self._health.items() if h.is_available]