const UPLOAD_ERROR_MESSAGES = {
  invalid_type: {
    title: "图片格式不支持",
    content: "请上传 JPG/JPEG 或 PNG 图片，其他格式暂不支持。"
  },
  file_too_large: {
    title: "图片体积过大",
    content: "图片大小不能超过 10MB，请压缩后再上传。"
  },
  image_too_small: {
    title: "图片分辨率过低",
    content: "图片宽和高都需至少 512px，请换一张更清晰的照片。"
  },
  bad_aspect_ratio: {
    title: "图片比例不合适",
    content: "请上传标准生活照或人像照，宽高比需在 0.5 到 2.0 之间。过窄长图、截图和全景图容易失败。"
  },
  invalid_image: {
    title: "图片无法识别",
    content: "系统无法解析这张图片，请换一张正常的 JPG/PNG 照片。"
  },
  no_face: {
    title: "未检测到清晰人脸",
    content: "请上传单人正脸或半侧脸生活照，避免遮挡、过暗或过度模糊。"
  },
  multiple_faces: {
    title: "检测到多人",
    content: "请上传只包含一位人物的照片。"
  },
  face_too_small: {
    title: "人脸不够清晰",
    content: "请上传胸口以上近景或更近的人像照，确保人物脸部足够清晰、占画面更大。"
  },
  face_detection_unavailable: {
    title: "人脸检测暂不可用",
    content: "服务器当前无法完成人脸检测，请稍后再试。"
  }
};

function getErrorCode(error) {
  if (!error || typeof error !== "object") {
    return "";
  }
  if (error.detail && typeof error.detail === "object" && error.detail.code) {
    return error.detail.code;
  }
  if (typeof error.code === "string") {
    return error.code;
  }
  return "";
}

function getFriendlyUploadError(error) {
  const code = getErrorCode(error);
  return UPLOAD_ERROR_MESSAGES[code] || null;
}

function getErrorMessage(error, fallback = "请求失败，请稍后再试") {
  const uploadError = getFriendlyUploadError(error);
  if (uploadError) {
    return uploadError.content;
  }
  if (!error) {
    return fallback;
  }
  if (typeof error === "string") {
    return error;
  }
  if (error.detail && error.detail.message) {
    return error.detail.message;
  }
  if (error.detail && typeof error.detail === "string") {
    return error.detail;
  }
  if (error.message) {
    return error.message;
  }
  return fallback;
}

function showError(error, options = {}) {
  const {
    fallback = "请求失败，请稍后再试",
    preferModal = false
  } = options;
  const uploadError = getFriendlyUploadError(error);

  if (preferModal && uploadError) {
    wx.showModal({
      title: uploadError.title,
      content: uploadError.content,
      showCancel: false,
      confirmText: "我知道了"
    });
    return;
  }

  wx.showToast({
    title: getErrorMessage(error, fallback),
    icon: "none"
  });
}

module.exports = {
  getErrorCode,
  getErrorMessage,
  getFriendlyUploadError,
  showError
};
