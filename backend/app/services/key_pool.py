from __future__ import annotations

from dataclasses import dataclass
from threading import Condition, Lock
from time import monotonic

from app.config import ArkApiCredential


@dataclass(frozen=True, slots=True)
class ApiKeyLease:
    key_id: str
    api_key: str


@dataclass(slots=True)
class _ApiKeyState:
    credential: ArkApiCredential
    inflight_count: int = 0
    cooldown_until: float = 0.0
    last_used_at: float = 0.0
    success_count: int = 0
    error_count: int = 0
    disabled: bool = False
    disabled_reason: str | None = None
    disabled_at: float | None = None


class ApiKeyPool:
    def __init__(
        self,
        credentials: tuple[ArkApiCredential, ...],
        *,
        default_cooldown_seconds: int,
    ) -> None:
        if not credentials:
            raise ValueError("ApiKeyPool requires at least one credential.")

        self.default_cooldown_seconds = max(0, default_cooldown_seconds)
        self._states = {
            credential.key_id: _ApiKeyState(credential=credential)
            for credential in credentials
        }
        self._lock = Lock()
        self._condition = Condition(self._lock)

    @property
    def size(self) -> int:
        with self._condition:
            return len(self._states)

    @property
    def active_size(self) -> int:
        with self._condition:
            return sum(1 for state in self._states.values() if not state.disabled)

    def acquire(
        self,
        *,
        excluded_key_ids: set[str] | None = None,
        timeout: float = 0.5,
    ) -> ApiKeyLease | None:
        deadline = monotonic() + max(timeout, 0.0)
        excluded_key_ids = excluded_key_ids or set()

        with self._condition:
            while True:
                state = self._pick_available_state(excluded_key_ids)
                if state is not None:
                    state.inflight_count += 1
                    state.last_used_at = monotonic()
                    return ApiKeyLease(
                        key_id=state.credential.key_id,
                        api_key=state.credential.api_key,
                    )

                remaining = deadline - monotonic()
                if remaining <= 0:
                    return None

                self._condition.wait(timeout=min(remaining, 0.5))

    def release_success(self, key_id: str) -> None:
        with self._condition:
            state = self._states[key_id]
            state.inflight_count = max(0, state.inflight_count - 1)
            state.success_count += 1
            state.last_used_at = monotonic()
            self._condition.notify_all()

    def release_error(self, key_id: str, *, cooldown_seconds: int | None = None) -> None:
        with self._condition:
            state = self._states[key_id]
            state.inflight_count = max(0, state.inflight_count - 1)
            state.error_count += 1
            state.last_used_at = monotonic()
            cooldown = self.default_cooldown_seconds if cooldown_seconds is None else max(
                0, cooldown_seconds
            )
            if cooldown > 0:
                state.cooldown_until = monotonic() + cooldown
            self._condition.notify_all()

    def disable_key(self, key_id: str, *, reason: str | None = None) -> None:
        with self._condition:
            state = self._states[key_id]
            state.inflight_count = max(0, state.inflight_count - 1)
            state.error_count += 1
            state.last_used_at = monotonic()
            state.cooldown_until = float("inf")
            state.disabled = True
            state.disabled_reason = reason
            state.disabled_at = state.last_used_at
            self._condition.notify_all()

    def is_disabled(self, key_id: str) -> bool:
        with self._condition:
            return self._states[key_id].disabled

    def _pick_available_state(self, excluded_key_ids: set[str]) -> _ApiKeyState | None:
        now = monotonic()
        available = [
            state
            for key_id, state in self._states.items()
            if key_id not in excluded_key_ids
            and not state.disabled
            and state.cooldown_until <= now
            and state.inflight_count < state.credential.max_concurrency
        ]
        if not available:
            return None

        available.sort(
            key=lambda state: (
                state.inflight_count / max(1, state.credential.max_concurrency * state.credential.weight),
                state.last_used_at,
                state.credential.key_id,
            )
        )
        return available[0]
