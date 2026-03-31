const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const { request } = require("../../utils/request");
const {
  readCreationDraft,
  resetCreationDraft,
  updateCreationDraft
} = require("../../utils/creation-draft");
const { findById } = require("../../utils/generation");

Page({
  data: {
    loading: true,
    item: null,
    hasImage: false
  },

  async onLoad(options) {
    this.showcaseId = options.id || "";
    await this.loadShowcase();
  },

  async loadShowcase() {
    if (!this.showcaseId) {
      wx.navigateBack();
      return;
    }

    this.setData({
      loading: true,
      hasImage: !!readCreationDraft().imagePath
    });

    try {
      await ensureLogin();
      const [showcases, catalog] = await Promise.all([
        request({ url: "/api/templates/showcases" }),
        request({ url: "/api/templates" })
      ]);
      const rawItem = findById(showcases.items || [], this.showcaseId);
      if (!rawItem) {
        wx.showToast({
          title: "示例不存在",
          icon: "none"
        });
        wx.navigateBack();
        return;
      }

      const hairstyle = findById(catalog.hairstyles || [], rawItem.hairstyle_id) || {
        id: rawItem.hairstyle_id,
        name: rawItem.hairstyle_name,
        cover_url: rawItem.hairstyle_cover_url
      };
      const scene = findById(catalog.scenes || [], rawItem.scene_id) || {
        id: rawItem.scene_id,
        name: rawItem.scene_name,
        cover_url: rawItem.scene_cover_url
      };

      this.setData({
        loading: false,
        item: {
          ...rawItem,
          hairstyle,
          scene
        }
      });
    } catch (error) {
      this.setData({ loading: false });
      showError(error, { fallback: "加载示例失败" });
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

  applyShowcase() {
    const { item, hasImage } = this.data;
    if (!item) {
      return;
    }
    if (!hasImage) {
      wx.showToast({
        title: "请先上传照片",
        icon: "none"
      });
      return;
    }

    updateCreationDraft({
      hairstyle: item.hairstyle,
      scene: item.scene,
      gender: item.hairstyle.gender || "",
      generator_backend: item.generator_backend,
      aspect_ratio: item.aspect_ratio,
      resolution: item.resolution || ""
    });

    wx.navigateTo({
      url: "/pages/options/index"
    });
  }
});
