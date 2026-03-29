const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const { request } = require("../../utils/request");
const {
  ensureRecommendationFromCurrentUpload,
  getCachedRecommendation,
  getCurrentImagePath
} = require("../../utils/recommendation");

function findById(items, id) {
  if (!id) {
    return null;
  }
  return (items || []).find((item) => item.id === id) || null;
}

function readSelection() {
  return wx.getStorageSync("templateSelection") || {};
}

function getRecommendationGender(selection, selectedHairstyle) {
  if (
    selectedHairstyle &&
    (selectedHairstyle.gender === "male" || selectedHairstyle.gender === "female")
  ) {
    return selectedHairstyle.gender;
  }
  if (selection.gender === "male" || selection.gender === "female") {
    return selection.gender;
  }
  return "female";
}

function buildScenePageUrl(hairstyle) {
  if (!hairstyle || !hairstyle.id) {
    return "/pages/scenes/index";
  }
  return (
    `/pages/scenes/index?hairstyleId=${hairstyle.id}` +
    `&hairstyleName=${encodeURIComponent(hairstyle.name || "")}` +
    `&gender=${hairstyle.gender || "female"}`
  );
}

function getNextStepUrl(selectedImage, selectedHairstyle, selectedScene) {
  if (!selectedImage) {
    return "";
  }
  if (!selectedHairstyle) {
    return "/pages/templates/index";
  }
  if (!selectedScene) {
    return buildScenePageUrl(selectedHairstyle);
  }
  return "/pages/confirm/index";
}

function getContinueButtonLabel(selectedImage, selectedHairstyle, selectedScene) {
  if (!selectedImage) {
    return "返回上传照片";
  }
  if (!selectedHairstyle) {
    return "去选发型";
  }
  if (!selectedScene) {
    return "去选场景";
  }
  return "进入确认页";
}

function buildRecommendedHairstyles(recommendation, catalog, gender, selectedHairstyle) {
  const hairstyleItems =
    recommendation &&
    recommendation.recommended_hairstyles &&
    recommendation.recommended_hairstyles[gender]
      ? recommendation.recommended_hairstyles[gender]
      : [];
  return hairstyleItems
    .map((item) => {
      const full = findById(catalog.hairstyles || [], item.id);
      if (!full) {
        return null;
      }
      return {
        ...full,
        reason: (item.reasons || [])[0] || "",
        selected: !!selectedHairstyle && selectedHairstyle.id === full.id
      };
    })
    .filter(Boolean);
}

function buildRecommendedScenes(recommendation, catalog, selectedScene) {
  return ((recommendation && recommendation.recommended_scenes) || [])
    .map((item) => {
      const full = findById(catalog.scenes || [], item.id);
      if (!full) {
        return null;
      }
      return {
        ...full,
        reason: (item.reasons || [])[0] || "",
        selected: !!selectedScene && selectedScene.id === full.id
      };
    })
    .filter(Boolean);
}

function getRecommendationSource(page) {
  return page.recommendation || getCachedRecommendation() || null;
}

Page({
  data: {
    loading: true,
    emptyMessage: "",
    selectedImage: "",
    selectedHairstyle: null,
    selectedScene: null,
    recommendationGender: "female",
    recommendedHairstyles: [],
    recommendedScenes: [],
    continueButtonLabel: "去选发型"
  },

  async onLoad() {
    await this.loadRecommendations();
  },

  async loadRecommendations() {
    const selectedImage = getCurrentImagePath();
    if (!selectedImage) {
      this.setData({
        loading: false,
        emptyMessage: "请先上传照片，再查看 AI 推荐"
      });
      return;
    }

    try {
      await ensureLogin();
      const [catalog, recommendation] = await Promise.all([
        request({ url: "/api/templates" }),
        ensureRecommendationFromCurrentUpload({ silent: false })
      ]);

      if (!recommendation) {
        this.setData({
          loading: false,
          selectedImage,
          emptyMessage: "暂时无法生成推荐结果，你可以继续手动选择"
        });
        return;
      }

      this.catalog = catalog;
      this.recommendation = recommendation;
      const selection = readSelection();
      const selectedHairstyle =
        findById(catalog.hairstyles, selection.hairstyle && selection.hairstyle.id) ||
        selection.hairstyle ||
        null;
      const selectedScene =
        findById(catalog.scenes, selection.scene && selection.scene.id) ||
        selection.scene ||
        null;
      const recommendationGender = getRecommendationGender(selection, selectedHairstyle);

      this.setData({
        loading: false,
        emptyMessage: "",
        selectedImage,
        selectedHairstyle,
        selectedScene,
        recommendationGender,
        recommendedHairstyles: buildRecommendedHairstyles(
          recommendation,
          catalog,
          recommendationGender,
          selectedHairstyle
        ),
        recommendedScenes: buildRecommendedScenes(
          recommendation,
          catalog,
          selectedScene
        ),
        continueButtonLabel: getContinueButtonLabel(
          selectedImage,
          selectedHairstyle,
          selectedScene
        )
      });
    } catch (error) {
      this.setData({
        loading: false,
        selectedImage,
        emptyMessage: "推荐暂时不可用，你可以继续手动选择"
      });
      showError(error, { fallback: "推荐加载失败，请稍后再试" });
    }
  },

  selectRecommendationGender(event) {
    const gender = event.currentTarget.dataset.gender;
    if (gender !== "male" && gender !== "female" || !this.catalog) {
      return;
    }

    const recommendation = getRecommendationSource(this);
    if (!recommendation) {
      return;
    }

    this.setData({
      recommendationGender: gender,
      recommendedHairstyles: buildRecommendedHairstyles(
        recommendation,
        this.catalog,
        gender,
        this.data.selectedHairstyle
      )
    });
  },

  applyRecommendedHairstyle(event) {
    const hairstyleId = event.currentTarget.dataset.id;
    if (!this.catalog) {
      return;
    }

    const hairstyle = findById(this.catalog.hairstyles || [], hairstyleId);
    if (!hairstyle) {
      return;
    }

    const nextSelection = {
      hairstyle,
      scene: this.data.selectedScene,
      gender: hairstyle.gender || this.data.recommendationGender || "female"
    };
    wx.setStorageSync("templateSelection", nextSelection);

    const recommendation = getRecommendationSource(this);
    this.setData({
      selectedHairstyle: hairstyle,
      recommendationGender: hairstyle.gender || this.data.recommendationGender,
      recommendedHairstyles: buildRecommendedHairstyles(
        recommendation,
        this.catalog,
        hairstyle.gender || this.data.recommendationGender,
        hairstyle
      ),
      continueButtonLabel: getContinueButtonLabel(
        this.data.selectedImage,
        hairstyle,
        this.data.selectedScene
      )
    });

    wx.showToast({
      title: "已应用推荐发型",
      icon: "success"
    });
  },

  applyRecommendedScene(event) {
    const sceneId = event.currentTarget.dataset.id;
    if (!this.catalog) {
      return;
    }

    const scene = findById(this.catalog.scenes || [], sceneId);
    if (!scene) {
      return;
    }

    wx.setStorageSync("templateSelection", {
      hairstyle: this.data.selectedHairstyle,
      scene,
      gender:
        (this.data.selectedHairstyle && this.data.selectedHairstyle.gender) ||
        this.data.recommendationGender ||
        "female"
    });

    const recommendation = getRecommendationSource(this);
    this.setData({
      selectedScene: scene,
      recommendedScenes: buildRecommendedScenes(recommendation, this.catalog, scene),
      continueButtonLabel: getContinueButtonLabel(
        this.data.selectedImage,
        this.data.selectedHairstyle,
        scene
      )
    });

    wx.showToast({
      title: "已应用推荐场景",
      icon: "success"
    });
  },

  continueFlow() {
    const url = getNextStepUrl(
      this.data.selectedImage,
      this.data.selectedHairstyle,
      this.data.selectedScene
    );

    if (!url) {
      wx.switchTab({
        url: "/pages/index/index"
      });
      return;
    }

    wx.redirectTo({ url });
  }
});
