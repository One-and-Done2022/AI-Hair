const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const { request, uploadFile } = require("../../utils/request");

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
        this.setData({ selectedImage: filePath });
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
            this.setData({ selectedImage: payload.filePath });
          }
        });
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

  openScenePicker() {
    const hairstyle = this.data.selectedHairstyle;
    if (!hairstyle) {
      this.openTemplatePicker();
      return;
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
      this.setData({ loading: false });
    }
  },

  goHistory() {
    wx.switchTab({
      url: "/pages/history/index"
    });
  }
});
