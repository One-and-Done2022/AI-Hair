const { request } = require("./request");

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function doRequestPayment(payment) {
  return new Promise((resolve, reject) => {
    wx.requestPayment({
      ...payment,
      success: resolve,
      fail: (error) => {
        const message = (error && error.errMsg) || "";
        if (message.includes("cancel")) {
          reject({
            detail: {
              code: "payment_cancelled",
              message: "你已取消本次支付。"
            }
          });
          return;
        }
        reject(error);
      }
    });
  });
}

async function getPurchaseCatalog() {
  const payload = await request({
    url: "/api/purchase/catalog",
    withAuth: false
  });
  return payload.items || [];
}

async function getDefaultPurchaseItem() {
  const items = await getPurchaseCatalog();
  return items.find((item) => item.is_default) || items[0] || null;
}

async function getPurchaseOrder(orderId) {
  return request({
    url: `/api/purchase/orders/${orderId}`
  });
}

async function waitForPurchaseOrderConfirmed(orderId, options = {}) {
  const maxAttempts = options.maxAttempts || 12;
  const intervalMs = options.intervalMs || 1200;
  for (let index = 0; index < maxAttempts; index += 1) {
    const order = await getPurchaseOrder(orderId);
    if (order && order.status === "confirmed") {
      return order;
    }
    if (index < maxAttempts - 1) {
      await sleep(intervalMs);
    }
  }
  throw {
    detail: {
      code: "payment_confirm_timeout",
      message: "支付已发起成功，到账确认稍有延迟，请稍后刷新额度。"
    }
  };
}

async function quickPurchaseDefaultGenerationPack(productId = "") {
  const purchaseItem = productId
    ? { product_id: productId }
    : await getDefaultPurchaseItem();
  const selectedProductId = purchaseItem && purchaseItem.product_id;
  if (!selectedProductId) {
    throw new Error("当前没有可用的购买商品");
  }

  const order = await request({
    url: "/api/purchase/orders",
    method: "POST",
    data: {
      product_id: selectedProductId
    }
  });

  const paymentPreparation = await request({
    url: `/api/purchase/orders/${order.order_id}/pay`,
    method: "POST"
  });

  await doRequestPayment(paymentPreparation.payment);
  const confirmedOrder = await waitForPurchaseOrderConfirmed(order.order_id);
  return {
    item: purchaseItem.product_id ? purchaseItem : null,
    order: confirmedOrder
  };
}

module.exports = {
  getPurchaseCatalog,
  getDefaultPurchaseItem,
  getPurchaseOrder,
  quickPurchaseDefaultGenerationPack,
  waitForPurchaseOrderConfirmed
};
