# 微信小程序 HTTPS 接口部署

目标：把当前运行在 `127.0.0.1:8000` 的 FastAPI 服务通过 `https://api.lcynas.me` 暴露给微信小程序访问。

## 1. DNS

先确认 A 记录：

- `api.lcynas.me -> 1.95.32.219`

仓库当前已经按这个域名准备好了前端请求地址和 Nginx 配置模板。

## 2. 安装并启用 Nginx 站点

仓库内模板：

- `deploy/nginx/api.lcynas.me.conf`

服务器上执行：

```bash
sudo cp /home/lcy/AIFace/deploy/nginx/api.lcynas.me.conf /etc/nginx/sites-available/api.lcynas.me.conf
sudo ln -sf /etc/nginx/sites-available/api.lcynas.me.conf /etc/nginx/sites-enabled/api.lcynas.me.conf
sudo nginx -t
sudo systemctl reload nginx
```

这一步完成后，`http://api.lcynas.me/healthz` 应该能转发到后端。

## 3. 申请 HTTPS 证书

当前服务器未安装 `certbot`，也没有现成证书。执行：

```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d api.lcynas.me
```

执行完成后验证：

```bash
curl -I https://api.lcynas.me/healthz
curl https://api.lcynas.me/healthz
```

预期返回 `200`，接口内容为 `{"status":"ok"}`。

## 4. 微信后台白名单

进入微信公众平台 -> 小程序 -> 开发管理 -> 开发设置 -> 服务器域名，添加：

- `https://api.lcynas.me`

只需要填主域名，不要带路径，也不要写端口。

## 5. 小程序代码

当前默认请求地址已经切到：

- `https://api.lcynas.me`

文件：

- `miniapp/utils/config.js`

如果只是临时本地联调，可把 `useLocalDebug` 改成 `true`，这样会退回到：

- `http://1.95.32.219:8000`

但真机、体验版和正式版必须使用 HTTPS 域名。
