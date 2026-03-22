const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const { request } = require("../../utils/request");

const POLL_INTERVAL = 1200;
const PROGRESS_INTERVAL = 1000;
const ESTIMATED_TOTAL_SECONDS = 75;
const MAX_VISIBLE_PROGRESS = 96;
const MIN_VISIBLE_PROGRESS = 6;
const STAGE_LABELS = ["上传完成", "识别人脸", "首图生成", "候选精修", "完成"];

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
    created_at: job.created_at || "",
    upload_url: job.upload_url || "",
    media_expired: !!job.media_expired,
    media_expires_at: job.media_expires_at || ""
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
    currentJob.created_at !== nextJob.created_at ||
    currentJob.upload_url !== nextJob.upload_url ||
    currentJob.media_expired !== nextJob.media_expired ||
    currentJob.media_expires_at !== nextJob.media_expires_at
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

function isTerminalStatus(status) {
  return status === "succeeded" || status === "failed";
}

function getProgressStage(progressRatio, status) {
  if (status === "preview_ready") {
    return "首图已生成，正在补齐候选图";
  }
  if (progressRatio < 0.28) {
    return "正在生成首张预览图";
  }
  if (progressRatio < 0.72) {
    return "正在补齐候选图";
  }
  return "正在筛选最自然的一张";
}

function getStatusLabel(status) {
  if (status === "succeeded") {
    return "已完成";
  }
  if (status === "preview_ready") {
    return "首图已生成";
  }
  if (status === "failed") {
    return "失败";
  }
  return "生成中";
}

function getImageLoadingText(status) {
  return status === "preview_ready" ? "正在加载首张预览" : "正在加载最终结果";
}

function buildSaveChoices(imageUrls) {
  return (imageUrls || []).map((url, index) => ({
    url,
    label: index === 0 ? "系统推荐图（顶部）" : `候选结果 ${index + 1}`
  }));
}

function buildStageSteps(status, progressPercent) {
  let completedCount = 2;
  let activeIndex = 2;

  if (status === "preview_ready") {
    completedCount = 3;
    activeIndex = 3;
  } else if (status === "succeeded") {
    completedCount = STAGE_LABELS.length;
    activeIndex = -1;
  } else if (status === "failed") {
    completedCount = progressPercent >= 72 ? 3 : 2;
    activeIndex = progressPercent >= 72 ? 3 : 2;
  } else if (progressPercent >= 72) {
    completedCount = 3;
    activeIndex = 3;
  }

  return STAGE_LABELS.map((label, index) => {
    let state = "pending";
    if (index < completedCount) {
      state = "done";
    } else if (index === activeIndex) {
      state = status === "failed" ? "failed" : "active";
    }
    return {
      label,
      state
    };
  });
}

function buildStatusHint(status, remainingSeconds) {
  if (status === "preview_ready") {
    return `你已经可以先看第一张，预计还需 ${remainingSeconds} 秒完成最终筛选`;
  }
  if (status === "failed") {
    return "这次任务没有顺利完成，可以返回首页重新生成。";
  }
  if (remainingSeconds > 0) {
    return `预计还需 ${remainingSeconds} 秒，期间可以离开页面，稍后从历史记录回来查看`;
  }
  return "已进入最后筛选阶段，通常很快就会完成";
}

Page({
  data: {
    status: "pending",
    statusLabel: getStatusLabel("pending"),
    job: null,
    uploadUrl: "",
    resultImageUrl: "",
    resultImageUrls: [],
    mediaExpired: false,
    mediaExpiresAt: "",
    resultImageLoaded: false,
    imageLoadingText: getImageLoadingText("pending"),
    progressPercent: MIN_VISIBLE_PROGRESS,
    elapsedSeconds: 0,
    remainingSeconds: ESTIMATED_TOTAL_SECONDS,
    estimatedTotalSeconds: ESTIMATED_TOTAL_SECONDS,
    progressStage: "正在准备生成",
    progressHint: "预计总耗时约 75 秒",
    stageSteps: buildStageSteps("pending", MIN_VISIBLE_PROGRESS)
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

    const initialStatus = options.status || "pending";

    this.setData({
      status: initialStatus,
      statusLabel: getStatusLabel(initialStatus),
      imageLoadingText: getImageLoadingText(initialStatus),
      stageSteps: buildStageSteps(initialStatus, MIN_VISIBLE_PROGRESS),
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

  onShareAppMessage() {
    const hairstyle = (this.data.job && this.data.job.hairstyle_name) || "新发型";
    const scene = (this.data.job && this.data.job.scene_name) || "新场景";
    return {
      title: `我在 AIFace 试了 ${hairstyle} · ${scene}`,
      path: "/pages/index/index",
      imageUrl: this.data.resultImageUrl || this.data.uploadUrl || ""
    };
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
    if (isTerminalStatus(this.data.status)) {
      this.setData({
        stageSteps: buildStageSteps(this.data.status, this.data.progressPercent)
      });
      return;
    }

    const createdAtMs = this.jobCreatedAtMs || Date.now();
    const elapsedSeconds = Math.max(0, Math.floor((Date.now() - createdAtMs) / 1000));
    let progressPercent = MIN_VISIBLE_PROGRESS;
    let remainingSeconds = Math.max(0, ESTIMATED_TOTAL_SECONDS - elapsedSeconds);
    let progressStage = getProgressStage(0, this.data.status);

    if (this.data.status === "preview_ready") {
      progressPercent = Math.min(
        MAX_VISIBLE_PROGRESS,
        Math.max(72, 72 + Math.round(elapsedSeconds / 4))
      );
      remainingSeconds = Math.max(
        5,
        Math.round(Math.max(0, ESTIMATED_TOTAL_SECONDS - elapsedSeconds) / 2)
      );
      progressStage = getProgressStage(1, this.data.status);
    } else {
      const rawRatio = elapsedSeconds / ESTIMATED_TOTAL_SECONDS;
      const progressRatio = Math.min(rawRatio, MAX_VISIBLE_PROGRESS / 100);
      const rawPercent = Math.round(progressRatio * 100);
      progressPercent = Math.max(MIN_VISIBLE_PROGRESS, rawPercent);
      progressStage = getProgressStage(progressRatio, this.data.status);
    }

    this.setData({
      elapsedSeconds,
      remainingSeconds,
      progressPercent,
      progressStage,
      progressHint: buildStatusHint(this.data.status, remainingSeconds),
      stageSteps: buildStageSteps(this.data.status, progressPercent)
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
      if (isTerminalStatus(job.status)) {
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
      nextState.statusLabel = getStatusLabel(job.status);
      nextState.imageLoadingText = getImageLoadingText(job.status);
    }

    const createdAtMs = parseTimestamp(job.created_at);
    if (createdAtMs) {
      this.jobCreatedAtMs = createdAtMs;
    }

    if (hasMetaChanged(this.data.job, nextJob)) {
      nextState.job = nextJob;
    }

    if (this.data.uploadUrl !== (job.upload_url || "")) {
      nextState.uploadUrl = job.upload_url || "";
    }

    if (this.data.mediaExpired !== !!job.media_expired) {
      nextState.mediaExpired = !!job.media_expired;
    }

    if (this.data.mediaExpiresAt !== (job.media_expires_at || "")) {
      nextState.mediaExpiresAt = job.media_expires_at || "";
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

  previewOriginal() {
    if (!this.data.uploadUrl) {
      return;
    }
    wx.previewImage({
      current: this.data.uploadUrl,
      urls: [this.data.uploadUrl]
    });
  },

  previewComparison() {
    if (!this.data.uploadUrl || !this.data.resultImageUrl) {
      return;
    }
    const urls = [this.data.uploadUrl, ...(this.data.resultImageUrls.length
      ? this.data.resultImageUrls
      : [this.data.resultImageUrl])];
    wx.previewImage({
      current: this.data.resultImageUrl,
      urls
    });
  },

  async saveImage() {
    const imageUrls = this.data.resultImageUrls.length
      ? this.data.resultImageUrls
      : this.data.resultImageUrl
        ? [this.data.resultImageUrl]
        : [];

    if (!imageUrls.length) {
      return;
    }

    const saveChoices = buildSaveChoices(imageUrls);
    if (saveChoices.length === 1) {
      this.downloadAndSaveImage(saveChoices[0].url, saveChoices[0].label);
      return;
    }

    wx.showActionSheet({
      itemList: saveChoices.map((item) => item.label),
      success: ({ tapIndex }) => {
        const selectedChoice = saveChoices[tapIndex];
        if (!selectedChoice) {
          return;
        }
        this.downloadAndSaveImage(selectedChoice.url, selectedChoice.label);
      },
      fail: (error) => {
        if (error && error.errMsg && error.errMsg.includes("cancel")) {
          return;
        }
        wx.showToast({ title: "无法打开保存选项", icon: "none" });
      }
    });
  },

  downloadAndSaveImage(imageUrl, label) {
    if (!imageUrl) {
      return;
    }

    wx.showLoading({ title: "正在保存" });
    wx.downloadFile({
      url: imageUrl,
      success: (result) => {
        wx.saveImageToPhotosAlbum({
          filePath: result.tempFilePath,
          success: () => {
            wx.showToast({ title: `${label}已保存`, icon: "success" });
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
  },

  goHistory() {
    wx.switchTab({
      url: "/pages/history/index"
    });
  }
});
