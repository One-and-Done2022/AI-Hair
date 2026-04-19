const { showError } = require("../../utils/errors");
const { downloadFile, request } = require("../../utils/request");

function parseIsoTime(value) {
  if (!value) {
    return null;
  }
  const timestamp = Date.parse(String(value).replace(/\+00:00$/, "Z"));
  return Number.isNaN(timestamp) ? null : timestamp;
}

function formatExpireAt(value) {
  const timestamp = parseIsoTime(value);
  if (!timestamp) {
    return "";
  }
  const date = new Date(timestamp);
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}:${String(
    date.getSeconds()
  ).padStart(2, "0")}`;
}

Page({
  data: {
    loading: true,
    order: null,
    payment: null,
    qrcodeTempFile: "",
    qrcodeReady: false,
    qrcodeLoading: false,
    secondsRemaining: 0,
    expiresAtLabel: "",
    expired: false,
    refreshing: false,
    statusText: "正在准备支付信息"
  },

  onLoad() {
    this.completed = false;
    this.eventChannel = this.getOpenerEventChannel();
    if (this.eventChannel) {
      this.eventChannel.on("paymentSession", (payload) => {
        this.bootstrapSession(payload);
      });
    }
  },

  onUnload() {
    this.clearTimers();
    if (!this.completed) {
      this.emitCancellation();
    }
  },

  clearTimers() {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
    if (this.countdownTimer) {
      clearInterval(this.countdownTimer);
      this.countdownTimer = null;
    }
  },

  emitCancellation() {
    if (this.completed) {
      return;
    }
    this.completed = true;
    if (this.eventChannel) {
      this.eventChannel.emit("purchaseCancelled", {
        detail: {
          code: "payment_cancelled",
          message: "你已取消本次支付。"
        }
      });
    }
  },

  emitSuccess(order) {
    if (this.completed) {
      return;
    }
    this.completed = true;
    this.clearTimers();
    if (this.eventChannel) {
      this.eventChannel.emit("purchaseConfirmed", { order });
    }
    wx.showToast({
      title: "支付成功",
      icon: "success"
    });
    setTimeout(() => {
      wx.navigateBack();
    }, 500);
  },

  async bootstrapSession(payload) {
    const order = payload && payload.order ? payload.order : null;
    const payment = payload && payload.payment ? payload.payment : null;
    if (!order || !payment) {
      this.setData({
        loading: false,
        statusText: "支付信息加载失败"
      });
      return;
    }
    this.setData({
      loading: false,
      order,
      payment,
      expiresAtLabel: formatExpireAt(payment.expires_at),
      statusText: payment.display_text || "请扫码完成支付"
    });
    this.updateCountdown();
    this.startCountdown();
    if (payment.qrcode_download_url) {
      await this.loadQrcodeFile(payment.qrcode_download_url);
    }
    this.startPolling();
  },

  async loadQrcodeFile(downloadUrl) {
    this.setData({ qrcodeLoading: true });
    try {
      const response = await downloadFile({
        url: downloadUrl,
        withAuth: true,
        timeout: 15000
      });
      this.setData({
        qrcodeTempFile: response.tempFilePath,
        qrcodeReady: true
      });
    } catch (error) {
      this.setData({ qrcodeReady: false });
      showError(error, {
        fallback: "二维码加载失败，请稍后重试",
        preferModal: true
      });
    } finally {
      this.setData({ qrcodeLoading: false });
    }
  },

  startCountdown() {
    if (this.countdownTimer) {
      clearInterval(this.countdownTimer);
    }
    this.countdownTimer = setInterval(() => {
      this.updateCountdown();
    }, 1000);
  },

  updateCountdown() {
    const payment = this.data.payment || {};
    const expiresAt = parseIsoTime(payment.expires_at);
    if (!expiresAt) {
      this.setData({
        secondsRemaining: 0,
        expired: false
      });
      return;
    }
    const secondsRemaining = Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
    this.setData({
      secondsRemaining,
      expired: secondsRemaining <= 0
    });
  },

  startPolling() {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
    }
    this.pollTimer = setInterval(() => {
      this.refreshOrderStatus({ silent: true });
    }, 3000);
  },

  async refreshOrderStatus(options = {}) {
    const order = this.data.order;
    if (!order || this.completed) {
      return;
    }
    if (!options.silent) {
      this.setData({ refreshing: true });
    }
    try {
      const latestOrder = await request({
        url: `/api/purchase/orders/${order.order_id}`,
        withAuth: true
      });
      this.setData({
        order: latestOrder,
        statusText: latestOrder.status === "confirmed" ? "支付已确认，正在返回" : this.data.statusText
      });
      if (latestOrder.status === "confirmed") {
        this.emitSuccess(latestOrder);
      }
    } catch (error) {
      if (!options.silent) {
        showError(error, { fallback: "刷新支付状态失败" });
      }
    } finally {
      if (!options.silent) {
        this.setData({ refreshing: false });
      }
    }
  },

  previewQrcode() {
    if (!this.data.qrcodeTempFile) {
      wx.showToast({
        title: "二维码还没准备好",
        icon: "none"
      });
      return;
    }
    wx.previewImage({
      current: this.data.qrcodeTempFile,
      urls: [this.data.qrcodeTempFile]
    });
  },

  copyPayLink() {
    const payUrl = this.data.payment && this.data.payment.pay_url;
    if (!payUrl) {
      wx.showToast({
        title: "当前没有可复制的支付链接",
        icon: "none"
      });
      return;
    }
    wx.setClipboardData({
      data: payUrl,
      success: () => {
        wx.showToast({
          title: "支付链接已复制",
          icon: "success"
        });
      }
    });
  },

  goBack() {
    this.emitCancellation();
    wx.navigateBack();
  }
});
