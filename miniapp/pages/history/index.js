const { ensureLogin } = require("../../utils/auth");
const { request } = require("../../utils/request");

function getErrorMessage(error) {
  if (!error) {
    return "加载失败";
  }
  if (typeof error === "string") {
    return error;
  }
  if (error.detail && error.detail.message) {
    return error.detail.message;
  }
  if (error.detail && typeof error.detail === "string") {
    return error.detail;
  }
  return error.message || "加载失败";
}

Page({
  data: {
    loading: false,
    items: []
  },

  async onShow() {
    await this.loadHistory();
  },

  onPullDownRefresh() {
    this.loadHistory();
  },

  async loadHistory() {
    this.setData({ loading: true });
    try {
      await ensureLogin();
      const payload = await request({ url: "/api/history" });
      this.setData({
        items: payload.items || []
      });
    } catch (error) {
      wx.showToast({
        title: getErrorMessage(error),
        icon: "none"
      });
    } finally {
      this.setData({ loading: false });
      wx.stopPullDownRefresh();
    }
  },

  openJob(event) {
    const { jobId } = event.currentTarget.dataset;
    wx.navigateTo({
      url: `/pages/result/index?jobId=${jobId}`
    });
  }
});

