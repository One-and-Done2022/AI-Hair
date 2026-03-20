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

const STYLE_LINE_OPTIONS = [
  { id: "all", label: "全部场景" },
  { id: "realistic_editorial", label: "写实写真" },
  { id: "fashion_editorial", label: "时尚大片" }
];

function decorateScene(item, selectedHairstyle) {
  const isRecommended =
    !!selectedHairstyle &&
    !!selectedHairstyle.style_line &&
    item.style_line === selectedHairstyle.style_line;

  return {
    ...item,
    shortTags: (item.tags || []).slice(0, 2),
    recommended: isRecommended
  };
}

function buildVisibleScenes(scenes, styleLine) {
  const filtered = scenes.filter((item) => {
    if (styleLine !== "all" && item.style_line !== styleLine) {
      return false;
    }
    return true;
  });

  return filtered.sort((left, right) => {
    if (left.recommended === right.recommended) {
      return 0;
    }
    return left.recommended ? -1 : 1;
  });
}

function resolveVisibleSceneSelection(scenes, styleLine, selectedSceneId) {
  const visibleScenes = buildVisibleScenes(scenes, styleLine);
  const selectedScene = findById(visibleScenes, selectedSceneId) || visibleScenes[0] || null;
  return {
    visibleScenes,
    selectedSceneId: selectedScene ? selectedScene.id : ""
  };
}

Page({
  data: {
    loading: true,
    selectedHairstyle: null,
    selectedGender: "",
    scenes: [],
    selectedSceneId: "",
    selectedStyleLine: "all",
    styleLineOptions: STYLE_LINE_OPTIONS,
    visibleScenes: []
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
      const decoratedScenes = (catalog.scenes || []).map((item) =>
        decorateScene(item, selectedHairstyle)
      );
      const selectedStyleLine =
        (selectedHairstyle && selectedHairstyle.style_line) || "all";

      const sceneSelection = resolveVisibleSceneSelection(
        decoratedScenes,
        selectedStyleLine,
        selectedScene ? selectedScene.id : ""
      );

      this.setData({
        selectedHairstyle: selectedHairstyle
          ? selectedHairstyle
          : {
              id: this.hairstyleId,
              name: this.hairstyleName,
              gender: this.gender
            },
        selectedGender: selectedHairstyle ? selectedHairstyle.gender : this.gender,
        scenes: decoratedScenes,
        selectedStyleLine,
        visibleScenes: sceneSelection.visibleScenes,
        selectedSceneId: sceneSelection.selectedSceneId
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

  selectStyleLine(event) {
    const styleLine = event.currentTarget.dataset.styleLine || "all";
    const sceneSelection = resolveVisibleSceneSelection(
      this.data.scenes,
      styleLine,
      this.data.selectedSceneId
    );
    this.setData({
      selectedStyleLine: styleLine,
      visibleScenes: sceneSelection.visibleScenes,
      selectedSceneId: sceneSelection.selectedSceneId
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
