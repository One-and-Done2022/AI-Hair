from __future__ import annotations

from contextlib import contextmanager
from threading import BoundedSemaphore, Lock


_REGISTRY_LOCK = Lock()
_SEMAPHORE_REGISTRY: dict[str, tuple[int, BoundedSemaphore]] = {}


def _get_semaphore(name: str, limit: int) -> BoundedSemaphore:
    normalized_limit = max(1, int(limit))
    with _REGISTRY_LOCK:
        current = _SEMAPHORE_REGISTRY.get(name)
        if current is None or current[0] != normalized_limit:
            current = (normalized_limit, BoundedSemaphore(normalized_limit))
            _SEMAPHORE_REGISTRY[name] = current
        return current[1]


@contextmanager
def concurrency_slot(name: str, limit: int):
    semaphore = _get_semaphore(name, limit)
    semaphore.acquire()
    try:
        yield
    finally:
        semaphore.release()
