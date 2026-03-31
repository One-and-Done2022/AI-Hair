const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const { request } = require("../../utils/request");
const {
  ensureCurrentUpload,
  getCurrentImagePath
} = require("../../utils/recommendation");

function findById(items, id) {
  if (!id) {
    return null;
  }
  return items.find((item) => item.id === id) || null;
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

function buildHairstyleMeta(item) {
  if (!item) {
    return "";
  }
  return item.category_label || item.style_line_label || "";
}

const STYLE_LINE_OPTIONS = [
  { id: "all", label: "全部场景" },
  { id: "realistic_editorial", label: "写实写真" },
  { id: "fashion_editorial", label: "时尚大片" }
];

function decorateScene(item) {
  return {
    ...item,
    shortTags: (item.tags || []).slice(0, 2),
    primaryTag: (item.tags || [])[0] || ""
  };
}

function buildVisibleScenes(scenes, styleLine) {
  return scenes.filter((item) => {
    if (styleLine !== "all" && item.style_line !== styleLine) {
      return false;
    }
    return true;
  });
}

function resolveVisibleSceneSelection(scenes, styleLine, selectedSceneId) {
  const visibleScenes = buildVisibleScenes(scenes, styleLine);
  const selectedScene = findById(visibleScenes, selectedSceneId) || visibleScenes[0] || null;
  return {
    visibleScenes,
    selectedSceneId: selectedScene ? selectedScene.id : "",
    selectedSceneName: selectedScene ? selectedScene.name : ""
  };
}

function toOptionItems(items) {
  return (items || []).map((item) => ({ id: item, label: item }));
}

function findBackendById(items, id) {
  return findById(items || [], id);
}

function formatGenerationBackends(backends = []) {
  return backends.map((item) => {
    if (item.id === "basic") {
      return {
        ...item,
        description: "用基础模型，返回 1 张换发预览和 2 张场景成片"
      };
    }
    if (item.id === "premium") {
      return {
        ...item,
        description: "用高级模型，返回 1 张换发预览和 2 张场景成片"
      };
    }
    return item;
  });
}

function buildGenerationSelection(backends, cachedOptions = {}) {
  const availableBackends = (backends || []).filter((item) => item.enabled);
  const fallbackBackends = availableBackends.length ? availableBackends : backends || [];
  const selectedBackend =
    findBackendById(fallbackBackends, cachedOptions.generator_backend) ||
    fallbackBackends[0] ||
    null;
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
    loading: true,
    selectedImage: "",
    selectedHairstyle: null,
    selectedHairstyleMeta: "",
    selectedGender: "",
    scenes: [],
    selectedSceneId: "",
    selectedStyleLine: "all",
    styleLineOptions: STYLE_LINE_OPTIONS,
    visibleScenes: [],
    selectedSceneName: "",
    generationBackends: [],
    selectedGeneratorBackend: "",
    selectedAspectRatio: "3:4",
    selectedResolution: "",
    aspectRatioOptions: [],
    resolutionOptions: [],
    advancedOpen: false,
    submitting: false
  },

  async onLoad(options) {
    this.hairstyleId = options.hairstyleId || "";
    this.hairstyleName = decodeText(options.hairstyleName);
    this.gender = options.gender || "";
    await this.loadScenes();
  },

  async loadScenes() {
    const selectedImage = getCurrentImagePath();
    if (!selectedImage) {
      wx.showToast({
        title: "请先上传照片",
        icon: "none"
      });
      wx.switchTab({
        url: "/pages/index/index"
      });
      return;
    }

    this.setData({ loading: true });
    try {
      await ensureLogin();
      const catalog = await request({ url: "/api/templates" });
      const cached = wx.getStorageSync("templateSelection") || {};
      const selectedHairstyle =
        findById(catalog.hairstyles, this.hairstyleId) ||
        findById(catalog.hairstyles, cached.hairstyle && cached.hairstyle.id) ||
        catalog.hairstyles[0] ||
        null;
      if (!selectedHairstyle) {
        wx.redirectTo({
          url: "/pages/templates/index"
        });
        return;
      }

      const selectedScene =
        findById(catalog.scenes, cached.scene && cached.scene.id) ||
        catalog.scenes[0] ||
        null;
      const decoratedScenes = (catalog.scenes || []).map(decorateScene);
      const selectedStyleLine = (selectedHairstyle && selectedHairstyle.style_line) || "all";
      const generationBackends = formatGenerationBackends(catalog.generation_backends || []);
      const generationSelection = buildGenerationSelection(
        generationBackends,
        wx.getStorageSync("generationOptions") || {}
      );

      const sceneSelection = resolveVisibleSceneSelection(
        decoratedScenes,
        selectedStyleLine,
        selectedScene ? selectedScene.id : ""
      );

      this.setData({
        selectedImage,
        selectedHairstyle: selectedHairstyle
          ? selectedHairstyle
          : {
              id: this.hairstyleId,
              name: this.hairstyleName,
              gender: this.gender
            },
        selectedHairstyleMeta: buildHairstyleMeta(selectedHairstyle),
        selectedGender: selectedHairstyle ? selectedHairstyle.gender : this.gender,
        scenes: decoratedScenes,
        selectedStyleLine,
        visibleScenes: sceneSelection.visibleScenes,
        selectedSceneId: sceneSelection.selectedSceneId,
        selectedSceneName: sceneSelection.selectedSceneName,
        generationBackends,
        selectedGeneratorBackend: generationSelection.selectedGeneratorBackend,
        selectedAspectRatio: generationSelection.selectedAspectRatio,
        selectedResolution: generationSelection.selectedResolution,
        aspectRatioOptions: generationSelection.aspectRatioOptions,
        resolutionOptions: generationSelection.resolutionOptions
      });
    } catch (error) {
      showError(error, { fallback: "加载失败" });
    } finally {
      this.setData({ loading: false });
    }
  },

  selectScene(event) {
    const selectedId = event.currentTarget.dataset.id;
    const selectedScene = findById(this.data.scenes, selectedId);
    if (!selectedScene) {
      return;
    }
    this.setData({
      selectedSceneId: selectedId,
      selectedSceneName: selectedScene ? selectedScene.name : ""
    });
    wx.setStorageSync("templateSelection", {
      hairstyle: this.data.selectedHairstyle,
      scene: selectedScene,
      gender: (this.data.selectedHairstyle && this.data.selectedHairstyle.gender) || this.data.selectedGender || "male"
    });
  },

  previewScene(event) {
    const selectedId = event.currentTarget.dataset.id;
    const selectedScene = findById(this.data.scenes, selectedId);
    if (!selectedScene || !selectedScene.cover_url) {
      return;
    }
    wx.previewImage({
      current: selectedScene.cover_url,
      urls: [selectedScene.cover_url]
    });
  },

  selectStyleLine(event) {
    const styleLine = event.currentTarget.dataset.styleLine || "all";
    const sceneSelection = resolveVisibleSceneSelection(
      this.data.scenes,
      styleLine,
      this.data.selectedSceneId
    );
    this.setData({
      selectedStyleLine: styleLine,
      visibleScenes: sceneSelection.visibleScenes,
      selectedSceneId: sceneSelection.selectedSceneId,
      selectedSceneName: sceneSelection.selectedSceneName
    });
  },

  goBackStep() {
    wx.navigateBack();
  },

  toggleAdvanced() {
    this.setData({
      advancedOpen: !this.data.advancedOpen
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

  async createJob() {
    const selectedHairstyle = this.data.selectedHairstyle;
    const selectedScene = findById(this.data.scenes, this.data.selectedSceneId);

    if (!selectedHairstyle || !selectedScene) {
      wx.showToast({
        title: "请先选择场景",
        icon: "none"
      });
      return;
    }

    if (!this.data.selectedImage) {
      wx.showToast({
        title: "请先上传照片",
        icon: "none"
      });
      return;
    }

    wx.setStorageSync("templateSelection", {
      hairstyle: selectedHairstyle,
      scene: selectedScene,
      gender: selectedHairstyle.gender || this.data.selectedGender || "male"
    });

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
          hairstyle_id: selectedHairstyle.id,
          scene_id: selectedScene.id,
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
  }
});
