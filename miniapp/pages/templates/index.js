const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const { request } = require("../../utils/request");
const {
  readCreationDraft,
  resetCreationDraft,
  updateCreationDraft
} = require("../../utils/creation-draft");

function findById(items, id) {
  if (!id) {
    return null;
  }
  return (items || []).find((item) => item.id === id) || null;
}

function decorateTemplate(item) {
  return {
    ...item,
    primaryTag: (item.tags || [])[0] || ""
  };
}

function filterHairstyles(hairstyles, gender, categoryKey = "all") {
  return (hairstyles || []).filter((item) => {
    if (item.gender !== gender) {
      return false;
    }
    if (categoryKey !== "all" && item.category_key !== categoryKey) {
      return false;
    }
    return true;
  });
}

function buildCategoryOptions(hairstyles, gender) {
  const options = [{ id: "all", label: "全部分类" }];
  const seen = new Set();

  (hairstyles || []).forEach((item) => {
    if (item.gender !== gender) {
      return;
    }
    if (!item.category_key || !item.category_label || seen.has(item.category_key)) {
      return;
    }
    seen.add(item.category_key);
    options.push({
      id: item.category_key,
      label: item.category_label
    });
  });

  return options;
}

function getDefaultGender(hairstyles, draft) {
  if (draft.hairstyle && (draft.hairstyle.gender === "male" || draft.hairstyle.gender === "female")) {
    return draft.hairstyle.gender;
  }
  if (draft.gender === "male" || draft.gender === "female") {
    return draft.gender;
  }
  return (hairstyles[0] && hairstyles[0].gender) || "female";
}

function resolveSelectionState(catalog, draft) {
  const allHairstyles = catalog.hairstyles || [];
  const cachedHairstyle = findById(allHairstyles, draft.hairstyle && draft.hairstyle.id);
  const selectedGender = getDefaultGender(allHairstyles, draft);
  const categoryOptions = buildCategoryOptions(allHairstyles, selectedGender);
  const selectedCategoryKey =
    (cachedHairstyle && cachedHairstyle.category_key) || "all";
  const visibleHairstyles = filterHairstyles(
    allHairstyles,
    selectedGender,
    selectedCategoryKey
  ).map(decorateTemplate);
  const selectedHairstyle =
    findById(visibleHairstyles, cachedHairstyle && cachedHairstyle.id) ||
    visibleHairstyles[0] ||
    null;

  return {
    hairstyles: allHairstyles,
    categoryOptions,
    selectedGender,
    selectedCategoryKey,
    visibleHairstyles,
    selectedHairstyleId: selectedHairstyle ? selectedHairstyle.id : "",
    selectedHairstyleName: selectedHairstyle ? selectedHairstyle.name : ""
  };
}

Page({
  data: {
    loading: true,
    hairstyles: [],
    visibleHairstyles: [],
    categoryOptions: [],
    selectedGender: "female",
    selectedCategoryKey: "all",
    selectedHairstyleId: "",
    selectedHairstyleName: ""
  },

  async onLoad() {
    await this.loadTemplates();
  },

  async loadTemplates() {
    const draft = readCreationDraft();
    if (!draft.imagePath) {
      wx.showToast({
        title: "请先上传照片",
        icon: "none"
      });
      wx.switchTab({
        url: "/pages/index/index"
      });
      return;
    }

    this.setData({ loading: true });
    try {
      await ensureLogin();
      const catalog = await request({ url: "/api/templates" });
      this.catalog = catalog;
      this.setData(resolveSelectionState(catalog, draft));
    } catch (error) {
      showError(error, { fallback: "加载发型失败" });
    } finally {
      this.setData({ loading: false });
    }
  },

  goBackStep() {
    wx.navigateBack({
      fail: () => {
        wx.switchTab({ url: "/pages/index/index" });
      }
    });
  },

  resetFlow() {
    resetCreationDraft();
    wx.switchTab({
      url: "/pages/index/index"
    });
  },

  selectGender(event) {
    const gender = event.currentTarget.dataset.gender;
    if (gender !== "male" && gender !== "female") {
      return;
    }

    const categoryOptions = buildCategoryOptions(this.data.hairstyles, gender);
    const selectedCategoryKey = "all";
    const visibleHairstyles = filterHairstyles(
      this.data.hairstyles,
      gender,
      selectedCategoryKey
    ).map(decorateTemplate);
    const selectedHairstyle = visibleHairstyles[0] || null;

    this.setData({
      selectedGender: gender,
      categoryOptions,
      selectedCategoryKey,
      visibleHairstyles,
      selectedHairstyleId: selectedHairstyle ? selectedHairstyle.id : "",
      selectedHairstyleName: selectedHairstyle ? selectedHairstyle.name : ""
    });
  },

  selectCategory(event) {
    const categoryKey = event.currentTarget.dataset.categoryKey || "all";
    const visibleHairstyles = filterHairstyles(
      this.data.hairstyles,
      this.data.selectedGender,
      categoryKey
    ).map(decorateTemplate);
    const selectedHairstyle =
      findById(visibleHairstyles, this.data.selectedHairstyleId) || visibleHairstyles[0] || null;

    this.setData({
      selectedCategoryKey: categoryKey,
      visibleHairstyles,
      selectedHairstyleId: selectedHairstyle ? selectedHairstyle.id : "",
      selectedHairstyleName: selectedHairstyle ? selectedHairstyle.name : ""
    });
  },

  selectHairstyle(event) {
    const selectedId = event.currentTarget.dataset.id;
    const selectedHairstyle = findById(this.data.hairstyles, selectedId);
    if (!selectedHairstyle) {
      return;
    }

    this.setData({
      selectedHairstyleId: selectedId,
      selectedHairstyleName: selectedHairstyle.name || ""
    });
    updateCreationDraft({
      hairstyle: selectedHairstyle,
      scene: null,
      gender: selectedHairstyle.gender || this.data.selectedGender
    });
  },

  previewHairstyle(event) {
    const selectedId = event.currentTarget.dataset.id;
    const selectedHairstyle = findById(this.data.hairstyles, selectedId);
    if (!selectedHairstyle || !selectedHairstyle.cover_url) {
      return;
    }
    wx.previewImage({
      current: selectedHairstyle.cover_url,
      urls: [selectedHairstyle.cover_url]
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

    updateCreationDraft({
      hairstyle,
      scene: null,
      gender: hairstyle.gender || this.data.selectedGender
    });

    wx.navigateTo({
      url: "/pages/scenes/index"
    });
  }
});
