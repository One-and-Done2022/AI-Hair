# AI Hair Remix Mini Program

一个本地可跑通的 AI 换发小程序 MVP，包含：

- 微信原生小程序前端
- FastAPI 后端
- 本地磁盘存储原图与结果图
- SQLite 用户/上传/任务历史
- 火山引擎 Seedream 4.5/5.0 接入

## 目录

- `backend/` FastAPI 服务
- `miniapp/` 微信小程序代码
- `tests/` 后端接口测试

## 本地启动

1. 创建环境并安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. 配置环境变量：

```bash
cp .env.example .env
```

至少需要设置：

- `ARK_API_KEY`：火山引擎 Ark API Key
- `WECHAT_APP_ID`、`WECHAT_APP_SECRET`：小程序正式登录时使用

如果只做本地联调，可保留：

- `ALLOW_DEV_LOGIN=true`
- `USE_MOCK_GENERATOR=true`
- `ENFORCE_FACE_DETECTION=false`

3. 启动后端：

```bash
set -a && source .env && set +a
uvicorn app.main:app --reload --app-dir backend --host 0.0.0.0 --port 8000
```

4. 运行测试：

```bash
pytest -q
```

5. 打开微信开发者工具：

- 项目目录选择仓库根目录
- `miniprogramRoot` 已指向 `miniapp/`
- 当前默认请求地址为 `https://api.lcynas.me`
- 如果只是临时本地联调，可将 `miniapp/utils/config.js` 中的 `useLocalDebug` 改成 `true`，临时走 `http://1.95.32.219:8000`
- 开发阶段在开发者工具里关闭“校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书”
- 真机预览、体验版和正式版不能直接使用公网 IP + HTTP，后续必须切换到已备案 HTTPS 域名并在小程序后台配置 `request` 合法域名

## HTTPS 部署

仓库已提供 `api.lcynas.me` 的 Nginx 反向代理模板：

- `deploy/nginx/api.lcynas.me.conf`

完整步骤见：

- `docs/wechat-https-deploy.md`

## systemd 常驻运行

仓库内已提供用户级 service 模板：`deploy/systemd/aiface-backend.service`。

启用方式：

```bash
mkdir -p ~/.config/systemd/user
ln -sf /home/lcy/AIFace/deploy/systemd/aiface-backend.service ~/.config/systemd/user/aiface-backend.service
loginctl enable-linger "$USER"
systemctl --user daemon-reload
systemctl --user enable --now aiface-backend.service
```

常用命令：

```bash
systemctl --user status aiface-backend.service
systemctl --user restart aiface-backend.service
journalctl --user -u aiface-backend.service -n 100 --no-pager
```

## Git 使用

首次初始化：

```bash
git init -b main
```

建议分支：

- `main`
- `feature/backend-api`
- `feature/miniapp-ui`

提交前确认：

- `.env` 未被纳入版本控制
- `storage/` 和本地样例图片未被纳入版本控制
- `pytest -q` 通过
