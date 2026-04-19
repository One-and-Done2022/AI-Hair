const { rewardedVideoAdUnitId } = require("./config");
const { request } = require("./request");

function isRewardedVideoAdEnabled() {
  return !!rewardedVideoAdUnitId;
}

function createAdUnlockSession() {
  return request({
    url: "/api/quota/ad-unlock/session",
    method: "POST"
  });
}

function claimAdUnlockSession(sessionId) {
  return request({
    url: "/api/quota/ad-unlock/claim",
    method: "POST",
    data: {
      session_id: sessionId
    }
  });
}

function showRewardedVideoAd() {
  return new Promise((resolve, reject) => {
    if (!isRewardedVideoAdEnabled()) {
      reject({
        detail: {
          code: "rewarded_ad_unavailable",
          message: "激励广告暂未配置，请直接购买 1 次生成包。"
        }
      });
      return;
    }
    if (typeof wx.createRewardedVideoAd !== "function") {
      reject({
        detail: {
          code: "rewarded_ad_unavailable",
          message: "当前微信版本不支持激励广告，请直接购买 1 次生成包。"
        }
      });
      return;
    }

    const ad = wx.createRewardedVideoAd({
      adUnitId: rewardedVideoAdUnitId
    });

    const cleanup = (onClose, onError) => {
      if (typeof ad.offClose === "function") {
        ad.offClose(onClose);
      }
      if (typeof ad.offError === "function") {
        ad.offError(onError);
      }
    };

    const handleClose = (result) => {
      cleanup(handleClose, handleError);
      if (!result || result.isEnded) {
        resolve(true);
        return;
      }
      reject({
        detail: {
          code: "rewarded_ad_not_completed",
          message: "完整观看广告后才能解锁本次生成。"
        }
      });
    };

    const handleError = () => {
      cleanup(handleClose, handleError);
      reject({
        detail: {
          code: "rewarded_ad_unavailable",
          message: "激励广告加载失败，请稍后再试或直接购买。"
        }
      });
    };

    ad.onClose(handleClose);
    ad.onError(handleError);

    ad.show().catch(() => ad.load().then(() => ad.show())).catch(handleError);
  });
}

async function unlockQuotaByRewardedAd() {
  const session = await createAdUnlockSession();
  await showRewardedVideoAd();
  return claimAdUnlockSession(session.session_id);
}

module.exports = {
  claimAdUnlockSession,
  createAdUnlockSession,
  isRewardedVideoAdEnabled,
  showRewardedVideoAd,
  unlockQuotaByRewardedAd
};
