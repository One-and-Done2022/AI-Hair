from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.dependencies import get_current_user
from app.schemas import (
    PurchaseCatalogItem,
    PurchaseCatalogResponse,
    PurchasePaymentPrepareResponse,
    PurchaseOrderCreateRequest,
    PurchaseOrderResponse,
)
from app.services import billing, repository, wechat_pay


router = APIRouter(prefix="/purchase", tags=["purchase"])


def _format_amount_label(amount_cents: int) -> str:
    if amount_cents % 100 == 0:
        return f"{amount_cents // 100} 元"
    return f"{amount_cents / 100:.2f} 元"


def _order_response(order: dict) -> PurchaseOrderResponse:
    return PurchaseOrderResponse(
        order_id=order["id"],
        product_id=order["product_id"],
        product_name=order["product_name"],
        quantity=int(order["quantity"] or 0),
        unit_price_cents=int(order["unit_price_cents"] or 0),
        amount_cents=int(order["amount_cents"] or 0),
        amount_label=_format_amount_label(int(order["amount_cents"] or 0)),
        status=order["status"],
        wechat_prepay_id=order.get("wechat_prepay_id"),
        wechat_transaction_id=order.get("wechat_transaction_id"),
        created_at=order["created_at"],
        updated_at=order["updated_at"],
        confirmed_at=order.get("confirmed_at"),
    )


@router.get("/catalog", response_model=PurchaseCatalogResponse)
def get_catalog() -> PurchaseCatalogResponse:
    return PurchaseCatalogResponse(
        items=[PurchaseCatalogItem(**item) for item in billing.list_products()]
    )


@router.post("/orders", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: PurchaseOrderCreateRequest,
    current_user: dict = Depends(get_current_user),
) -> PurchaseOrderResponse:
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
    try:
        prepared = wechat_pay.prepare_jsapi_payment(
            order=order,
            openid=str(current_user.get("openid") or "").strip(),
        )
    except wechat_pay.WechatPayConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "wechat_pay_not_configured",
                "message": str(exc),
            },
        ) from exc
    except wechat_pay.WechatPayRequestError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "wechat_pay_prepare_failed",
                "message": str(exc),
            },
        ) from exc
    refreshed_order = repository.mark_purchase_order_payment_prepared(
        order_id,
        wechat_prepay_id=prepared["prepay_id"],
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
        payment=prepared["payment"],
    )


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
        paid_amount_cents = int(amount_payload.get("payer_total") or amount_payload.get("total") or 0)
        order = repository.get_purchase_order(order_id)
        if order is None:
            raise wechat_pay.WechatPayNotificationError("订单不存在。")
        expected_amount_cents = int(order.get("amount_cents") or 0)
        if paid_amount_cents != expected_amount_cents:
            raise wechat_pay.WechatPayNotificationError("支付金额与订单金额不一致。")
        if trade_state == "SUCCESS":
            repository.finalize_purchase_order_payment(
                order_id,
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
