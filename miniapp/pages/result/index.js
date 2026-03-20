const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const { request } = require("../../utils/request");

const POLL_INTERVAL = 2500;
const PROGRESS_INTERVAL = 1000;
const ESTIMATED_TOTAL_SECONDS = 75;
const MAX_VISIBLE_PROGRESS = 96;
const MIN_VISIBLE_PROGRESS = 6;

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
    error_message: job.error_message || "",
    created_at: job.created_at || ""
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
    currentJob.error_message !== nextJob.error_message ||
    currentJob.created_at !== nextJob.created_at
  );
}

function arraysEqual(left, right) {
  if (left === right) {
    return true;
  }
  if (!Array.isArray(left) || !Array.isArray(right) || left.length !== right.length) {
    return false;
  }
  return left.every((item, index) => item === right[index]);
}

function parseTimestamp(value) {
  if (!value) {
    return null;
  }
  const normalized = value.replace(/\+00:00$/, "Z");
  const timestamp = Date.parse(normalized);
  return Number.isNaN(timestamp) ? null : timestamp;
}

function getProgressStage(progressRatio) {
  if (progressRatio < 0.28) {
    return "正在生成第 1 张候选图";
  }
  if (progressRatio < 0.58) {
    return "正在生成第 2 张候选图";
  }
  if (progressRatio < 0.86) {
    return "正在生成第 3 张候选图";
  }
  return "正在筛选最自然的一张";
}

Page({
  data: {
    status: "pending",
    job: null,
    resultImageUrl: "",
    resultImageUrls: [],
    resultImageLoaded: false,
    progressPercent: MIN_VISIBLE_PROGRESS,
    elapsedSeconds: 0,
    remainingSeconds: ESTIMATED_TOTAL_SECONDS,
    estimatedTotalSeconds: ESTIMATED_TOTAL_SECONDS,
    progressStage: "正在准备生成",
    progressHint: "预计总耗时约 75 秒"
  },

  onLoad(options) {
    if (!options.jobId) {
      wx.showToast({ title: "缺少任务 ID", icon: "none" });
      return;
    }

    this.jobId = options.jobId;
    this.isPolling = false;
    this.jobCreatedAtMs = parseTimestamp(decodeText(options.createdAt)) || Date.now();

    const initialJob = buildJobMeta({
      job_id: options.jobId,
      created_at: decodeText(options.createdAt),
      hairstyle_name: decodeText(options.hairstyleName),
      scene_name: decodeText(options.sceneName),
      error_message: ""
    });

    this.setData({
      status: options.status || "pending",
      job: initialJob
    });

    this.startProgressClock();
    this.fetchJob();
    this.pollTimer = setInterval(() => {
      this.fetchJob();
    }, POLL_INTERVAL);
  },

  onUnload() {
    this.stopPolling();
    this.stopProgressClock();
  },

  stopPolling() {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  },

  startProgressClock() {
    this.updateProgressState();
    if (this.progressTimer) {
      clearInterval(this.progressTimer);
    }
    this.progressTimer = setInterval(() => {
      this.updateProgressState();
    }, PROGRESS_INTERVAL);
  },

  stopProgressClock() {
    if (this.progressTimer) {
      clearInterval(this.progressTimer);
      this.progressTimer = null;
    }
  },

  updateProgressState() {
    if (this.data.status === "succeeded" || this.data.status === "failed") {
      return;
    }

    const createdAtMs = this.jobCreatedAtMs || Date.now();
    const elapsedSeconds = Math.max(0, Math.floor((Date.now() - createdAtMs) / 1000));
    const rawRatio = elapsedSeconds / ESTIMATED_TOTAL_SECONDS;
    const progressRatio = Math.min(rawRatio, MAX_VISIBLE_PROGRESS / 100);
    const rawPercent = Math.round(progressRatio * 100);
    const progressPercent = Math.max(MIN_VISIBLE_PROGRESS, rawPercent);
    const remainingSeconds = Math.max(0, ESTIMATED_TOTAL_SECONDS - elapsedSeconds);
    const progressStage = getProgressStage(progressRatio);
    const progressHint =
      remainingSeconds > 0
        ? `预计还需 ${remainingSeconds} 秒，网络波动会略有浮动`
        : "已进入最后筛选阶段，通常很快就会完成";

    this.setData({
      elapsedSeconds,
      remainingSeconds,
      progressPercent,
      progressStage,
      progressHint
    });
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
        this.stopProgressClock();
      }
      this.applyJobState(job);
    } catch (error) {
      this.stopPolling();
      this.stopProgressClock();
      showError(error, { fallback: "请求失败" });
    } finally {
      this.isPolling = false;
    }
  },

  applyJobState(job) {
    const nextJob = buildJobMeta(job);
    const nextImageUrls =
      Array.isArray(job.result_image_urls) && job.result_image_urls.length
        ? job.result_image_urls
        : job.result_image_url
          ? [job.result_image_url]
          : [];
    const nextImageUrl = nextImageUrls[0] || "";
    const nextState = {};

    if (this.data.status !== job.status) {
      nextState.status = job.status;
    }

    const createdAtMs = parseTimestamp(job.created_at);
    if (createdAtMs) {
      this.jobCreatedAtMs = createdAtMs;
    }

    if (hasMetaChanged(this.data.job, nextJob)) {
      nextState.job = nextJob;
    }

    if (!arraysEqual(this.data.resultImageUrls, nextImageUrls)) {
      nextState.resultImageUrls = nextImageUrls;
    }

    if (this.data.resultImageUrl !== nextImageUrl) {
      nextState.resultImageUrl = nextImageUrl;
      nextState.resultImageLoaded = false;
    }

    if (Object.keys(nextState).length > 0) {
      this.setData(nextState);
    }

    this.updateProgressState();
  },

  handleResultImageLoad() {
    if (!this.data.resultImageLoaded) {
      this.setData({ resultImageLoaded: true });
    }
  },

  previewResult(event) {
    const current = event.currentTarget.dataset.url;
    const urls = this.data.resultImageUrls.length
      ? this.data.resultImageUrls
      : this.data.resultImageUrl
        ? [this.data.resultImageUrl]
        : [];

    if (!current || !urls.length) {
      return;
    }

    wx.previewImage({
      current,
      urls
    });
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
