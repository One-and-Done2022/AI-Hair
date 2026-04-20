const { ensureLogin, clearLogin } = require("../../utils/auth");
const { readCreationDraft } = require("../../utils/creation-draft");
const { showError } = require("../../utils/errors");
const {
  getDefaultPurchaseItem,
  quickPurchaseDefaultGenerationPack
} = require("../../utils/purchase");
const { request } = require("../../utils/request");
const { enableInternalSceneTool } = require("../../utils/config");

const SERVICE_WECHAT_ID = "look4warding";
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

function showActionSheet(items = []) {
  return new Promise((resolve) => {
    wx.showActionSheet({
      itemList: items,
      success: (result) => resolve(result.tapIndex),
      fail: () => resolve(-1)
    });
  });
}

Page({
  data: {
    loading: false,
    profile: null,
    purchaseItem: null,
    purchasing: false,
    hasActiveCreation: false,
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
        purchaseItem,
        hasActiveCreation: this.hasActiveCreationDraft()
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
      content: "新用户默认可免费生成 1 次。首次成功出图后填写体验反馈，还会再赠送 1 次使用机会；后续也可以在“我的”页按次购买生成包，每次购买成功后剩余可用次数都会 +1。",
      showCancel: false
    });
  },

  hasActiveCreationDraft() {
    const draft = readCreationDraft();
    return !!(draft.imagePath || draft.hairstyle || draft.scene);
  },

  continueCreation() {
    const draft = readCreationDraft();
    if (!draft.imagePath) {
      wx.switchTab({
        url: "/pages/index/index"
      });
      return;
    }
    if (!draft.hairstyle) {
      wx.navigateTo({
        url: "/pages/templates/index"
      });
      return;
    }
    if (!draft.scene) {
      wx.navigateTo({
        url: "/pages/scenes/index"
      });
      return;
    }
    wx.navigateTo({
      url: "/pages/review/index"
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
        content: `确认购买 ${purchaseItem.name}（${purchaseItem.price_label}）？确认后会进入支付页。`,
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
      if (this.hasActiveCreationDraft()) {
        const shouldContinue = await showConfirmModal({
          title: "购买成功",
          content: "已为你增加 1 次生成，是否回到当前创作继续生成？",
          confirmText: "继续创作",
          cancelText: "稍后再说"
        });
        if (shouldContinue) {
          this.continueCreation();
        }
      }
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

  async syncWechatNickname() {
    try {
      await ensureLogin();
      const profilePayload = await new Promise((resolve, reject) => {
        if (typeof wx.getUserProfile !== "function") {
          reject(new Error("当前微信版本不支持同步昵称"));
          return;
        }
        wx.getUserProfile({
          desc: "用于在管理后台展示你的微信昵称",
          success: resolve,
          fail: reject
        });
      });
      const nickname = profilePayload && profilePayload.userInfo && profilePayload.userInfo.nickName
        ? String(profilePayload.userInfo.nickName).trim()
        : "";
      if (!nickname) {
        wx.showToast({
          title: "未获取到昵称",
          icon: "none"
        });
        return;
      }
      await request({
        url: "/api/me/profile",
        method: "PATCH",
        data: { nickname }
      });
      wx.showToast({
        title: "昵称已同步",
        icon: "success"
      });
      await this.loadProfile();
    } catch (error) {
      if (error && /cancel/i.test(String(error.errMsg || error.message || ""))) {
        return;
      }
      showError(error, { fallback: "同步昵称失败" });
    }
  },

  async copyServiceWechat() {
    try {
      await new Promise((resolve, reject) => {
        wx.setClipboardData({
          data: SERVICE_WECHAT_ID,
          success: resolve,
          fail: reject
        });
      });
      wx.showToast({
        title: "客服微信已复制",
        icon: "success"
      });
    } catch (error) {
      showError(error, { fallback: "复制客服微信失败" });
    }
  },

  async openHelpFeedback() {
    const tapIndex = await showActionSheet([
      "使用说明",
      "复制客服微信",
      "联系人工支持"
    ]);

    if (tapIndex === 0) {
      wx.showModal({
        title: "帮助反馈",
        content:
          `1. 先上传清晰单人照片，再依次选择发型、场景和参数。\n2. 生成成功后可保存图片，也可以在作品记录里回看。\n3. 遇到问题可添加客服微信 ${SERVICE_WECHAT_ID}，并附上 UID、截图和问题描述。`,
        showCancel: false,
        confirmText: "我知道了"
      });
      return;
    }

    if (tapIndex === 1) {
      this.copyServiceWechat();
      return;
    }

    if (tapIndex === 2) {
      const confirmed = await showConfirmModal({
        title: "联系人工支持",
        content: `客服微信：${SERVICE_WECHAT_ID}\n建议同时发送你的 UID、问题截图和出现时间，方便更快定位问题。`,
        confirmText: "复制微信",
        cancelText: "关闭"
      });
      if (confirmed) {
        this.copyServiceWechat();
      }
    }
  },

  async relogin() {
    wx.showLoading({ title: "刷新中" });
    try {
      clearLogin();
      await this.loadProfile();
      wx.showToast({
        title: "登录状态已刷新",
        icon: "success"
      });
    } catch (error) {
      showError(error, { fallback: "刷新登录失败" });
    } finally {
      wx.hideLoading();
    }
  }
});
