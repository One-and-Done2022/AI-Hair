const { ensureLogin } = require("../../utils/auth");
const { getErrorCode, showError } = require("../../utils/errors");
const { request, uploadFile } = require("../../utils/request");

const CURRENT_UPLOAD_STORAGE_KEY = "currentUpload";
const SMART_RECOMMENDATION_STORAGE_KEY = "smartRecommendation";

function findById(items, id) {
  if (!id) {
    return null;
  }
  return items.find((item) => item.id === id) || null;
}

function getCachedUpload(selectedImage) {
  const cached = wx.getStorageSync(CURRENT_UPLOAD_STORAGE_KEY) || null;
  if (!cached || !cached.upload_id || cached.local_path !== selectedImage) {
    return null;
  }
  return cached;
}

function getCachedRecommendation(uploadId) {
  const cached = wx.getStorageSync(SMART_RECOMMENDATION_STORAGE_KEY) || null;
  if (!cached || !cached.upload_id || cached.upload_id !== uploadId) {
    return null;
  }
  return cached;
}

Page({
  data: {
    selectedImage: "",
    selectedHairstyle: null,
    selectedScene: null,
    showcaseItems: [],
    profileSummary: null,
    submitting: false,
    preparingRecommendation: false,
    bootstrapping: true
  },

  async onLoad() {
    await this.bootstrap();
  },

  onShow() {
    this.syncSelection();
  },

  async bootstrap() {
    this.setData({ bootstrapping: true });
    try {
      await ensureLogin();
      const [catalog, profileSummary] = await Promise.all([
        request({ url: "/api/templates" }),
        request({ url: "/api/me" })
      ]);
      const cachedSelection = wx.getStorageSync("templateSelection") || {};
      const selectedHairstyle =
        findById(catalog.hairstyles, cachedSelection.hairstyle && cachedSelection.hairstyle.id) ||
        null;
      const selectedScene =
        findById(catalog.scenes, cachedSelection.scene && cachedSelection.scene.id) ||
        null;
      if (selectedHairstyle || selectedScene) {
        wx.setStorageSync("templateSelection", {
          hairstyle: selectedHairstyle,
          scene: selectedScene,
          gender:
            (selectedHairstyle && selectedHairstyle.gender) ||
            cachedSelection.gender ||
            "male"
        });
      } else {
        wx.removeStorageSync("templateSelection");
      }
      this.setData({
        showcaseItems: (catalog.hairstyles || []).slice(0, 4).map((item) => ({
          id: item.id,
          name: item.name,
          coverUrl: item.cover_url,
          tag: item.style_line_label || ((item.tags || [])[0] || "风格")
        })),
        profileSummary,
        selectedHairstyle,
        selectedScene
      });
    } catch (error) {
      showError(error, { fallback: "加载失败，请稍后再试" });
    } finally {
      this.setData({ bootstrapping: false });
    }
  },

  syncSelection() {
    const selection = wx.getStorageSync("templateSelection") || {};
    this.setData({
      selectedHairstyle: selection.hairstyle || this.data.selectedHairstyle,
      selectedScene: selection.scene || this.data.selectedScene
    });
  },

  chooseImage() {
    wx.chooseImage({
      count: 1,
      sizeType: ["compressed"],
      sourceType: ["album"],
      success: (result) => {
        const filePath = result.tempFilePaths[0];
        this.applySelectedImage(filePath);
      }
    });
  },

  openImageSource() {
    wx.showActionSheet({
      itemList: ["手机自拍", "从相册选择"],
      success: (result) => {
        if (result.tapIndex === 0) {
          this.takeSelfie();
          return;
        }
        if (result.tapIndex === 1) {
          this.chooseImage();
        }
      }
    });
  },

  takeSelfie() {
    wx.navigateTo({
      url: "/pages/capture/index",
      success: (result) => {
        result.eventChannel.on("captured", (payload) => {
          if (payload && payload.filePath) {
            this.applySelectedImage(payload.filePath);
          }
        });
      }
    });
  },

  applySelectedImage(filePath) {
    if (!filePath) {
      return;
    }
    wx.removeStorageSync(CURRENT_UPLOAD_STORAGE_KEY);
    wx.removeStorageSync(SMART_RECOMMENDATION_STORAGE_KEY);
    this.setData({ selectedImage: filePath });
  },

  previewImage() {
    if (!this.data.selectedImage) {
      return;
    }
    wx.previewImage({
      urls: [this.data.selectedImage]
    });
  },

  async ensureCurrentUpload() {
    const cachedUpload = getCachedUpload(this.data.selectedImage);
    if (cachedUpload) {
      return cachedUpload;
    }

    const upload = await uploadFile({
      url: "/api/uploads",
      filePath: this.data.selectedImage,
      name: "file"
    });
    const preparedUpload = {
      ...upload,
      local_path: this.data.selectedImage
    };
    wx.setStorageSync(CURRENT_UPLOAD_STORAGE_KEY, preparedUpload);
    return preparedUpload;
  },

  async ensureRecommendation() {
    const upload = await this.ensureCurrentUpload();
    const cachedRecommendation = getCachedRecommendation(upload.upload_id);
    if (cachedRecommendation) {
      return cachedRecommendation;
    }

    try {
      const recommendation = await request({
        url: "/api/recommendations",
        method: "POST",
        data: {
          upload_id: upload.upload_id
        }
      });
      const preparedRecommendation = {
        ...recommendation,
        local_path: this.data.selectedImage
      };
      wx.setStorageSync(SMART_RECOMMENDATION_STORAGE_KEY, preparedRecommendation);
      return preparedRecommendation;
    } catch (error) {
      if (getErrorCode(error) === "recommendation_unavailable") {
        wx.removeStorageSync(SMART_RECOMMENDATION_STORAGE_KEY);
        wx.showToast({
          title: "暂时无法完成智能推荐，可继续手动选择",
          icon: "none"
        });
        return null;
      }
      throw error;
    }
  },

  async prepareRecommendation() {
    if (!this.data.selectedImage) {
      return null;
    }
    await ensureLogin();
    return this.ensureRecommendation();
  },

  async openTemplatePicker() {
    if (this.data.selectedImage) {
      this.setData({ preparingRecommendation: true });
      wx.showLoading({ title: "正在分析照片" });
      try {
        await this.prepareRecommendation();
      } catch (error) {
        showError(error, {
          fallback: "照片分析失败，请换一张试试",
          preferModal: true
        });
        return;
      } finally {
        wx.hideLoading();
        this.setData({ preparingRecommendation: false });
      }
    }

    wx.navigateTo({
      url: "/pages/templates/index"
    });
  },

  async openScenePicker() {
    const hairstyle = this.data.selectedHairstyle;
    if (!hairstyle) {
      await this.openTemplatePicker();
      return;
    }

    if (this.data.selectedImage) {
      this.setData({ preparingRecommendation: true });
      wx.showLoading({ title: "正在分析照片" });
      try {
        await this.prepareRecommendation();
      } catch (error) {
        showError(error, {
          fallback: "照片分析失败，请换一张试试",
          preferModal: true
        });
        return;
      } finally {
        wx.hideLoading();
        this.setData({ preparingRecommendation: false });
      }
    }

    wx.navigateTo({
      url:
        `/pages/scenes/index?hairstyleId=${hairstyle.id}` +
        `&hairstyleName=${encodeURIComponent(hairstyle.name || "")}` +
        `&gender=${hairstyle.gender || "male"}`
    });
  },

  async createJob() {
    if (!this.data.selectedImage) {
      wx.showToast({ title: "请先上传照片", icon: "none" });
      return;
    }
    if (!this.data.selectedHairstyle || !this.data.selectedScene) {
      wx.showToast({ title: "请先选择发型和场景", icon: "none" });
      return;
    }

    this.setData({ submitting: true });
    wx.showLoading({ title: "正在提交任务" });
    try {
      await ensureLogin();
      const upload = await this.ensureCurrentUpload();
      const job = await request({
        url: "/api/jobs",
        method: "POST",
        data: {
          upload_id: upload.upload_id,
          hairstyle_id: this.data.selectedHairstyle.id,
          scene_id: this.data.selectedScene.id
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
  },

  goHistory() {
    wx.switchTab({
      url: "/pages/history/index"
    });
  }
});
