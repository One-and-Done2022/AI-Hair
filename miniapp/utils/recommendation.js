const { ensureLogin } = require("./auth");
const { getErrorCode } = require("./errors");
const { request, uploadFile } = require("./request");

const CURRENT_IMAGE_PATH_STORAGE_KEY = "currentImagePath";
const CURRENT_UPLOAD_STORAGE_KEY = "currentUpload";
const SMART_RECOMMENDATION_STORAGE_KEY = "smartRecommendation";
const COMPRESS_THRESHOLD_BYTES = 2 * 1024 * 1024;
const COMPRESS_QUALITY_STEPS = [82, 72, 62];

let pendingUploadPromise = null;
let pendingUploadPath = "";
let pendingRecommendationPromise = null;
let pendingRecommendationKey = "";

function getCachedUpload(localPath = "") {
  const cached = wx.getStorageSync(CURRENT_UPLOAD_STORAGE_KEY) || null;
  if (!cached || !cached.upload_id) {
    return null;
  }
  if (localPath && cached.local_path !== localPath) {
    return null;
  }
  return cached;
}

function getCachedRecommendation(uploadId = "") {
  const cached = wx.getStorageSync(SMART_RECOMMENDATION_STORAGE_KEY) || null;
  if (!cached || !cached.upload_id) {
    return null;
  }
  if (uploadId && cached.upload_id !== uploadId) {
    return null;
  }
  return cached;
}

function clearRecommendationCache() {
  wx.removeStorageSync(CURRENT_IMAGE_PATH_STORAGE_KEY);
  wx.removeStorageSync(CURRENT_UPLOAD_STORAGE_KEY);
  wx.removeStorageSync(SMART_RECOMMENDATION_STORAGE_KEY);
  pendingUploadPromise = null;
  pendingUploadPath = "";
  pendingRecommendationPromise = null;
  pendingRecommendationKey = "";
}

function setCurrentImagePath(localPath) {
  if (!localPath) {
    wx.removeStorageSync(CURRENT_IMAGE_PATH_STORAGE_KEY);
    return;
  }
  wx.setStorageSync(CURRENT_IMAGE_PATH_STORAGE_KEY, localPath);
}

function getCurrentImagePath() {
  return wx.getStorageSync(CURRENT_IMAGE_PATH_STORAGE_KEY) || "";
}

function getFileInfo(filePath) {
  return new Promise((resolve, reject) => {
    wx.getFileInfo({
      filePath,
      success: resolve,
      fail: reject
    });
  });
}

function compressLocalImage(src, quality) {
  return new Promise((resolve, reject) => {
    if (typeof wx.compressImage !== "function") {
      resolve({ tempFilePath: src });
      return;
    }
    wx.compressImage({
      src,
      quality,
      success: resolve,
      fail: reject
    });
  });
}

async function prepareImageForUpload(localPath) {
  if (!localPath) {
    return {
      filePath: "",
      compressed: false,
      originalSize: 0,
      finalSize: 0
    };
  }

  const originalInfo = await getFileInfo(localPath).catch(() => null);
  let preparedPath = localPath;
  let preparedInfo = originalInfo;
  let compressed = false;

  if (originalInfo && originalInfo.size > COMPRESS_THRESHOLD_BYTES) {
    for (const quality of COMPRESS_QUALITY_STEPS) {
      const result = await compressLocalImage(localPath, quality).catch(() => null);
      const nextPath = result && result.tempFilePath ? result.tempFilePath : "";
      if (!nextPath) {
        continue;
      }
      const nextInfo = await getFileInfo(nextPath).catch(() => null);
      if (!nextInfo) {
        continue;
      }
      if (!preparedInfo || nextInfo.size < preparedInfo.size) {
        preparedPath = nextPath;
        preparedInfo = nextInfo;
        compressed = preparedPath !== localPath;
      }
      if (nextInfo.size <= COMPRESS_THRESHOLD_BYTES) {
        break;
      }
    }
  }

  return {
    filePath: preparedPath,
    compressed,
    originalSize: originalInfo ? originalInfo.size : 0,
    finalSize: preparedInfo ? preparedInfo.size : 0
  };
}

async function ensureCurrentUpload(localPath, options = {}) {
  const { timeout = 15000, onProgress } = options;
  if (!localPath) {
    return null;
  }

  const cachedUpload = getCachedUpload(localPath);
  if (cachedUpload) {
    return cachedUpload;
  }

  if (pendingUploadPromise && pendingUploadPath === localPath) {
    return pendingUploadPromise;
  }

  pendingUploadPath = localPath;
  pendingUploadPromise = uploadFile({
    url: "/api/uploads",
    filePath: localPath,
    name: "file",
    timeout,
    onProgress
  })
    .then((upload) => {
      const preparedUpload = {
        ...upload,
        local_path: localPath
      };
      if (getCurrentImagePath() === localPath) {
        wx.setStorageSync(CURRENT_UPLOAD_STORAGE_KEY, preparedUpload);
      }
      return preparedUpload;
    })
    .finally(() => {
      pendingUploadPromise = null;
      pendingUploadPath = "";
    });

  return pendingUploadPromise;
}

async function ensureRecommendation(localPath, options = {}) {
  const {
    silent = false,
    uploadTimeout = 15000,
    recommendationTimeout = 12000
  } = options;

  if (!localPath) {
    return null;
  }

  await ensureLogin();
  const upload = await ensureCurrentUpload(localPath, { timeout: uploadTimeout });
  if (!upload) {
    return null;
  }

  const cachedRecommendation = getCachedRecommendation(upload.upload_id);
  if (cachedRecommendation) {
    return cachedRecommendation;
  }

  const promiseKey = `${localPath}:${upload.upload_id}`;
  if (pendingRecommendationPromise && pendingRecommendationKey === promiseKey) {
    return pendingRecommendationPromise;
  }

  pendingRecommendationKey = promiseKey;
  pendingRecommendationPromise = request({
    url: "/api/recommendations",
    method: "POST",
    data: {
      upload_id: upload.upload_id
    },
    timeout: recommendationTimeout
  })
    .then((recommendation) => {
      const preparedRecommendation = {
        ...recommendation,
        local_path: localPath
      };
      if (getCurrentImagePath() === localPath) {
        wx.setStorageSync(SMART_RECOMMENDATION_STORAGE_KEY, preparedRecommendation);
      }
      return preparedRecommendation;
    })
    .catch((error) => {
      if (getErrorCode(error) === "recommendation_unavailable") {
        wx.removeStorageSync(SMART_RECOMMENDATION_STORAGE_KEY);
        return null;
      }
      if (silent) {
        return null;
      }
      throw error;
    })
    .finally(() => {
      pendingRecommendationPromise = null;
      pendingRecommendationKey = "";
    });

  return pendingRecommendationPromise;
}

async function ensureRecommendationFromCurrentUpload(options = {}) {
  const {
    silent = true,
    recommendationTimeout = 12000
  } = options;

  let upload = getCachedUpload();
  if ((!upload || !upload.upload_id) && pendingUploadPromise) {
    try {
      await pendingUploadPromise;
    } catch (error) {
      return null;
    }
    upload = getCachedUpload();
  }

  if (!upload || !upload.upload_id) {
    const localPath = getCurrentImagePath();
    if (localPath) {
      return ensureRecommendation(localPath, {
        silent,
        recommendationTimeout
      });
    }
    if (pendingRecommendationPromise) {
      return pendingRecommendationPromise;
    }
    return null;
  }

  const cachedRecommendation = getCachedRecommendation(upload.upload_id);
  if (cachedRecommendation) {
    return cachedRecommendation;
  }

  if (upload.local_path) {
    return ensureRecommendation(upload.local_path, {
      silent,
      recommendationTimeout
    });
  }

  if (pendingRecommendationPromise) {
    return pendingRecommendationPromise;
  }

  pendingRecommendationKey = upload.upload_id;
  pendingRecommendationPromise = request({
    url: "/api/recommendations",
    method: "POST",
    data: {
      upload_id: upload.upload_id
    },
    timeout: recommendationTimeout
  })
    .then((recommendation) => {
      wx.setStorageSync(SMART_RECOMMENDATION_STORAGE_KEY, recommendation);
      return recommendation;
    })
    .catch((error) => {
      if (getErrorCode(error) === "recommendation_unavailable") {
        wx.removeStorageSync(SMART_RECOMMENDATION_STORAGE_KEY);
        return null;
      }
      if (silent) {
        return null;
      }
      throw error;
    })
    .finally(() => {
      pendingRecommendationPromise = null;
      pendingRecommendationKey = "";
    });

  return pendingRecommendationPromise;
}

module.exports = {
  clearRecommendationCache,
  prepareImageForUpload,
  ensureCurrentUpload,
  ensureRecommendation,
  ensureRecommendationFromCurrentUpload,
  getCurrentImagePath,
  getCachedRecommendation,
  getCachedUpload,
  setCurrentImagePath
};
