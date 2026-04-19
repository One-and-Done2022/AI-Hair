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
    content: "当前免费次数已用完。你可以先看广告再解锁 1 次生成，也可以直接购买 1 次生成包。"
  },
  reward_ad_limit_reached: {
    title: "广告次数已用完",
    content: "你最多只能通过广告解锁 2 次生成，请直接购买 1 次生成包继续。"
  },
  rewarded_ad_unavailable: {
    title: "广告暂不可用",
    content: "激励广告暂未开放或加载失败，请直接购买 1 次生成包。"
  },
  rewarded_ad_not_completed: {
    title: "广告未看完",
    content: "完整观看广告后才能解锁本次生成。"
  },
  quota_still_available: {
    title: "当前还有次数",
    content: "你当前还有可用次数，无需通过广告解锁。"
  },
  ad_unlock_session_not_found: {
    title: "解锁会话失效",
    content: "未找到本次广告解锁会话，请重新开始。"
  },
  ad_unlock_session_expired: {
    title: "解锁已过期",
    content: "广告解锁会话已过期，请重新观看广告。"
  },
  ad_unlock_session_already_claimed: {
    title: "奖励已领取",
    content: "本次广告奖励已领取，请勿重复提交。"
  },
  invalid_purchase_product: {
    title: "商品不可用",
    content: "当前购买项暂不可用，请稍后刷新后重试。"
  },
  purchase_order_not_found: {
    title: "订单不存在",
    content: "未找到当前订单，请重新发起购买。"
  },
  wechat_pay_not_configured: {
    title: "支付暂不可用",
    content: "当前微信支付尚未配置完成，请稍后再试。"
  },
  wechat_pay_prepare_failed: {
    title: "拉起支付失败",
    content: "微信支付下单失败，请稍后再试。"
  },
  payment_provider_unavailable: {
    title: "支付暂不可用",
    content: "当前支付通道尚未配置完成，请稍后再试。"
  },
  payment_disabled: {
    title: "支付暂未开放",
    content: "当前支付入口暂未开放，请稍后再试。"
  },
  payment_prepare_failed: {
    title: "拉起支付失败",
    content: "当前支付下单失败，请稍后再试。"
  },
  payment_qrcode_unavailable: {
    title: "二维码暂不可用",
    content: "当前二维码加载失败，请稍后重新发起支付。"
  },
  payment_cancelled: {
    title: "已取消支付",
    content: "你已取消本次支付。"
  },
  payment_confirm_timeout: {
    title: "支付确认中",
    content: "支付已发起成功，到账确认稍有延迟，请稍后刷新额度。"
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
