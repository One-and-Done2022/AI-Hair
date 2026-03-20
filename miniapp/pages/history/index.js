const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const { request } = require("../../utils/request");

function getStatusLabel(status) {
  if (status === "succeeded") {
    return "已完成";
  }
  if (status === "preview_ready") {
    return "首图已返回";
  }
  if (status === "failed") {
    return "失败";
  }
  return "生成中";
}

function normalizeHistoryItems(items) {
  return (items || []).map((item) => ({
    ...item,
    status_label: getStatusLabel(item.status)
  }));
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
        items: normalizeHistoryItems(payload.items)
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
