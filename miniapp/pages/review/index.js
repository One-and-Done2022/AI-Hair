const { ensureLogin } = require("../../utils/auth");
const { getErrorCode, showError } = require("../../utils/errors");
const {
  isRewardedVideoAdEnabled,
  unlockQuotaByRewardedAd
} = require("../../utils/ad-unlock");
const {
  findProfessionalHairColorById,
  resolveHairColorSelection,
  resolveProfessionalMappedSelection
} = require("../../utils/hair-color");
const { upsertPendingHistoryJob } = require("../../utils/pending-history");
const {
  getDefaultPurchaseItem,
  quickPurchaseDefaultGenerationPack
} = require("../../utils/purchase");
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

function getTotalRemaining(profileSummary) {
  if (!profileSummary) {
    return 0;
  }
  const explicitTotal = Number(profileSummary.total_remaining);
  if (!Number.isNaN(explicitTotal)) {
    return explicitTotal;
  }
  const fallback = Number(profileSummary.remaining_quota);
  return Number.isNaN(fallback) ? 0 : fallback;
}

function canUnlockByAd(profileSummary) {
  return !!(profileSummary && profileSummary.can_unlock_by_ad);
}

function showConfirmModal(options) {
  return new Promise((resolve) => {
    wx.showModal({
      ...options,
      success: ({ confirm }) => resolve(!!confirm),
      fail: () => resolve(false)
    });
  });
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
    selectedHairColorMode: "basic",
    selectedHairColorToneLabel: "",
    selectedHairColorTechniqueLabel: "",
    selectedHairColorProfessionalSummary: "",
    profileSummary: null,
    purchaseItem: null,
    rewardedAdEnabled: isRewardedVideoAdEnabled(),
    adUnlocking: false,
    submitting: false,
    purchasing: false
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
      const [catalog, profileSummary, purchaseItem] = await Promise.all([
        request({ url: "/api/templates" }),
        request({ url: "/api/me" }).catch(() => null),
        getDefaultPurchaseItem().catch(() => null)
      ]);
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
      if (selectedProfessionalHairColor) {
        const mappedSelection = resolveProfessionalMappedSelection({
          professionalColor: selectedProfessionalHairColor,
          hairColors: catalog.hair_colors || [],
          hairColorTechniques: catalog.hair_color_techniques || [],
          currentTechnique: selectedHairTechnique
        });
        selectedHairColor = mappedSelection.tone || selectedHairColor;
        selectedHairTechnique = mappedSelection.technique || selectedHairTechnique;
      }
      const selectedHairColorMode = selectedProfessionalHairColor
        ? "professional"
        : (draft.hair_color_selection_mode || "basic");

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
        selectedHairColorMode,
        selectedHairColorToneLabel: selectedHairColor ? selectedHairColor.label : "",
        selectedHairColorTechniqueLabel: selectedHairTechnique ? selectedHairTechnique.label : "",
        selectedHairColorProfessionalSummary: buildProfessionalSummary(selectedProfessionalHairColor),
        profileSummary,
        purchaseItem
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

  async refreshQuotaSummary() {
    const profileSummary = await request({ url: "/api/me" });
    this.setData({ profileSummary });
    return profileSummary;
  },

  async ensurePurchaseItem() {
    if (this.data.purchaseItem) {
      return this.data.purchaseItem;
    }
    const purchaseItem = await getDefaultPurchaseItem().catch(() => null);
    if (purchaseItem) {
      this.setData({ purchaseItem });
    }
    return purchaseItem;
  },

  async promptPurchaseForQuota() {
    const purchaseItem = await this.ensurePurchaseItem();
    if (!purchaseItem) {
      wx.showToast({
        title: "当前没有可购买商品",
        icon: "none"
      });
      return false;
    }
    const confirmed = await showConfirmModal({
      title: "购买生成包",
      content: `当前可用次数已用完。确认购买 ${purchaseItem.name}（${purchaseItem.price_label}）后，会进入支付页，支付完成后继续本次生成。`,
      confirmText: "立即购买"
    });
    if (!confirmed) {
      return false;
    }

    this.setData({ purchasing: true });
    wx.showLoading({ title: "正在购买" });
    try {
      await quickPurchaseDefaultGenerationPack(purchaseItem.product_id);
      wx.showToast({
        title: "已增加 1 次生成",
        icon: "success"
      });
      const profileSummary = await this.refreshQuotaSummary().catch(() => null);
      return getTotalRemaining(profileSummary || this.data.profileSummary) > 0;
    } catch (error) {
      showError(error, {
        fallback: "购买失败，请稍后再试",
        preferModal: true
      });
      return false;
    } finally {
      wx.hideLoading();
      this.setData({ purchasing: false });
    }
  },

  async purchaseOnePack() {
    await this.promptPurchaseForQuota();
  },

  async unlockOneQuotaByAd() {
    if (this.data.adUnlocking) {
      return false;
    }
    this.setData({ adUnlocking: true });
    wx.showLoading({ title: "正在准备广告" });
    try {
      const quotaSnapshot = await unlockQuotaByRewardedAd();
      const profileSummary = await this.refreshQuotaSummary().catch(() => ({
        ...(this.data.profileSummary || {}),
        ...quotaSnapshot
      }));
      this.setData({ profileSummary });
      wx.showToast({
        title: "已解锁 1 次生成",
        icon: "success"
      });
      return getTotalRemaining(profileSummary) > 0;
    } catch (error) {
      showError(error, {
        fallback: "广告解锁失败，请稍后再试",
        preferModal: true
      });
      return false;
    } finally {
      wx.hideLoading();
      this.setData({ adUnlocking: false });
    }
  },

  async promptUnlockAction(profileSummary) {
    if (canUnlockByAd(profileSummary) && this.data.rewardedAdEnabled) {
      const tapIndex = await new Promise((resolve) => {
        wx.showActionSheet({
          itemList: ["看广告解锁 1 次", "直接购买 1 次"],
          success: (result) => resolve(result.tapIndex),
          fail: () => resolve(-1)
        });
      });
      if (tapIndex === 0) {
        return this.unlockOneQuotaByAd();
      }
      if (tapIndex === 1) {
        return this.promptPurchaseForQuota();
      }
      return false;
    }
    return this.promptPurchaseForQuota();
  },

  async ensureQuotaBeforeCreateJob() {
    const profileSummary = await this.refreshQuotaSummary().catch(() => this.data.profileSummary);
    if (getTotalRemaining(profileSummary) > 0) {
      return true;
    }
    wx.hideLoading();
    const unlocked = await this.promptUnlockAction(profileSummary);
    if (!unlocked) {
      return false;
    }
    wx.showLoading({ title: "正在提交任务" });
    return true;
  },

  async submitJobRequest() {
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
      hair_color_selection_mode: draft.hair_color_professional_id ? "professional" : "basic",
      hair_color_tone: job.hair_color_tone || draft.hair_color_tone || "",
      hair_color_tone_label: job.hair_color_tone_label || this.data.selectedHairColorToneLabel || "",
      hair_color_technique: job.hair_color_technique || draft.hair_color_technique || "",
      hair_color_technique_label: job.hair_color_technique_label || this.data.selectedHairColorTechniqueLabel || "",
      hair_color_professional_id: job.hair_color_professional_id || draft.hair_color_professional_id || "",
      hair_color_professional_brand: job.hair_color_professional_brand || draft.hair_color_professional_brand || "",
      hair_color_professional_series: job.hair_color_professional_series || draft.hair_color_professional_series || "",
      hair_color_professional_series_label: job.hair_color_professional_series_label || draft.hair_color_professional_series_label || "",
      hair_color_professional_code: job.hair_color_professional_code || draft.hair_color_professional_code || "",
      hair_color_professional_note: job.hair_color_professional_note || draft.hair_color_professional_note || "",
      hair_color_professional_hex_estimate: job.hair_color_professional_hex_estimate || draft.hair_color_professional_hex_estimate || "",
      created_at: job.created_at || new Date().toISOString(),
      updated_at: job.updated_at || job.created_at || new Date().toISOString()
    });
    return job;
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
      const canCreate = await this.ensureQuotaBeforeCreateJob();
      if (!canCreate) {
        return;
      }
      let job;
      try {
        job = await this.submitJobRequest();
      } catch (error) {
        if (getErrorCode(error) !== "quota_exhausted") {
          throw error;
        }
        wx.hideLoading();
        const profileSummary = await this.refreshQuotaSummary().catch(() => this.data.profileSummary);
        const unlocked = await this.promptUnlockAction(profileSummary);
        if (!unlocked) {
          return;
        }
        wx.showLoading({ title: "正在提交任务" });
        job = await this.submitJobRequest();
      }

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
