"""Circuit Breaker — Prevents cascading failures across inference engine adapters.

State machine: CLOSED → OPEN → HALF_OPEN → CLOSED
- CLOSED: requests pass through; failures counted
- OPEN: requests rejected immediately; timer running
- HALF_OPEN: single probe request allowed; success → CLOSED, failure → OPEN

URI: softwareos-base://backend/ai/services/circuit_breaker
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Per-engine circuit breaker with configurable thresholds."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls: int = 0

        # Metrics
        self.total_requests: int = 0
        self.total_failures: int = 0
        self.total_rejections: int = 0
        self.total_successes: int = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                logger.info(
                    "Circuit %s: OPEN → HALF_OPEN after %.1fs recovery",
                    self.name,
                    elapsed,
                )
        return self._state

    def allow_request(self) -> bool:
        """Check if a request should be allowed through."""
        self.total_requests += 1
        current = self.state

        if current == CircuitState.CLOSED:
            return True

        if current == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            self.total_rejections += 1
            return False

        # OPEN
        self.total_rejections += 1
        return False

    def record_success(self) -> None:
        """Record a successful request."""
        self.total_successes += 1
        current = self.state

        if current == CircuitState.HALF_OPEN:
            self._success_count += 1
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            logger.info("Circuit %s: HALF_OPEN → CLOSED (probe succeeded)", self.name)
        elif current == CircuitState.CLOSED:
            self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self) -> None:
        """Record a failed request."""
        self.total_failures += 1
        current = self.state

        if current == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._last_failure_time = time.monotonic()
            logger.warning(
                "Circuit %s: HALF_OPEN → OPEN (probe failed)", self.name
            )
            return

        if current == CircuitState.CLOSED:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._last_failure_time = time.monotonic()
                logger.warning(
                    "Circuit %s: CLOSED → OPEN after %d failures",
                    self.name,
                    self._failure_count,
                )

    def reset(self) -> None:
        """Force reset to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        logger.info("Circuit %s: force reset to CLOSED", self.name)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "total_rejections": self.total_rejections,
            "total_successes": self.total_successes,
        }