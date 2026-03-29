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
  return (items || []).find((item) => item.id === id) || null;
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

function buildScenePageUrl(hairstyle) {
  if (!hairstyle || !hairstyle.id) {
    return "/pages/scenes/index";
  }
  return (
    `/pages/scenes/index?hairstyleId=${hairstyle.id}` +
    `&hairstyleName=${encodeURIComponent(hairstyle.name || "")}` +
    `&gender=${hairstyle.gender || "female"}`
  );
}

Page({
  data: {
    loading: true,
    selectedImage: "",
    selectedHairstyle: null,
    selectedScene: null,
    generationBackends: [],
    selectedGeneratorBackend: "",
    selectedAspectRatio: "3:4",
    selectedResolution: "",
    aspectRatioOptions: [],
    resolutionOptions: [],
    advancedOpen: false,
    submitting: false
  },

  async onLoad() {
    await this.loadConfirmState();
  },

  async loadConfirmState() {
    const selectedImage = getCurrentImagePath();
    const selection = wx.getStorageSync("templateSelection") || {};
    const cachedHairstyle = selection.hairstyle || null;
    const cachedScene = selection.scene || null;

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

    if (!cachedHairstyle) {
      wx.redirectTo({
        url: "/pages/templates/index"
      });
      return;
    }

    if (!cachedScene) {
      wx.redirectTo({
        url: buildScenePageUrl(cachedHairstyle)
      });
      return;
    }

    this.setData({ loading: true });
    try {
      await ensureLogin();
      const catalog = await request({ url: "/api/templates" });
      const generationBackends = formatGenerationBackends(catalog.generation_backends || []);
      const generationSelection = buildGenerationSelection(
        generationBackends,
        wx.getStorageSync("generationOptions") || {}
      );
      const selectedHairstyle =
        findById(catalog.hairstyles, cachedHairstyle.id) || cachedHairstyle;
      const selectedScene =
        findById(catalog.scenes, cachedScene.id) || cachedScene;

      this.setData({
        loading: false,
        selectedImage,
        selectedHairstyle,
        selectedScene,
        generationBackends,
        selectedGeneratorBackend: generationSelection.selectedGeneratorBackend,
        selectedAspectRatio: generationSelection.selectedAspectRatio,
        selectedResolution: generationSelection.selectedResolution,
        aspectRatioOptions: generationSelection.aspectRatioOptions,
        resolutionOptions: generationSelection.resolutionOptions
      });
    } catch (error) {
      this.setData({ loading: false });
      showError(error, { fallback: "加载确认信息失败" });
    }
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
    if (!this.data.selectedImage) {
      wx.showToast({ title: "请先上传照片", icon: "none" });
      return;
    }
    if (!this.data.selectedHairstyle || !this.data.selectedScene) {
      wx.showToast({ title: "请先完成发型和场景选择", icon: "none" });
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
  }
});
