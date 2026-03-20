const PROD_BASE_URL = "https://api.foodtop1.com";
const LOCAL_DEBUG_BASE_URL = "http://1.95.32.219:8000";

// 需要临时绕过微信合法域名校验做本地联调时，改成 true。
const useLocalDebug = false;

const baseUrl = useLocalDebug ? LOCAL_DEBUG_BASE_URL : PROD_BASE_URL;

module.exports = {
  PROD_BASE_URL,
  LOCAL_DEBUG_BASE_URL,
  useLocalDebug,
  baseUrl
};
