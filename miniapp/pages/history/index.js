const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const { request } = require("../../utils/request");

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
      showError(error, { fallback: "加载失败" });
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
