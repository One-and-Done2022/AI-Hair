from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

from app.config import get_settings
from app.dependencies import get_current_user
from app.schemas import (
    PurchaseCatalogItem,
    PurchaseCatalogResponse,
    PurchasePaymentPrepareResponse,
    PurchaseOrderCreateRequest,
    PurchaseOrderResponse,
)
from app.services import billing, payment_provider, repository, wechat_pay, xunhu_pay


router = APIRouter(prefix="/purchase", tags=["purchase"])
public_router = APIRouter(tags=["purchase"])


def _format_amount_label(amount_cents: int) -> str:
    if amount_cents % 100 == 0:
        return f"{amount_cents // 100} 元"
    return f"{amount_cents / 100:.2f} 元"


def _parse_order_payment_payload(order: dict) -> dict[str, Any]:
    raw_payload = order.get("payment_payload")
    if isinstance(raw_payload, dict):
        return dict(raw_payload)
    if not raw_payload:
        return {}
    try:
        parsed = json.loads(raw_payload)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _build_payment_session(order_id: str, payment: dict[str, Any]) -> dict[str, Any]:
    session = dict(payment)
    if session.get("payment_mode") == "qrcode" and session.get("qrcode_url"):
        session["qrcode_download_url"] = f"/api/purchase/orders/{order_id}/qrcode"
    return session


def _extract_existing_payment_session(order: dict) -> dict[str, Any] | None:
    payload = _parse_order_payment_payload(order)
    if payload.get("payment_mode"):
        return _build_payment_session(str(order["id"]), payload)
    return None


def _derive_payment_mode(order: dict) -> str | None:
    payload = _parse_order_payment_payload(order)
    if payload.get("payment_mode"):
        return str(payload["payment_mode"])
    if order.get("wechat_prepay_id"):
        return "jsapi"
    return None


def _derive_payment_status_hint(order: dict, payment_mode: str | None) -> str | None:
    if order.get("status") == repository.PURCHASE_ORDER_CONFIRMED:
        return "paid"
    if payment_mode == "qrcode":
        return "scan_to_pay"
    if payment_mode == "jsapi":
        return "request_payment"
    return None


def _order_response(order: dict) -> PurchaseOrderResponse:
    payment_mode = _derive_payment_mode(order)
    return PurchaseOrderResponse(
        order_id=order["id"],
        product_id=order["product_id"],
        product_name=order["product_name"],
        quantity=int(order["quantity"] or 0),
        unit_price_cents=int(order["unit_price_cents"] or 0),
        amount_cents=int(order["amount_cents"] or 0),
        amount_label=_format_amount_label(int(order["amount_cents"] or 0)),
        status=order["status"],
        payment_provider=str(order.get("payment_provider") or "").strip() or None,
        payment_mode=payment_mode,
        payment_status_hint=_derive_payment_status_hint(order, payment_mode),
        provider_order_id=str(order.get("provider_order_id") or "").strip() or None,
        provider_transaction_id=(
            str(order.get("provider_transaction_id") or "").strip() or None
        ),
        wechat_prepay_id=order.get("wechat_prepay_id"),
        wechat_transaction_id=order.get("wechat_transaction_id"),
        created_at=order["created_at"],
        updated_at=order["updated_at"],
        confirmed_at=order.get("confirmed_at"),
    )


def _payment_disabled_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "code": "payment_disabled",
            "message": "当前支付入口暂未开放。",
        },
    )


def _ensure_payment_enabled() -> None:
    if not get_settings().payment_enabled:
        raise _payment_disabled_error()


def _payment_status_page(*, title: str, description: str) -> HTMLResponse:
    html = f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f4f7fb;
        --card: rgba(255, 255, 255, 0.92);
        --text: #14213d;
        --muted: #61708a;
        --line: rgba(20, 33, 61, 0.12);
        --accent: #0058ba;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 24px;
        font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
        color: var(--text);
        background:
          radial-gradient(circle at top right, rgba(0, 88, 186, 0.12), transparent 28%),
          radial-gradient(circle at bottom left, rgba(80, 145, 255, 0.14), transparent 26%),
          linear-gradient(180deg, #f8fbff 0%, var(--bg) 100%);
      }}
      .card {{
        width: min(560px, 100%);
        padding: 28px 24px;
        border-radius: 28px;
        background: var(--card);
        border: 1px solid var(--line);
        box-shadow: 0 18px 46px rgba(0, 88, 186, 0.08);
      }}
      .eyebrow {{
        margin: 0 0 12px;
        color: var(--accent);
        font-size: 12px;
        letter-spacing: 0.16em;
        text-transform: uppercase;
      }}
      h1 {{
        margin: 0 0 12px;
        font-size: 28px;
        line-height: 1.2;
      }}
      p {{
        margin: 0;
        line-height: 1.75;
        color: var(--muted);
      }}
      .tips {{
        margin-top: 18px;
        padding: 16px 18px;
        border-radius: 18px;
        background: rgba(0, 88, 186, 0.06);
        color: var(--text);
      }}
      .tips strong {{
        display: block;
        margin-bottom: 8px;
      }}
    </style>
  </head>
  <body>
    <main class="card">
      <p class="eyebrow">AIFace Payment</p>
      <h1>{title}</h1>
      <p>{description}</p>
      <section class="tips">
        <strong>接下来怎么做</strong>
        <p>请返回微信小程序，回到支付页点击“我已支付，刷新状态”，或进入“我的”页查看剩余次数是否已增加。</p>
      </section>
    </main>
  </body>
</html>
"""
    return HTMLResponse(content=html)


@public_router.get("/payment/success", include_in_schema=False)
def payment_success_page() -> HTMLResponse:
    return _payment_status_page(
        title="支付已完成",
        description="如果你已经完成付款，这个页面只是支付回跳提示页，不需要继续操作网页端。",
    )


@public_router.get("/payment/retry", include_in_schema=False)
def payment_retry_page() -> HTMLResponse:
    return _payment_status_page(
        title="支付处理中",
        description="如果网页没有自动返回，请直接回到微信小程序继续确认支付状态。",
    )


@router.get("/catalog", response_model=PurchaseCatalogResponse)
def get_catalog() -> PurchaseCatalogResponse:
    settings = get_settings()
    payment_mode = "qrcode" if settings.payment_provider == "xunhu" else "jsapi"
    return PurchaseCatalogResponse(
        items=(
            [PurchaseCatalogItem(**item) for item in billing.list_products()]
            if settings.payment_enabled
            else []
        ),
        payment_enabled=settings.payment_enabled,
        default_provider=settings.payment_provider,
        default_payment_mode=payment_mode,
    )


@router.post("/orders", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: PurchaseOrderCreateRequest,
    current_user: dict = Depends(get_current_user),
) -> PurchaseOrderResponse:
    _ensure_payment_enabled()
    try:
        order = billing.create_order_for_product(
            user_id=current_user["id"],
            product_id=payload.product_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_purchase_product",
                "message": "当前商品不可购买，请刷新后重试。",
            },
        ) from exc
    return _order_response(order)


@router.get("/orders/{order_id}", response_model=PurchaseOrderResponse)
def get_order(
    order_id: str,
    current_user: dict = Depends(get_current_user),
) -> PurchaseOrderResponse:
    order = repository.get_purchase_order_for_user(order_id, current_user["id"])
    if order is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "purchase_order_not_found",
                "message": "订单不存在，请重新发起购买。",
            },
        )
    return _order_response(order)


@router.post("/orders/{order_id}/pay", response_model=PurchasePaymentPrepareResponse)
def prepare_order_payment(
    order_id: str,
    current_user: dict = Depends(get_current_user),
) -> PurchasePaymentPrepareResponse:
    _ensure_payment_enabled()
    order = repository.get_purchase_order_for_user(order_id, current_user["id"])
    if order is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "purchase_order_not_found",
                "message": "订单不存在，请重新发起购买。",
            },
        )
    if order["status"] == repository.PURCHASE_ORDER_CONFIRMED:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "purchase_order_already_paid",
                "message": "该订单已支付成功，无需重复支付。",
            },
        )

    existing_payment = _extract_existing_payment_session(order)
    if order["status"] == repository.PURCHASE_ORDER_PAYMENT_PREPARED and existing_payment:
        return PurchasePaymentPrepareResponse(
            order=_order_response(order),
            payment=existing_payment,
        )

    try:
        prepared = payment_provider.prepare_payment(
            order=order,
            openid=str(current_user.get("openid") or "").strip(),
        )
    except payment_provider.PaymentProviderConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "payment_provider_unavailable",
                "message": str(exc),
            },
        ) from exc
    except payment_provider.PaymentProviderRequestError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "payment_prepare_failed",
                "message": str(exc),
            },
        ) from exc

    refreshed_order = repository.mark_purchase_order_payment_prepared(
        order_id,
        payment_provider=prepared["provider"],
        provider_order_id=prepared.get("provider_order_id"),
        provider_transaction_id=prepared.get("provider_transaction_id"),
        wechat_prepay_id=(
            prepared.get("provider_order_id")
            if prepared["provider"] == "wechat_pay"
            else None
        ),
        payment_payload=prepared["payment"],
    )
    if refreshed_order is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "purchase_order_not_found",
                "message": "订单不存在，请重新发起购买。",
            },
        )
    return PurchasePaymentPrepareResponse(
        order=_order_response(refreshed_order),
        payment=_build_payment_session(order_id, prepared["payment"]),
    )


@router.get("/orders/{order_id}/qrcode")
def download_order_qrcode(
    order_id: str,
    current_user: dict = Depends(get_current_user),
) -> Response:
    order = repository.get_purchase_order_for_user(order_id, current_user["id"])
    if order is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "purchase_order_not_found",
                "message": "订单不存在，请重新发起购买。",
            },
        )
    payment_session = _extract_existing_payment_session(order)
    qrcode_url = str((payment_session or {}).get("qrcode_url") or "").strip()
    if not qrcode_url:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "payment_qrcode_unavailable",
                "message": "当前订单还没有可用二维码，请重新发起支付。",
            },
        )
    try:
        response = httpx.get(
            qrcode_url,
            timeout=get_settings().xunhu_pay_timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "payment_qrcode_unavailable",
                "message": f"二维码拉取失败：{exc}",
            },
        ) from exc
    media_type = response.headers.get("content-type", "image/png")
    return Response(content=response.content, media_type=media_type)


@router.post("/orders/{order_id}/confirm", response_model=PurchaseOrderResponse)
def confirm_order(
    order_id: str,
    current_user: dict = Depends(get_current_user),
) -> PurchaseOrderResponse:
    settings = get_settings()
    if not settings.allow_dev_login:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "purchase_manual_confirm_disabled",
                "message": "生产环境不允许手动确认订单。",
            },
        )
    order = billing.confirm_order(user_id=current_user["id"], order_id=order_id)
    if order is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "purchase_order_not_found",
                "message": "订单不存在，请重新发起购买。",
            },
        )
    return _order_response(order)


@router.post("/wechat/notify")
async def wechat_notify(request: Request) -> JSONResponse:
    body = await request.body()
    try:
        parsed = wechat_pay.parse_payment_notification(
            headers={key: value for key, value in request.headers.items()},
            body=body,
        )
        resource = parsed["resource"]
        order_id = str(resource.get("out_trade_no") or "").strip()
        transaction_id = str(resource.get("transaction_id") or "").strip()
        trade_state = str(resource.get("trade_state") or "").strip()
        amount_payload = resource.get("amount") or {}
        paid_amount_cents = int(
            amount_payload.get("payer_total") or amount_payload.get("total") or 0
        )
        order = repository.get_purchase_order(order_id)
        if order is None:
            raise wechat_pay.WechatPayNotificationError("订单不存在。")
        expected_amount_cents = int(order.get("amount_cents") or 0)
        if paid_amount_cents != expected_amount_cents:
            raise wechat_pay.WechatPayNotificationError("支付金额与订单金额不一致。")
        if trade_state == "SUCCESS":
            repository.finalize_purchase_order_payment(
                order_id,
                provider_transaction_id=transaction_id,
                wechat_transaction_id=transaction_id,
                payment_payload=resource,
            )
    except wechat_pay.WechatPayNotificationError as exc:
        return JSONResponse(
            status_code=500,
            content={"code": "FAIL", "message": str(exc)},
        )
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"code": "FAIL", "message": "处理支付回调失败"},
        )

    return JSONResponse(
        status_code=200,
        content={"code": "SUCCESS", "message": "成功"},
    )


@router.post("/xunhu/notify")
async def xunhu_notify(request: Request) -> PlainTextResponse:
    form = await request.form()
    try:
        parsed = xunhu_pay.parse_payment_notification(
            {key: value for key, value in form.items()}
        )
        order_id = str(parsed.get("trade_order_id") or "").strip()
        order = repository.get_purchase_order(order_id)
        if order is None:
            raise xunhu_pay.XunhuPayNotificationError("订单不存在。")
        expected_amount_cents = int(order.get("amount_cents") or 0)
        paid_amount_cents = xunhu_pay.parse_amount_cents(
            str(parsed.get("total_fee") or "")
        )
        if expected_amount_cents != paid_amount_cents:
            raise xunhu_pay.XunhuPayNotificationError("支付金额与订单金额不一致。")
        if str(parsed.get("status") or "").strip() == "OD":
            repository.finalize_purchase_order_payment(
                order_id,
                provider_order_id=str(parsed.get("open_order_id") or "").strip() or None,
                provider_transaction_id=(
                    str(parsed.get("transaction_id") or "").strip() or None
                ),
                payment_payload=parsed,
            )
    except xunhu_pay.XunhuPayNotificationError:
        return PlainTextResponse("fail", status_code=400)
    except Exception:
        return PlainTextResponse("fail", status_code=500)
    return PlainTextResponse("success")
