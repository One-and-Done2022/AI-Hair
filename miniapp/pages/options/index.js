const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const { request } = require("../../utils/request");
const {
  readCreationDraft,
  resetCreationDraft,
  updateCreationDraft
} = require("../../utils/creation-draft");
const {
  buildGenerationSelection,
  findBackendById,
  findById,
  formatGenerationBackends
} = require("../../utils/generation");

Page({
  data: {
    loading: true,
    selectedHairstyle: null,
    selectedScene: null,
    generationBackends: [],
    selectedGeneratorBackend: "",
    selectedAspectRatio: "3:4",
    selectedResolution: "",
    aspectRatioOptions: [],
    resolutionOptions: [],
    advancedOpen: false
  },

  async onLoad() {
    await this.loadOptions();
  },

  async loadOptions() {
    const draft = readCreationDraft();
    if (!draft.imagePath) {
      wx.switchTab({
        url: "/pages/index/index"
      });
      return;
    }
    if (!draft.hairstyle) {
      wx.redirectTo({
        url: "/pages/templates/index"
      });
      return;
    }
    if (!draft.scene) {
      wx.redirectTo({
        url: "/pages/scenes/index"
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
        draft
      );

      const selectedHairstyle =
        findById(catalog.hairstyles, draft.hairstyle.id) || draft.hairstyle;
      const selectedScene =
        findById(catalog.scenes, draft.scene.id) || draft.scene;

      updateCreationDraft({
        hairstyle: selectedHairstyle,
        scene: selectedScene,
        generator_backend: generationSelection.selectedGeneratorBackend,
        aspect_ratio: generationSelection.selectedAspectRatio,
        resolution: generationSelection.selectedResolution
      });

      this.setData({
        loading: false,
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
      showError(error, { fallback: "加载参数失败" });
    }
  },

  goBackStep() {
    wx.navigateBack({
      fail: () => {
        wx.redirectTo({ url: "/pages/scenes/index" });
      }
    });
  },

  resetFlow() {
    resetCreationDraft();
    wx.switchTab({
      url: "/pages/index/index"
    });
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
        title: "该方案暂不可用",
        icon: "none"
      });
      return;
    }

    const selection = buildGenerationSelection(this.data.generationBackends, {
      generator_backend: backendId
    });

    this.setData({
      selectedGeneratorBackend: selection.selectedGeneratorBackend,
      selectedAspectRatio: selection.selectedAspectRatio,
      selectedResolution: selection.selectedResolution,
      aspectRatioOptions: selection.aspectRatioOptions,
      resolutionOptions: selection.resolutionOptions
    });

    updateCreationDraft({
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
    this.setData({
      selectedAspectRatio: aspectRatio
    });
    updateCreationDraft({
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
    this.setData({
      selectedResolution: resolution
    });
    updateCreationDraft({
      generator_backend: this.data.selectedGeneratorBackend,
      aspect_ratio: this.data.selectedAspectRatio,
      resolution
    });
  },

  goNext() {
    updateCreationDraft({
      generator_backend: this.data.selectedGeneratorBackend,
      aspect_ratio: this.data.selectedAspectRatio,
      resolution: this.data.selectedResolution
    });
    wx.navigateTo({
      url: "/pages/review/index"
    });
  }
});
