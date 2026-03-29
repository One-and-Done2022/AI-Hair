const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const { request } = require("../../utils/request");

function findById(items, id) {
  if (!id) {
    return null;
  }
  return items.find((item) => item.id === id) || null;
}

function decorateTemplate(item) {
  return {
    ...item,
    primaryTag: (item.tags || [])[0] || ""
  };
}

function filterHairstyles(hairstyles, gender, categoryKey = "all") {
  return hairstyles.filter((item) => {
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

  hairstyles.forEach((item) => {
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
  const categoryOptions = buildCategoryOptions(allHairstyles, selectedGender);
  const selectedCategoryKey =
    cachedHairstyle && cachedHairstyle.category_key
      ? cachedHairstyle.category_key
      : "all";
  const visibleHairstyles = filterHairstyles(allHairstyles, selectedGender, selectedCategoryKey)
    .map(decorateTemplate);
  const selectedHairstyle =
    findById(visibleHairstyles, cachedHairstyle && cachedHairstyle.id) ||
    visibleHairstyles[0] ||
    null;

  return {
    hairstyles: allHairstyles,
    visibleHairstyles,
    categoryOptions,
    selectedGender,
    selectedCategoryKey,
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
    selectedGender: "male",
    selectedCategoryKey: "all",
    selectedHairstyleId: "",
    selectedHairstyleName: ""
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
      showError(error, { fallback: "加载失败" });
    } finally {
      this.setData({ loading: false });
    }
  },

  selectGender(event) {
    const gender = event.currentTarget.dataset.gender;
    if (gender !== "male" && gender !== "female") {
      return;
    }

    const categoryOptions = buildCategoryOptions(this.data.hairstyles, gender);
    const hasCurrentCategory = categoryOptions.some(
      (item) => item.id === this.data.selectedCategoryKey
    );
    const selectedCategoryKey = hasCurrentCategory ? this.data.selectedCategoryKey : "all";
    const visibleHairstyles = filterHairstyles(
      this.data.hairstyles,
      gender,
      selectedCategoryKey
    ).map(decorateTemplate);
    const selectedHairstyle =
      findById(visibleHairstyles, this.data.selectedHairstyleId) || visibleHairstyles[0] || null;

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
    this.setData({
      selectedHairstyleId: selectedId,
      selectedHairstyleName: selectedHairstyle ? selectedHairstyle.name : ""
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

    const cachedSelection = wx.getStorageSync("templateSelection") || {};
    const keepScene =
      cachedSelection.hairstyle &&
      cachedSelection.hairstyle.id === hairstyle.id
        ? cachedSelection.scene || null
        : null;

    wx.setStorageSync("templateSelection", {
      hairstyle,
      scene: keepScene,
      gender: hairstyle.gender
    });

    wx.navigateTo({
      url:
        `/pages/scenes/index?hairstyleId=${hairstyle.id}` +
        `&hairstyleName=${encodeURIComponent(hairstyle.name)}` +
        `&gender=${hairstyle.gender}`
    });
  }
});
