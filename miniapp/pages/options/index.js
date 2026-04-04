const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const {
  PROFESSIONAL_HAIR_COLOR_QUICK_KEYWORDS,
  buildTechniqueOptions,
  findHairColorById,
  findProfessionalHairColorById,
  resolveHairColorSelection,
  resolveProfessionalMappedSelection,
  searchProfessionalHairColors,
  shouldClearProfessionalColor
} = require("../../utils/hair-color");
const { baseUrl, request } = require("../../utils/request");
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
  return [
    {
      id: "all",
      label: "全部",
      description: "全部可生成色号"
    }
  ].concat(
    (series || []).filter((item) => item.recommended_option_count > 0)
  );
}

function findProfessionalSeriesLabel(series = [], id = "all") {
  if (!id || id === "all") {
    return "全部";
  }
  const matched = (series || []).find((item) => item.id === id);
  return matched ? matched.label : "当前系列";
}

function buildProfessionalSearchSummary({
  keyword = "",
  searchResult = null,
  selectedSeries = "all",
  series = []
} = {}) {
  const matchedCount = searchResult ? searchResult.matchedCount : 0;
  const recommendedCount = searchResult ? searchResult.recommendedCount : 0;
  const trimmedKeyword = String(keyword || "").trim();

  if (trimmedKeyword) {
    if (!matchedCount) {
      return "没有找到匹配色号";
    }
    if (recommendedCount === matchedCount) {
      return `找到 ${matchedCount} 个可生成色号`;
    }
    if (!recommendedCount) {
      return `找到 ${matchedCount} 个结果，当前仅供参考`;
    }
    return `找到 ${matchedCount} 个结果，其中 ${recommendedCount} 个可生成`;
  }

  const prefix = selectedSeries === "all"
    ? "全部可生成色号"
    : `${findProfessionalSeriesLabel(series, selectedSeries)} 可生成色号`;
  return `${prefix} ${matchedCount} 个`;
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
    selectedHairColor: null,
    selectedHairTechnique: null,
    techniqueOptions: [],
    detectedHairColorLabel: "",
    detectedHairColorHint: "",
    professionalExpanded: false,
    professionalSeries: [],
    professionalColors: [],
    professionalSelectedSeries: "all",
    professionalSearchKeyword: "",
    professionalSearchQuickKeywords: PROFESSIONAL_HAIR_COLOR_QUICK_KEYWORDS,
    professionalSearchResultText: "全部可生成色号 0 个",
    professionalSearchUsesGlobal: false,
    filteredProfessionalColors: [],
    selectedProfessionalHairColor: null
  },

  async onLoad() {
    await this.loadOptions();
  },

  buildProfessionalSearchState(nextState = {}) {
    const professionalColors = nextState.professionalColors || this.data.professionalColors;
    const professionalSeries = nextState.professionalSeries || this.data.professionalSeries;
    const professionalSelectedSeries =
      nextState.professionalSelectedSeries || this.data.professionalSelectedSeries || "all";
    const professionalSearchKeyword =
      Object.prototype.hasOwnProperty.call(nextState, "professionalSearchKeyword")
        ? nextState.professionalSearchKeyword
        : this.data.professionalSearchKeyword;
    const trimmedKeyword = String(professionalSearchKeyword || "").trim();
    const searchResult = searchProfessionalHairColors({
      professionalColors,
      selectedSeries: professionalSelectedSeries,
      keyword: professionalSearchKeyword,
      recommendedOnly: !trimmedKeyword
    });

    return {
      filteredProfessionalColors: searchResult.items,
      professionalSearchResultText: buildProfessionalSearchSummary({
        keyword: professionalSearchKeyword,
        searchResult,
        selectedSeries: professionalSelectedSeries,
        series: professionalSeries
      }),
      professionalSearchUsesGlobal: searchResult.usesGlobalSearch
    };
  },

  persistDraft(patch = {}) {
    const tone = patch.selectedHairColor || this.data.selectedHairColor;
    const technique = patch.selectedHairTechnique || this.data.selectedHairTechnique;
    const professionalColor =
      Object.prototype.hasOwnProperty.call(patch, "selectedProfessionalHairColor")
        ? patch.selectedProfessionalHairColor
        : this.data.selectedProfessionalHairColor;
    updateCreationDraft({
      generator_backend: this.data.selectedGeneratorBackend,
      aspect_ratio: patch.selectedAspectRatio || this.data.selectedAspectRatio,
      resolution: this.data.selectedResolution,
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
        findById(catalog.hairstyles, draft.hairstyle.id) || draft.hairstyle;
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
      if (
        selectedProfessionalHairColor &&
        !selectedProfessionalHairColor.is_recommended_for_generation
      ) {
        selectedProfessionalHairColor = null;
      }
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
      const professionalSearchState = this.buildProfessionalSearchState({
        professionalColors,
        professionalSeries,
        professionalSelectedSeries: draft.hair_color_professional_series || "all",
        professionalSearchKeyword: ""
      });

      updateCreationDraft({
        hairstyle: selectedHairstyle,
        scene: selectedScene,
        generator_backend: generationSelection.selectedGeneratorBackend,
        aspect_ratio: generationSelection.selectedAspectRatio,
        resolution: generationSelection.selectedResolution,
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
        professionalSeries,
        professionalColors,
        professionalSelectedSeries: draft.hair_color_professional_series || "all",
        selectedHairColor,
        selectedHairTechnique,
        techniqueOptions,
        detectedHairColorLabel: detectedHairColor ? detectedHairColor.label : "",
        detectedHairColorHint: detectedHairColor
          ? `不选时默认沿用原图预估的 ${detectedHairColor.label}`
          : "未识别到原发色时会按模板默认色生成，可手动调整",
        selectedProfessionalHairColor,
        ...professionalSearchState
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

  onProfessionalSearchInput(event) {
    const professionalSearchKeyword = event.detail.value || "";
    this.setData({
      professionalExpanded: true,
      professionalSearchKeyword,
      ...this.buildProfessionalSearchState({
        professionalSearchKeyword
      })
    });
  },

  applyProfessionalQuickKeyword(event) {
    const professionalSearchKeyword = event.currentTarget.dataset.value || "";
    if (!professionalSearchKeyword) {
      return;
    }
    this.setData({
      professionalExpanded: true,
      professionalSearchKeyword,
      ...this.buildProfessionalSearchState({
        professionalSearchKeyword
      })
    });
  },

  clearProfessionalSearch() {
    this.setData({
      professionalSearchKeyword: "",
      ...this.buildProfessionalSearchState({
        professionalSearchKeyword: ""
      })
    });
  },

  async openProfessionalReference() {
    const referenceUrl = `${baseUrl}/api/templates/hair-color-reference.pdf`;
    let fallbackUrl = "";
    try {
      const payload = await request({
        url: "/api/templates/hair-color-reference-link"
      });
      fallbackUrl = payload && payload.url ? payload.url : "";
    } catch (error) {
      fallbackUrl = "";
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

    downloadReference(referenceUrl);
  },

  selectProfessionalSeries(event) {
    const professionalSelectedSeries = event.currentTarget.dataset.value || "all";
    this.setData({
      professionalSelectedSeries,
      ...this.buildProfessionalSearchState({
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
    if (!professionalColor.is_recommended_for_generation) {
      wx.showToast({
        title: "这个色号当前只做参考，暂不支持直接生成",
        icon: "none"
      });
      return;
    }
    const mappedSelection = resolveProfessionalMappedSelection({
      professionalColor,
      hairColors: this.data.hairColors,
      hairColorTechniques: this.data.hairColorTechniques,
      currentTechnique: this.data.selectedHairTechnique
    });
    this.setData({
      selectedProfessionalHairColor: professionalColor,
      selectedHairColor: mappedSelection.tone,
      selectedHairTechnique: mappedSelection.technique,
      techniqueOptions: mappedSelection.techniqueOptions,
      professionalExpanded: true
    });
    this.persistDraft({
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
      selectedHairColor: nextTone,
      selectedHairTechnique: nextTechnique,
      techniqueOptions: nextTechniqueOptions,
      selectedProfessionalHairColor: nextProfessionalHairColor
    });
    this.persistDraft({
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
      selectedHairTechnique: nextTechnique,
      selectedProfessionalHairColor: nextProfessionalHairColor
    });
    this.persistDraft({
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
    this.persistDraft();
    wx.navigateTo({
      url: "/pages/review/index"
    });
  }
});
