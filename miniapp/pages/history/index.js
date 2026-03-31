const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const {
  mergePendingHistoryJobs,
  removePendingHistoryJob
} = require("../../utils/pending-history");
const { request } = require("../../utils/request");

const FAVORITES_STORAGE_KEY = "favoriteJobIds";

function getStatusLabel(status) {
  if (status === "succeeded") {
    return "已完成";
  }
  if (status === "hair_generating") {
    return "换发中";
  }
  if (status === "hair_ready") {
    return "发型预览已返回";
  }
  if (status === "scene_generating") {
    return "场景生成中";
  }
  if (status === "scene_partial") {
    return "场景图已返回";
  }
  if (status === "preview_ready") {
    return "预览已返回";
  }
  if (status === "failed") {
    return "失败";
  }
  return "生成中";
}

function parseTimestamp(value) {
  if (!value) {
    return null;
  }
  const normalized = value.replace(/\+00:00$/, "Z");
  const timestamp = Date.parse(normalized);
  return Number.isNaN(timestamp) ? null : timestamp;
}

function pad(value) {
  return String(value).padStart(2, "0");
}

function formatCreatedAt(value) {
  const timestamp = parseTimestamp(value);
  if (!timestamp) {
    return value || "";
  }

  const date = new Date(timestamp);
  const now = new Date();
  const sameYear = date.getFullYear() === now.getFullYear();
  const sameMonth = sameYear && date.getMonth() === now.getMonth();
  const sameDay = sameMonth && date.getDate() === now.getDate();

  if (sameDay) {
    return `今天 ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  return `${date.getMonth() + 1}月${date.getDate()}日 ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function loadFavoriteIds() {
  const value = wx.getStorageSync(FAVORITES_STORAGE_KEY);
  return Array.isArray(value) ? value : [];
}

function saveFavoriteIds(ids) {
  wx.setStorageSync(FAVORITES_STORAGE_KEY, ids);
}

function decorateHistoryItems(items, favoriteIds) {
  return (items || []).map((item) => ({
    ...item,
    cover_url: item.result_image_url || item.upload_url || "",
    media_expired: !!item.media_expired,
    status_label: getStatusLabel(item.status),
    placeholder_label: item.media_expired ? "图片已过期" : getStatusLabel(item.status),
    created_at_label: formatCreatedAt(item.created_at),
    isFavorite: favoriteIds.includes(item.job_id)
  }));
}

function pickVisibleItems(items, activeTab) {
  if (activeTab === "favorites") {
    return items.filter((item) => item.isFavorite);
  }
  return items;
}

Page({
  data: {
    loading: false,
    activeTab: "all",
    items: [],
    visibleItems: [],
    favoriteIds: [],
    favoriteCount: 0,
    completedCount: 0
  },

  async onShow() {
    await this.loadHistory();
  },

  onPullDownRefresh() {
    this.loadHistory();
  },

  onShareAppMessage(options) {
    const jobId = options && options.target && options.target.dataset
      ? options.target.dataset.jobId
      : "";
    const item = this.data.items.find((entry) => entry.job_id === jobId);
    if (!item) {
      return {
        title: "我在 AIFace 做了一组新发型",
        path: "/pages/index/index"
      };
    }
    return {
      title: `${item.hairstyle_name} · ${item.scene_name}`,
      path: `/pages/result/index?jobId=${item.job_id}`,
      imageUrl: item.result_image_url || item.upload_url || ""
    };
  },

  async loadHistory() {
    this.setData({ loading: true });
    try {
      await ensureLogin();
      const payload = await request({ url: "/api/history" });
      const favoriteIds = loadFavoriteIds();
      const items = decorateHistoryItems(
        mergePendingHistoryJobs(payload.items || []),
        favoriteIds
      );
      this.setData({
        items,
        favoriteIds,
        favoriteCount: items.filter((item) => item.isFavorite).length,
        completedCount: items.filter((item) => item.status === "succeeded").length,
        visibleItems: pickVisibleItems(items, this.data.activeTab)
      });
    } catch (error) {
      showError(error, { fallback: "加载失败" });
    } finally {
      this.setData({ loading: false });
      wx.stopPullDownRefresh();
    }
  },

  changeTab(event) {
    const { tab } = event.currentTarget.dataset;
    if (!tab || tab === this.data.activeTab) {
      return;
    }
    this.setData({
      activeTab: tab,
      visibleItems: pickVisibleItems(this.data.items, tab)
    });
  },

  openJob(event) {
    const { jobId } = event.currentTarget.dataset;
    if (!jobId) {
      return;
    }
    wx.navigateTo({
      url: `/pages/result/index?jobId=${jobId}`
    });
  },

  toggleFavorite(event) {
    const { jobId } = event.currentTarget.dataset;
    if (!jobId) {
      return;
    }

    const current = new Set(this.data.favoriteIds);
    if (current.has(jobId)) {
      current.delete(jobId);
    } else {
      current.add(jobId);
    }

    const favoriteIds = Array.from(current);
    saveFavoriteIds(favoriteIds);
    const items = decorateHistoryItems(this.data.items, favoriteIds);
    this.setData({
      items,
      favoriteIds,
      favoriteCount: items.filter((item) => item.isFavorite).length,
      visibleItems: pickVisibleItems(items, this.data.activeTab)
    });
  },

  openMoreActions(event) {
    const { jobId } = event.currentTarget.dataset;
    const item = this.data.items.find((entry) => entry.job_id === jobId);
    if (!item) {
      return;
    }

    const actionList = [
      item.isFavorite ? "取消收藏" : "收藏作品",
      item.result_image_url ? "查看作品" : item.media_expired ? "查看记录" : "查看进度"
    ];
    if (item.result_image_url) {
      actionList.push("保存图片");
    }
    actionList.push("同款再来", "删除作品");

    wx.showActionSheet({
      itemList: actionList,
      success: ({ tapIndex }) => {
        const action = actionList[tapIndex];
        if (action === "取消收藏" || action === "收藏作品") {
          this.toggleFavorite({ currentTarget: { dataset: { jobId } } });
          return;
        }
        if (action === "查看作品" || action === "查看进度" || action === "查看记录") {
          this.openJob({ currentTarget: { dataset: { jobId } } });
          return;
        }
        if (action === "保存图片") {
          this.saveWorkImage(item.result_image_url);
          return;
        }
        if (action === "同款再来") {
          this.reuseTemplate(item);
          return;
        }
        if (action === "删除作品") {
          this.confirmDelete(item);
        }
      }
    });
  },

  saveWorkImage(imageUrl) {
    if (!imageUrl) {
      wx.showToast({ title: "当前还没有可保存的图片", icon: "none" });
      return;
    }

    wx.showLoading({ title: "正在保存" });
    wx.downloadFile({
      url: imageUrl,
      success: (result) => {
        wx.saveImageToPhotosAlbum({
          filePath: result.tempFilePath,
          success: () => {
            wx.showToast({ title: "图片已保存", icon: "success" });
          },
          fail: () => {
            wx.showToast({ title: "保存失败，请检查权限", icon: "none" });
          },
          complete: () => {
            wx.hideLoading();
          }
        });
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: "下载失败", icon: "none" });
      }
    });
  },

  async reuseTemplate(item) {
    try {
      const catalog = await request({ url: "/api/templates" });
      const hairstyle = (catalog.hairstyles || []).find((entry) => entry.id === item.hairstyle_id) || null;
      const scene = (catalog.scenes || []).find((entry) => entry.id === item.scene_id) || null;
      wx.setStorageSync("templateSelection", {
        hairstyle,
        scene,
        gender: (hairstyle && hairstyle.gender) || "female"
      });
      wx.switchTab({
        url: "/pages/index/index"
      });
    } catch (error) {
      showError(error, { fallback: "无法加载同款模板" });
    }
  },

  confirmDelete(item) {
    wx.showModal({
      title: "删除作品",
      content: "删除后这条作品记录会从作品页移除，是否继续？",
      confirmColor: "#b31b25",
      success: async ({ confirm }) => {
        if (!confirm) {
          return;
        }
        await this.deleteJob(item.job_id);
      }
    });
  },

  async deleteJob(jobId) {
    wx.showLoading({ title: "正在删除" });
    try {
      await request({
        url: `/api/jobs/${jobId}`,
        method: "DELETE"
      });
      removePendingHistoryJob(jobId);
      const favoriteIds = this.data.favoriteIds.filter((id) => id !== jobId);
      saveFavoriteIds(favoriteIds);
      const items = this.data.items.filter((item) => item.job_id !== jobId);
      this.setData({
        items,
        favoriteIds,
        favoriteCount: items.filter((item) => item.isFavorite).length,
        completedCount: items.filter((item) => item.status === "succeeded").length,
        visibleItems: pickVisibleItems(
          decorateHistoryItems(items, favoriteIds),
          this.data.activeTab
        )
      });
      wx.showToast({ title: "已删除", icon: "success" });
    } catch (error) {
      showError(error, { fallback: "删除失败" });
    } finally {
      wx.hideLoading();
    }
  }
});
