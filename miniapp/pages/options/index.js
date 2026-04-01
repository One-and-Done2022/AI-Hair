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
    selectedBackendLabel: "",
    selectedBackendDescription: "",
    selectedAspectRatio: "3:4",
    selectedResolution: "",
    aspectRatioOptions: [],
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
        selectedBackendLabel: generationSelection.selectedBackend ? generationSelection.selectedBackend.name : "",
        selectedBackendDescription: generationSelection.selectedBackend ? generationSelection.selectedBackend.description : "",
        selectedAspectRatio: generationSelection.selectedAspectRatio,
        selectedResolution: generationSelection.selectedResolution,
        aspectRatioOptions: generationSelection.aspectRatioOptions
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

  goEditHairstyle() {
    wx.redirectTo({
      url: "/pages/templates/index"
    });
  },

  goEditScene() {
    wx.redirectTo({
      url: "/pages/scenes/index"
    });
  },

  toggleAdvanced() {
    this.setData({
      advancedOpen: !this.data.advancedOpen
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
    return;
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
