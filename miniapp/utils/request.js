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
    timeout,
    _retriedAfterAuthRefresh = false
  } = options;

  return new Promise((resolve, reject) => {
    wx.request({
      url: `${baseUrl}${url}`,
      method,
      data,
      timeout,
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
              timeout,
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
    timeout,
    onProgress,
    _retriedAfterAuthRefresh = false
  } = options;

  return new Promise((resolve, reject) => {
    const uploadTask = wx.uploadFile({
      url: `${baseUrl}${url}`,
      filePath,
      name,
      timeout,
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
              timeout,
              onProgress,
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

    if (uploadTask && typeof uploadTask.onProgressUpdate === "function" && typeof onProgress === "function") {
      uploadTask.onProgressUpdate((progressEvent) => {
        onProgress(progressEvent || {});
      });
    }
  });
}

function downloadFile(options) {
  const {
    url,
    header = {},
    withAuth = true,
    timeout,
    _retriedAfterAuthRefresh = false
  } = options;

  return new Promise((resolve, reject) => {
    const downloadTask = wx.downloadFile({
      url: `${baseUrl}${url}`,
      timeout,
      header: getHeaders(withAuth, header),
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response);
          return;
        }
        if (withAuth && !_retriedAfterAuthRefresh && isUnauthorized(response)) {
          refreshAuthToken()
            .then(() => downloadFile({
              url,
              header,
              withAuth,
              timeout,
              _retriedAfterAuthRefresh: true
            }))
            .then(resolve)
            .catch(reject);
          return;
        }
        reject({
          detail: {
            code: "download_failed",
            message: "资源下载失败，请稍后再试。"
          },
          statusCode: response.statusCode
        });
      },
      fail(error) {
        reject(error);
      }
    });

    if (downloadTask && typeof downloadTask.onProgressUpdate === "function" && typeof options.onProgress === "function") {
      downloadTask.onProgressUpdate((progressEvent) => {
        options.onProgress(progressEvent || {});
      });
    }
  });
}

module.exports = {
  baseUrl,
  request,
  uploadFile,
  downloadFile
};
