from __future__ import annotations

import base64
import json
import secrets
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings


JSAPI_PAY_ENDPOINT = "/v3/pay/transactions/jsapi"


class WechatPayConfigurationError(Exception):
    pass


class WechatPayRequestError(Exception):
    pass


class WechatPayNotificationError(Exception):
    pass


def _load_text(path: Path) -> bytes:
    if not path or not str(path).strip():
        raise WechatPayConfigurationError("缺少微信支付密钥文件路径。")
    if not path.exists():
        raise WechatPayConfigurationError(f"微信支付密钥文件不存在: {path}")
    return path.read_bytes()


@lru_cache
def _merchant_private_key():
    settings = get_settings()
    return serialization.load_pem_private_key(
        _load_text(settings.wechat_pay_private_key_path),
        password=None,
    )


@lru_cache
def _platform_public_key():
    settings = get_settings()
    if not settings.wechat_pay_notify_verification_enabled:
        raise WechatPayConfigurationError("缺少微信支付平台公钥配置。")
    return serialization.load_pem_public_key(
        _load_text(settings.wechat_pay_platform_public_key_path)
    )


def clear_key_caches() -> None:
    _merchant_private_key.cache_clear()
    _platform_public_key.cache_clear()


def ensure_wechat_pay_ready() -> None:
    settings = get_settings()
    if not settings.wechat_pay_enabled:
        raise WechatPayConfigurationError(
            "微信支付未配置完成，请补充商户号、商户私钥、证书序列号、APIv3 Key 和回调地址。"
        )
    _merchant_private_key()


def ensure_wechat_pay_notify_ready() -> None:
    ensure_wechat_pay_ready()
    settings = get_settings()
    if not settings.wechat_pay_notify_verification_enabled:
        raise WechatPayConfigurationError(
            "微信支付回调验签未配置完成，请补充平台公钥文件。"
        )
    _platform_public_key()


def _random_nonce(length: int = 24) -> str:
    return secrets.token_urlsafe(length)[:32]


def _sign_message(message: str) -> str:
    signature = _merchant_private_key().sign(
        message.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def _authorization_header(*, method: str, canonical_url: str, body: str) -> str:
    settings = get_settings()
    timestamp = str(int(time.time()))
    nonce_str = _random_nonce()
    message = f"{method}\n{canonical_url}\n{timestamp}\n{nonce_str}\n{body}\n"
    signature = _sign_message(message)
    return (
        'WECHATPAY2-SHA256-RSA2048 '
        f'mchid="{settings.wechat_pay_mch_id}",'
        f'nonce_str="{nonce_str}",'
        f'signature="{signature}",'
        f'timestamp="{timestamp}",'
        f'serial_no="{settings.wechat_pay_certificate_serial_no}"'
    )


def _parse_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        payload = None
    if isinstance(payload, dict):
        message = str(payload.get("message") or payload.get("detail") or "").strip()
        if message:
            return message
    return f"HTTP {response.status_code}"


def prepare_jsapi_payment(*, order: dict, openid: str) -> dict[str, Any]:
    ensure_wechat_pay_ready()
    settings = get_settings()
    payload = {
        "appid": settings.wechat_app_id,
        "mchid": settings.wechat_pay_mch_id,
        "description": order["product_name"],
        "out_trade_no": order["id"],
        "notify_url": settings.wechat_pay_notify_url,
        "amount": {
            "total": int(order["amount_cents"]),
            "currency": "CNY",
        },
        "payer": {
            "openid": openid,
        },
    }
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": _authorization_header(
            method="POST",
            canonical_url=JSAPI_PAY_ENDPOINT,
            body=body,
        ),
    }
    response = httpx.post(
        f"{settings.wechat_pay_base_url}{JSAPI_PAY_ENDPOINT}",
        content=body.encode("utf-8"),
        headers=headers,
        timeout=settings.wechat_pay_timeout_seconds,
    )
    if response.status_code not in {200, 201}:
        raise WechatPayRequestError(
            f"微信下单失败：{_parse_error_message(response)}"
        )
    data = response.json()
    prepay_id = str(data.get("prepay_id") or "").strip()
    if not prepay_id:
        raise WechatPayRequestError("微信下单失败：未返回 prepay_id。")
    return {
        "prepay_id": prepay_id,
        "payment": build_request_payment_params(prepay_id),
    }


def build_request_payment_params(prepay_id: str) -> dict[str, str]:
    settings = get_settings()
    timestamp = str(int(time.time()))
    nonce_str = _random_nonce()
    package = f"prepay_id={prepay_id}"
    message = f"{settings.wechat_app_id}\n{timestamp}\n{nonce_str}\n{package}\n"
    return {
        "timeStamp": timestamp,
        "nonceStr": nonce_str,
        "package": package,
        "signType": "RSA",
        "paySign": _sign_message(message),
    }


def _verify_notification_signature(
    *,
    headers: dict[str, str],
    body: bytes,
) -> None:
    ensure_wechat_pay_notify_ready()
    normalized_headers = {str(key).lower(): value for key, value in headers.items()}
    serial = str(normalized_headers.get("wechatpay-serial") or "").strip()
    signature = str(normalized_headers.get("wechatpay-signature") or "").strip()
    timestamp = str(normalized_headers.get("wechatpay-timestamp") or "").strip()
    nonce = str(normalized_headers.get("wechatpay-nonce") or "").strip()

    if not serial or not signature or not timestamp or not nonce:
        raise WechatPayNotificationError("缺少微信支付回调签名头。")

    settings = get_settings()
    expected_serial = settings.wechat_pay_platform_serial.strip()
    if expected_serial and serial != expected_serial:
        raise WechatPayNotificationError("微信支付回调平台序列号不匹配。")

    message = f"{timestamp}\n{nonce}\n{body.decode('utf-8')}\n"
    try:
        _platform_public_key().verify(
            base64.b64decode(signature),
            message.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except InvalidSignature as exc:
        raise WechatPayNotificationError("微信支付回调验签失败。") from exc


def _decrypt_notification_resource(resource: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    nonce = str(resource.get("nonce") or "").encode("utf-8")
    associated_data = str(resource.get("associated_data") or "").encode("utf-8")
    ciphertext = str(resource.get("ciphertext") or "").strip()
    if not nonce or not ciphertext:
        raise WechatPayNotificationError("微信支付回调缺少加密资源。")
    plaintext = AESGCM(settings.wechat_pay_api_v3_key.encode("utf-8")).decrypt(
        nonce,
        base64.b64decode(ciphertext),
        associated_data,
    )
    try:
        return json.loads(plaintext.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise WechatPayNotificationError("微信支付回调解密后不是有效 JSON。") from exc


def parse_payment_notification(*, headers: dict[str, str], body: bytes) -> dict[str, Any]:
    _verify_notification_signature(headers=headers, body=body)
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise WechatPayNotificationError("微信支付回调体不是有效 JSON。") from exc
    resource = payload.get("resource")
    if not isinstance(resource, dict):
        raise WechatPayNotificationError("微信支付回调缺少 resource。")
    decrypted = _decrypt_notification_resource(resource)
    return {
        "notification": payload,
        "resource": decrypted,
    }
