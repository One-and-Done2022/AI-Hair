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

function decodeText(value) {
  if (!value) {
    return "";
  }
  try {
    return decodeURIComponent(value);
  } catch (error) {
    return value;
  }
}

function buildJobMeta(job) {
  if (!job) {
    return null;
  }
  return {
    job_id: job.job_id || "",
    hairstyle_name: job.hairstyle_name || "",
    scene_name: job.scene_name || "",
    error_message: job.error_message || ""
  };
}

function hasMetaChanged(currentJob, nextJob) {
  if (!currentJob && nextJob) {
    return true;
  }
  if (!currentJob || !nextJob) {
    return false;
  }
  return (
    currentJob.job_id !== nextJob.job_id ||
    currentJob.hairstyle_name !== nextJob.hairstyle_name ||
    currentJob.scene_name !== nextJob.scene_name ||
    currentJob.error_message !== nextJob.error_message
  );
}

Page({
  data: {
    status: "pending",
    job: null,
    resultImageUrl: "",
    resultImageLoaded: false
  },

  onLoad(options) {
    if (!options.jobId) {
      wx.showToast({ title: "缺少任务 ID", icon: "none" });
      return;
    }

    this.jobId = options.jobId;
    this.isPolling = false;

    const initialJob = buildJobMeta({
      job_id: options.jobId,
      hairstyle_name: decodeText(options.hairstyleName),
      scene_name: decodeText(options.sceneName),
      error_message: ""
    });

    this.setData({
      status: options.status || "pending",
      job: initialJob
    });

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
    if (this.isPolling || !this.jobId) {
      return;
    }

    this.isPolling = true;
    try {
      await ensureLogin();
      const job = await request({
        url: `/api/jobs/${this.jobId}`
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
      this.isPolling = false;
    }
  },

  applyJobState(job) {
    const nextJob = buildJobMeta(job);
    const nextImageUrl = job.result_image_url || "";
    const nextState = {};

    if (this.data.status !== job.status) {
      nextState.status = job.status;
    }

    if (hasMetaChanged(this.data.job, nextJob)) {
      nextState.job = nextJob;
    }

    if (this.data.resultImageUrl !== nextImageUrl) {
      nextState.resultImageUrl = nextImageUrl;
      nextState.resultImageLoaded = false;
    }

    if (Object.keys(nextState).length > 0) {
      this.setData(nextState);
    }
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
