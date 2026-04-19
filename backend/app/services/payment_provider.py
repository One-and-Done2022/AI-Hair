from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.services import wechat_pay, xunhu_pay


class PaymentProviderConfigurationError(Exception):
    pass


class PaymentProviderRequestError(Exception):
    pass


def current_provider() -> str:
    return get_settings().payment_provider


def prepare_payment(*, order: dict, openid: str) -> dict[str, Any]:
    provider = current_provider()
    if provider == "wechat_pay":
        try:
            prepared = wechat_pay.prepare_jsapi_payment(order=order, openid=openid)
        except wechat_pay.WechatPayConfigurationError as exc:
            raise PaymentProviderConfigurationError(str(exc)) from exc
        except wechat_pay.WechatPayRequestError as exc:
            raise PaymentProviderRequestError(str(exc)) from exc
        return {
            "provider": provider,
            "provider_order_id": prepared["prepay_id"],
            "payment": {
                "provider": provider,
                "payment_mode": "jsapi",
                "display_text": "即将拉起微信支付",
                "jsapi": prepared["payment"],
            },
        }

    if provider == "xunhu":
        try:
            return xunhu_pay.prepare_qrcode_payment(order=order)
        except xunhu_pay.XunhuPayConfigurationError as exc:
            raise PaymentProviderConfigurationError(str(exc)) from exc
        except xunhu_pay.XunhuPayRequestError as exc:
            raise PaymentProviderRequestError(str(exc)) from exc

    raise PaymentProviderConfigurationError("当前未配置可用支付通道。")
