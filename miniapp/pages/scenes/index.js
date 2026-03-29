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

function buildHairstyleMeta(item) {
  if (!item) {
    return "";
  }
  return item.category_label || item.style_line_label || "";
}

const STYLE_LINE_OPTIONS = [
  { id: "all", label: "全部场景" },
  { id: "realistic_editorial", label: "写实写真" },
  { id: "fashion_editorial", label: "时尚大片" }
];

function decorateScene(item) {
  return {
    ...item,
    shortTags: (item.tags || []).slice(0, 2),
    primaryTag: (item.tags || [])[0] || ""
  };
}

function buildVisibleScenes(scenes, styleLine) {
  return scenes.filter((item) => {
    if (styleLine !== "all" && item.style_line !== styleLine) {
      return false;
    }
    return true;
  });
}

function resolveVisibleSceneSelection(scenes, styleLine, selectedSceneId) {
  const visibleScenes = buildVisibleScenes(scenes, styleLine);
  const selectedScene = findById(visibleScenes, selectedSceneId) || visibleScenes[0] || null;
  return {
    visibleScenes,
    selectedSceneId: selectedScene ? selectedScene.id : "",
    selectedSceneName: selectedScene ? selectedScene.name : ""
  };
}

Page({
  data: {
    loading: true,
    selectedHairstyle: null,
    selectedHairstyleMeta: "",
    selectedGender: "",
    scenes: [],
    selectedSceneId: "",
    selectedStyleLine: "all",
    styleLineOptions: STYLE_LINE_OPTIONS,
    visibleScenes: [],
    selectedSceneName: ""
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
      const decoratedScenes = (catalog.scenes || []).map(decorateScene);
      const selectedStyleLine = (selectedHairstyle && selectedHairstyle.style_line) || "all";

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
        selectedHairstyleMeta: buildHairstyleMeta(selectedHairstyle),
        selectedGender: selectedHairstyle ? selectedHairstyle.gender : this.gender,
        scenes: decoratedScenes,
        selectedStyleLine,
        visibleScenes: sceneSelection.visibleScenes,
        selectedSceneId: sceneSelection.selectedSceneId,
        selectedSceneName: sceneSelection.selectedSceneName
      });
    } catch (error) {
      showError(error, { fallback: "加载失败" });
    } finally {
      this.setData({ loading: false });
    }
  },

  selectScene(event) {
    const selectedId = event.currentTarget.dataset.id;
    const selectedScene = findById(this.data.scenes, selectedId);
    this.setData({
      selectedSceneId: selectedId,
      selectedSceneName: selectedScene ? selectedScene.name : ""
    });
  },

  previewScene(event) {
    const selectedId = event.currentTarget.dataset.id;
    const selectedScene = findById(this.data.scenes, selectedId);
    if (!selectedScene || !selectedScene.cover_url) {
      return;
    }
    wx.previewImage({
      current: selectedScene.cover_url,
      urls: [selectedScene.cover_url]
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
      selectedSceneId: sceneSelection.selectedSceneId,
      selectedSceneName: sceneSelection.selectedSceneName
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
