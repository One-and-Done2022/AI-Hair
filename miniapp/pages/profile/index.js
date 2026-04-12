const { ensureLogin, clearLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
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

Page({
  data: {
    loading: false,
    profile: null,
    enableInternalSceneTool
  },

  async onShow() {
    await this.loadProfile();
  },

  async loadProfile() {
    this.setData({ loading: true });
    try {
      await ensureLogin();
      const profile = await request({ url: "/api/me" });
      this.setData({
        profile: {
          ...profile,
          provider_alerts: [],
          joined_label: formatJoinedAt(profile.created_at),
          avatar_text: "AI"
        }
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
      content: "当前版本按本月生成次数做展示。后续接入正式会员与计费后，这里会切换成真实剩余额度。",
      showCancel: false
    });
  },

  showMemberIntro() {
    wx.showModal({
      title: "会员权益",
      content: "后续可扩展为更高生成次数、优先排队、更多模板与高清导出。",
      showCancel: false
    });
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
