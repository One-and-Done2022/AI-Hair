const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
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
  buildGenerationSelection,
  findById,
  formatGenerationBackends
} = require("../../utils/generation");

Page({
  data: {
    loading: true,
    selectedImage: "",
    selectedHairstyle: null,
    selectedScene: null,
    selectedGeneratorBackend: "",
    selectedAspectRatio: "3:4",
    selectedResolution: "",
    backendLabel: "",
    backendDescription: "",
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
      const selectedBackend = generationSelection.selectedBackend;
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
        selectedImage,
        selectedHairstyle,
        selectedScene,
        selectedGeneratorBackend: generationSelection.selectedGeneratorBackend,
        selectedAspectRatio: generationSelection.selectedAspectRatio,
        selectedResolution: generationSelection.selectedResolution,
        backendLabel: selectedBackend ? selectedBackend.name : "",
        backendDescription: selectedBackend ? selectedBackend.description : ""
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
      upsertPendingHistoryJob({
        job_id: job.job_id,
        status: job.status,
        upload_url: upload.upload_url || "",
        hairstyle_id: this.data.selectedHairstyle.id,
        hairstyle_name: job.hairstyle_name || this.data.selectedHairstyle.name || "",
        scene_id: this.data.selectedScene.id,
        scene_name: job.scene_name || this.data.selectedScene.name || "",
        generator_backend: this.data.selectedGeneratorBackend,
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
