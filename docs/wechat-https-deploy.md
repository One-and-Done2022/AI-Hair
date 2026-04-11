# 微信小程序 HTTPS 接口部署

目标：

- 把当前运行在 `127.0.0.1:8000` 的 FastAPI 服务通过 `https://api.lcynas.me` 暴露给微信小程序访问。

## 1. DNS

先确认 A 记录：

- `api.lcynas.me -> 1.95.32.219`

仓库当前已经按这个域名准备好了前端请求地址和 Nginx 配置模板。

说明：

- 当前仓库只维护小程序 API 对应的站点模板。
- 系统里其他 Nginx 站点，例如 NAS 反向代理，继续单独管理，不在这里覆盖。

## 2. 放置 HTTPS 证书

当前项目直接使用已有证书，不走 `certbot`。建议统一放到系统目录：

- `/etc/nginx/ssl/lcynas.me_certificate.pem`
- `/etc/nginx/ssl/lcynas.me_private.key`

当前工作区里已有一份源文件：

- `/home/lcy/AIFace/lcynas.me_certificate.pem`
- `/home/lcy/AIFace/lcynas.me_private.key`

复制到系统目录：

```bash
sudo install -d -m 755 /etc/nginx/ssl
sudo install -m 644 /home/lcy/AIFace/lcynas.me_certificate.pem /etc/nginx/ssl/lcynas.me_certificate.pem
sudo install -m 600 /home/lcy/AIFace/lcynas.me_private.key /etc/nginx/ssl/lcynas.me_private.key
```

当前证书需要覆盖 `api.lcynas.me`。

## 3. 安装并启用 Nginx 站点

仓库内模板：

- `deploy/nginx/api.lcynas.me.conf`

服务器上执行：

```bash
sudo cp /home/lcy/AIFace/deploy/nginx/api.lcynas.me.conf /etc/nginx/sites-available/api.lcynas.me.conf
sudo ln -sf /etc/nginx/sites-available/api.lcynas.me.conf /etc/nginx/sites-enabled/api.lcynas.me.conf
sudo nginx -t
sudo systemctl reload nginx
```

这一步完成后：

- `http://api.lcynas.me/healthz` 会重定向到 HTTPS。

执行完成后验证：

```bash
curl -i https://api.lcynas.me/healthz
```

预期：

- `https://api.lcynas.me/healthz` 返回 `200 OK`，接口内容为 `{"status":"ok"}`。

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
