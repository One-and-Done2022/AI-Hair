const { request } = require("./request");

const DEV_LOGIN_CODE_STORAGE_KEY = "devLoginCode";

function doWxLogin() {
  return new Promise((resolve, reject) => {
    wx.login({
      success: resolve,
      fail: reject
    });
  });
}

function getStableDevLoginCode() {
  let code = wx.getStorageSync(DEV_LOGIN_CODE_STORAGE_KEY);
  if (code) {
    return code;
  }
  code = `dev_local_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
  wx.setStorageSync(DEV_LOGIN_CODE_STORAGE_KEY, code);
  return code;
}

async function ensureLogin(forceRefresh = false) {
  const cachedToken = !forceRefresh && wx.getStorageSync("authToken");
  if (cachedToken) {
    return cachedToken;
  }

  const loginResult = await doWxLogin();
  const code = loginResult.code || getStableDevLoginCode();
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
