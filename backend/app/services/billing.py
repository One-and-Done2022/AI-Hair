from __future__ import annotations

from app.services import payment_provider, repository

DEFAULT_PRODUCT_ID = "single-generation-pack"

PRODUCT_CATALOG = (
    {
        "product_id": DEFAULT_PRODUCT_ID,
        "name": "1 次完整生成",
        "description": "本次生成会返回 1 张换发预览 + 2 张场景成片。",
        "price_cents": 100,
        "price_label": "1 元 / 次",
        "generation_count": 1,
        "is_default": True,
    },
)


def list_products() -> list[dict]:
    return [dict(item) for item in PRODUCT_CATALOG]


def get_product(product_id: str) -> dict | None:
    normalized = (product_id or "").strip()
    if not normalized:
        normalized = DEFAULT_PRODUCT_ID
    for item in PRODUCT_CATALOG:
        if item["product_id"] == normalized:
            return dict(item)
    return None


def create_order_for_product(*, user_id: int, product_id: str) -> dict:
    product = get_product(product_id)
    if product is None:
        raise ValueError("Unsupported purchase product.")
    return repository.create_purchase_order(
        user_id=user_id,
        product_id=product["product_id"],
        product_name=product["name"],
        quantity=product["generation_count"],
        unit_price_cents=product["price_cents"],
        payment_provider=payment_provider.current_provider(),
    )


def confirm_order(*, user_id: int, order_id: str) -> dict | None:
    return repository.confirm_purchase_order_for_user(order_id, user_id)
