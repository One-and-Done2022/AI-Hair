const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const { request } = require("../../utils/request");

function findById(items, id) {
  if (!id) {
    return null;
  }
  return items.find((item) => item.id === id) || null;
}

const STYLE_LINE_OPTIONS = [
  { id: "all", label: "全部风格" },
  { id: "realistic_editorial", label: "写实写真" },
  { id: "fashion_editorial", label: "时尚大片" }
];

function decorateTemplate(item) {
  return {
    ...item,
    shortTags: (item.tags || []).slice(0, 2)
  };
}

function filterHairstyles(hairstyles, gender, styleLine = "all") {
  return hairstyles.filter((item) => {
    if (item.gender !== gender) {
      return false;
    }
    if (styleLine !== "all" && item.style_line !== styleLine) {
      return false;
    }
    return true;
  });
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
  const allHairstyles = (catalog.hairstyles || []).map(decorateTemplate);
  const cachedHairstyle = findById(allHairstyles, cached.hairstyle && cached.hairstyle.id);
  const selectedGender = getDefaultGender(allHairstyles, cached);
  const selectedStyleLine = "all";
  const visibleHairstyles = filterHairstyles(allHairstyles, selectedGender, selectedStyleLine);
  const selectedHairstyle =
    findById(visibleHairstyles, cachedHairstyle && cachedHairstyle.id) ||
    visibleHairstyles[0] ||
    null;

  return {
    hairstyles: allHairstyles,
    visibleHairstyles,
    styleLineOptions: STYLE_LINE_OPTIONS,
    selectedGender,
    selectedStyleLine,
    selectedHairstyleId: selectedHairstyle ? selectedHairstyle.id : ""
  };
}

Page({
  data: {
    loading: true,
    hairstyles: [],
    visibleHairstyles: [],
    styleLineOptions: STYLE_LINE_OPTIONS,
    selectedGender: "male",
    selectedStyleLine: "all",
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

    const visibleHairstyles = filterHairstyles(
      this.data.hairstyles,
      gender,
      this.data.selectedStyleLine
    );
    const selectedHairstyle =
      findById(visibleHairstyles, this.data.selectedHairstyleId) || visibleHairstyles[0] || null;

    this.setData({
      selectedGender: gender,
      visibleHairstyles,
      selectedHairstyleId: selectedHairstyle ? selectedHairstyle.id : ""
    });
  },

  selectStyleLine(event) {
    const styleLine = event.currentTarget.dataset.styleLine || "all";
    const visibleHairstyles = filterHairstyles(
      this.data.hairstyles,
      this.data.selectedGender,
      styleLine
    );
    const selectedHairstyle =
      findById(visibleHairstyles, this.data.selectedHairstyleId) || visibleHairstyles[0] || null;

    this.setData({
      selectedStyleLine: styleLine,
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
