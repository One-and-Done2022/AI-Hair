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

function parseTimestamp(value) {
  if (!value) {
    return null;
  }
  const normalized = value.replace(/\+00:00$/, "Z");
  const timestamp = Date.parse(normalized);
  return Number.isNaN(timestamp) ? null : timestamp;
}

function pad(value) {
  return String(value).padStart(2, "0");
}

function formatCreatedAt(value) {
  const timestamp = parseTimestamp(value);
  if (!timestamp) {
    return value || "";
  }

  const date = new Date(timestamp);
  const now = new Date();
  const sameYear = date.getFullYear() === now.getFullYear();
  const sameMonth = sameYear && date.getMonth() === now.getMonth();
  const sameDay = sameMonth && date.getDate() === now.getDate();

  if (sameDay) {
    return `今天 ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  return `${date.getMonth() + 1}月${date.getDate()}日 ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function normalizeHistoryItems(items) {
  return (items || []).map((item) => ({
    ...item,
    status_label: getStatusLabel(item.status),
    created_at_label: formatCreatedAt(item.created_at)
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
