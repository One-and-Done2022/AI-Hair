const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const { request } = require("../../utils/request");
const {
  readCreationDraft,
  resetCreationDraft,
  updateCreationDraft
} = require("../../utils/creation-draft");

const STYLE_LINE_OPTIONS = [
  { id: "all", label: "全部场景" },
  { id: "realistic_editorial", label: "写实写真" },
  { id: "fashion_editorial", label: "时尚大片" }
];

function findById(items, id) {
  if (!id) {
    return null;
  }
  return (items || []).find((item) => item.id === id) || null;
}

function decorateScene(item) {
  return {
    ...item,
    shortTags: (item.tags || []).slice(0, 2),
    primaryTag: (item.tags || [])[0] || ""
  };
}

function buildVisibleScenes(scenes, styleLine) {
  return (scenes || []).filter((item) => {
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

function buildHairstyleMeta(item) {
  if (!item) {
    return "";
  }
  return item.category_label || item.style_line_label || "";
}

Page({
  data: {
    loading: true,
    selectedHairstyle: null,
    selectedHairstyleMeta: "",
    scenes: [],
    visibleScenes: [],
    selectedSceneId: "",
    selectedSceneName: "",
    selectedStyleLine: "all",
    styleLineOptions: STYLE_LINE_OPTIONS
  },

  async onLoad() {
    await this.loadScenes();
  },

  async loadScenes() {
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

    if (!draft.hairstyle || !draft.hairstyle.id) {
      wx.redirectTo({
        url: "/pages/templates/index"
      });
      return;
    }

    this.setData({ loading: true });
    try {
      await ensureLogin();
      const catalog = await request({ url: "/api/templates" });
      this.catalog = catalog;

      const selectedHairstyle =
        findById(catalog.hairstyles, draft.hairstyle.id) || draft.hairstyle;
      const decoratedScenes = (catalog.scenes || []).map(decorateScene);
      const selectedScene =
        findById(decoratedScenes, draft.scene && draft.scene.id) || null;
      const selectedStyleLine =
        (selectedScene && selectedScene.style_line) ||
        (selectedHairstyle && selectedHairstyle.style_line) ||
        "all";
      const sceneSelection = resolveVisibleSceneSelection(
        decoratedScenes,
        selectedStyleLine,
        selectedScene ? selectedScene.id : ""
      );

      this.setData({
        loading: false,
        selectedHairstyle,
        selectedHairstyleMeta: buildHairstyleMeta(selectedHairstyle),
        scenes: decoratedScenes,
        selectedStyleLine,
        visibleScenes: sceneSelection.visibleScenes,
        selectedSceneId: sceneSelection.selectedSceneId,
        selectedSceneName: sceneSelection.selectedSceneName
      });
    } catch (error) {
      this.setData({ loading: false });
      showError(error, { fallback: "加载场景失败" });
    }
  },

  goBackStep() {
    wx.navigateBack({
      fail: () => {
        wx.redirectTo({ url: "/pages/templates/index" });
      }
    });
  },

  resetFlow() {
    resetCreationDraft();
    wx.switchTab({
      url: "/pages/index/index"
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

  selectScene(event) {
    const selectedId = event.currentTarget.dataset.id;
    const selectedScene = findById(this.data.scenes, selectedId);
    if (!selectedScene) {
      return;
    }

    this.setData({
      selectedSceneId: selectedId,
      selectedSceneName: selectedScene.name || ""
    });
    updateCreationDraft({
      scene: selectedScene
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

  goNext() {
    const selectedScene = findById(this.data.scenes, this.data.selectedSceneId);
    if (!selectedScene) {
      wx.showToast({
        title: "请先选择场景",
        icon: "none"
      });
      return;
    }

    updateCreationDraft({
      scene: selectedScene
    });
    wx.navigateTo({
      url: "/pages/options/index"
    });
  }
});
