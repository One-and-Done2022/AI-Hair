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
  face_not_detected: {
    title: "未检测到清晰人脸",
    content: "请上传单人正脸或半侧脸自拍，避免遮挡、逆光、过暗和明显模糊。"
  },
  no_face: {
    title: "未检测到清晰人脸",
    content: "请上传单人正脸或半侧脸自拍，避免遮挡、逆光、过暗和明显模糊。"
  },
  multiple_faces: {
    title: "检测到多张明显人脸",
    content: "请上传只包含一位人物的自拍或单人照，避免背景海报、屏幕头像或多人同框。"
  },
  face_too_small: {
    title: "人脸不够清晰",
    content: "请上传胸口以上近景或更靠近镜头的人像照，让脸部在画面中更大、更清晰。"
  },
  face_detection_unavailable: {
    title: "人脸检测暂不可用",
    content: "服务器当前无法完成人脸检测，请稍后再试。"
  }
};

const GENERIC_ERROR_MESSAGES = {
  quota_exhausted: {
    title: "次数已用完",
    content: "当前体验次数已用完，请前往“我的”页联系内测支持补充次数后继续。"
  },
  reward_ad_limit_reached: {
    title: "额外免费次数已用完",
    content: "当前额外免费次数已用完，请联系内测支持处理。"
  },
  reward_ad_disabled: {
    title: "额外免费暂未开放",
    content: "当前额外免费入口暂未开放，请联系内测支持处理。"
  },
  rewarded_ad_unavailable: {
    title: "额外免费暂不可用",
    content: "当前额外免费入口暂不可用，请联系内测支持处理。"
  },
  rewarded_ad_not_completed: {
    title: "额外免费未完成",
    content: "当前额外免费流程未完成，请稍后再试或联系内测支持。"
  },
  quota_still_available: {
    title: "当前还有次数",
    content: "你当前还有可用次数，无需额外解锁。"
  },
  ad_unlock_session_not_found: {
    title: "解锁会话失效",
    content: "未找到本次额外免费会话，请重新开始。"
  },
  ad_unlock_session_expired: {
    title: "解锁已过期",
    content: "本次额外免费会话已过期，请重新开始。"
  },
  ad_unlock_session_already_claimed: {
    title: "奖励已领取",
    content: "本次额外免费次数已领取，请勿重复提交。"
  },
  invalid_purchase_product: {
    title: "功能暂未开放",
    content: "当前购买入口在审核版本中未开放。"
  },
  purchase_order_not_found: {
    title: "功能暂未开放",
    content: "当前购买入口在审核版本中未开放。"
  },
  wechat_pay_not_configured: {
    title: "功能暂未开放",
    content: "当前审核版本未开放支付能力。"
  },
  wechat_pay_prepare_failed: {
    title: "功能暂未开放",
    content: "当前审核版本未开放支付能力。"
  },
  payment_provider_unavailable: {
    title: "功能暂未开放",
    content: "当前审核版本未开放支付能力。"
  },
  payment_disabled: {
    title: "功能暂未开放",
    content: "当前审核版本未开放支付能力。"
  },
  payment_prepare_failed: {
    title: "功能暂未开放",
    content: "当前审核版本未开放支付能力。"
  },
  payment_qrcode_unavailable: {
    title: "功能暂未开放",
    content: "当前审核版本未开放支付能力。"
  },
  payment_cancelled: {
    title: "功能暂未开放",
    content: "当前审核版本未开放支付能力。"
  },
  payment_confirm_timeout: {
    title: "功能暂未开放",
    content: "当前审核版本未开放支付能力。"
  },
  download_failed: {
    title: "下载失败",
    content: "资源下载失败，请稍后再试。"
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

function getFriendlyGenericError(error) {
  const code = getErrorCode(error);
  return GENERIC_ERROR_MESSAGES[code] || null;
}

function getErrorMessage(error, fallback = "请求失败，请稍后再试") {
  const uploadError = getFriendlyUploadError(error);
  if (uploadError) {
    return uploadError.content;
  }
  const genericError = getFriendlyGenericError(error);
  if (genericError) {
    return genericError.content;
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
  if (typeof error.errMsg === "string" && error.errMsg.trim()) {
    return error.errMsg.trim();
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
  const genericError = getFriendlyGenericError(error);

  if (preferModal && uploadError) {
    wx.showModal({
      title: uploadError.title,
      content: uploadError.content,
      showCancel: false,
      confirmText: "我知道了"
    });
    return;
  }

  if (preferModal && genericError) {
    wx.showModal({
      title: genericError.title,
      content: genericError.content,
      showCancel: false,
      confirmText: "我知道了"
    });
    return;
  }

  if (preferModal) {
    wx.showModal({
      title: "请求失败",
      content: getErrorMessage(error, fallback),
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
  getFriendlyGenericError,
  getFriendlyUploadError,
  showError
};
