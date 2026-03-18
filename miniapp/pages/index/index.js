const { ensureLogin } = require("../../utils/auth");
const { request, uploadFile } = require("../../utils/request");

function getErrorMessage(error) {
  if (!error) {
    return "请求失败，请稍后再试";
  }
  if (typeof error === "string") {
    return error;
  }
  if (error.detail && error.detail.message) {
    return error.detail.message;
  }
  if (error.detail && typeof error.detail === "string") {
    return error.detail;
  }
  if (error.message) {
    return error.message;
  }
  return "请求失败，请稍后再试";
}

function findById(items, id) {
  if (!id) {
    return null;
  }
  return items.find((item) => item.id === id) || null;
}

Page({
  data: {
    selectedImage: "",
    selectedHairstyle: null,
    selectedScene: null,
    loading: false,
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
      const catalog = await request({ url: "/api/templates" });
      const cachedSelection = wx.getStorageSync("templateSelection") || {};
      const selectedHairstyle =
        findById(catalog.hairstyles, cachedSelection.hairstyle && cachedSelection.hairstyle.id) ||
        catalog.hairstyles[0] ||
        null;
      const selectedScene =
        findById(catalog.scenes, cachedSelection.scene && cachedSelection.scene.id) ||
        catalog.scenes[0] ||
        null;
      wx.setStorageSync("templateSelection", {
        hairstyle: selectedHairstyle,
        scene: selectedScene,
        gender: selectedHairstyle ? selectedHairstyle.gender : "male"
      });
      this.setData({
        selectedHairstyle,
        selectedScene
      });
    } catch (error) {
      wx.showToast({
        title: getErrorMessage(error),
        icon: "none"
      });
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
      sourceType: ["album", "camera"],
      success: (result) => {
        const filePath = result.tempFilePaths[0];
        this.setData({ selectedImage: filePath });
      }
    });
  },

  previewImage() {
    if (!this.data.selectedImage) {
      return;
    }
    wx.previewImage({
      urls: [this.data.selectedImage]
    });
  },

  openTemplatePicker() {
    wx.navigateTo({
      url: "/pages/templates/index"
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

    this.setData({ loading: true });
    wx.showLoading({ title: "正在提交任务" });
    try {
      await ensureLogin();
      const upload = await uploadFile({
        url: "/api/uploads",
        filePath: this.data.selectedImage,
        name: "file"
      });
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
        url: `/pages/result/index?jobId=${job.job_id}`
      });
    } catch (error) {
      wx.showToast({
        title: getErrorMessage(error),
        icon: "none"
      });
    } finally {
      wx.hideLoading();
      this.setData({ loading: false });
    }
  }
});
