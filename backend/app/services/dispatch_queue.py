from __future__ import annotations

import json
from dataclasses import dataclass
from queue import Empty, Queue
from time import time

from app.config import get_settings

try:
    import redis  # type: ignore
except ImportError:  # pragma: no cover
    redis = None


@dataclass(frozen=True, slots=True)
class JobLease:
    job_id: str
    payload: str


class BaseJobQueue:
    is_durable = False

    def enqueue(self, job_id: str) -> None:
        raise NotImplementedError

    def dequeue(self, timeout: float = 0.5) -> JobLease | None:
        raise NotImplementedError

    def ack(self, lease: JobLease) -> None:
        raise NotImplementedError

    def recover_inflight(self) -> None:
        return None


class LocalJobQueue(BaseJobQueue):
    def __init__(self) -> None:
        self._queue: Queue[JobLease] = Queue()

    def enqueue(self, job_id: str) -> None:
        payload = json.dumps({"job_id": job_id, "enqueued_at": time()})
        self._queue.put(JobLease(job_id=job_id, payload=payload))

    def dequeue(self, timeout: float = 0.5) -> JobLease | None:
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            return None

    def ack(self, lease: JobLease) -> None:
        self._queue.task_done()


class RedisJobQueue(BaseJobQueue):
    is_durable = True

    def __init__(self, *, redis_url: str, queue_key: str) -> None:
        if redis is None:
            raise RuntimeError("redis must be installed when JOB_QUEUE_BACKEND=redis.")

        self.client = redis.Redis.from_url(redis_url, decode_responses=True)
        self.pending_key = f"{queue_key}:pending"
        self.processing_key = f"{queue_key}:processing"

    def enqueue(self, job_id: str) -> None:
        payload = json.dumps({"job_id": job_id, "enqueued_at": time()})
        self.client.lpush(self.pending_key, payload)

    def dequeue(self, timeout: float = 0.5) -> JobLease | None:
        raw = self.client.brpoplpush(
            self.pending_key,
            self.processing_key,
            timeout=max(1, int(timeout)),
        )
        if raw is None:
            return None

        payload = json.loads(raw)
        return JobLease(job_id=payload["job_id"], payload=raw)

    def ack(self, lease: JobLease) -> None:
        self.client.lrem(self.processing_key, 1, lease.payload)

    def recover_inflight(self) -> None:
        while True:
            raw = self.client.rpoplpush(self.processing_key, self.pending_key)
            if raw is None:
                break


def build_job_queue() -> BaseJobQueue:
    settings = get_settings()
    if settings.queue_backend == "redis":
        return RedisJobQueue(
            redis_url=settings.redis_url,
            queue_key=settings.redis_queue_key,
        )
    return LocalJobQueue()
