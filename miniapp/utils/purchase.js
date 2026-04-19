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
  return request({
    url: "/api/purchase/catalog",
    withAuth: false
  });
}

async function getDefaultPurchaseItem() {
  const payload = await getPurchaseCatalog();
  const items = payload.items || [];
  if (!payload.payment_enabled) {
    return null;
  }
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

function openQrPaymentPage(paymentPreparation) {
  const orderId = paymentPreparation && paymentPreparation.order
    ? paymentPreparation.order.order_id
    : "";
  return new Promise((resolve, reject) => {
    wx.navigateTo({
      url: `/pages/payment/index?orderId=${encodeURIComponent(orderId)}`,
      events: {
        purchaseConfirmed(payload) {
          resolve(payload);
        },
        purchaseCancelled(error) {
          reject(error || {
            detail: {
              code: "payment_cancelled",
              message: "你已取消本次支付。"
            }
          });
        }
      },
      success(res) {
        res.eventChannel.emit("paymentSession", paymentPreparation);
      },
      fail(error) {
        reject(error);
      }
    });
  });
}

async function quickPurchaseDefaultGenerationPack(productId = "") {
  const purchaseItem = productId
    ? { product_id: productId }
    : await getDefaultPurchaseItem();
  const selectedProductId = purchaseItem && purchaseItem.product_id;
  if (!selectedProductId) {
    throw {
      detail: {
        code: "payment_disabled",
        message: "当前支付暂未开放。"
      }
    };
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

  const payment = paymentPreparation.payment || {};
  let confirmedOrder = null;
  if (payment.payment_mode === "jsapi" && payment.jsapi) {
    await doRequestPayment(payment.jsapi);
    confirmedOrder = await waitForPurchaseOrderConfirmed(order.order_id);
  } else if (payment.payment_mode === "qrcode") {
    const pagePayload = await openQrPaymentPage(paymentPreparation);
    confirmedOrder = (pagePayload && pagePayload.order) || pagePayload;
  } else {
    throw {
      detail: {
        code: "payment_prepare_failed",
        message: "当前支付通道返回了不支持的支付方式。"
      }
    };
  }

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
