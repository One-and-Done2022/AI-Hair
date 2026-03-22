const { ensureLogin } = require("./auth");
const { getErrorCode } = require("./errors");
const { request, uploadFile } = require("./request");

const CURRENT_UPLOAD_STORAGE_KEY = "currentUpload";
const SMART_RECOMMENDATION_STORAGE_KEY = "smartRecommendation";

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
  wx.removeStorageSync(CURRENT_UPLOAD_STORAGE_KEY);
  wx.removeStorageSync(SMART_RECOMMENDATION_STORAGE_KEY);
  pendingUploadPromise = null;
  pendingUploadPath = "";
  pendingRecommendationPromise = null;
  pendingRecommendationKey = "";
}

async function ensureCurrentUpload(localPath, options = {}) {
  const { timeout = 15000 } = options;
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
    timeout
  })
    .then((upload) => {
      const preparedUpload = {
        ...upload,
        local_path: localPath
      };
      wx.setStorageSync(CURRENT_UPLOAD_STORAGE_KEY, preparedUpload);
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
      wx.setStorageSync(SMART_RECOMMENDATION_STORAGE_KEY, preparedRecommendation);
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
  ensureCurrentUpload,
  ensureRecommendation,
  ensureRecommendationFromCurrentUpload,
  getCachedRecommendation,
  getCachedUpload
};
