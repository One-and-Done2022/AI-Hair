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
          message: "当前额外免费入口暂未配置，请联系内测支持处理。"
        }
      });
      return;
    }
    if (typeof wx.createRewardedVideoAd !== "function") {
      reject({
        detail: {
          code: "rewarded_ad_unavailable",
          message: "当前微信版本不支持额外免费入口，请联系内测支持处理。"
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
          message: "当前额外免费流程未完成，请稍后再试或联系内测支持。"
        }
      });
    };

    const handleError = () => {
      cleanup(handleClose, handleError);
      reject({
        detail: {
          code: "rewarded_ad_unavailable",
          message: "当前额外免费入口加载失败，请稍后再试或联系内测支持。"
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
