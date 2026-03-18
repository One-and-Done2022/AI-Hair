const { ensureLogin } = require("../../utils/auth");
const { request } = require("../../utils/request");

const POLL_INTERVAL = 2500;

function getErrorMessage(error) {
  if (!error) {
    return "请求失败";
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
  return error.message || "请求失败";
}

Page({
  data: {
    jobId: "",
    status: "pending",
    job: null,
    polling: false
  },

  onLoad(options) {
    if (!options.jobId) {
      wx.showToast({ title: "缺少任务 ID", icon: "none" });
      return;
    }
    this.setData({ jobId: options.jobId });
    this.fetchJob();
    this.timer = setInterval(() => {
      this.fetchJob();
    }, POLL_INTERVAL);
  },

  onUnload() {
    this.stopPolling();
  },

  stopPolling() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  },

  async fetchJob() {
    if (this.data.polling || !this.data.jobId) {
      return;
    }

    this.setData({ polling: true });
    try {
      await ensureLogin();
      const job = await request({
        url: `/api/jobs/${this.data.jobId}`
      });
      this.setData({
        job,
        status: job.status
      });
      if (job.status === "succeeded" || job.status === "failed") {
        this.stopPolling();
      }
    } catch (error) {
      this.stopPolling();
      wx.showToast({
        title: getErrorMessage(error),
        icon: "none"
      });
    } finally {
      this.setData({ polling: false });
    }
  },

  async saveImage() {
    if (!this.data.job || !this.data.job.result_image_url) {
      return;
    }

    wx.showLoading({ title: "正在保存" });
    wx.downloadFile({
      url: this.data.job.result_image_url,
      success: (result) => {
        wx.saveImageToPhotosAlbum({
          filePath: result.tempFilePath,
          success: () => {
            wx.showToast({ title: "已保存到相册", icon: "success" });
          },
          fail: () => {
            wx.showToast({ title: "保存失败，请检查权限", icon: "none" });
          },
          complete: () => {
            wx.hideLoading();
          }
        });
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: "下载失败", icon: "none" });
      }
    });
  },

  createAnother() {
    wx.switchTab({
      url: "/pages/index/index"
    });
  }
});

