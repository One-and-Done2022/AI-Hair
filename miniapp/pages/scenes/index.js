const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const { request } = require("../../utils/request");

function findById(items, id) {
  if (!id) {
    return null;
  }
  return items.find((item) => item.id === id) || null;
}

function decodeText(value) {
  if (!value) {
    return "";
  }
  try {
    return decodeURIComponent(value);
  } catch (error) {
    return value;
  }
}

Page({
  data: {
    loading: true,
    selectedHairstyle: null,
    selectedGender: "",
    scenes: [],
    selectedSceneId: ""
  },

  async onLoad(options) {
    this.hairstyleId = options.hairstyleId || "";
    this.hairstyleName = decodeText(options.hairstyleName);
    this.gender = options.gender || "";
    await this.loadScenes();
  },

  async loadScenes() {
    this.setData({ loading: true });
    try {
      await ensureLogin();
      const catalog = await request({ url: "/api/templates" });
      const cached = wx.getStorageSync("templateSelection") || {};
      const selectedHairstyle =
        findById(catalog.hairstyles, this.hairstyleId) ||
        findById(catalog.hairstyles, cached.hairstyle && cached.hairstyle.id) ||
        catalog.hairstyles[0] ||
        null;
      const selectedScene =
        findById(catalog.scenes, cached.scene && cached.scene.id) ||
        catalog.scenes[0] ||
        null;

      this.setData({
        selectedHairstyle: selectedHairstyle
          ? selectedHairstyle
          : {
              id: this.hairstyleId,
              name: this.hairstyleName,
              gender: this.gender
            },
        selectedGender: selectedHairstyle ? selectedHairstyle.gender : this.gender,
        scenes: catalog.scenes || [],
        selectedSceneId: selectedScene ? selectedScene.id : ""
      });
    } catch (error) {
      showError(error, { fallback: "加载失败" });
    } finally {
      this.setData({ loading: false });
    }
  },

  selectScene(event) {
    this.setData({
      selectedSceneId: event.currentTarget.dataset.id
    });
  },

  goBackStep() {
    wx.navigateBack();
  },

  saveSelection() {
    const selectedHairstyle = this.data.selectedHairstyle;
    const selectedScene = findById(this.data.scenes, this.data.selectedSceneId);

    if (!selectedHairstyle || !selectedScene) {
      wx.showToast({
        title: "请先选择场景",
        icon: "none"
      });
      return;
    }

    wx.setStorageSync("templateSelection", {
      hairstyle: selectedHairstyle,
      scene: selectedScene,
      gender: selectedHairstyle.gender || this.data.selectedGender || "male"
    });

    wx.showToast({
      title: "模板已更新",
      icon: "success"
    });

    setTimeout(() => {
      const pageCount = getCurrentPages().length;
      if (pageCount >= 3) {
        wx.navigateBack({ delta: 2 });
        return;
      }
      wx.switchTab({
        url: "/pages/index/index"
      });
    }, 350);
  }
});
