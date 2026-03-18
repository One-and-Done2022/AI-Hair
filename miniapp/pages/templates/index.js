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

function findById(items, id) {
  if (!id) {
    return null;
  }
  return items.find((item) => item.id === id) || null;
}

function filterHairstyles(hairstyles, gender) {
  return hairstyles.filter((item) => item.gender === gender);
}

function getDefaultGender(hairstyles, cached) {
  const cachedGender = cached.hairstyle && cached.hairstyle.gender;
  if (cachedGender === "male" || cachedGender === "female") {
    return cachedGender;
  }
  if (cached.gender === "male" || cached.gender === "female") {
    return cached.gender;
  }
  return hairstyles[0] ? hairstyles[0].gender : "male";
}

function resolveSelectionState(catalog, cached) {
  const allHairstyles = catalog.hairstyles || [];
  const allScenes = catalog.scenes || [];
  const cachedHairstyle = findById(allHairstyles, cached.hairstyle && cached.hairstyle.id);
  const selectedGender = getDefaultGender(allHairstyles, cached);
  const visibleHairstyles = filterHairstyles(allHairstyles, selectedGender);
  const selectedHairstyle =
    findById(visibleHairstyles, cachedHairstyle && cachedHairstyle.id) ||
    visibleHairstyles[0] ||
    null;
  const selectedScene = findById(allScenes, cached.scene && cached.scene.id) || allScenes[0] || null;

  return {
    hairstyles: allHairstyles,
    visibleHairstyles,
    scenes: allScenes,
    selectedGender,
    selectedHairstyleId: selectedHairstyle ? selectedHairstyle.id : "",
    selectedSceneId: selectedScene ? selectedScene.id : ""
  };
}

Page({
  data: {
    loading: true,
    hairstyles: [],
    visibleHairstyles: [],
    scenes: [],
    selectedGender: "male",
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
      this.setData(resolveSelectionState(catalog, cached));
    } catch (error) {
      wx.showToast({
        title: getErrorMessage(error),
        icon: "none"
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  selectGender(event) {
    const gender = event.currentTarget.dataset.gender;
    if (gender !== "male" && gender !== "female") {
      return;
    }

    const visibleHairstyles = filterHairstyles(this.data.hairstyles, gender);
    const selectedHairstyle =
      findById(visibleHairstyles, this.data.selectedHairstyleId) || visibleHairstyles[0] || null;

    this.setData({
      selectedGender: gender,
      visibleHairstyles,
      selectedHairstyleId: selectedHairstyle ? selectedHairstyle.id : ""
    });
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
    const hairstyle = findById(this.data.hairstyles, this.data.selectedHairstyleId);
    const scene = findById(this.data.scenes, this.data.selectedSceneId);

    if (!hairstyle || !scene) {
      wx.showToast({
        title: "请选择发型和场景",
        icon: "none"
      });
      return;
    }

    wx.setStorageSync("templateSelection", {
      hairstyle,
      scene,
      gender: this.data.selectedGender
    });
    wx.showToast({
      title: "模板已更新",
      icon: "success"
    });
    setTimeout(() => {
      wx.navigateBack();
    }, 350);
  }
});
