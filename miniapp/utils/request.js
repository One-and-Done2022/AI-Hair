const { baseUrl } = require("./config");

let refreshingAuthPromise = null;

function getToken() {
  return wx.getStorageSync("authToken");
}

function parsePayload(payload) {
  if (typeof payload !== "string") {
    return payload;
  }

  try {
    return JSON.parse(payload);
  } catch (error) {
    return { message: payload };
  }
}

function getHeaders(withAuth, extraHeaders) {
  const headers = Object.assign({}, extraHeaders || {});
  if (withAuth) {
    const token = getToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }
  return headers;
}

function isUnauthorized(response) {
  return response && response.statusCode === 401;
}

function refreshAuthToken() {
  if (refreshingAuthPromise) {
    return refreshingAuthPromise;
  }

  refreshingAuthPromise = (async () => {
    const { clearLogin, ensureLogin } = require("./auth");
    clearLogin();
    await ensureLogin(true);
  })();

  return refreshingAuthPromise.finally(() => {
    refreshingAuthPromise = null;
  });
}

function request(options) {
  const {
    url,
    method = "GET",
    data = {},
    header = {},
    withAuth = true,
    _retriedAfterAuthRefresh = false
  } = options;

  return new Promise((resolve, reject) => {
    wx.request({
      url: `${baseUrl}${url}`,
      method,
      data,
      header: getHeaders(withAuth, header),
      success(response) {
        const payload = parsePayload(response.data);
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(payload);
          return;
        }
        if (withAuth && !_retriedAfterAuthRefresh && isUnauthorized(response)) {
          refreshAuthToken()
            .then(() => request({
              url,
              method,
              data,
              header,
              withAuth,
              _retriedAfterAuthRefresh: true
            }))
            .then(resolve)
            .catch(reject);
          return;
        }
        reject(payload);
      },
      fail(error) {
        reject(error);
      }
    });
  });
}

function uploadFile(options) {
  const {
    url,
    filePath,
    name = "file",
    formData = {},
    _retriedAfterAuthRefresh = false
  } = options;

  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: `${baseUrl}${url}`,
      filePath,
      name,
      formData,
      header: getHeaders(true),
      success(response) {
        const payload = parsePayload(response.data);
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(payload);
          return;
        }
        if (!_retriedAfterAuthRefresh && isUnauthorized(response)) {
          refreshAuthToken()
            .then(() => uploadFile({
              url,
              filePath,
              name,
              formData,
              _retriedAfterAuthRefresh: true
            }))
            .then(resolve)
            .catch(reject);
          return;
        }
        reject(payload);
      },
      fail(error) {
        reject(error);
      }
    });
  });
}

module.exports = {
  baseUrl,
  request,
  uploadFile
};
