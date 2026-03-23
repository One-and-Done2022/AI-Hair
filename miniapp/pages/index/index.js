const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const { request } = require("../../utils/request");
const {
  clearRecommendationCache,
  ensureCurrentUpload,
  ensureRecommendation,
  getCachedRecommendation,
  getCurrentImagePath,
  setCurrentImagePath
} = require("../../utils/recommendation");

function toOptionItems(items) {
  return (items || []).map((item) => ({ id: item, label: item }));
}

function findById(items, id) {
  if (!id) {
    return null;
  }
  return items.find((item) => item.id === id) || null;
}

function getRecommendationGender(selection, selectedHairstyle) {
  if (selectedHairstyle && (selectedHairstyle.gender === "male" || selectedHairstyle.gender === "female")) {
    return selectedHairstyle.gender;
  }
  if (selection && (selection.gender === "male" || selection.gender === "female")) {
    return selection.gender;
  }
  return "female";
}

function findBackendById(items, id) {
  return findById(items || [], id);
}

function buildGenerationSelection(backends, cachedOptions = {}) {
  const availableBackends = (backends || []).filter((item) => item.enabled);
  const fallbackBackends = availableBackends.length ? availableBackends : (backends || []);
  const selectedBackend =
    findBackendById(fallbackBackends, cachedOptions.generator_backend) || fallbackBackends[0] || null;
  const aspectRatios = selectedBackend ? selectedBackend.aspect_ratios || [] : [];
  const resolutions = selectedBackend ? selectedBackend.resolutions || [] : [];
  const selectedAspectRatio =
    (aspectRatios.includes(cachedOptions.aspect_ratio) && cachedOptions.aspect_ratio) ||
    (selectedBackend && selectedBackend.default_aspect_ratio) ||
    aspectRatios[0] ||
    "3:4";
  const selectedResolution = resolutions.length
    ? (
        (resolutions.includes(cachedOptions.resolution) && cachedOptions.resolution) ||
        (selectedBackend && selectedBackend.default_resolution) ||
        resolutions[0]
      )
    : "";

  return {
    selectedBackend,
    selectedGeneratorBackend: selectedBackend ? selectedBackend.id : "",
    selectedAspectRatio,
    selectedResolution,
    aspectRatioOptions: toOptionItems(aspectRatios),
    resolutionOptions: toOptionItems(resolutions)
  };
}

Page({
  data: {
    selectedImage: "",
    selectedHairstyle: null,
    selectedScene: null,
    showcaseItems: [],
    profileSummary: null,
    submitting: false,
    recommendationLoading: false,
    recommendation: null,
    recommendationGender: "female",
    recommendedHairstyles: [],
    recommendedScenes: [],
    recommendationMessage: "",
    bootstrapping: true,
    generationBackends: [],
    selectedGeneratorBackend: "",
    aspectRatioOptions: [],
    resolutionOptions: [],
    selectedAspectRatio: "3:4",
    selectedResolution: "4K"
  },

  async onLoad() {
    await this.bootstrap();
  },

  onShow() {
    this.syncSelection();
  },

  async bootstrap() {
    this.setData({ bootstrapping: true });
    try {
      await ensureLogin();
      const [catalog, profileSummary] = await Promise.all([
        request({ url: "/api/templates" }),
        request({ url: "/api/me" })
      ]);
      this.catalog = catalog;
      const currentImagePath = getCurrentImagePath();
      const cachedSelection = wx.getStorageSync("templateSelection") || {};
      const cachedGenerationOptions = wx.getStorageSync("generationOptions") || {};
      const generationSelection = buildGenerationSelection(
        catalog.generation_backends || [],
        cachedGenerationOptions
      );
      const selectedHairstyle =
        findById(catalog.hairstyles, cachedSelection.hairstyle && cachedSelection.hairstyle.id) ||
        null;
      const selectedScene =
        findById(catalog.scenes, cachedSelection.scene && cachedSelection.scene.id) ||
        null;
      const recommendationGender = getRecommendationGender(cachedSelection, selectedHairstyle);
      if (selectedHairstyle || selectedScene) {
        wx.setStorageSync("templateSelection", {
          hairstyle: selectedHairstyle,
          scene: selectedScene,
          gender:
            (selectedHairstyle && selectedHairstyle.gender) ||
            cachedSelection.gender ||
            "male"
        });
      } else {
        wx.removeStorageSync("templateSelection");
      }
      this.setData({
        showcaseItems: (catalog.hairstyles || []).slice(0, 4).map((item) => ({
          id: item.id,
          name: item.name,
          coverUrl: item.cover_url,
          tag: item.style_line_label || ((item.tags || [])[0] || "风格")
        })),
        selectedImage: currentImagePath,
        profileSummary,
        selectedHairstyle,
        selectedScene,
        recommendationGender,
        generationBackends: catalog.generation_backends || [],
        selectedGeneratorBackend: generationSelection.selectedGeneratorBackend,
        aspectRatioOptions: generationSelection.aspectRatioOptions,
        resolutionOptions: generationSelection.resolutionOptions,
        selectedAspectRatio: generationSelection.selectedAspectRatio,
        selectedResolution: generationSelection.selectedResolution
      });
      wx.setStorageSync("generationOptions", {
        generator_backend: generationSelection.selectedGeneratorBackend,
        aspect_ratio: generationSelection.selectedAspectRatio,
        resolution: generationSelection.selectedResolution
      });
      this.syncRecommendationView({
        recommendation: currentImagePath ? getCachedRecommendation() : null,
        selectedHairstyle,
        selectedScene,
        recommendationGender
      });
    } catch (error) {
      showError(error, { fallback: "加载失败，请稍后再试" });
    } finally {
      this.setData({ bootstrapping: false });
    }
  },

  syncSelection() {
    const selection = wx.getStorageSync("templateSelection") || {};
    const selectedHairstyle = selection.hairstyle || this.data.selectedHairstyle;
    const selectedScene = selection.scene || this.data.selectedScene;
    const recommendationGender = getRecommendationGender(selection, selectedHairstyle);
    this.setData({
      selectedHairstyle,
      selectedScene,
      recommendationGender
    });
    this.syncRecommendationView({
      selectedHairstyle,
      selectedScene,
      recommendationGender
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

  openImageSource() {
    wx.showActionSheet({
      itemList: ["手机自拍", "从相册选择"],
      success: (result) => {
        if (result.tapIndex === 0) {
          this.takeSelfie();
          return;
        }
        if (result.tapIndex === 1) {
          this.chooseImage();
        }
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

  applySelectedImage(filePath) {
    if (!filePath) {
      return;
    }
    clearRecommendationCache();
    setCurrentImagePath(filePath);
    this.setData({
      selectedImage: filePath,
      recommendationLoading: false,
      recommendation: null,
      recommendedHairstyles: [],
      recommendedScenes: [],
      recommendationMessage: ""
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

  buildRecommendedHairstyles(recommendation, gender, selectedHairstyle) {
    if (!recommendation || !this.catalog) {
      return [];
    }
    const hairstyleItems = recommendation.recommended_hairstyles &&
      recommendation.recommended_hairstyles[gender]
      ? recommendation.recommended_hairstyles[gender]
      : [];
    return hairstyleItems
      .map((item) => {
        const full = findById(this.catalog.hairstyles || [], item.id);
        if (!full) {
          return null;
        }
        return {
          ...full,
          reason: (item.reasons || [])[0] || "",
          selected: !!selectedHairstyle && selectedHairstyle.id === full.id
        };
      })
      .filter(Boolean);
  },

  buildRecommendedScenes(recommendation, selectedScene) {
    if (!recommendation || !this.catalog) {
      return [];
    }
    return (recommendation.recommended_scenes || [])
      .map((item) => {
        const full = findById(this.catalog.scenes || [], item.id);
        if (!full) {
          return null;
        }
        return {
          ...full,
          reason: (item.reasons || [])[0] || "",
          selected: !!selectedScene && selectedScene.id === full.id
        };
      })
      .filter(Boolean);
  },

  syncRecommendationView(overrides = {}) {
    const recommendation = Object.prototype.hasOwnProperty.call(overrides, "recommendation")
      ? overrides.recommendation
      : this.data.recommendation;
    const selectedHairstyle = Object.prototype.hasOwnProperty.call(overrides, "selectedHairstyle")
      ? overrides.selectedHairstyle
      : this.data.selectedHairstyle;
    const selectedScene = Object.prototype.hasOwnProperty.call(overrides, "selectedScene")
      ? overrides.selectedScene
      : this.data.selectedScene;
    const recommendationGender = overrides.recommendationGender || this.data.recommendationGender;

    this.setData({
      recommendation: recommendation || null,
      recommendationGender,
      recommendedHairstyles: this.buildRecommendedHairstyles(
        recommendation,
        recommendationGender,
        selectedHairstyle
      ),
      recommendedScenes: this.buildRecommendedScenes(recommendation, selectedScene)
    });
  },

  selectRecommendationGender(event) {
    const gender = event.currentTarget.dataset.gender;
    if (gender !== "male" && gender !== "female") {
      return;
    }
    this.syncRecommendationView({ recommendationGender: gender });
  },

  async runRecommendation() {
    if (!this.data.selectedImage) {
      wx.showToast({
        title: "请先上传照片",
        icon: "none"
      });
      return;
    }

    this.setData({
      recommendationLoading: true,
      recommendationMessage: "正在分析照片并生成推荐"
    });
    try {
      const recommendation = await ensureRecommendation(this.data.selectedImage, { silent: false });
      if (!recommendation) {
        this.setData({
          recommendationLoading: false,
          recommendation: null,
          recommendedHairstyles: [],
          recommendedScenes: [],
          recommendationMessage: "暂时无法完成智能推荐，可继续手动选择"
        });
        return;
      }
      this.setData({
        recommendationLoading: false,
        recommendationMessage: "推荐结果已更新"
      });
      this.syncRecommendationView({ recommendation });
    } catch (error) {
      this.setData({
        recommendationLoading: false,
        recommendationMessage: "推荐失败，可继续手动选择"
      });
      showError(error, {
        fallback: "推荐失败，请稍后再试"
      });
    }
  },

  applyTemplateSelection(nextSelection) {
    const hairstyle = Object.prototype.hasOwnProperty.call(nextSelection, "hairstyle")
      ? nextSelection.hairstyle
      : this.data.selectedHairstyle;
    const scene = Object.prototype.hasOwnProperty.call(nextSelection, "scene")
      ? nextSelection.scene
      : this.data.selectedScene;
    const gender = getRecommendationGender({ gender: this.data.recommendationGender }, hairstyle);

    wx.setStorageSync("templateSelection", {
      hairstyle,
      scene,
      gender
    });
    this.setData({
      selectedHairstyle: hairstyle,
      selectedScene: scene
    });
    this.syncRecommendationView({
      selectedHairstyle: hairstyle,
      selectedScene: scene,
      recommendationGender: gender
    });
  },

  applyRecommendedHairstyle(event) {
    const hairstyleId = event.currentTarget.dataset.id;
    const hairstyle = findById((this.catalog && this.catalog.hairstyles) || [], hairstyleId);
    if (!hairstyle) {
      return;
    }
    this.applyTemplateSelection({ hairstyle });
    wx.showToast({
      title: "已应用推荐发型",
      icon: "success"
    });
  },

  applyRecommendedScene(event) {
    const sceneId = event.currentTarget.dataset.id;
    const scene = findById((this.catalog && this.catalog.scenes) || [], sceneId);
    if (!scene) {
      return;
    }
    this.applyTemplateSelection({ scene });
    wx.showToast({
      title: "已应用推荐场景",
      icon: "success"
    });
  },

  openTemplatePicker() {
    wx.navigateTo({
      url: "/pages/templates/index"
    });
  },

  openScenePicker() {
    const hairstyle = this.data.selectedHairstyle;
    if (!hairstyle) {
      this.openTemplatePicker();
      return;
    }

    wx.navigateTo({
      url:
        `/pages/scenes/index?hairstyleId=${hairstyle.id}` +
        `&hairstyleName=${encodeURIComponent(hairstyle.name || "")}` +
        `&gender=${hairstyle.gender || "male"}`
    });
  },

  selectAspectRatio(event) {
    const aspectRatio = event.currentTarget.dataset.value;
    if (!aspectRatio) {
      return;
    }
    this.setData({ selectedAspectRatio: aspectRatio });
    wx.setStorageSync("generationOptions", {
      generator_backend: this.data.selectedGeneratorBackend,
      aspect_ratio: aspectRatio,
      resolution: this.data.selectedResolution
    });
  },

  selectResolution(event) {
    const resolution = event.currentTarget.dataset.value;
    if (!resolution) {
      return;
    }
    this.setData({ selectedResolution: resolution });
    wx.setStorageSync("generationOptions", {
      generator_backend: this.data.selectedGeneratorBackend,
      aspect_ratio: this.data.selectedAspectRatio,
      resolution
    });
  },

  selectGeneratorBackend(event) {
    const backendId = event.currentTarget.dataset.value;
    const backend = findBackendById(this.data.generationBackends, backendId);
    if (!backend) {
      return;
    }
    if (!backend.enabled) {
      wx.showToast({
        title: "该模型暂未配置",
        icon: "none"
      });
      return;
    }

    const selection = buildGenerationSelection(this.data.generationBackends, {
      generator_backend: backendId
    });
    this.setData({
      selectedGeneratorBackend: selection.selectedGeneratorBackend,
      aspectRatioOptions: selection.aspectRatioOptions,
      resolutionOptions: selection.resolutionOptions,
      selectedAspectRatio: selection.selectedAspectRatio,
      selectedResolution: selection.selectedResolution
    });
    wx.setStorageSync("generationOptions", {
      generator_backend: selection.selectedGeneratorBackend,
      aspect_ratio: selection.selectedAspectRatio,
      resolution: selection.selectedResolution
    });
  },

  async createJob() {
    if (!this.data.selectedImage) {
      wx.showToast({ title: "请先上传照片", icon: "none" });
      return;
    }
    if (!this.data.selectedHairstyle || !this.data.selectedScene) {
      wx.showToast({ title: "请先选择发型和场景", icon: "none" });
      return;
    }

    this.setData({ submitting: true });
    wx.showLoading({ title: "正在提交任务" });
    try {
      await ensureLogin();
      const upload = await ensureCurrentUpload(this.data.selectedImage);
      const job = await request({
        url: "/api/jobs",
        method: "POST",
        data: {
          upload_id: upload.upload_id,
          hairstyle_id: this.data.selectedHairstyle.id,
          scene_id: this.data.selectedScene.id,
          generator_backend: this.data.selectedGeneratorBackend,
          aspect_ratio: this.data.selectedAspectRatio,
          resolution: this.data.selectedResolution || null
        }
      });
      wx.navigateTo({
        url:
          `/pages/result/index?jobId=${job.job_id}` +
          `&status=${job.status}` +
          `&createdAt=${encodeURIComponent(job.created_at || "")}` +
          `&hairstyleName=${encodeURIComponent(job.hairstyle_name)}` +
          `&sceneName=${encodeURIComponent(job.scene_name)}`
      });
    } catch (error) {
      showError(error, {
        fallback: "提交失败，请稍后再试",
        preferModal: true
      });
    } finally {
      wx.hideLoading();
      this.setData({ submitting: false });
    }
  },

  goHistory() {
    wx.switchTab({
      url: "/pages/history/index"
    });
  }
});
