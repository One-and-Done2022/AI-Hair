const PROD_BASE_URL = "https://api.foodtop1.com";
const LOCAL_DEBUG_BASE_URL = "http://1.95.32.219:8000";

// 需要临时绕过微信合法域名校验做本地联调时，改成 true。
const useLocalDebug = false;
// 内部工具开关。默认关闭，只有需要运营录入场景时再手动改成 true 并重新编译小程序。
const enableInternalSceneTool = false;

const baseUrl = useLocalDebug ? LOCAL_DEBUG_BASE_URL : PROD_BASE_URL;

module.exports = {
  PROD_BASE_URL,
  LOCAL_DEBUG_BASE_URL,
  useLocalDebug,
  enableInternalSceneTool,
  baseUrl
};
