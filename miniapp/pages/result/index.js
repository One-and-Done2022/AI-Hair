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
    polling: false,
    resultImageUrl: "",
    resultImageLoaded: false
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
      if (job.status === "succeeded" || job.status === "failed") {
        this.stopPolling();
      }
      this.applyJobState(job);
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

  applyJobState(job) {
    const nextImageUrl = job.result_image_url || "";
    const currentJob = this.data.job;
    const currentImageUrl = this.data.resultImageUrl || "";
    const hasMeaningfulChange =
      !currentJob ||
      currentJob.updated_at !== job.updated_at ||
      this.data.status !== job.status ||
      currentImageUrl !== nextImageUrl;

    if (!hasMeaningfulChange) {
      return;
    }

    const nextState = {
      job,
      status: job.status
    };

    if (currentImageUrl !== nextImageUrl) {
      nextState.resultImageUrl = nextImageUrl;
      nextState.resultImageLoaded = false;
    }

    this.setData(nextState);
  },

  handleResultImageLoad() {
    if (!this.data.resultImageLoaded) {
      this.setData({ resultImageLoaded: true });
    }
  },

  async saveImage() {
    if (!this.data.resultImageUrl) {
      return;
    }

    wx.showLoading({ title: "正在保存" });
    wx.downloadFile({
      url: this.data.resultImageUrl,
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
