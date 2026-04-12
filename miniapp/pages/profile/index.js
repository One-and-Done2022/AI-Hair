const { ensureLogin, clearLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const {
  getDefaultPurchaseItem,
  quickPurchaseDefaultGenerationPack
} = require("../../utils/purchase");
const { request } = require("../../utils/request");
const { enableInternalSceneTool } = require("../../utils/config");

function formatJoinedAt(value) {
  if (!value) {
    return "";
  }
  const timestamp = Date.parse(value.replace(/\+00:00$/, "Z"));
  if (Number.isNaN(timestamp)) {
    return value;
  }
  const date = new Date(timestamp);
  return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, "0")}.${String(
    date.getDate()
  ).padStart(2, "0")} 加入`;
}

function showConfirmModal(options) {
  return new Promise((resolve) => {
    wx.showModal({
      ...options,
      success: ({ confirm }) => resolve(!!confirm),
      fail: () => resolve(false)
    });
  });
}

Page({
  data: {
    loading: false,
    profile: null,
    purchaseItem: null,
    purchasing: false,
    enableInternalSceneTool
  },

  async onShow() {
    await this.loadProfile();
  },

  async loadProfile() {
    this.setData({ loading: true });
    try {
      await ensureLogin();
      const [profile, purchaseItem] = await Promise.all([
        request({ url: "/api/me" }),
        getDefaultPurchaseItem().catch(() => null)
      ]);
      this.setData({
        profile: {
          ...profile,
          provider_alerts: [],
          joined_label: formatJoinedAt(profile.created_at),
          avatar_text: "AI"
        },
        purchaseItem
      });
    } catch (error) {
      showError(error, { fallback: "加载失败" });
    } finally {
      this.setData({ loading: false });
    }
  },

  openWorks() {
    wx.switchTab({
      url: "/pages/history/index"
    });
  },

  openSceneTool() {
    wx.navigateTo({
      url: "/pages/scene-tool/index"
    });
  },

  showQuotaHelp() {
    wx.showModal({
      title: "额度说明",
      content: "新用户会一次性获得 10 次免费完整生成。每次完整生成会返回 1 张换发预览和 2 张场景成片。免费次数用完后，可按 1 元 1 次继续购买。",
      showCancel: false
    });
  },

  async purchaseOnePack() {
    if (this.data.purchasing) {
      return;
    }
    try {
      await ensureLogin();
      const purchaseItem = this.data.purchaseItem || await getDefaultPurchaseItem();
      if (!purchaseItem) {
        wx.showToast({
          title: "当前没有可购买商品",
          icon: "none"
        });
        return;
      }
      const confirmed = await showConfirmModal({
        title: "购买生成包",
        content: `确认购买 ${purchaseItem.name}（${purchaseItem.price_label}）？确认后会拉起微信支付。`,
        confirmText: "立即购买"
      });
      if (!confirmed) {
        return;
      }
      this.setData({ purchasing: true });
      wx.showLoading({ title: "正在购买" });
      await quickPurchaseDefaultGenerationPack(purchaseItem.product_id);
      wx.showToast({
        title: "已增加 1 次生成",
        icon: "success"
      });
      await this.loadProfile();
    } catch (error) {
      showError(error, {
        fallback: "购买失败，请稍后再试",
        preferModal: true
      });
    } finally {
      wx.hideLoading();
      this.setData({ purchasing: false });
    }
  },

  showComingSoon(event) {
    const { label } = event.currentTarget.dataset;
    wx.showToast({
      title: `${label}即将开放`,
      icon: "none"
    });
  },

  relogin() {
    clearLogin();
    this.loadProfile();
  }
});
