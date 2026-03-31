const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
const { request } = require("../../utils/request");
const {
  clearRecommendationCache,
  ensureCurrentUpload,
  ensureRecommendationFromCurrentUpload,
  getCachedRecommendation,
  getCachedUpload,
  getCurrentImagePath,
  prepareImageForUpload,
  setCurrentImagePath
} = require("../../utils/recommendation");

function findById(items, id) {
  if (!id) {
    return null;
  }
  return (items || []).find((item) => item.id === id) || null;
}

function formatFileSize(bytes) {
  if (!bytes || bytes <= 0) {
    return "0KB";
  }
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))}KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(bytes >= 10 * 1024 * 1024 ? 0 : 1)}MB`;
}

function readSelection() {
  const selection = wx.getStorageSync("templateSelection") || {};
  return {
    selectedHairstyle: selection.hairstyle || null,
    selectedScene: selection.scene || null,
    selectedGender: selection.gender || ""
  };
}

function getRecommendationGender(selection, selectedHairstyle) {
  if (
    selectedHairstyle &&
    (selectedHairstyle.gender === "male" || selectedHairstyle.gender === "female")
  ) {
    return selectedHairstyle.gender;
  }
  if (selection && (selection.gender === "male" || selection.gender === "female")) {
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

function getNextStepUrl(selectedImage, selectedHairstyle) {
  if (!selectedImage) {
    return "";
  }
  if (!selectedHairstyle) {
    return "/pages/templates/index";
  }
  return buildScenePageUrl(selectedHairstyle);
}

function getContinueButtonLabel(selectedImage, selectedHairstyle, selectedScene) {
  if (!selectedImage) {
    return "";
  }
  if (!selectedHairstyle) {
    return "去选发型";
  }
  if (!selectedScene) {
    return "去选场景";
  }
  return "去生成";
}

function getContinueHelper(imagePreparing, uploadPriming, selectedHairstyle, selectedScene) {
  if (imagePreparing) {
    return "图片处理中，稍后就能继续选择";
  }
  if (uploadPriming) {
    return "照片正在预上传，你可以继续挑选搭配";
  }
  if (!selectedHairstyle) {
    return "先选一个发型，再继续场景与生成";
  }
  if (!selectedScene) {
    return "再选一个场景，就可以开始生成";
  }
  return "搭配已完成，进入下一步直接生成";
}

function getFlowSummary(selectedHairstyle, selectedScene) {
  if (!selectedHairstyle) {
    return "下一步先选发型";
  }
  if (!selectedScene) {
    return "发型已选好，再补一个场景";
  }
  return "搭配已完成，可以开始生成";
}

function buildFlowState({
  selectedImage,
  selectedHairstyle,
  selectedScene,
  imagePreparing,
  uploadPriming
}) {
  return {
    continueButtonLabel: getContinueButtonLabel(
      selectedImage,
      selectedHairstyle,
      selectedScene
    ),
    continueHelper: getContinueHelper(
      imagePreparing,
      uploadPriming,
      selectedHairstyle,
      selectedScene
    ),
    flowSummary: getFlowSummary(selectedHairstyle, selectedScene)
  };
}

function buildRecommendationCardState(recommendation, loading) {
  if (loading) {
    return {
      recommendationReady: false,
      recommendationTitle: "AI 正在分析你的照片",
      recommendationSummary: "很快会给你推荐更适合的发型和场景"
    };
  }

  if (recommendation) {
    const hairstyleGroups = recommendation.recommended_hairstyles || {};
    const hairstyleCount =
      Math.max(
        (hairstyleGroups.female || []).length,
        (hairstyleGroups.male || []).length
      ) || 3;
    const sceneCount = (recommendation.recommended_scenes || []).length || 3;
    return {
      recommendationReady: true,
      recommendationTitle: "AI 已分析你的照片",
      recommendationSummary: `为你准备了 ${hairstyleCount} 个发型和 ${sceneCount} 个场景`
    };
  }

  return {
    recommendationReady: false,
    recommendationTitle: "AI 推荐搭配",
    recommendationSummary: "上传后可一键套用更适合的发型和场景"
  };
}

function buildRecommendedHairstyles(recommendation, catalog, gender, selectedHairstyle) {
  if (!recommendation || !catalog) {
    return [];
  }
  const hairstyleItems =
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
  if (!recommendation || !catalog) {
    return [];
  }

  return (recommendation.recommended_scenes || [])
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

Page({
  data: {
    bootstrapping: true,
    profileSummary: null,
    selectedImage: "",
    selectedHairstyle: null,
    selectedScene: null,
    imagePreparing: false,
    uploadPriming: false,
    uploadReady: false,
    uploadProgress: 0,
    uploadMessage: "",
    recommendationLoading: false,
    recommendationReady: false,
    recommendationTitle: "AI 推荐搭配",
    recommendationSummary: "上传后可一键套用更适合的发型和场景",
    recommendationExpanded: false,
    recommendation: null,
    recommendationGender: "female",
    recommendedHairstyles: [],
    recommendedScenes: [],
    continueButtonLabel: "",
    continueHelper: "",
    flowSummary: ""
  },

  async onLoad() {
    await this.bootstrap();
  },

  onShow() {
    this.syncSelection();
    if (this.data.selectedImage) {
      this.refreshRecommendationCard({ silent: true });
    }
  },

  updateSelectionState(overrides = {}) {
    const selectedHairstyle = Object.prototype.hasOwnProperty.call(overrides, "selectedHairstyle")
      ? overrides.selectedHairstyle
      : this.data.selectedHairstyle;
    const selectedScene = Object.prototype.hasOwnProperty.call(overrides, "selectedScene")
      ? overrides.selectedScene
      : this.data.selectedScene;
    const recommendation = Object.prototype.hasOwnProperty.call(overrides, "recommendation")
      ? overrides.recommendation
      : this.data.recommendation;
    const selection = readSelection();
    const recommendationGender = overrides.recommendationGender ||
      getRecommendationGender(selection, selectedHairstyle);

    this.setData({
      selectedHairstyle,
      selectedScene,
      recommendation: recommendation || null,
      recommendationGender,
      recommendedHairstyles: buildRecommendedHairstyles(
        recommendation,
        this.catalog,
        recommendationGender,
        selectedHairstyle
      ),
      recommendedScenes: buildRecommendedScenes(
        recommendation,
        this.catalog,
        selectedScene
      ),
      ...buildFlowState({
        selectedImage: this.data.selectedImage,
        selectedHairstyle,
        selectedScene,
        imagePreparing: this.data.imagePreparing,
        uploadPriming: this.data.uploadPriming
      })
    });
  },

  async bootstrap() {
    this.setData({ bootstrapping: true });
    try {
      await ensureLogin();
      const [catalog, profileSummary] = await Promise.all([
        request({ url: "/api/templates" }),
        request({ url: "/api/me" }).catch(() => null)
      ]);

      this.catalog = catalog;

      const currentImagePath = getCurrentImagePath();
      const cachedUpload = currentImagePath ? getCachedUpload(currentImagePath) : null;
      const selection = readSelection();
      const selectedHairstyle =
        findById(catalog.hairstyles, selection.selectedHairstyle && selection.selectedHairstyle.id) ||
        selection.selectedHairstyle ||
        null;
      const selectedScene =
        findById(catalog.scenes, selection.selectedScene && selection.selectedScene.id) ||
        selection.selectedScene ||
        null;
      const recommendation =
        (cachedUpload && getCachedRecommendation(cachedUpload.upload_id)) ||
        getCachedRecommendation() ||
        null;
      const recommendationGender = getRecommendationGender(
        { gender: selection.selectedGender },
        selectedHairstyle
      );

      if (selectedHairstyle || selectedScene) {
        wx.setStorageSync("templateSelection", {
          hairstyle: selectedHairstyle,
          scene: selectedScene,
          gender: recommendationGender
        });
      }

      this.setData({
        profileSummary,
        selectedImage: currentImagePath,
        selectedHairstyle,
        selectedScene,
        uploadReady: !!cachedUpload,
        uploadPriming: false,
        uploadProgress: cachedUpload ? 100 : 0,
        uploadMessage: currentImagePath
          ? cachedUpload
            ? "照片已上传完成，可继续创作"
            : "照片已选择，可继续创作"
          : "",
        recommendationExpanded: false,
        recommendationGender,
        ...buildRecommendationCardState(currentImagePath ? recommendation : null, false),
        ...buildFlowState({
          selectedImage: currentImagePath,
          selectedHairstyle,
          selectedScene,
          imagePreparing: false,
          uploadPriming: false
        })
      });

      this.updateSelectionState({
        selectedHairstyle,
        selectedScene,
        recommendation,
        recommendationGender
      });

      if (currentImagePath) {
        this.refreshRecommendationCard({ silent: true });
      }
    } catch (error) {
      showError(error, { fallback: "加载失败，请稍后再试" });
    } finally {
      this.setData({ bootstrapping: false });
    }
  },

  syncSelection() {
    const selection = readSelection();
    this.updateSelectionState({
      selectedHairstyle: selection.selectedHairstyle,
      selectedScene: selection.selectedScene
    });
  },

  async refreshRecommendationCard({ silent = true, expand = false } = {}) {
    const localPath = this.data.selectedImage || getCurrentImagePath();
    if (!localPath) {
      this.setData({
        recommendationLoading: false,
        recommendationExpanded: false,
        recommendation: null,
        recommendedHairstyles: [],
        recommendedScenes: [],
        ...buildRecommendationCardState(null, false)
      });
      return;
    }

    const cachedUpload = getCachedUpload(localPath);
    const cachedRecommendation =
      (cachedUpload && getCachedRecommendation(cachedUpload.upload_id)) ||
      getCachedRecommendation();

    if (cachedRecommendation) {
      this.setData({
        recommendationLoading: false,
        recommendationExpanded: expand ? true : this.data.recommendationExpanded,
        ...buildRecommendationCardState(cachedRecommendation, false)
      });
      this.updateSelectionState({ recommendation: cachedRecommendation });
      return;
    }

    this.setData({
      recommendationLoading: true,
      ...buildRecommendationCardState(null, true)
    });

    try {
      const recommendation = await ensureRecommendationFromCurrentUpload({ silent });
      const latestPath = this.data.selectedImage || getCurrentImagePath();
      if (!latestPath || latestPath !== localPath) {
        return;
      }
      this.setData({
        recommendationLoading: false,
        recommendationExpanded: expand ? true : this.data.recommendationExpanded,
        ...buildRecommendationCardState(recommendation, false)
      });
      this.updateSelectionState({ recommendation: recommendation || null });
    } catch (error) {
      if (!silent) {
        showError(error, { fallback: "推荐失败，请稍后再试" });
      }
      const latestPath = this.data.selectedImage || getCurrentImagePath();
      if (!latestPath || latestPath !== localPath) {
        return;
      }
      this.setData({
        recommendationLoading: false,
        ...buildRecommendationCardState(null, false)
      });
      this.updateSelectionState({ recommendation: null });
    }
  },

  chooseImage() {
    wx.chooseImage({
      count: 1,
      sizeType: ["compressed"],
      sourceType: ["album"],
      success: (result) => {
        const filePath = result.tempFilePaths[0];
        this.applySelectedImage(filePath);
      }
    });
  },

  openImageSource() {
    wx.showActionSheet({
      itemList: ["手机自拍", "从相册选择"],
      success: (result) => {
        if (result.tapIndex === 0) {
          this.takeSelfie();
          return;
        }
        if (result.tapIndex === 1) {
          this.chooseImage();
        }
      }
    });
  },

  takeSelfie() {
    wx.navigateTo({
      url: "/pages/capture/index",
      success: (result) => {
        result.eventChannel.on("captured", (payload) => {
          if (payload && payload.filePath) {
            this.applySelectedImage(payload.filePath);
          }
        });
      }
    });
  },

  async applySelectedImage(filePath) {
    if (!filePath) {
      return;
    }

    const selectionToken = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    this.currentImageSelectionToken = selectionToken;
    clearRecommendationCache();
    setCurrentImagePath(filePath);

    const selection = readSelection();

    this.setData({
      selectedImage: filePath,
      recommendationExpanded: false,
      recommendationLoading: false,
      recommendation: null,
      recommendedHairstyles: [],
      recommendedScenes: [],
      imagePreparing: true,
      uploadPriming: false,
      uploadReady: false,
      uploadProgress: 0,
      uploadMessage: "正在优化图片大小",
      ...buildRecommendationCardState(null, false),
      ...buildFlowState({
        selectedImage: filePath,
        selectedHairstyle: selection.selectedHairstyle,
        selectedScene: selection.selectedScene,
        imagePreparing: true,
        uploadPriming: false
      })
    });

    try {
      const prepared = await prepareImageForUpload(filePath);
      if (this.currentImageSelectionToken !== selectionToken) {
        return;
      }

      const preparedPath = prepared.filePath || filePath;
      setCurrentImagePath(preparedPath);
      this.setData({
        selectedImage: preparedPath,
        imagePreparing: false,
        uploadPriming: true,
        uploadReady: false,
        uploadProgress: 0,
        uploadMessage: prepared.compressed
          ? `已压缩 ${formatFileSize(prepared.originalSize)} -> ${formatFileSize(prepared.finalSize)}`
          : "图片已选择，正在预上传",
        ...buildFlowState({
          selectedImage: preparedPath,
          selectedHairstyle: selection.selectedHairstyle,
          selectedScene: selection.selectedScene,
          imagePreparing: false,
          uploadPriming: true
        })
      });
      this.primeUpload(preparedPath, selectionToken, prepared);
    } catch (error) {
      if (this.currentImageSelectionToken !== selectionToken) {
        return;
      }

      this.setData({
        imagePreparing: false,
        uploadPriming: false,
        uploadReady: false,
        uploadProgress: 0,
        uploadMessage: "图片已选择，可继续创作",
        ...buildFlowState({
          selectedImage: filePath,
          selectedHairstyle: selection.selectedHairstyle,
          selectedScene: selection.selectedScene,
          imagePreparing: false,
          uploadPriming: false
        })
      });
    }
  },

  async primeUpload(localPath, selectionToken, prepared = null) {
    if (!localPath) {
      return;
    }

    const compressionPrefix =
      prepared && prepared.compressed
        ? `已压缩至 ${formatFileSize(prepared.finalSize)}，`
        : "";

    this.setData({
      uploadPriming: true,
      uploadReady: false,
      uploadProgress: 0,
      uploadMessage: `${compressionPrefix}正在预上传`,
      ...buildFlowState({
        selectedImage: localPath,
        selectedHairstyle: this.data.selectedHairstyle,
        selectedScene: this.data.selectedScene,
        imagePreparing: false,
        uploadPriming: true
      })
    });

    try {
      await ensureCurrentUpload(localPath, {
        onProgress: (progressEvent) => {
          if (
            this.currentImageSelectionToken !== selectionToken ||
            this.data.selectedImage !== localPath
          ) {
            return;
          }
          const progress = Math.max(
            0,
            Math.min(100, Number(progressEvent.progress || 0))
          );
          this.setData({
            uploadPriming: progress < 100,
            uploadReady: progress >= 100,
            uploadProgress: progress,
            uploadMessage:
              progress >= 100
                ? `${compressionPrefix}照片已上传完成`
                : `${compressionPrefix}正在预上传 ${progress}%`,
            ...buildFlowState({
              selectedImage: localPath,
              selectedHairstyle: this.data.selectedHairstyle,
              selectedScene: this.data.selectedScene,
              imagePreparing: false,
              uploadPriming: progress < 100
            })
          });
        }
      });

      if (
        this.currentImageSelectionToken !== selectionToken ||
        this.data.selectedImage !== localPath
      ) {
        return;
      }

      this.setData({
        uploadPriming: false,
        uploadReady: true,
        uploadProgress: 100,
        uploadMessage: `${compressionPrefix}照片已上传完成，可继续创作`,
        ...buildFlowState({
          selectedImage: localPath,
          selectedHairstyle: this.data.selectedHairstyle,
          selectedScene: this.data.selectedScene,
          imagePreparing: false,
          uploadPriming: false
        })
      });
      this.refreshRecommendationCard({ silent: true });
    } catch (error) {
      if (
        this.currentImageSelectionToken !== selectionToken ||
        this.data.selectedImage !== localPath
      ) {
        return;
      }

      this.setData({
        uploadPriming: false,
        uploadReady: false,
        uploadProgress: 0,
        uploadMessage: `${compressionPrefix}预上传失败，生成时会自动重试`,
        ...buildFlowState({
          selectedImage: localPath,
          selectedHairstyle: this.data.selectedHairstyle,
          selectedScene: this.data.selectedScene,
          imagePreparing: false,
          uploadPriming: false
        })
      });
    }
  },

  previewImage() {
    if (!this.data.selectedImage) {
      return;
    }
    wx.previewImage({
      urls: [this.data.selectedImage]
    });
  },

  applyTemplateSelection(nextSelection) {
    const hairstyle = Object.prototype.hasOwnProperty.call(nextSelection, "hairstyle")
      ? nextSelection.hairstyle
      : this.data.selectedHairstyle;
    const scene = Object.prototype.hasOwnProperty.call(nextSelection, "scene")
      ? nextSelection.scene
      : this.data.selectedScene;
    const gender = getRecommendationGender(
      { gender: this.data.recommendationGender },
      hairstyle
    );

    wx.setStorageSync("templateSelection", {
      hairstyle,
      scene,
      gender
    });

    this.updateSelectionState({
      selectedHairstyle: hairstyle,
      selectedScene: scene,
      recommendationGender: gender
    });
  },

  selectRecommendationGender(event) {
    const gender = event.currentTarget.dataset.gender;
    if (gender !== "male" && gender !== "female") {
      return;
    }
    this.updateSelectionState({ recommendationGender: gender });
  },

  applyRecommendedHairstyle(event) {
    const hairstyleId = event.currentTarget.dataset.id;
    const hairstyle = findById((this.catalog && this.catalog.hairstyles) || [], hairstyleId);
    if (!hairstyle) {
      return;
    }
    this.applyTemplateSelection({ hairstyle });
    wx.showToast({
      title: "已应用推荐发型",
      icon: "success"
    });
  },

  applyRecommendedScene(event) {
    const sceneId = event.currentTarget.dataset.id;
    const scene = findById((this.catalog && this.catalog.scenes) || [], sceneId);
    if (!scene) {
      return;
    }
    this.applyTemplateSelection({ scene });
    wx.showToast({
      title: "已应用推荐场景",
      icon: "success"
    });
  },

  applyRecommendedCombo() {
    const hairstyle = this.data.recommendedHairstyles[0] || null;
    const scene = this.data.recommendedScenes[0] || null;

    if (!hairstyle && !scene) {
      wx.showToast({
        title: "先生成推荐结果",
        icon: "none"
      });
      return;
    }

    this.applyTemplateSelection({
      hairstyle: hairstyle || this.data.selectedHairstyle,
      scene: scene || this.data.selectedScene
    });
    wx.showToast({
      title: "已套用推荐",
      icon: "success"
    });
  },

  async openRecommendationFlow() {
    if (!this.data.selectedImage) {
      wx.showToast({
        title: "请先上传照片",
        icon: "none"
      });
      return;
    }

    if (this.data.imagePreparing) {
      wx.showToast({
        title: "图片处理中，请稍候",
        icon: "none"
      });
      return;
    }

    if (this.data.recommendationReady) {
      this.setData({
        recommendationExpanded: !this.data.recommendationExpanded
      });
      return;
    }

    await this.refreshRecommendationCard({ silent: false, expand: true });
  },

  openTemplatePicker() {
    wx.navigateTo({
      url: "/pages/templates/index"
    });
  },

  openScenePicker() {
    const hairstyle = this.data.selectedHairstyle;
    if (!hairstyle) {
      this.openTemplatePicker();
      return;
    }

    wx.navigateTo({
      url: buildScenePageUrl(hairstyle)
    });
  },

  goHistory() {
    wx.switchTab({
      url: "/pages/history/index"
    });
  },

  goNextStep() {
    const url = getNextStepUrl(
      this.data.selectedImage,
      this.data.selectedHairstyle
    );
    if (!url) {
      wx.showToast({
        title: "请先上传照片",
        icon: "none"
      });
      return;
    }
    wx.navigateTo({ url });
  }
});
