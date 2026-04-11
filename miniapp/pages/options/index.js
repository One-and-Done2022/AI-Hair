const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const {
  buildTechniqueOptions,
  findHairColorById,
  findProfessionalHairColorById,
  resolveHairColorSelection,
  resolveProfessionalMappedSelection,
  shouldClearProfessionalColor
} = require("../../utils/hair-color");
const { baseUrl, request } = require("../../utils/request");
const {
  readCreationDraft,
  resetCreationDraft,
  updateCreationDraft
} = require("../../utils/creation-draft");
const { findCatalogHairstyle } = require("../../utils/template-selection");
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

function buildProfessionalDraftPatch(professionalColor) {
  return {
    hair_color_professional_id: professionalColor ? professionalColor.id : "",
    hair_color_professional_brand: professionalColor ? professionalColor.brand : "",
    hair_color_professional_series: professionalColor ? professionalColor.series_type : "",
    hair_color_professional_series_label: professionalColor ? professionalColor.series_name : "",
    hair_color_professional_code: professionalColor ? professionalColor.code : "",
    hair_color_professional_note: professionalColor ? professionalColor.visual_note : "",
    hair_color_professional_hex_estimate: professionalColor ? professionalColor.hex_estimate : ""
  };
}

function buildProfessionalSeries(series = []) {
  return (series || []).filter((item) => item.option_count > 0);
}

function resolveProfessionalSeriesId({
  series = [],
  draftSeries = "",
  selectedProfessionalHairColor = null
} = {}) {
  const preferredId =
    (selectedProfessionalHairColor && selectedProfessionalHairColor.series_type) ||
    draftSeries ||
    "";
  if (preferredId && (series || []).some((item) => item.id === preferredId)) {
    return preferredId;
  }
  return series.length ? series[0].id : "";
}

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
    advancedOpen: false,
    hairColors: [],
    hairColorTechniques: [],
    hairColorMode: "basic",
    selectedHairColor: null,
    selectedHairTechnique: null,
    techniqueOptions: [],
    detectedHairColorLabel: "",
    detectedHairColorHint: "",
    professionalExpanded: false,
    professionalSeries: [],
    professionalColors: [],
    professionalSelectedSeries: "",
    professionalSelectedSeriesLabel: "",
    professionalSeriesResultText: "",
    filteredProfessionalColors: [],
    selectedProfessionalHairColor: null
  },

  async onLoad() {
    await this.loadOptions();
  },

  buildProfessionalPaletteState(nextState = {}) {
    const professionalColors = nextState.professionalColors || this.data.professionalColors;
    const professionalSeries = nextState.professionalSeries || this.data.professionalSeries;
    const selectedProfessionalHairColor = Object.prototype.hasOwnProperty.call(
      nextState,
      "selectedProfessionalHairColor"
    )
      ? nextState.selectedProfessionalHairColor
      : this.data.selectedProfessionalHairColor;
    const draftSeries = Object.prototype.hasOwnProperty.call(nextState, "professionalSelectedSeries")
      ? nextState.professionalSelectedSeries
      : this.data.professionalSelectedSeries;
    const professionalSelectedSeries = resolveProfessionalSeriesId({
      series: professionalSeries,
      draftSeries,
      selectedProfessionalHairColor
    });
    const filteredProfessionalColors = professionalSelectedSeries
      ? (professionalColors || []).filter((item) => item.series_type === professionalSelectedSeries)
      : professionalColors;
    const selectedSeries = (professionalSeries || []).find((item) => item.id === professionalSelectedSeries) || null;

    return {
      professionalSelectedSeries,
      professionalSelectedSeriesLabel: selectedSeries ? selectedSeries.label : "",
      professionalSeriesResultText: selectedSeries
        ? `${selectedSeries.label} · ${filteredProfessionalColors.length} 个色号`
        : `共 ${filteredProfessionalColors.length} 个色号`,
      filteredProfessionalColors
    };
  },

  persistDraft(patch = {}) {
    const tone = patch.selectedHairColor || this.data.selectedHairColor;
    const technique = patch.selectedHairTechnique || this.data.selectedHairTechnique;
    const professionalColor =
      Object.prototype.hasOwnProperty.call(patch, "selectedProfessionalHairColor")
        ? patch.selectedProfessionalHairColor
        : this.data.selectedProfessionalHairColor;
    const hairColorMode = patch.hairColorMode || this.data.hairColorMode || "basic";
    updateCreationDraft({
      generator_backend: this.data.selectedGeneratorBackend,
      aspect_ratio: patch.selectedAspectRatio || this.data.selectedAspectRatio,
      resolution: this.data.selectedResolution,
      hair_color_selection_mode: hairColorMode,
      ...buildHairColorDraftPatch(tone, technique),
      ...buildProfessionalDraftPatch(professionalColor)
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
        findCatalogHairstyle(catalog, draft.hairstyle) || draft.hairstyle;
      const selectedScene =
        findById(catalog.scenes, draft.scene.id) || draft.scene;
      const hairColors = catalog.hair_colors || [];
      const hairColorTechniques = catalog.hair_color_techniques || [];
      const professionalColors = (catalog.hair_color_professional_options || []).map((item) => ({
        ...item,
        mapped_technique_text: (item.mapped_technique_labels || []).join(" / ")
      }));
      const professionalSeries = buildProfessionalSeries(
        catalog.hair_color_professional_series || []
      );

      let upload = null;
      try {
        upload = await ensureCurrentUpload(draft.imagePath, { timeout: 15000 });
      } catch (error) {
        upload = null;
      }

      const baseHairColorSelection = resolveHairColorSelection({
        hairColors,
        hairColorTechniques,
        draft,
        hairstyle: selectedHairstyle,
        upload
      });
      const detectedHairColor = baseHairColorSelection.detectedHairColor;
      let selectedHairColor = baseHairColorSelection.tone;
      let selectedHairTechnique = baseHairColorSelection.technique;
      let techniqueOptions = baseHairColorSelection.techniqueOptions;
      let selectedProfessionalHairColor = findProfessionalHairColorById(
        professionalColors,
        draft.hair_color_professional_id
      );
      if (selectedProfessionalHairColor) {
        const mappedSelection = resolveProfessionalMappedSelection({
          professionalColor: selectedProfessionalHairColor,
          hairColors,
          hairColorTechniques,
          currentTechnique: selectedHairTechnique
        });
        selectedHairColor = mappedSelection.tone || selectedHairColor;
        selectedHairTechnique = mappedSelection.technique || selectedHairTechnique;
        techniqueOptions = mappedSelection.techniqueOptions.length
          ? mappedSelection.techniqueOptions
          : techniqueOptions;
      }
      const hairColorMode = selectedProfessionalHairColor
        ? "professional"
        : (draft.hair_color_selection_mode || "basic");
      const professionalPaletteState = this.buildProfessionalPaletteState({
        professionalColors,
        professionalSeries,
        professionalSelectedSeries: draft.hair_color_professional_series || "",
        selectedProfessionalHairColor
      });

      updateCreationDraft({
        hairstyle: selectedHairstyle,
        scene: selectedScene,
        generator_backend: generationSelection.selectedGeneratorBackend,
        aspect_ratio: generationSelection.selectedAspectRatio,
        resolution: generationSelection.selectedResolution,
        hair_color_selection_mode: hairColorMode,
        ...buildHairColorDraftPatch(
          selectedHairColor,
          selectedHairTechnique
        ),
        ...buildProfessionalDraftPatch(selectedProfessionalHairColor)
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
        hairColors,
        hairColorTechniques,
        hairColorMode,
        professionalSeries,
        professionalColors,
        selectedHairColor,
        selectedHairTechnique,
        techniqueOptions,
        detectedHairColorLabel: detectedHairColor ? detectedHairColor.label : "",
        detectedHairColorHint: detectedHairColor
          ? `默认发色为自然黑，也可参考原图预估的 ${detectedHairColor.label} 手动调整`
          : "默认发色为自然黑，可手动调整或直接选择专业色号",
        selectedProfessionalHairColor,
        ...professionalPaletteState
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

  toggleProfessionalExpand() {
    this.setData({
      professionalExpanded: !this.data.professionalExpanded
    });
  },

  switchToBasicHairColor() {
    this.setData({
      hairColorMode: "basic",
      professionalExpanded: false,
      selectedProfessionalHairColor: null
    });
    this.persistDraft({
      hairColorMode: "basic",
      selectedProfessionalHairColor: null
    });
  },

  switchToProfessionalHairColor() {
    this.setData({
      hairColorMode: "professional",
      professionalExpanded: true
    });
    this.persistDraft({
      hairColorMode: "professional"
    });
  },

  async openProfessionalReference() {
    const staticReferenceUrl = `${baseUrl}/static/reference_docs/solugtor-hair-color-with-rgb-reference-latest.pdf`;
    let fallbackUrl = `${baseUrl}/api/templates/hair-color-reference.pdf`;
    try {
      const payload = await request({
        url: "/api/templates/hair-color-reference-link"
      });
      if (payload && payload.api_url) {
        fallbackUrl = payload.api_url;
      }
    } catch (error) {
      fallbackUrl = `${baseUrl}/api/templates/hair-color-reference.pdf`;
    }

    wx.showLoading({ title: "准备参考" });

    const openDownloadedPdf = (result) => {
      if (!result || result.statusCode < 200 || result.statusCode >= 300 || !result.tempFilePath) {
        return false;
      }
      wx.openDocument({
        filePath: result.tempFilePath,
        fileType: "pdf",
        showMenu: true,
        success: () => {
          wx.hideLoading();
        },
        fail: () => {
          wx.hideLoading();
          wx.showToast({ title: "当前环境暂时无法打开 PDF", icon: "none" });
        }
      });
      return true;
    };

    const downloadReference = (url, isFallback = false) => {
      if (!url) {
        wx.hideLoading();
        wx.showToast({ title: "参考文件下载失败", icon: "none" });
        return;
      }
      wx.downloadFile({
        url,
        success: (result) => {
          if (openDownloadedPdf(result)) {
            return;
          }
          if (!isFallback && fallbackUrl && fallbackUrl !== url) {
            downloadReference(fallbackUrl, true);
            return;
          }
          wx.hideLoading();
          wx.showToast({ title: "参考文件加载失败", icon: "none" });
        },
        fail: () => {
          if (!isFallback && fallbackUrl && fallbackUrl !== url) {
            downloadReference(fallbackUrl, true);
            return;
          }
          wx.hideLoading();
          wx.showToast({ title: "参考文件下载失败", icon: "none" });
        }
      });
    };

    downloadReference(staticReferenceUrl);
  },

  selectProfessionalSeries(event) {
    const professionalSelectedSeries = event.currentTarget.dataset.value || "";
    this.setData({
      ...this.buildProfessionalPaletteState({
        professionalSelectedSeries
      })
    });
  },

  selectProfessionalHairColor(event) {
    const professionalId = event.currentTarget.dataset.value;
    if (!professionalId) {
      return;
    }
    const professionalColor = findProfessionalHairColorById(
      this.data.professionalColors,
      professionalId
    );
    if (!professionalColor) {
      return;
    }
    const mappedSelection = resolveProfessionalMappedSelection({
      professionalColor,
      hairColors: this.data.hairColors,
      hairColorTechniques: this.data.hairColorTechniques,
      currentTechnique: this.data.selectedHairTechnique
    });
    this.setData({
      hairColorMode: "professional",
      selectedProfessionalHairColor: professionalColor,
      selectedHairColor: mappedSelection.tone,
      selectedHairTechnique: mappedSelection.technique,
      techniqueOptions: mappedSelection.techniqueOptions,
      professionalExpanded: true,
      ...this.buildProfessionalPaletteState({
        selectedProfessionalHairColor: professionalColor,
        professionalSelectedSeries: professionalColor.series_type
      })
    });
    this.persistDraft({
      hairColorMode: "professional",
      selectedProfessionalHairColor: professionalColor,
      selectedHairColor: mappedSelection.tone,
      selectedHairTechnique: mappedSelection.technique
    });
  },

  selectHairColorTone(event) {
    const toneId = event.currentTarget.dataset.value;
    if (!toneId) {
      return;
    }
    const nextTone = findHairColorById(this.data.hairColors, toneId);
    if (!nextTone) {
      return;
    }
    const nextTechniqueOptions = buildTechniqueOptions(
      this.data.hairColorTechniques,
      nextTone
    );
    const nextTechnique =
      findHairColorById(
        nextTechniqueOptions,
        this.data.selectedHairTechnique && this.data.selectedHairTechnique.id
      ) ||
      findHairColorById(nextTechniqueOptions, nextTone.default_technique) ||
      nextTechniqueOptions[0] ||
      null;
    const nextProfessionalHairColor = shouldClearProfessionalColor(
      this.data.selectedProfessionalHairColor,
      nextTone,
      nextTechnique
    )
      ? null
      : this.data.selectedProfessionalHairColor;

    this.setData({
      hairColorMode: "basic",
      selectedHairColor: nextTone,
      selectedHairTechnique: nextTechnique,
      techniqueOptions: nextTechniqueOptions,
      selectedProfessionalHairColor: nextProfessionalHairColor
    });
    this.persistDraft({
      hairColorMode: "basic",
      selectedHairColor: nextTone,
      selectedHairTechnique: nextTechnique,
      selectedProfessionalHairColor: nextProfessionalHairColor
    });
  },

  selectHairColorTechnique(event) {
    const techniqueId = event.currentTarget.dataset.value;
    if (!techniqueId) {
      return;
    }
    const nextTechnique = findHairColorById(this.data.techniqueOptions, techniqueId);
    if (!nextTechnique) {
      return;
    }
    const nextProfessionalHairColor = shouldClearProfessionalColor(
      this.data.selectedProfessionalHairColor,
      this.data.selectedHairColor,
      nextTechnique
    )
      ? null
      : this.data.selectedProfessionalHairColor;

    this.setData({
      hairColorMode: "basic",
      selectedHairTechnique: nextTechnique,
      selectedProfessionalHairColor: nextProfessionalHairColor
    });
    this.persistDraft({
      hairColorMode: "basic",
      selectedHairTechnique: nextTechnique,
      selectedProfessionalHairColor: nextProfessionalHairColor
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
    if (this.data.hairColorMode === "professional" && !this.data.selectedProfessionalHairColor) {
      wx.showToast({
        title: "请先选择专业色号，或切换回基础发色",
        icon: "none"
      });
      return;
    }
    this.persistDraft();
    wx.navigateTo({
      url: "/pages/review/index"
    });
  }
});
