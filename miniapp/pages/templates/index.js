const { ensureLogin } = require("../../utils/auth");
const { request } = require("../../utils/request");

function getErrorMessage(error) {
  if (!error) {
    return "加载失败";
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
  return error.message || "加载失败";
}

Page({
  data: {
    loading: true,
    hairstyles: [],
    scenes: [],
    selectedHairstyleId: "",
    selectedSceneId: ""
  },

  async onLoad() {
    await this.loadTemplates();
  },

  async loadTemplates() {
    this.setData({ loading: true });
    try {
      await ensureLogin();
      const catalog = await request({ url: "/api/templates" });
      const cached = wx.getStorageSync("templateSelection") || {};
      this.setData({
        hairstyles: catalog.hairstyles,
        scenes: catalog.scenes,
        selectedHairstyleId: cached.hairstyle ? cached.hairstyle.id : catalog.hairstyles[0].id,
        selectedSceneId: cached.scene ? cached.scene.id : catalog.scenes[0].id
      });
    } catch (error) {
      wx.showToast({
        title: getErrorMessage(error),
        icon: "none"
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  selectHairstyle(event) {
    this.setData({
      selectedHairstyleId: event.currentTarget.dataset.id
    });
  },

  selectScene(event) {
    this.setData({
      selectedSceneId: event.currentTarget.dataset.id
    });
  },

  saveSelection() {
    const hairstyle = this.data.hairstyles.find(
      (item) => item.id === this.data.selectedHairstyleId
    );
    const scene = this.data.scenes.find(
      (item) => item.id === this.data.selectedSceneId
    );

    wx.setStorageSync("templateSelection", { hairstyle, scene });
    wx.showToast({
      title: "模板已更新",
      icon: "success"
    });
    setTimeout(() => {
      wx.navigateBack();
    }, 350);
  }
});

