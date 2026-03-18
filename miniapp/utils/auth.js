const { request } = require("./request");

function doWxLogin() {
  return new Promise((resolve, reject) => {
    wx.login({
      success: resolve,
      fail: reject
    });
  });
}

async function ensureLogin(forceRefresh = false) {
  const cachedToken = !forceRefresh && wx.getStorageSync("authToken");
  if (cachedToken) {
    return cachedToken;
  }

  const loginResult = await doWxLogin();
  const code = loginResult.code || `dev_${Date.now()}`;
  const payload = await request({
    url: "/api/auth/wechat/login",
    method: "POST",
    data: { code },
    withAuth: false
  });
  wx.setStorageSync("authToken", payload.token);
  wx.setStorageSync("userId", payload.user_id);
  return payload.token;
}

function clearLogin() {
  wx.removeStorageSync("authToken");
  wx.removeStorageSync("userId");
}

module.exports = {
  ensureLogin,
  clearLogin
};

