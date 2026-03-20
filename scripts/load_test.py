#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx


@dataclass(slots=True)
class StepMetric:
    name: str
    elapsed_ms: float
    ok: bool
    status_code: int | None = None


@dataclass(slots=True)
class JobRunResult:
    user_code: str
    job_index: int
    success: bool
    final_status: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    preview_elapsed_ms: float | None = None
    complete_elapsed_ms: float | None = None
    steps: list[StepMetric] = field(default_factory=list)
    exception: str | None = None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="对 AI Hair Remix 后端执行多用户并发压测。",
    )
    parser.add_argument("--host", required=True, help="例如 http://127.0.0.1:8000")
    parser.add_argument("--image", required=True, help="用于上传的测试图片路径")
    parser.add_argument("--users", type=int, default=4, help="并发用户数")
    parser.add_argument("--jobs-per-user", type=int, default=1, help="每个用户连续生成多少次")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="任务轮询间隔，单位秒")
    parser.add_argument("--job-timeout", type=float, default=180.0, help="单个任务超时，单位秒")
    parser.add_argument("--request-timeout", type=float, default=30.0, help="单次 HTTP 请求超时，单位秒")
    parser.add_argument("--hairstyle-id", default="", help="固定发型模板 id，可选")
    parser.add_argument("--scene-id", default="", help="固定场景模板 id，可选")
    parser.add_argument(
        "--random-templates",
        action="store_true",
        help="每次任务随机选择发型和场景模板",
    )
    return parser.parse_args()


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * ratio)))
    return ordered[index]


def _format_ms(values: list[float]) -> str:
    if not values:
        return "-"
    return (
        f"p50={_percentile(values, 0.50):.1f}ms "
        f"p95={_percentile(values, 0.95):.1f}ms "
        f"max={max(values):.1f}ms"
    )


def _format_seconds(values_ms: list[float]) -> str:
    if not values_ms:
        return "-"
    values_s = [value / 1000 for value in values_ms]
    return (
        f"p50={_percentile(values_s, 0.50):.2f}s "
        f"p95={_percentile(values_s, 0.95):.2f}s "
        f"max={max(values_s):.2f}s"
    )


def _response_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return response.text.strip()[:240]

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, dict):
            code = detail.get("code", "")
            message = detail.get("message", "")
            return f"{code}: {message}".strip(": ")
        if detail:
            return str(detail)
    return json.dumps(payload, ensure_ascii=False)[:240]


def _pick_template_id(
    items: list[dict[str, Any]],
    *,
    fixed_id: str,
    randomize: bool,
    rng: random.Random,
) -> str:
    if fixed_id:
        return fixed_id
    if not items:
        raise RuntimeError("模板列表为空，无法创建任务。")
    if randomize:
        return rng.choice(items)["id"]
    return items[0]["id"]


async def _request_json(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    expected_status: int,
    metric_name: str,
    **kwargs: Any,
) -> tuple[dict[str, Any], StepMetric]:
    started_at = time.perf_counter()
    response = await client.request(method, path, **kwargs)
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    metric = StepMetric(
        name=metric_name,
        elapsed_ms=elapsed_ms,
        ok=response.status_code == expected_status,
        status_code=response.status_code,
    )
    if response.status_code != expected_status:
        raise RuntimeError(
            f"{metric_name} 失败，HTTP {response.status_code}: {_response_detail(response)}"
        )
    return response.json(), metric


async def _poll_job(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    job_id: str,
    poll_interval: float,
    timeout_seconds: float,
) -> tuple[dict[str, Any], StepMetric, float | None]:
    started_at = time.perf_counter()
    preview_elapsed_ms: float | None = None

    while True:
        payload, metric = await _request_json(
            client,
            "GET",
            f"/api/jobs/{job_id}",
            expected_status=200,
            metric_name="poll_job",
            headers=headers,
        )
        if payload["status"] == "preview_ready" and preview_elapsed_ms is None:
            preview_elapsed_ms = (time.perf_counter() - started_at) * 1000
        if payload["status"] in {"succeeded", "failed"}:
            final_metric = StepMetric(
                name="poll_until_final",
                elapsed_ms=(time.perf_counter() - started_at) * 1000,
                ok=payload["status"] == "succeeded",
                status_code=metric.status_code,
            )
            return payload, final_metric, preview_elapsed_ms

        if time.perf_counter() - started_at > timeout_seconds:
            raise TimeoutError(f"任务 {job_id} 在 {timeout_seconds:.0f}s 内未完成。")

        await asyncio.sleep(poll_interval)


async def _run_job(
    client: httpx.AsyncClient,
    *,
    user_code: str,
    job_index: int,
    token: str,
    image_name: str,
    image_bytes: bytes,
    mime_type: str,
    hairstyles: list[dict[str, Any]],
    scenes: list[dict[str, Any]],
    hairstyle_id: str,
    scene_id: str,
    random_templates: bool,
    poll_interval: float,
    job_timeout: float,
) -> JobRunResult:
    rng = random.Random(f"{user_code}:{job_index}")
    headers = {"Authorization": f"Bearer {token}"}
    result = JobRunResult(user_code=user_code, job_index=job_index, success=False)

    try:
        upload_payload, upload_metric = await _request_json(
            client,
            "POST",
            "/api/uploads",
            expected_status=200,
            metric_name="upload",
            headers=headers,
            files={"file": (image_name, image_bytes, mime_type)},
        )
        result.steps.append(upload_metric)

        chosen_hairstyle_id = _pick_template_id(
            hairstyles,
            fixed_id=hairstyle_id,
            randomize=random_templates,
            rng=rng,
        )
        chosen_scene_id = _pick_template_id(
            scenes,
            fixed_id=scene_id,
            randomize=random_templates,
            rng=rng,
        )

        job_payload, create_metric = await _request_json(
            client,
            "POST",
            "/api/jobs",
            expected_status=201,
            metric_name="create_job",
            headers=headers,
            json={
                "upload_id": upload_payload["upload_id"],
                "hairstyle_id": chosen_hairstyle_id,
                "scene_id": chosen_scene_id,
            },
        )
        result.steps.append(create_metric)

        final_payload, final_metric, preview_elapsed_ms = await _poll_job(
            client,
            headers,
            job_id=job_payload["job_id"],
            poll_interval=poll_interval,
            timeout_seconds=job_timeout,
        )
        result.steps.append(final_metric)
        result.preview_elapsed_ms = preview_elapsed_ms
        result.complete_elapsed_ms = final_metric.elapsed_ms
        result.final_status = final_payload["status"]
        result.error_code = final_payload.get("error_code")
        result.error_message = final_payload.get("error_message")
        result.success = final_payload["status"] == "succeeded"
        return result
    except Exception as exc:
        result.exception = str(exc)
        return result


async def _run_user(
    client: httpx.AsyncClient,
    *,
    user_index: int,
    jobs_per_user: int,
    image_name: str,
    image_bytes: bytes,
    mime_type: str,
    hairstyles: list[dict[str, Any]],
    scenes: list[dict[str, Any]],
    hairstyle_id: str,
    scene_id: str,
    random_templates: bool,
    poll_interval: float,
    job_timeout: float,
) -> list[JobRunResult]:
    user_code = f"dev-load-user-{user_index:04d}"
    login_payload, login_metric = await _request_json(
        client,
        "POST",
        "/api/auth/wechat/login",
        expected_status=200,
        metric_name="login",
        json={"code": user_code},
    )
    token = login_payload["token"]

    results: list[JobRunResult] = []
    for job_index in range(1, jobs_per_user + 1):
        job_result = await _run_job(
            client,
            user_code=user_code,
            job_index=job_index,
            token=token,
            image_name=image_name,
            image_bytes=image_bytes,
            mime_type=mime_type,
            hairstyles=hairstyles,
            scenes=scenes,
            hairstyle_id=hairstyle_id,
            scene_id=scene_id,
            random_templates=random_templates,
            poll_interval=poll_interval,
            job_timeout=job_timeout,
        )
        if job_index == 1:
            job_result.steps.insert(0, login_metric)
        results.append(job_result)
    return results


def _print_summary(results: list[JobRunResult], total_elapsed_ms: float) -> None:
    succeeded = [item for item in results if item.success]
    failed = [item for item in results if not item.success]
    final_statuses = Counter(item.final_status or "exception" for item in results)
    error_codes = Counter(
        (item.error_code or item.exception or "unknown")
        for item in failed
    )

    step_map: dict[str, list[float]] = defaultdict(list)
    for item in results:
        for step in item.steps:
            step_map[step.name].append(step.elapsed_ms)

    preview_values = [item.preview_elapsed_ms for item in results if item.preview_elapsed_ms is not None]
    complete_values = [item.complete_elapsed_ms for item in results if item.complete_elapsed_ms is not None]

    print("压测完成")
    print(f"总任务数: {len(results)}")
    print(f"成功任务: {len(succeeded)}")
    print(f"失败任务: {len(failed)}")
    print(f"总耗时: {total_elapsed_ms / 1000:.2f}s")
    print(f"整体吞吐: {len(results) / max(total_elapsed_ms / 1000, 0.001):.2f} job/s")
    print()

    print("步骤耗时")
    for step_name in ("login", "upload", "create_job", "poll_until_final"):
        print(f"- {step_name}: {_format_ms(step_map.get(step_name, []))}")
    print(f"- preview_ready: {_format_seconds(preview_values)}")
    print(f"- completed: {_format_seconds(complete_values)}")
    print()

    print("最终状态分布")
    for status_name, count in sorted(final_statuses.items()):
        print(f"- {status_name}: {count}")
    print()

    if error_codes:
        print("失败原因分布")
        for error_name, count in error_codes.most_common():
            print(f"- {error_name}: {count}")
        print()

    if failed:
        print("失败样例")
        for item in failed[:5]:
            detail = item.error_code or item.exception or item.error_message or "unknown"
            print(f"- {item.user_code} job#{item.job_index}: {detail}")


async def _main() -> int:
    args = _parse_args()
    image_path = Path(args.image).expanduser().resolve()
    if not image_path.exists():
        print(f"图片不存在: {image_path}", file=sys.stderr)
        return 2

    image_bytes = image_path.read_bytes()
    mime_type = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
    timeout = httpx.Timeout(args.request_timeout, connect=args.request_timeout)
    host = args.host.rstrip("/")

    async with httpx.AsyncClient(base_url=host, timeout=timeout) as client:
        template_payload, template_metric = await _request_json(
            client,
            "GET",
            "/api/templates",
            expected_status=200,
            metric_name="templates",
        )
        hairstyles = template_payload.get("hairstyles", [])
        scenes = template_payload.get("scenes", [])

        started_at = time.perf_counter()
        batches = await asyncio.gather(
            *[
                _run_user(
                    client,
                    user_index=user_index,
                    jobs_per_user=args.jobs_per_user,
                    image_name=image_path.name,
                    image_bytes=image_bytes,
                    mime_type=mime_type,
                    hairstyles=hairstyles,
                    scenes=scenes,
                    hairstyle_id=args.hairstyle_id,
                    scene_id=args.scene_id,
                    random_templates=args.random_templates,
                    poll_interval=args.poll_interval,
                    job_timeout=args.job_timeout,
                )
                for user_index in range(1, args.users + 1)
            ]
        )
        total_elapsed_ms = (time.perf_counter() - started_at) * 1000

    results = [item for batch in batches for item in batch]
    if results:
        results[0].steps.insert(0, template_metric)
    _print_summary(results, total_elapsed_ms)
    return 0 if all(item.success for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
