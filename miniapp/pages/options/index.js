const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const {
  resolveHairColorSelection
} = require("../../utils/hair-color");
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
const {
  ensureCurrentUpload
} = require("../../utils/recommendation");

function buildHairColorDraftPatch(tone, technique) {
  return {
    hair_color_tone: tone ? tone.id : "",
    hair_color_tone_label: tone ? tone.label : "",
    hair_color_technique: technique ? technique.id : "",
    hair_color_technique_label: technique ? technique.label : ""
  };
}

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
    advancedOpen: false,
    hairColors: [],
    hairColorTechniques: [],
    selectedHairColor: null,
    selectedHairTechnique: null,
    techniqueOptions: [],
    detectedHairColorLabel: "",
    detectedHairColorHint: ""
  },

  async onLoad() {
    await this.loadOptions();
  },

  persistDraft(patch = {}) {
    const tone = patch.selectedHairColor || this.data.selectedHairColor;
    const technique = patch.selectedHairTechnique || this.data.selectedHairTechnique;
    updateCreationDraft({
      generator_backend: this.data.selectedGeneratorBackend,
      aspect_ratio: patch.selectedAspectRatio || this.data.selectedAspectRatio,
      resolution: this.data.selectedResolution,
      ...buildHairColorDraftPatch(tone, technique)
    });
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
      const hairColors = catalog.hair_colors || [];
      const hairColorTechniques = catalog.hair_color_techniques || [];

      let upload = null;
      try {
        upload = await ensureCurrentUpload(draft.imagePath, { timeout: 15000 });
      } catch (error) {
        upload = null;
      }

      const hairColorSelection = resolveHairColorSelection({
        hairColors,
        hairColorTechniques,
        draft,
        hairstyle: selectedHairstyle,
        upload
      });
      const detectedHairColor = hairColorSelection.detectedHairColor;

      updateCreationDraft({
        hairstyle: selectedHairstyle,
        scene: selectedScene,
        generator_backend: generationSelection.selectedGeneratorBackend,
        aspect_ratio: generationSelection.selectedAspectRatio,
        resolution: generationSelection.selectedResolution,
        ...buildHairColorDraftPatch(
          hairColorSelection.tone,
          hairColorSelection.technique
        )
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
        aspectRatioOptions: generationSelection.aspectRatioOptions,
        hairColors,
        hairColorTechniques,
        selectedHairColor: hairColorSelection.tone,
        selectedHairTechnique: hairColorSelection.technique,
        techniqueOptions: hairColorSelection.techniqueOptions,
        detectedHairColorLabel: detectedHairColor ? detectedHairColor.label : "",
        detectedHairColorHint: detectedHairColor
          ? `已按原图预估为 ${detectedHairColor.label}`
          : "可手动调整更想尝试的发色"
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

  selectHairColorTone(event) {
    const toneId = event.currentTarget.dataset.value;
    if (!toneId) {
      return;
    }
    const nextTone = findById(this.data.hairColors, toneId);
    if (!nextTone) {
      return;
    }
    const nextTechniqueOptions = (this.data.hairColorTechniques || []).filter((item) => {
      const allowed = nextTone.allowed_techniques || [];
      return !allowed.length || allowed.includes(item.id);
    });
    const nextTechnique =
      findById(nextTechniqueOptions, this.data.selectedHairTechnique && this.data.selectedHairTechnique.id) ||
      findById(nextTechniqueOptions, nextTone.default_technique) ||
      nextTechniqueOptions[0] ||
      null;

    this.setData({
      selectedHairColor: nextTone,
      selectedHairTechnique: nextTechnique,
      techniqueOptions: nextTechniqueOptions
    });
    this.persistDraft({
      selectedHairColor: nextTone,
      selectedHairTechnique: nextTechnique
    });
  },

  selectHairColorTechnique(event) {
    const techniqueId = event.currentTarget.dataset.value;
    if (!techniqueId) {
      return;
    }
    const nextTechnique = findById(this.data.techniqueOptions, techniqueId);
    if (!nextTechnique) {
      return;
    }
    this.setData({
      selectedHairTechnique: nextTechnique
    });
    this.persistDraft({
      selectedHairTechnique: nextTechnique
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
    this.persistDraft({
      selectedAspectRatio: aspectRatio
    });
  },

  selectResolution() {
    return;
  },

  goNext() {
    this.persistDraft();
    wx.navigateTo({
      url: "/pages/review/index"
    });
  }
});
