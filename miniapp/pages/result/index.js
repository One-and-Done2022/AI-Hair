const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const {
  buildHairColorDisplay,
  inferHairColorSelectionMode
} = require("../../utils/hair-color");
const {
  removePendingHistoryJob,
  upsertPendingHistoryJob
} = require("../../utils/pending-history");
const { request } = require("../../utils/request");

const POLL_INTERVAL = 1200;
const PROGRESS_INTERVAL = 1000;
const ESTIMATED_TOTAL_SECONDS = 80;
const MIN_VISIBLE_PROGRESS = 6;

const STAGE_LABELS = [
  "上传完成",
  "发型预览",
  "场景成片 1",
  "场景成片 2",
  "完成"
];

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
  const hairColorDisplay = buildHairColorDisplay(job);
  return {
    job_id: job.job_id || "",
    hairstyle_name: job.hairstyle_name || "",
    scene_name: job.scene_name || "",
    hair_color_selection_mode: inferHairColorSelectionMode(job),
    hair_color_tone: job.hair_color_tone || "",
    hair_color_tone_label: job.hair_color_tone_label || "",
    hair_color_technique: job.hair_color_technique || "",
    hair_color_technique_label: job.hair_color_technique_label || "",
    hair_color_professional_id: job.hair_color_professional_id || "",
    hair_color_professional_brand: job.hair_color_professional_brand || "",
    hair_color_professional_series: job.hair_color_professional_series || "",
    hair_color_professional_series_label: job.hair_color_professional_series_label || "",
    hair_color_professional_code: job.hair_color_professional_code || "",
    hair_color_professional_note: job.hair_color_professional_note || "",
    hair_color_professional_hex_estimate: job.hair_color_professional_hex_estimate || "",
    hair_color_mode_label: hairColorDisplay.mode_label,
    hair_color_primary_label: hairColorDisplay.primary_label,
    hair_color_secondary_label: hairColorDisplay.secondary_label,
    error_message: job.error_message || "",
    created_at: job.created_at || "",
    upload_url: job.upload_url || "",
    media_expired: !!job.media_expired,
    media_expires_at: job.media_expires_at || "",
    generator_backend: job.generator_backend || "",
    aspect_ratio: job.aspect_ratio || "",
    resolution: job.resolution || ""
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
    currentJob.hair_color_selection_mode !== nextJob.hair_color_selection_mode ||
    currentJob.hair_color_tone !== nextJob.hair_color_tone ||
    currentJob.hair_color_tone_label !== nextJob.hair_color_tone_label ||
    currentJob.hair_color_technique !== nextJob.hair_color_technique ||
    currentJob.hair_color_technique_label !== nextJob.hair_color_technique_label ||
    currentJob.hair_color_professional_id !== nextJob.hair_color_professional_id ||
    currentJob.hair_color_professional_brand !== nextJob.hair_color_professional_brand ||
    currentJob.hair_color_professional_series !== nextJob.hair_color_professional_series ||
    currentJob.hair_color_professional_series_label !== nextJob.hair_color_professional_series_label ||
    currentJob.hair_color_professional_code !== nextJob.hair_color_professional_code ||
    currentJob.hair_color_professional_note !== nextJob.hair_color_professional_note ||
    currentJob.hair_color_professional_hex_estimate !== nextJob.hair_color_professional_hex_estimate ||
    currentJob.error_message !== nextJob.error_message ||
    currentJob.created_at !== nextJob.created_at ||
    currentJob.upload_url !== nextJob.upload_url ||
    currentJob.media_expired !== nextJob.media_expired ||
    currentJob.media_expires_at !== nextJob.media_expires_at ||
    currentJob.generator_backend !== nextJob.generator_backend ||
    currentJob.aspect_ratio !== nextJob.aspect_ratio ||
    currentJob.resolution !== nextJob.resolution
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

function getStatusLabel(status, completedSceneCount = 0) {
  if (status === "succeeded") {
    return "已完成";
  }
  if (status === "failed") {
    return completedSceneCount > 0 ? "部分完成" : "失败";
  }
  if (status === "hair_generating") {
    return "换发中";
  }
  if (status === "hair_ready") {
    return "发型预览已返回";
  }
  if (status === "scene_generating") {
    return "场景生成中";
  }
  if (status === "scene_partial") {
    return "场景图已返回";
  }
  return "排队中";
}

function getImageLoadingText(status, hasHairPreview, completedSceneCount) {
  if (completedSceneCount > 0) {
    return "正在加载场景成片";
  }
  if (hasHairPreview) {
    return "正在加载发型预览";
  }
  if (status === "hair_generating") {
    return "正在加载换发结果";
  }
  return "正在加载生成结果";
}

function buildSaveChoices(hairPreviewUrl, sceneImageUrls) {
  const choices = [];
  if (hairPreviewUrl) {
    choices.push({
      url: hairPreviewUrl,
      label: "发型预览图"
    });
  }
  (sceneImageUrls || []).forEach((url, index) => {
    choices.push({
      url,
      label: `场景成片 ${index + 1}`
    });
  });
  return choices;
}

function formatImageSizeText(width, height) {
  if (!width || !height) {
    return "";
  }
  return `${width} × ${height}`;
}

function buildPreviewUrls(current, sceneImageUrls) {
  if (!current) {
    return [];
  }
  return Array.isArray(sceneImageUrls) && sceneImageUrls.includes(current)
    ? sceneImageUrls
    : [current];
}

function buildStageSteps(status, hasHairPreview, completedSceneCount) {
  const steps = STAGE_LABELS.map((label) => ({
    label,
    state: "pending"
  }));

  steps[0].state = "done";

  if (status === "hair_generating") {
    steps[1].state = "active";
  } else if (hasHairPreview || completedSceneCount > 0 || isTerminalStatus(status)) {
    steps[1].state = "done";
  }

  if (completedSceneCount >= 1) {
    steps[2].state = "done";
  } else if (status === "scene_generating") {
    steps[2].state = "active";
  }

  if (completedSceneCount >= 2) {
    steps[3].state = "done";
  } else if (status === "scene_partial") {
    steps[3].state = "active";
  }

  if (status === "succeeded") {
    steps[4].state = "done";
  } else if (status === "failed") {
    const failureIndex = completedSceneCount > 0 ? Math.min(3, completedSceneCount + 1) : (hasHairPreview ? 2 : 1);
    steps[failureIndex].state = "failed";
  }

  return steps;
}

function getProgressPercent(status, elapsedSeconds, hasHairPreview, completedSceneCount) {
  if (status === "succeeded") {
    return 100;
  }
  if (status === "failed") {
    if (completedSceneCount >= 1) {
      return 86;
    }
    if (hasHairPreview) {
      return 46;
    }
    return 18;
  }
  if (status === "hair_generating") {
    return Math.min(34, 14 + Math.round(elapsedSeconds * 0.7));
  }
  if (status === "hair_ready") {
    return 42;
  }
  if (status === "scene_generating") {
    return Math.min(74, 54 + Math.round(elapsedSeconds * 0.35));
  }
  if (status === "scene_partial") {
    return Math.min(92, 80 + Math.round(elapsedSeconds * 0.18));
  }
  return MIN_VISIBLE_PROGRESS;
}

function getProgressStage(status, hasHairPreview, completedSceneCount) {
  if (status === "hair_generating") {
    return "正在生成仅换发型预览图";
  }
  if (status === "hair_ready") {
    return "发型预览已返回，正在准备场景生成";
  }
  if (status === "scene_generating") {
    return hasHairPreview ? "正在生成第 1 张场景成片" : "正在准备场景成片";
  }
  if (status === "scene_partial") {
    return completedSceneCount >= 1 ? "第 1 张场景成片已返回，正在生成第 2 张" : "正在生成场景成片";
  }
  if (status === "succeeded") {
    return "两张场景成片已全部返回";
  }
  if (status === "failed") {
    if (completedSceneCount > 0) {
      return "已返回部分结果，本次任务未完整完成";
    }
    if (hasHairPreview) {
      return "发型预览已返回，但场景生成失败";
    }
    return "本次任务未能完成";
  }
  return "正在排队准备生成";
}

function buildStatusHint(status, remainingSeconds, hasHairPreview, completedSceneCount) {
  if (status === "failed") {
    if (completedSceneCount > 0 || hasHairPreview) {
      return "当前保留已生成内容，你可以先保存，再返回首页重新生成。";
    }
    return "这次任务没有顺利完成，可以返回首页重新生成。";
  }
  if (status === "succeeded") {
    return "发型预览与 2 张场景成片都已经准备完成。";
  }
  if (status === "hair_generating") {
    return "系统先只改发型，确保人物身份稳定后再继续做场景。";
  }
  if (status === "hair_ready") {
    return "发型预览已准备好，接下来会继续生成两张场景成片。";
  }
  if (status === "scene_generating") {
    return `正在生成第 1 张场景成片，预计还需 ${remainingSeconds} 秒。`;
  }
  if (status === "scene_partial") {
    return `第 1 张已经可以先看，预计还需 ${remainingSeconds} 秒完成第 2 张。`;
  }
  return "任务已进入队列，生成完成后会自动刷新。";
}

Page({
  data: {
    status: "pending",
    statusLabel: getStatusLabel("pending"),
    job: null,
    uploadUrl: "",
    hairPreviewUrl: "",
    resultImageUrl: "",
    resultImageUrls: [],
    completedSceneCount: 0,
    mediaExpired: false,
    mediaExpiresAt: "",
    resultImageLoaded: false,
    resultImageDisplayMode: "aspectFit",
    resultImageSizeText: "",
    imageLoadingText: getImageLoadingText("pending", false, 0),
    progressPercent: MIN_VISIBLE_PROGRESS,
    elapsedSeconds: 0,
    remainingSeconds: ESTIMATED_TOTAL_SECONDS,
    estimatedTotalSeconds: ESTIMATED_TOTAL_SECONDS,
    progressStage: "正在排队准备生成",
    progressHint: "先生成发型预览，再继续生成 2 张场景成片",
    stageSteps: buildStageSteps("pending", false, 0)
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
      statusLabel: getStatusLabel(initialStatus, 0),
      imageLoadingText: getImageLoadingText(initialStatus, false, 0),
      stageSteps: buildStageSteps(initialStatus, false, 0),
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
      imageUrl: this.data.resultImageUrl || this.data.hairPreviewUrl || this.data.uploadUrl || ""
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
    const hasHairPreview = !!this.data.hairPreviewUrl;
    const completedSceneCount = this.data.completedSceneCount || 0;

    const createdAtMs = this.jobCreatedAtMs || Date.now();
    const elapsedSeconds = Math.max(0, Math.floor((Date.now() - createdAtMs) / 1000));
    const progressPercent = getProgressPercent(
      this.data.status,
      elapsedSeconds,
      hasHairPreview,
      completedSceneCount
    );
    const remainingSeconds = isTerminalStatus(this.data.status)
      ? 0
      : Math.max(0, ESTIMATED_TOTAL_SECONDS - elapsedSeconds);

    this.setData({
      elapsedSeconds,
      remainingSeconds,
      progressPercent,
      progressStage: getProgressStage(this.data.status, hasHairPreview, completedSceneCount),
      progressHint: buildStatusHint(
        this.data.status,
        remainingSeconds,
        hasHairPreview,
        completedSceneCount
      ),
      stageSteps: buildStageSteps(this.data.status, hasHairPreview, completedSceneCount)
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
    const nextHairPreviewUrl = job.hair_preview_url || "";
    const nextSceneUrls = Array.isArray(job.result_image_urls) ? job.result_image_urls : [];
    const nextHeroImageUrl = job.result_image_url || nextHairPreviewUrl || "";
    const nextCompletedSceneCount = Number(job.completed_scene_count || nextSceneUrls.length || 0);
    const nextState = {};
    let nextHeroImageInfoUrl = "";

    if (this.data.status !== job.status || this.data.completedSceneCount !== nextCompletedSceneCount) {
      nextState.status = job.status;
      nextState.statusLabel = getStatusLabel(job.status, nextCompletedSceneCount);
      nextState.imageLoadingText = getImageLoadingText(
        job.status,
        !!nextHairPreviewUrl,
        nextCompletedSceneCount
      );
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

    if (this.data.hairPreviewUrl !== nextHairPreviewUrl) {
      nextState.hairPreviewUrl = nextHairPreviewUrl;
    }

    if (this.data.mediaExpired !== !!job.media_expired) {
      nextState.mediaExpired = !!job.media_expired;
    }

    if (this.data.mediaExpiresAt !== (job.media_expires_at || "")) {
      nextState.mediaExpiresAt = job.media_expires_at || "";
    }

    if (!arraysEqual(this.data.resultImageUrls, nextSceneUrls)) {
      nextState.resultImageUrls = nextSceneUrls;
    }

    if (this.data.completedSceneCount !== nextCompletedSceneCount) {
      nextState.completedSceneCount = nextCompletedSceneCount;
    }

    if (this.data.resultImageUrl !== nextHeroImageUrl) {
      nextState.resultImageUrl = nextHeroImageUrl;
      nextState.resultImageLoaded = false;
      nextState.resultImageSizeText = "";
      nextHeroImageInfoUrl = nextHeroImageUrl;
    } else if (!nextHeroImageUrl && this.data.resultImageSizeText) {
      nextState.resultImageSizeText = "";
    }

    if (Object.keys(nextState).length > 0) {
      this.setData(nextState, () => {
        if (nextHeroImageInfoUrl) {
          this.loadResultImageInfo(nextHeroImageInfoUrl);
        }
      });
    } else if (nextHeroImageUrl && !this.data.resultImageSizeText) {
      this.loadResultImageInfo(nextHeroImageUrl);
    }

    this.syncPendingHistory(job, nextHairPreviewUrl, nextSceneUrls, nextCompletedSceneCount);
    this.updateProgressState();
  },

  syncPendingHistory(job, hairPreviewUrl, sceneUrls, completedSceneCount) {
    if (!job || !job.job_id) {
      return;
    }

    if (isTerminalStatus(job.status)) {
      removePendingHistoryJob(job.job_id);
      return;
    }

    upsertPendingHistoryJob({
      job_id: job.job_id,
      status: job.status,
      upload_url: job.upload_url || "",
      hair_preview_url: hairPreviewUrl || "",
      result_image_url: job.result_image_url || hairPreviewUrl || "",
      result_image_urls: sceneUrls || [],
      completed_scene_count: completedSceneCount || 0,
      media_expired: !!job.media_expired,
      media_expires_at: job.media_expires_at || "",
      hairstyle_id: job.hairstyle_id || (this.data.job && this.data.job.hairstyle_id) || "",
      preset_id: job.preset_id || (this.data.job && this.data.job.preset_id) || "",
      hairstyle_name: job.hairstyle_name || (this.data.job && this.data.job.hairstyle_name) || "",
      preset_name: job.preset_name || (this.data.job && this.data.job.preset_name) || "",
      scene_id: job.scene_id || (this.data.job && this.data.job.scene_id) || "",
      scene_name: job.scene_name || (this.data.job && this.data.job.scene_name) || "",
      generator_backend: job.generator_backend || (this.data.job && this.data.job.generator_backend) || "",
      hair_color_selection_mode:
        inferHairColorSelectionMode(job) ||
        (this.data.job && this.data.job.hair_color_selection_mode) ||
        "basic",
      hair_color_tone: job.hair_color_tone || (this.data.job && this.data.job.hair_color_tone) || "",
      hair_color_tone_label: job.hair_color_tone_label || (this.data.job && this.data.job.hair_color_tone_label) || "",
      hair_color_technique: job.hair_color_technique || (this.data.job && this.data.job.hair_color_technique) || "",
      hair_color_technique_label: job.hair_color_technique_label || (this.data.job && this.data.job.hair_color_technique_label) || "",
      hair_color_professional_id:
        job.hair_color_professional_id || (this.data.job && this.data.job.hair_color_professional_id) || "",
      hair_color_professional_brand:
        job.hair_color_professional_brand || (this.data.job && this.data.job.hair_color_professional_brand) || "",
      hair_color_professional_series:
        job.hair_color_professional_series || (this.data.job && this.data.job.hair_color_professional_series) || "",
      hair_color_professional_series_label:
        job.hair_color_professional_series_label || (this.data.job && this.data.job.hair_color_professional_series_label) || "",
      hair_color_professional_code:
        job.hair_color_professional_code || (this.data.job && this.data.job.hair_color_professional_code) || "",
      hair_color_professional_note:
        job.hair_color_professional_note || (this.data.job && this.data.job.hair_color_professional_note) || "",
      hair_color_professional_hex_estimate:
        job.hair_color_professional_hex_estimate || (this.data.job && this.data.job.hair_color_professional_hex_estimate) || "",
      error_code: job.error_code || "",
      error_message: job.error_message || "",
      created_at: job.created_at || (this.data.job && this.data.job.created_at) || new Date().toISOString(),
      updated_at: job.updated_at || new Date().toISOString()
    });
  },

  handleResultImageLoad() {
    if (!this.data.resultImageLoaded) {
      this.setData({ resultImageLoaded: true });
    }
  },

  loadResultImageInfo(imageUrl) {
    if (!imageUrl) {
      return;
    }

    this.resultImageInfoUrl = imageUrl;
    wx.getImageInfo({
      src: imageUrl,
      success: (result) => {
        if (this.resultImageInfoUrl !== imageUrl) {
          return;
        }
        const sizeText = formatImageSizeText(result.width, result.height);
        if (sizeText && this.data.resultImageSizeText !== sizeText) {
          this.setData({ resultImageSizeText: sizeText });
        }
      },
      fail: () => {
        if (this.resultImageInfoUrl === imageUrl && this.data.resultImageSizeText) {
          this.setData({ resultImageSizeText: "" });
        }
      }
    });
  },

  openImagePreview(current) {
    if (!current) {
      return;
    }
    wx.previewImage({
      current,
      urls: buildPreviewUrls(current, this.data.resultImageUrls)
    });
  },

  setResultImageDisplayMode(event) {
    const mode = event.currentTarget.dataset.mode;
    if (mode !== "aspectFit" && mode !== "aspectFill") {
      return;
    }
    if (this.data.resultImageDisplayMode === mode) {
      return;
    }
    this.setData({ resultImageDisplayMode: mode });
  },

  previewHeroResult() {
    this.openImagePreview(this.data.resultImageUrl || this.data.hairPreviewUrl);
  },

  previewResult(event) {
    const current = event.currentTarget.dataset.url;
    this.openImagePreview(current);
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
    const currentResult = this.data.resultImageUrl || this.data.hairPreviewUrl;
    if (!this.data.uploadUrl || !currentResult) {
      return;
    }
    wx.previewImage({
      current: currentResult,
      urls: [this.data.uploadUrl, currentResult]
    });
  },

  async saveImage() {
    const saveChoices = buildSaveChoices(
      this.data.hairPreviewUrl,
      this.data.resultImageUrls
    );

    if (!saveChoices.length && this.data.resultImageUrl) {
      saveChoices.push({
        url: this.data.resultImageUrl,
        label: "当前结果图"
      });
    }

    if (!saveChoices.length) {
      return;
    }

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
