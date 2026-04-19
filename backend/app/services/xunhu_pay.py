from __future__ import annotations

import hashlib
import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

import httpx

from app.config import get_settings


XUNHU_QRCODE_EXPIRES_SECONDS = 300


class XunhuPayConfigurationError(Exception):
    pass


class XunhuPayRequestError(Exception):
    pass


class XunhuPayNotificationError(Exception):
    pass


def ensure_xunhu_pay_ready() -> None:
    settings = get_settings()
    if not settings.xunhu_pay_enabled:
        raise XunhuPayConfigurationError(
            "虎皮椒支付参数未配置完成，请补充 AppID、API Key、支付网关与回调地址。"
        )


def _stringify_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value).strip()


def generate_xunhu_hash(data: Mapping[str, Any], api_key: str) -> str:
    parts: list[str] = []
    for key in sorted(data.keys()):
        if key == "hash":
            continue
        value = _stringify_value(data[key])
        if value == "":
            continue
        parts.append(f"{key}={value}")
    raw = "&".join(parts) + api_key
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _format_amount_yuan(amount_cents: int) -> str:
    amount = (Decimal(amount_cents) / Decimal("100")).quantize(Decimal("0.01"))
    normalized = format(amount, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def _sanitize_title(title: str) -> str:
    cleaned = str(title or "").replace("%", "").strip()
    if not cleaned:
        cleaned = "AI换发生成"
    return cleaned[:42]


def _current_expire_at() -> str:
    return (datetime.now(UTC) + timedelta(seconds=XUNHU_QRCODE_EXPIRES_SECONDS)).isoformat()


def _prepare_request_payload(order: Mapping[str, Any]) -> dict[str, str]:
    settings = get_settings()
    now_ts = int(time.time())
    payload: dict[str, str] = {
        "version": "1.1",
        "appid": settings.xunhu_pay_app_id,
        "trade_order_id": str(order["id"]),
        "total_fee": _format_amount_yuan(int(order.get("amount_cents") or 0)),
        "title": _sanitize_title(str(order.get("product_name") or "")),
        "time": str(now_ts),
        "notify_url": settings.xunhu_pay_notify_url,
        "nonce_str": secrets.token_hex(16),
    }
    if settings.xunhu_pay_return_url.strip():
        payload["return_url"] = settings.xunhu_pay_return_url.strip()
    if settings.xunhu_pay_callback_url.strip():
        payload["callback_url"] = settings.xunhu_pay_callback_url.strip()
    if settings.xunhu_pay_plugins.strip():
        payload["plugins"] = settings.xunhu_pay_plugins.strip()
    payload["attach"] = json.dumps(
        {
            "user_id": int(order.get("user_id") or 0),
            "product_id": str(order.get("product_id") or ""),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    payload["hash"] = generate_xunhu_hash(payload, settings.xunhu_pay_api_key)
    return payload


def _parse_json_response(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        raise XunhuPayRequestError("虎皮椒返回了无法解析的响应。") from exc
    if not isinstance(data, dict):
        raise XunhuPayRequestError("虎皮椒返回了非法响应。")
    return data


def _verify_provider_payload(payload: Mapping[str, Any]) -> None:
    settings = get_settings()
    received_hash = _stringify_value(payload.get("hash")).lower()
    if not received_hash:
        raise XunhuPayRequestError("虎皮椒响应缺少签名。")
    expected_hash = generate_xunhu_hash(payload, settings.xunhu_pay_api_key)
    if expected_hash.lower() != received_hash:
        raise XunhuPayRequestError("虎皮椒响应签名校验失败。")


def prepare_qrcode_payment(*, order: Mapping[str, Any]) -> dict[str, Any]:
    ensure_xunhu_pay_ready()
    settings = get_settings()
    payload = _prepare_request_payload(order)
    try:
        response = httpx.post(
            settings.xunhu_pay_gateway_url,
            data=payload,
            timeout=settings.xunhu_pay_timeout_seconds,
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        raise XunhuPayRequestError(f"虎皮椒下单请求失败：{exc}") from exc

    parsed = _parse_json_response(response)
    _verify_provider_payload(parsed)

    errcode = int(parsed.get("errcode") or 0)
    if errcode != 0:
        raise XunhuPayRequestError(
            str(parsed.get("errmsg") or "虎皮椒下单失败，请稍后再试。")
        )

    qrcode_url = _stringify_value(parsed.get("url_qrcode"))
    pay_url = _stringify_value(parsed.get("url"))
    if not qrcode_url and not pay_url:
        raise XunhuPayRequestError("虎皮椒下单成功，但未返回可用支付链接。")

    payment_session = {
        "provider": "xunhu",
        "payment_mode": "qrcode",
        "display_text": "请使用微信扫码或长按识别二维码完成支付",
        "pay_url": pay_url or None,
        "qrcode_url": qrcode_url or None,
        "expires_at": _current_expire_at(),
        "raw_response": dict(parsed),
    }
    return {
        "provider": "xunhu",
        "provider_order_id": _stringify_value(parsed.get("openid")) or None,
        "payment": payment_session,
    }


def parse_payment_notification(form_data: Mapping[str, Any]) -> dict[str, str]:
    ensure_xunhu_pay_ready()
    normalized = {
        str(key): _stringify_value(value)
        for key, value in form_data.items()
    }
    received_hash = normalized.get("hash", "").lower()
    if not received_hash:
        raise XunhuPayNotificationError("支付回调缺少签名。")

    expected_hash = generate_xunhu_hash(normalized, get_settings().xunhu_pay_api_key)
    if expected_hash.lower() != received_hash:
        raise XunhuPayNotificationError("支付回调签名校验失败。")

    order_id = normalized.get("trade_order_id", "").strip()
    if not order_id:
        raise XunhuPayNotificationError("支付回调缺少订单号。")

    if normalized.get("appid", "").strip() and (
        normalized.get("appid", "").strip() != get_settings().xunhu_pay_app_id
    ):
        raise XunhuPayNotificationError("支付回调渠道不匹配。")

    return normalized


def parse_amount_cents(total_fee: str) -> int:
    try:
        return int((Decimal(total_fee) * Decimal("100")).quantize(Decimal("1")))
    except (InvalidOperation, ValueError) as exc:
        raise XunhuPayNotificationError("支付回调金额格式无效。") from exc
