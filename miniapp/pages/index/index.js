const { ensureLogin } = require("../../utils/auth");
const { showError } = require("../../utils/errors");
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
    selectedScene: selection.scene || null
  };
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
    return "";
  }
  if (!selectedHairstyle) {
    return "继续选发型";
  }
  if (!selectedScene) {
    return "继续选场景";
  }
  return "进入确认页";
}

function getContinueHelper(imagePreparing, uploadPriming, selectedHairstyle, selectedScene) {
  if (imagePreparing) {
    return "图片处理中后会自动进入发型选择";
  }
  if (uploadPriming) {
    return "图片正在预上传，你可以继续往下选择";
  }
  if (!selectedHairstyle) {
    return "先完成发型选择，再继续场景与生成";
  }
  if (!selectedScene) {
    return "再选一个场景，就可以进入最终确认";
  }
  return "确认后会返回 1 张换发预览和 2 张场景成片";
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
    )
  };
}

function buildRecommendationCardState(recommendation, loading) {
  if (loading) {
    return {
      recommendationReady: false,
      recommendationTitle: "AI 正在分析你的照片",
      recommendationSummary: "很快会给你推荐更适合的发型和场景",
      recommendationButtonLabel: "稍后查看"
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
      recommendationSummary: `推荐 ${hairstyleCount} 个发型 + ${sceneCount} 个场景`,
      recommendationButtonLabel: "查看推荐"
    };
  }

  return {
    recommendationReady: false,
    recommendationTitle: "AI 推荐搭配",
    recommendationSummary: "基于当前照片，给你推荐更适合的发型和场景",
    recommendationButtonLabel: "AI 推荐搭配"
  };
}

Page({
  data: {
    bootstrapping: true,
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
    recommendationSummary: "上传照片后可查看推荐",
    recommendationButtonLabel: "AI 推荐搭配",
    continueButtonLabel: "",
    continueHelper: ""
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

  async bootstrap() {
    this.setData({ bootstrapping: true });
    try {
      await ensureLogin();
    } catch (error) {
      showError(error, { fallback: "登录失败，请稍后再试" });
    }

    const currentImagePath = getCurrentImagePath();
    const cachedUpload = currentImagePath ? getCachedUpload(currentImagePath) : null;
    const { selectedHairstyle, selectedScene } = readSelection();
    const cachedRecommendation =
      (cachedUpload && getCachedRecommendation(cachedUpload.upload_id)) ||
      getCachedRecommendation();

    const recommendationCard = buildRecommendationCardState(
      currentImagePath ? cachedRecommendation : null,
      false
    );

    this.setData({
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
      ...recommendationCard,
      ...buildFlowState({
        selectedImage: currentImagePath,
        selectedHairstyle,
        selectedScene,
        imagePreparing: false,
        uploadPriming: false
      })
    });

    if (currentImagePath) {
      this.refreshRecommendationCard({ silent: true });
    }

    this.setData({ bootstrapping: false });
  },

  syncSelection() {
    const { selectedHairstyle, selectedScene } = readSelection();
    this.setData({
      selectedHairstyle,
      selectedScene,
      ...buildFlowState({
        selectedImage: this.data.selectedImage,
        selectedHairstyle,
        selectedScene,
        imagePreparing: this.data.imagePreparing,
        uploadPriming: this.data.uploadPriming
      })
    });
  },

  async refreshRecommendationCard({ silent = true } = {}) {
    const localPath = this.data.selectedImage || getCurrentImagePath();
    if (!localPath) {
      this.setData({
        recommendationLoading: false,
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
        ...buildRecommendationCardState(cachedRecommendation, false)
      });
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
        ...buildRecommendationCardState(recommendation, false)
      });
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
    this.autoNavigating = false;
    clearRecommendationCache();
    setCurrentImagePath(filePath);

    const { selectedHairstyle, selectedScene } = readSelection();

    this.setData({
      selectedImage: filePath,
      selectedHairstyle,
      selectedScene,
      recommendationLoading: false,
      ...buildRecommendationCardState(null, false),
      imagePreparing: true,
      uploadPriming: false,
      uploadReady: false,
      uploadProgress: 0,
      uploadMessage: "正在优化图片大小",
      ...buildFlowState({
        selectedImage: filePath,
        selectedHairstyle,
        selectedScene,
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
          selectedHairstyle,
          selectedScene,
          imagePreparing: false,
          uploadPriming: true
        })
      });
      this.primeUpload(preparedPath, selectionToken, prepared);
      this.navigateToHairstyleStep(selectionToken);
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
          selectedHairstyle,
          selectedScene,
          imagePreparing: false,
          uploadPriming: false
        })
      });
      this.navigateToHairstyleStep(selectionToken);
    }
  },

  navigateToHairstyleStep(selectionToken) {
    if (this.currentImageSelectionToken !== selectionToken || this.autoNavigating) {
      return;
    }
    this.autoNavigating = true;
    wx.navigateTo({
      url: "/pages/templates/index",
      complete: () => {
        this.autoNavigating = false;
      }
    });
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

  openRecommendationFlow() {
    if (!this.data.selectedImage) {
      wx.showToast({
        title: "请先上传照片",
        icon: "none"
      });
      return;
    }
    wx.navigateTo({
      url: "/pages/recommend/index"
    });
  },

  goNextStep() {
    const url = getNextStepUrl(
      this.data.selectedImage,
      this.data.selectedHairstyle,
      this.data.selectedScene
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
