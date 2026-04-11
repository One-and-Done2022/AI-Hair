const { ensureLogin } = require("../../utils/auth");
const { getFriendlyUploadError, showError } = require("../../utils/errors");
const { buildHairColorDisplay } = require("../../utils/hair-color");
const { request } = require("../../utils/request");
const {
  clearRecommendationCache,
  ensureCurrentUpload,
  ensureRecommendationFromCurrentUpload,
  getCachedRecommendation,
  getCachedUpload,
  getCurrentImagePath,
  prepareImageForUpload,
  setCurrentImagePath
} = require("../../utils/recommendation");
const {
  readCreationDraft,
  updateCreationDraft
} = require("../../utils/creation-draft");
const { mergePendingHistoryJobs } = require("../../utils/pending-history");

function formatFileSize(bytes) {
  if (!bytes || bytes <= 0) {
    return "0KB";
  }
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))}KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(bytes >= 10 * 1024 * 1024 ? 0 : 1)}MB`;
}

function getRecommendationGender(draft, recommendation) {
  const draftGender =
    (draft.hairstyle && draft.hairstyle.gender) ||
    draft.gender ||
    "female";
  if (
    recommendation &&
    recommendation.recommended_hairstyles &&
    recommendation.recommended_hairstyles[draftGender] &&
    recommendation.recommended_hairstyles[draftGender].length
  ) {
    return draftGender;
  }
  if (
    recommendation &&
    recommendation.recommended_hairstyles &&
    recommendation.recommended_hairstyles.female &&
    recommendation.recommended_hairstyles.female.length
  ) {
    return "female";
  }
  return "male";
}

function parseTimestamp(value) {
  if (!value) {
    return 0;
  }
  const normalized = String(value).replace(/\+00:00$/, "Z");
  const timestamp = Date.parse(normalized);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function buildHistoryShowcases(items) {
  return (items || [])
    .filter((item) => item && item.status === "succeeded" && (item.result_image_url || item.hair_preview_url))
    .sort((left, right) => parseTimestamp(right.created_at) - parseTimestamp(left.created_at))
    .slice(0, 6)
    .map((item) => {
      const hairColorDisplay = buildHairColorDisplay(item);
      return {
      id: item.job_id,
      job_id: item.job_id,
      title: `${item.hairstyle_name || "发型"} · ${item.scene_name || "场景"}`,
      hair_color_mode_label: hairColorDisplay.mode_label,
      hair_color_primary_label: hairColorDisplay.primary_label,
      summary: hairColorDisplay.secondary_label || "",
      cover_url: item.result_image_url || item.hair_preview_url || "",
      created_at: item.created_at || "",
      status: item.status || ""
    };
    });
}

function buildRecommendationCard(recommendation, loading, draft, selectedImage) {
  if (!selectedImage) {
    return {
      recommendationState: "idle",
      recommendationTitle: "AI 照片分析",
      recommendationSummary: "上传后会自动分析你的照片，不会打断你继续选发型和场景。",
      recommendationFaceShape: "",
      recommendationFeatureTags: [],
      recommendationHairstyles: [],
      recommendationScenes: []
    };
  }

  if (loading) {
    return {
      recommendationState: "loading",
      recommendationTitle: "AI 正在分析照片",
      recommendationSummary: "分析完成后会给你推荐更适合的发型和场景。",
      recommendationFaceShape: "",
      recommendationFeatureTags: [],
      recommendationHairstyles: [],
      recommendationScenes: []
    };
  }

  if (!recommendation) {
    return {
      recommendationState: "unavailable",
      recommendationTitle: "AI 分析暂未完成",
      recommendationSummary: "你可以先继续选发型，分析完成后再回来查看推荐。",
      recommendationFaceShape: "",
      recommendationFeatureTags: [],
      recommendationHairstyles: [],
      recommendationScenes: []
    };
  }

  const gender = getRecommendationGender(draft, recommendation);
  const hairstyles =
    (recommendation.recommended_hairstyles &&
      recommendation.recommended_hairstyles[gender]) ||
    [];
  const scenes = recommendation.recommended_scenes || [];
  return {
    recommendationState: "ready",
    recommendationTitle: "AI 已完成照片分析",
    recommendationSummary: recommendation.summary || "已为你准备更合适的发型和场景方向。",
    recommendationFaceShape:
      (recommendation.face_shape && recommendation.face_shape.label) || "",
    recommendationFeatureTags: (recommendation.feature_tags || []).slice(0, 4),
    recommendationHairstyles: hairstyles.slice(0, 3).map((item) => item.name),
    recommendationScenes: scenes.slice(0, 3).map((item) => item.name)
  };
}

function openPageWithFallback(url, fallbackTitle) {
  return new Promise((resolve) => {
    wx.navigateTo({
      url,
      success() {
        resolve(true);
      },
      fail(error) {
        const message = (error && error.errMsg) || "";
        if (message.includes("page stack")) {
          wx.redirectTo({
            url,
            success() {
              resolve(true);
            },
            fail() {
              wx.showToast({
                title: fallbackTitle,
                icon: "none"
              });
              resolve(false);
            }
          });
          return;
        }

        wx.showToast({
          title: message.includes("is not found") ? "推荐页未编译" : fallbackTitle,
          icon: "none"
        });
        resolve(false);
      }
    });
  });
}

Page({
  data: {
    loading: true,
    profileSummary: null,
    showcases: [],
    selectedImage: "",
    selectedHairstyleName: "",
    selectedSceneName: "",
    imagePreparing: false,
    uploadPriming: false,
    uploadReady: false,
    uploadProgress: 0,
    uploadMessage: "",
    uploadInvalid: false,
    recommendationLoading: false,
    recommendationState: "idle",
    recommendationTitle: "AI 照片分析",
    recommendationSummary: "上传后会自动分析你的照片，不会打断你继续选发型和场景。",
    recommendationFaceShape: "",
    recommendationFeatureTags: [],
    recommendationHairstyles: [],
    recommendationScenes: []
  },

  async onLoad() {
    await this.bootstrap();
  },

  onShow() {
    this.syncDraftState();
    if (this.data.selectedImage && !this.data.imagePreparing) {
      this.refreshRecommendation({ silent: true });
    }
  },

  syncDraftState() {
    const draft = readCreationDraft();
    this.setData({
      selectedImage: getCurrentImagePath(),
      selectedHairstyleName: (draft.hairstyle && draft.hairstyle.name) || "",
      selectedSceneName: (draft.scene && draft.scene.name) || ""
    });
  },

  async bootstrap() {
    this.setData({ loading: true });
    try {
      await ensureLogin();
      const [historyPayload, profileSummary] = await Promise.all([
        request({ url: "/api/history" }).catch(() => ({ items: [] })),
        request({ url: "/api/me" }).catch(() => null)
      ]);

      const selectedImage = getCurrentImagePath();
      const cachedUpload = selectedImage ? getCachedUpload(selectedImage) : null;
      const draft = readCreationDraft();
      const cachedRecommendation =
        (cachedUpload && getCachedRecommendation(cachedUpload.upload_id)) ||
        getCachedRecommendation() ||
        null;

      this.setData({
        loading: false,
        profileSummary,
        showcases: buildHistoryShowcases(mergePendingHistoryJobs((historyPayload && historyPayload.items) || [])),
        selectedImage,
        selectedHairstyleName: (draft.hairstyle && draft.hairstyle.name) || "",
        selectedSceneName: (draft.scene && draft.scene.name) || "",
        uploadReady: !!cachedUpload,
        uploadPriming: false,
        uploadProgress: cachedUpload ? 100 : 0,
        uploadMessage: selectedImage
          ? cachedUpload
            ? "照片已上传完成，可继续创作"
            : "照片已选择，可继续创作"
          : "",
        ...buildRecommendationCard(cachedRecommendation, false, draft, selectedImage)
      });

      if (selectedImage) {
        this.refreshRecommendation({ silent: true });
      }
    } catch (error) {
      this.setData({ loading: false });
      showError(error, { fallback: "加载首页失败，请稍后再试" });
    }
  },

  async refreshRecommendation({ silent = true } = {}) {
    const selectedImage = this.data.selectedImage || getCurrentImagePath();
    const draft = readCreationDraft();
    if (!selectedImage) {
      this.setData(buildRecommendationCard(null, false, draft, ""));
      return;
    }

    const cachedUpload = getCachedUpload(selectedImage);
    const cachedRecommendation =
      (cachedUpload && getCachedRecommendation(cachedUpload.upload_id)) ||
      getCachedRecommendation();
    if (cachedRecommendation) {
      this.setData(buildRecommendationCard(cachedRecommendation, false, draft, selectedImage));
      return;
    }

    this.setData({
      recommendationLoading: true,
      ...buildRecommendationCard(null, true, draft, selectedImage)
    });

    try {
      const recommendation = await ensureRecommendationFromCurrentUpload({ silent });
      const latestImage = this.data.selectedImage || getCurrentImagePath();
      if (!latestImage || latestImage !== selectedImage) {
        return;
      }
      this.setData({
        recommendationLoading: false,
        ...buildRecommendationCard(recommendation, false, readCreationDraft(), latestImage)
      });
    } catch (error) {
      if (!silent) {
        showError(error, { fallback: "AI 分析失败，请稍后再试" });
      }
      const latestImage = this.data.selectedImage || getCurrentImagePath();
      if (!latestImage || latestImage !== selectedImage) {
        return;
      }
      this.setData({
        recommendationLoading: false,
        ...buildRecommendationCard(null, false, readCreationDraft(), latestImage)
      });
    }
  },

  openExampleDetail(event) {
    const jobId = event.currentTarget.dataset.jobId;
    const id = event.currentTarget.dataset.id;
    if (jobId) {
      wx.navigateTo({
        url: `/pages/result/index?jobId=${jobId}`
      });
      return;
    }
    if (!id) {
      return;
    }
    wx.navigateTo({
      url: `/pages/examples/index?id=${id}`
    });
  },

  openImageSource() {
    wx.showActionSheet({
      itemList: ["手机自拍", "从相册选择"],
      success: ({ tapIndex }) => {
        if (tapIndex === 0) {
          this.takeSelfie();
          return;
        }
        if (tapIndex === 1) {
          this.chooseImage();
        }
      }
    });
  },

  chooseImage() {
    wx.chooseImage({
      count: 1,
      sizeType: ["compressed"],
      sourceType: ["album"],
      success: (result) => {
        const filePath = result.tempFilePaths[0];
        this.applySelectedImage(filePath);
      }
    });
  },

  takeSelfie() {
    wx.navigateTo({
      url: "/pages/capture/index",
      success: (result) => {
        result.eventChannel.on("captured", (payload) => {
          if (payload && payload.filePath) {
            this.applySelectedImage(payload.filePath);
          }
        });
      }
    });
  },

  previewImage() {
    if (!this.data.selectedImage) {
      return;
    }
    wx.previewImage({
      urls: [this.data.selectedImage]
    });
  },

  async applySelectedImage(filePath) {
    if (!filePath) {
      return;
    }

    const selectionToken = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    this.currentImageSelectionToken = selectionToken;
    clearRecommendationCache();
    setCurrentImagePath(filePath);
    updateCreationDraft({ imagePath: filePath });

    this.setData({
      selectedImage: filePath,
      imagePreparing: true,
      uploadPriming: false,
      uploadReady: false,
      uploadProgress: 0,
      uploadInvalid: false,
      uploadMessage: "正在优化图片大小",
      recommendationLoading: false,
      ...buildRecommendationCard(null, false, readCreationDraft(), filePath)
    });

    try {
      const prepared = await prepareImageForUpload(filePath);
      if (this.currentImageSelectionToken !== selectionToken) {
        return;
      }

      const preparedPath = prepared.filePath || filePath;
      setCurrentImagePath(preparedPath);
      updateCreationDraft({ imagePath: preparedPath });
      this.setData({
        selectedImage: preparedPath,
        imagePreparing: false,
        uploadPriming: true,
        uploadReady: false,
        uploadProgress: 0,
        uploadInvalid: false,
        uploadMessage: prepared.compressed
          ? `已压缩 ${formatFileSize(prepared.originalSize)} -> ${formatFileSize(prepared.finalSize)}`
          : "图片已选择，正在预上传"
      });
      this.primeUpload(preparedPath, selectionToken, prepared);
    } catch (error) {
      if (this.currentImageSelectionToken !== selectionToken) {
        return;
      }
      this.setData({
        imagePreparing: false,
        uploadPriming: false,
        uploadReady: false,
        uploadInvalid: false,
        uploadProgress: 0,
        uploadMessage: "图片已选择，可继续创作"
      });
    }
  },

  async primeUpload(localPath, selectionToken, prepared = null) {
    if (!localPath) {
      return;
    }

    const compressionPrefix =
      prepared && prepared.compressed
        ? `已压缩至 ${formatFileSize(prepared.finalSize)}，`
        : "";

    this.setData({
      uploadPriming: true,
      uploadReady: false,
      uploadProgress: 0,
      uploadInvalid: false,
      uploadMessage: `${compressionPrefix}正在预上传`
    });

    try {
      await ensureCurrentUpload(localPath, {
        onProgress: (progressEvent) => {
          if (
            this.currentImageSelectionToken !== selectionToken ||
            this.data.selectedImage !== localPath
          ) {
            return;
          }
          const progress = Math.max(0, Math.min(100, Number(progressEvent.progress || 0)));
          this.setData({
            uploadPriming: progress < 100,
            uploadReady: progress >= 100,
            uploadProgress: progress,
            uploadInvalid: false,
            uploadMessage:
              progress >= 100
                ? `${compressionPrefix}照片已上传完成`
                : `${compressionPrefix}正在预上传 ${progress}%`
          });
        }
      });

      if (
        this.currentImageSelectionToken !== selectionToken ||
        this.data.selectedImage !== localPath
      ) {
        return;
      }

      this.setData({
        uploadPriming: false,
        uploadReady: true,
        uploadProgress: 100,
        uploadInvalid: false,
        uploadMessage: `${compressionPrefix}照片已上传完成，可继续创作`
      });
      this.refreshRecommendation({ silent: true });
    } catch (error) {
      if (
        this.currentImageSelectionToken !== selectionToken ||
        this.data.selectedImage !== localPath
      ) {
        return;
      }

      const uploadError = getFriendlyUploadError(error);
      const uploadInvalid = !!uploadError;
      this.setData({
        uploadPriming: false,
        uploadReady: false,
        uploadProgress: 0,
        uploadInvalid,
        uploadMessage: uploadInvalid
          ? "照片未通过校验，请重新选择"
          : `${compressionPrefix}预上传失败，稍后会自动重试`
      });

      if (uploadError) {
        showError(error, { preferModal: true });
      }
    }
  },

  openRecommendation() {
    if (!this.data.selectedImage) {
      wx.showToast({
        title: "请先上传照片",
        icon: "none"
      });
      return Promise.resolve(false);
    }
    return openPageWithFallback("/pages/recommend/index", "打开推荐页失败");
  },

  goNext() {
    if (!this.data.selectedImage) {
      wx.showToast({
        title: "请先上传照片",
        icon: "none"
      });
      return;
    }
    if (this.data.imagePreparing) {
      wx.showToast({
        title: "图片处理中，请稍候",
        icon: "none"
      });
      return;
    }
    if (this.data.uploadInvalid) {
      wx.showToast({
        title: "请先更换合格照片",
        icon: "none"
      });
      return;
    }

    wx.navigateTo({
      url: "/pages/templates/index"
    });
  }
});
