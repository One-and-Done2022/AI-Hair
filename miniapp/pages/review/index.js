const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const {
  findProfessionalHairColorById,
  resolveHairColorSelection,
  resolveProfessionalMappedSelection
} = require("../../utils/hair-color");
const { upsertPendingHistoryJob } = require("../../utils/pending-history");
const { request } = require("../../utils/request");
const {
  ensureCurrentUpload,
  getCurrentImagePath
} = require("../../utils/recommendation");
const {
  readCreationDraft,
  resetCreationDraft,
  updateCreationDraft
} = require("../../utils/creation-draft");
const {
  buildJobCreatePayload,
  findCatalogHairstyle
} = require("../../utils/template-selection");
const {
  buildGenerationSelection,
  findById,
  formatGenerationBackends
} = require("../../utils/generation");

function buildProfessionalSummary(professionalColor) {
  if (!professionalColor) {
    return "";
  }
  return `${professionalColor.series_name} · ${professionalColor.code}`;
}

Page({
  data: {
    loading: true,
    selectedImage: "",
    selectedHairstyle: null,
    selectedScene: null,
    selectedGeneratorBackend: "",
    selectedAspectRatio: "3:4",
    selectedResolution: "",
    selectedHairColorToneLabel: "",
    selectedHairColorTechniqueLabel: "",
    selectedHairColorProfessionalSummary: "",
    submitting: false
  },

  async onLoad() {
    await this.loadReviewState();
  },

  async loadReviewState() {
    const draft = readCreationDraft();
    const selectedImage = getCurrentImagePath();

    if (!selectedImage) {
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
      const generationSelection = buildGenerationSelection(generationBackends, draft);
      const selectedHairstyle =
        findCatalogHairstyle(catalog, draft.hairstyle) || draft.hairstyle;
      const selectedScene =
        findById(catalog.scenes, draft.scene.id) || draft.scene;
      const upload = await ensureCurrentUpload(selectedImage, { timeout: 15000 }).catch(() => null);
      const baseHairColorSelection = resolveHairColorSelection({
        hairColors: catalog.hair_colors || [],
        hairColorTechniques: catalog.hair_color_techniques || [],
        draft,
        hairstyle: selectedHairstyle,
        upload
      });
      let selectedProfessionalHairColor = findProfessionalHairColorById(
        catalog.hair_color_professional_options || [],
        draft.hair_color_professional_id
      );
      let selectedHairColor = baseHairColorSelection.tone;
      let selectedHairTechnique = baseHairColorSelection.technique;
      if (
        selectedProfessionalHairColor &&
        selectedProfessionalHairColor.is_recommended_for_generation
      ) {
        const mappedSelection = resolveProfessionalMappedSelection({
          professionalColor: selectedProfessionalHairColor,
          hairColors: catalog.hair_colors || [],
          hairColorTechniques: catalog.hair_color_techniques || [],
          currentTechnique: selectedHairTechnique
        });
        selectedHairColor = mappedSelection.tone || selectedHairColor;
        selectedHairTechnique = mappedSelection.technique || selectedHairTechnique;
      } else {
        selectedProfessionalHairColor = null;
      }

      updateCreationDraft({
        hairstyle: selectedHairstyle,
        scene: selectedScene,
        generator_backend: generationSelection.selectedGeneratorBackend,
        aspect_ratio: generationSelection.selectedAspectRatio,
        resolution: generationSelection.selectedResolution,
        hair_color_tone: selectedHairColor ? selectedHairColor.id : "",
        hair_color_tone_label: selectedHairColor ? selectedHairColor.label : "",
        hair_color_technique: selectedHairTechnique ? selectedHairTechnique.id : "",
        hair_color_technique_label: selectedHairTechnique ? selectedHairTechnique.label : "",
        hair_color_professional_id: selectedProfessionalHairColor ? selectedProfessionalHairColor.id : "",
        hair_color_professional_brand: selectedProfessionalHairColor ? selectedProfessionalHairColor.brand : "",
        hair_color_professional_series: selectedProfessionalHairColor ? selectedProfessionalHairColor.series_type : "",
        hair_color_professional_series_label: selectedProfessionalHairColor ? selectedProfessionalHairColor.series_name : "",
        hair_color_professional_code: selectedProfessionalHairColor ? selectedProfessionalHairColor.code : "",
        hair_color_professional_note: selectedProfessionalHairColor ? selectedProfessionalHairColor.visual_note : "",
        hair_color_professional_hex_estimate: selectedProfessionalHairColor ? selectedProfessionalHairColor.hex_estimate : ""
      });

      this.setData({
        loading: false,
        selectedImage,
        selectedHairstyle,
        selectedScene,
        selectedGeneratorBackend: generationSelection.selectedGeneratorBackend,
        selectedAspectRatio: generationSelection.selectedAspectRatio,
        selectedResolution: generationSelection.selectedResolution,
        selectedHairColorToneLabel: selectedHairColor ? selectedHairColor.label : "",
        selectedHairColorTechniqueLabel: selectedHairTechnique ? selectedHairTechnique.label : "",
        selectedHairColorProfessionalSummary: buildProfessionalSummary(selectedProfessionalHairColor)
      });
    } catch (error) {
      this.setData({ loading: false });
      showError(error, { fallback: "加载确认信息失败" });
    }
  },

  goBackStep() {
    wx.navigateBack({
      fail: () => {
        wx.redirectTo({ url: "/pages/options/index" });
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

  goEditOptions() {
    wx.redirectTo({
      url: "/pages/options/index"
    });
  },

  async createJob() {
    if (!this.data.selectedImage) {
      wx.showToast({ title: "请先上传照片", icon: "none" });
      return;
    }
    if (!this.data.selectedHairstyle || !this.data.selectedScene) {
      wx.showToast({ title: "请先完成搭配选择", icon: "none" });
      return;
    }

    this.setData({ submitting: true });
    wx.showLoading({ title: "正在提交任务" });
    try {
      await ensureLogin();
      const upload = await ensureCurrentUpload(this.data.selectedImage);
      const draft = readCreationDraft();
      const job = await request({
        url: "/api/jobs",
        method: "POST",
        data: buildJobCreatePayload({
          uploadId: upload.upload_id,
          hairstyle: this.data.selectedHairstyle,
          scene: this.data.selectedScene,
          generatorBackend: this.data.selectedGeneratorBackend,
          aspectRatio: this.data.selectedAspectRatio,
          resolution: this.data.selectedResolution,
          hairColorTone: draft.hair_color_tone,
          hairColorTechnique: draft.hair_color_technique,
          hairColorProfessionalId: draft.hair_color_professional_id
        })
      });
      upsertPendingHistoryJob({
        job_id: job.job_id,
        status: job.status,
        upload_url: upload.upload_url || "",
        hairstyle_id: job.hairstyle_id || this.data.selectedHairstyle.id,
        preset_id: job.preset_id || this.data.selectedHairstyle.preset_id || "",
        hairstyle_name: job.hairstyle_name || this.data.selectedHairstyle.name || "",
        preset_name: job.preset_name || this.data.selectedHairstyle.name || "",
        scene_id: this.data.selectedScene.id,
        scene_name: job.scene_name || this.data.selectedScene.name || "",
        generator_backend: this.data.selectedGeneratorBackend,
        hair_color_tone: job.hair_color_tone || draft.hair_color_tone || "",
        hair_color_tone_label: job.hair_color_tone_label || this.data.selectedHairColorToneLabel || "",
        hair_color_technique: job.hair_color_technique || draft.hair_color_technique || "",
        hair_color_technique_label: job.hair_color_technique_label || this.data.selectedHairColorTechniqueLabel || "",
        created_at: job.created_at || new Date().toISOString(),
        updated_at: job.updated_at || job.created_at || new Date().toISOString()
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
