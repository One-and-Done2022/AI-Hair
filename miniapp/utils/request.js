const { baseUrl } = require("./config");

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

function request(options) {
  const {
    url,
    method = "GET",
    data = {},
    header = {},
    withAuth = true
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
    formData = {}
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

