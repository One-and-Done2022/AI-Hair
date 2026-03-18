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
  const cachedHairstyle = findById(allHairstyles, cached.hairstyle && cached.hairstyle.id);
  const selectedGender = getDefaultGender(allHairstyles, cached);
  const visibleHairstyles = filterHairstyles(allHairstyles, selectedGender);
  const selectedHairstyle =
    findById(visibleHairstyles, cachedHairstyle && cachedHairstyle.id) ||
    visibleHairstyles[0] ||
    null;

  return {
    hairstyles: allHairstyles,
    visibleHairstyles,
    selectedGender,
    selectedHairstyleId: selectedHairstyle ? selectedHairstyle.id : ""
  };
}

Page({
  data: {
    loading: true,
    hairstyles: [],
    visibleHairstyles: [],
    selectedGender: "male",
    selectedHairstyleId: ""
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

  goNext() {
    const hairstyle = findById(this.data.hairstyles, this.data.selectedHairstyleId);
    if (!hairstyle) {
      wx.showToast({
        title: "请先选择发型",
        icon: "none"
      });
      return;
    }

    wx.navigateTo({
      url:
        `/pages/scenes/index?hairstyleId=${hairstyle.id}` +
        `&hairstyleName=${encodeURIComponent(hairstyle.name)}` +
        `&gender=${hairstyle.gender}`
    });
  }
});
