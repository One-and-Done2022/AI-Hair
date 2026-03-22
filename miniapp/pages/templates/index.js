const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const { request } = require("../../utils/request");

const CURRENT_UPLOAD_STORAGE_KEY = "currentUpload";
const SMART_RECOMMENDATION_STORAGE_KEY = "smartRecommendation";

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
    shortTags: (item.tags || []).slice(0, 2),
    primaryTag: (item.tags || [])[0] || ""
  };
}

function getCachedRecommendation() {
  const recommendation = wx.getStorageSync(SMART_RECOMMENDATION_STORAGE_KEY) || null;
  const upload = wx.getStorageSync(CURRENT_UPLOAD_STORAGE_KEY) || null;
  if (!recommendation || !upload || recommendation.upload_id !== upload.upload_id) {
    return null;
  }
  return recommendation;
}

function buildHairstyleRecommendationMap(recommendation, gender) {
  const groups = recommendation && recommendation.recommended_hairstyles
    ? recommendation.recommended_hairstyles
    : {};
  const items = groups && groups[gender] ? groups[gender] : [];
  return items.reduce((result, item, index) => {
    result[item.id] = {
      rank: index,
      reasons: item.reasons || []
    };
    return result;
  }, {});
}

function filterHairstyles(hairstyles, gender, styleLine = "all", recommendation = null) {
  const recommendationMap = buildHairstyleRecommendationMap(recommendation, gender);
  const filtered = hairstyles.filter((item) => {
    if (item.gender !== gender) {
      return false;
    }
    if (styleLine !== "all" && item.style_line !== styleLine) {
      return false;
    }
    return true;
  });

  return filtered
    .map((item) => {
      const decorated = decorateTemplate(item);
      const recommendationMeta = recommendationMap[item.id];
      return {
        ...decorated,
        recommended: !!recommendationMeta,
        recommendationRank: recommendationMeta ? recommendationMeta.rank : 999,
        recommendationReasons: recommendationMeta ? recommendationMeta.reasons : []
      };
    })
    .sort((left, right) => {
      if (left.recommended !== right.recommended) {
        return left.recommended ? -1 : 1;
      }
      if (
        left.recommended &&
        right.recommended &&
        left.recommendationRank !== right.recommendationRank
      ) {
        return left.recommendationRank - right.recommendationRank;
      }
      return 0;
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

function resolveSelectionState(catalog, cached, recommendation) {
  const allHairstyles = catalog.hairstyles || [];
  const cachedHairstyle = findById(allHairstyles, cached.hairstyle && cached.hairstyle.id);
  const selectedGender = getDefaultGender(allHairstyles, cached);
  const selectedStyleLine = "all";
  const visibleHairstyles = filterHairstyles(
    allHairstyles,
    selectedGender,
    selectedStyleLine,
    recommendation
  );
  const selectedHairstyle =
    findById(visibleHairstyles, cachedHairstyle && cachedHairstyle.id) ||
    visibleHairstyles[0] ||
    null;

  return {
    hairstyles: allHairstyles,
    recommendation,
    visibleHairstyles,
    styleLineOptions: STYLE_LINE_OPTIONS,
    selectedGender,
    selectedStyleLine,
    selectedHairstyleId: selectedHairstyle ? selectedHairstyle.id : "",
    selectedHairstyleName: selectedHairstyle ? selectedHairstyle.name : ""
  };
}

Page({
  data: {
    loading: true,
    hairstyles: [],
    recommendation: null,
    visibleHairstyles: [],
    styleLineOptions: STYLE_LINE_OPTIONS,
    selectedGender: "male",
    selectedStyleLine: "all",
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
      this.setData(resolveSelectionState(catalog, cached, getCachedRecommendation()));
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
      this.data.selectedStyleLine,
      this.data.recommendation
    );
    const selectedHairstyle =
      findById(visibleHairstyles, this.data.selectedHairstyleId) || visibleHairstyles[0] || null;

    this.setData({
      selectedGender: gender,
      visibleHairstyles,
      selectedHairstyleId: selectedHairstyle ? selectedHairstyle.id : "",
      selectedHairstyleName: selectedHairstyle ? selectedHairstyle.name : ""
    });
  },

  selectStyleLine(event) {
    const styleLine = event.currentTarget.dataset.styleLine || "all";
    const visibleHairstyles = filterHairstyles(
      this.data.hairstyles,
      this.data.selectedGender,
      styleLine,
      this.data.recommendation
    );
    const selectedHairstyle =
      findById(visibleHairstyles, this.data.selectedHairstyleId) || visibleHairstyles[0] || null;

    this.setData({
      selectedStyleLine: styleLine,
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

    wx.navigateTo({
      url:
        `/pages/scenes/index?hairstyleId=${hairstyle.id}` +
        `&hairstyleName=${encodeURIComponent(hairstyle.name)}` +
        `&gender=${hairstyle.gender}`
    });
  }
});
