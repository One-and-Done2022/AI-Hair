const { ensureLogin } = require("../../utils/auth");
const { getErrorMessage, getFriendlyUploadError, showError } = require("../../utils/errors");
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
const { findCatalogHairstyle } = require("../../utils/template-selection");

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

function padDateUnit(value) {
  return String(value).padStart(2, "0");
}

function buildLocalDateKey(timestamp) {
  if (!timestamp) {
    return "";
  }
  const date = new Date(timestamp);
  return `${date.getFullYear()}-${padDateUnit(date.getMonth() + 1)}-${padDateUnit(date.getDate())}`;
}

function findById(items, id) {
  if (!id) {
    return null;
  }
  return (items || []).find((item) => item.id === id) || null;
}

function buildShowcaseHairKey(item) {
  if (!item) {
    return "";
  }
  return (
    item.preset_id ||
    item.hairstyle_id ||
    item.hairstyle_name ||
    item.job_id ||
    ""
  );
}

function pickPreferredBobShowcase(items) {
  const keyword = "一刀切波波头";
  const candidates = (items || []).filter((item) => {
    return item && String(item.hairstyle_name || "").includes(keyword);
  });
  if (!candidates.length) {
    return null;
  }

  const todayKey = buildLocalDateKey(Date.now());
  const targetTime = new Date(`${todayKey}T13:30:00`).getTime();
  const sameDayCandidates = candidates.filter((item) => {
    return buildLocalDateKey(parseTimestamp(item.created_at)) === todayKey;
  });
  const pool = sameDayCandidates.length ? sameDayCandidates : candidates;

  return pool
    .slice()
    .sort((left, right) => {
      const leftDiff = Math.abs(parseTimestamp(left.created_at) - targetTime);
      const rightDiff = Math.abs(parseTimestamp(right.created_at) - targetTime);
      if (leftDiff !== rightDiff) {
        return leftDiff - rightDiff;
      }
      return parseTimestamp(right.created_at) - parseTimestamp(left.created_at);
    })[0];
}

function buildCuratedShowcaseItems(items) {
  const succeededItems = (items || [])
    .filter((item) => item && item.status === "succeeded" && (item.result_image_url || item.hair_preview_url))
    .sort((left, right) => parseTimestamp(right.created_at) - parseTimestamp(left.created_at));

  const preferredBob = pickPreferredBobShowcase(succeededItems);
  const prioritizedItems = preferredBob
    ? [preferredBob].concat(
        succeededItems.filter((item) => item && item.job_id !== preferredBob.job_id)
      )
    : succeededItems;

  const seenHairKeys = new Set();
  const curated = [];
  prioritizedItems.forEach((item) => {
    if (curated.length >= 6) {
      return;
    }
    const hairKey = buildShowcaseHairKey(item);
    if (!hairKey || seenHairKeys.has(hairKey)) {
      return;
    }
    seenHairKeys.add(hairKey);
    curated.push(item);
  });

  return curated.sort((left, right) => parseTimestamp(right.created_at) - parseTimestamp(left.created_at));
}

function isSameHairColorSelection(showcase, draft) {
  const showcaseMode = showcase.hair_color_selection_mode || "basic";
  const draftMode = draft.hair_color_selection_mode || "basic";
  if (showcaseMode !== draftMode) {
    return false;
  }

  if (showcaseMode === "professional") {
    return (
      (showcase.hair_color_professional_id || "") ===
      (draft.hair_color_professional_id || "")
    );
  }

  return (
    (showcase.hair_color_tone || "") === (draft.hair_color_tone || "") &&
    (showcase.hair_color_technique || "") === (draft.hair_color_technique || "")
  );
}

function isActiveShowcase(showcase, draft) {
  if (!showcase || !draft || !draft.hairstyle || !draft.scene) {
    return false;
  }
  const showcaseHairKey = showcase.preset_id || showcase.hairstyle_id || "";
  const draftHairKey = draft.hairstyle.preset_id || draft.hairstyle.id || "";
  if (!showcaseHairKey || !draftHairKey || showcaseHairKey !== draftHairKey) {
    return false;
  }
  if ((showcase.scene_id || "") !== (draft.scene.id || "")) {
    return false;
  }
  return isSameHairColorSelection(showcase, draft);
}

function buildFixedShowcases(items, draft = {}) {
  return buildCuratedShowcaseItems(items)
    .map((item) => {
      const hairColorDisplay = buildHairColorDisplay(item);
      const isActive = isActiveShowcase(item, draft);
      return {
        id: item.job_id,
        job_id: item.job_id,
        title: item.hairstyle_name || "发型模板",
        scene_name: item.scene_name || "场景模板",
        hair_color_mode_label: hairColorDisplay.mode_label,
        hair_color_primary_label: hairColorDisplay.primary_label,
        summary: hairColorDisplay.secondary_label || "点击套用这组搭配",
        cover_url: item.result_image_url || item.hair_preview_url || "",
        created_at: item.created_at || "",
        status: item.status || "",
        hairstyle_id: item.hairstyle_id || "",
        preset_id: item.preset_id || "",
        generator_backend: item.generator_backend || "",
        aspect_ratio: item.aspect_ratio || "",
        resolution: item.resolution || "",
        hair_color_selection_mode: item.hair_color_selection_mode || "basic",
        hair_color_tone: item.hair_color_tone || "",
        hair_color_tone_label: item.hair_color_tone_label || "",
        hair_color_technique: item.hair_color_technique || "",
        hair_color_technique_label: item.hair_color_technique_label || "",
        hair_color_professional_id: item.hair_color_professional_id || "",
        hair_color_professional_brand: item.hair_color_professional_brand || "",
        hair_color_professional_series: item.hair_color_professional_series || "",
        hair_color_professional_series_label: item.hair_color_professional_series_label || "",
        hair_color_professional_code: item.hair_color_professional_code || "",
        hair_color_professional_note: item.hair_color_professional_note || "",
        hair_color_professional_hex_estimate: item.hair_color_professional_hex_estimate || "",
        scene_id: item.scene_id || "",
        is_active: isActive,
        action_label: isActive ? "已套用" : "换这套"
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
    const nextData = {
      selectedImage: getCurrentImagePath(),
      selectedHairstyleName: (draft.hairstyle && draft.hairstyle.name) || "",
      selectedSceneName: (draft.scene && draft.scene.name) || ""
    };
    if (this.showcaseSourceItems) {
      nextData.showcases = buildFixedShowcases(this.showcaseSourceItems, draft);
    }
    this.setData(nextData);
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
      const mergedHistoryItems = mergePendingHistoryJobs((historyPayload && historyPayload.items) || []);
      this.showcaseSourceItems = mergedHistoryItems;
      const cachedRecommendation =
        (cachedUpload && getCachedRecommendation(cachedUpload.upload_id)) ||
        getCachedRecommendation() ||
        null;

      this.setData({
        loading: false,
        profileSummary: profileSummary ? { ...profileSummary, provider_alerts: [] } : null,
        showcases: buildFixedShowcases(mergedHistoryItems, draft),
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

  async ensureTemplateCatalog() {
    if (this.templateCatalog) {
      return this.templateCatalog;
    }
    const catalog = await request({ url: "/api/templates" });
    this.templateCatalog = catalog;
    return catalog;
  },

  async applyShowcaseTemplate(event) {
    const id = event.currentTarget.dataset.id;
    const showcase = this.data.showcases.find((item) => item.id === id);
    if (!showcase) {
      return;
    }

    wx.showLoading({ title: "正在套用" });
    try {
      const catalog = await this.ensureTemplateCatalog();
      const hairstyle = findCatalogHairstyle(catalog, showcase);
      const scene = findById(catalog.scenes || [], showcase.scene_id);

      if (!hairstyle || !scene) {
        wx.showToast({
          title: "模板内容已失效",
          icon: "none"
        });
        return;
      }

      updateCreationDraft({
        hairstyle,
        scene,
        gender: hairstyle.gender || readCreationDraft().gender || "female",
        generator_backend: showcase.generator_backend || "",
        aspect_ratio: showcase.aspect_ratio || "",
        resolution: showcase.resolution || "",
        hair_color_selection_mode: showcase.hair_color_selection_mode || "basic",
        hair_color_tone: showcase.hair_color_tone || "",
        hair_color_tone_label: showcase.hair_color_tone_label || "",
        hair_color_technique: showcase.hair_color_technique || "",
        hair_color_technique_label: showcase.hair_color_technique_label || "",
        hair_color_professional_id: showcase.hair_color_professional_id || "",
        hair_color_professional_brand: showcase.hair_color_professional_brand || "",
        hair_color_professional_series: showcase.hair_color_professional_series || "",
        hair_color_professional_series_label: showcase.hair_color_professional_series_label || "",
        hair_color_professional_code: showcase.hair_color_professional_code || "",
        hair_color_professional_note: showcase.hair_color_professional_note || "",
        hair_color_professional_hex_estimate: showcase.hair_color_professional_hex_estimate || ""
      });
      const nextDraft = readCreationDraft();

      this.setData({
        selectedHairstyleName: hairstyle.name || "",
        selectedSceneName: scene.name || "",
        showcases: buildFixedShowcases(this.showcaseSourceItems || [], nextDraft)
      });

      if (this.data.selectedImage && !this.data.imagePreparing && !this.data.uploadInvalid) {
        wx.navigateTo({
          url: "/pages/options/index"
        });
        return;
      }

      wx.showToast({
        title: this.data.selectedImage ? "模板已套用，可继续下一步" : "模板已套用，请先上传照片",
        icon: "none"
      });
    } catch (error) {
      showError(error, { fallback: "套用模板失败，请稍后再试" });
    } finally {
      wx.hideLoading();
    }
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
      const rawErrorMessage = getErrorMessage(error, "预上传失败，请稍后再试");
      this.setData({
        uploadPriming: false,
        uploadReady: false,
        uploadProgress: 0,
        uploadInvalid,
        uploadMessage: uploadInvalid
          ? "照片未通过校验，请重新选择"
          : `${compressionPrefix}预上传失败：${rawErrorMessage}`
      });

      showError(error, {
        fallback: "预上传失败，请稍后再试",
        preferModal: true
      });
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
