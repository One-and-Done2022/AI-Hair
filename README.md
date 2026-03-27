# AI Hair Remix Mini Program

一个面向微信小程序的 AI 换发项目，当前包含：

- `backend/`：FastAPI API、任务状态查询、模板下发、图片校验、Seedream 调用
- `miniapp/`：微信原生小程序前端
- `tests/`：后端接口测试
- `deploy/`：Nginx 与 systemd 模板
- `docs/`：部署与架构文档

## 本地开发

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

本地联调建议：

- `ALLOW_DEV_LOGIN=true`
- `USE_MOCK_GENERATOR=true`
- `JOB_QUEUE_BACKEND=local`
- `RUN_EMBEDDED_WORKER=true`
- `OBJECT_STORAGE_BACKEND=local`
- `DATABASE_URL=` 置空，改用 `DATABASE_PATH`

启动后端：

```bash
set -a && source .env && set +a
uvicorn app.main:app --reload --app-dir backend --host 0.0.0.0 --port 8000
```

运行测试：

```bash
pytest -q
```

微信开发者工具直接打开仓库根目录即可，`project.config.json` 已把 `miniprogramRoot` 指到 `miniapp/`。

## 第一版生产架构

当前后端已支持第一版生产拆分：

- FastAPI 只负责鉴权、上传、创建任务、轮询结果
- PostgreSQL / MySQL 持久化用户、上传、任务状态
- Redis 负责任务队列
- 独立 Worker 进程消费任务
- OSS 负责原图、预览图、结果图存储
- 小程序继续通过 `/api/jobs/{job_id}` 轮询任务状态

完整说明见 [docs/production-architecture.md](/home/lcy/AIFace/docs/production-architecture.md)。

## 生产启动

API 服务：

```bash
set -a && source .env && set +a
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

独立 Worker：

```bash
set -a && source .env && set +a
PYTHONPATH=/home/lcy/AIFace/backend python -m app.worker
```

systemd 模板：

- [deploy/systemd/aiface-backend.service](/home/lcy/AIFace/deploy/systemd/aiface-backend.service)
- [deploy/systemd/aiface-worker.service](/home/lcy/AIFace/deploy/systemd/aiface-worker.service)

## Mock 压测

仓库内置了并发压测脚本：

```bash
python3 scripts/load_test.py \
  --host http://127.0.0.1:8013 \
  --image "/home/lcy/AIFace/微信图片_20260318192652_461_95.jpg" \
  --users 8 \
  --jobs-per-user 1 \
  --poll-interval 0.2 \
  --job-timeout 60 \
  --random-templates
```

本轮生产化改造的 mock 压测结果和解释已经写入 [docs/production-architecture.md](/home/lcy/AIFace/docs/production-architecture.md)。

## HTTPS 与微信域名

- HTTPS 反向代理说明见 [docs/wechat-https-deploy.md](/home/lcy/AIFace/docs/wechat-https-deploy.md)
- 当前小程序默认接口域名见 `miniapp/utils/config.js`

## Git

提交前确认：

- `.env`、`storage/`、本地样例图、生成图没有被加入版本控制
- `pytest -q` 通过
- 小程序界面改动附带截图

## 场景草案工具

后端已支持把场景参考图拆成 `scene_only` block，并返回可直接落到 `scenes.json` 的 `scene_draft`。

小程序侧入口：

- `我的 -> 场景草案工具`

服务端落库脚本：

```bash
python3 scripts/add_scene_draft.py --input /path/to/scene-response.json
```

如果输入文件是完整接口响应，脚本会自动提取其中的 `scene_draft`；如果已经是纯 `scene_draft` JSON，也可以直接使用。

需要立即同步到后端数据目录时：

```bash
python3 scripts/add_scene_draft.py --input /path/to/scene-response.json --sync
```

如果你当前的 `faceprompt-sync.service` 已经在后台监听，通常只写入 `Faceprompt/src/faceprompt/data/scenes.json` 就够了，不必额外执行 `--sync`。

## 内部场景审核流水线

仓库已内置一套内部自动化流程，用于把热门场景参考图转换成“可审核的官方场景候选”。

### 1. 丢图进 inbox

把参考图放进：

```bash
storage/scene_pipeline/inbox/
```

审核示例人物固定使用：

- `assets/male.jpg`
- `assets/female.jpg`

### 2. 生成审核包

```bash
set -a && source .env && set +a
python3 scripts/scene_pipeline.py
```

它会自动完成：

- 用 Gemini 3 Pro 理解场景图并提取 block
- 生成 `scene_draft.json`
- 用男女两张官方示例人物图分别跑一次 `scene_only` 审核图

输出目录：

```bash
storage/scene_pipeline/review/<scene_id>/
```

其中会包含：

- `source.*`
- `blocks.json`
- `scene_draft.json`
- `scene_only_prompt.txt`
- `review_male.*`
- `review_female.*`
- `metadata.json`

### 3. 审核通过或驳回

通过并写入官方场景库：

```bash
python3 scripts/review_scene_pipeline.py approve <scene_id> --sync
```

如果需要同步后顺带重启后端：

```bash
python3 scripts/review_scene_pipeline.py approve <scene_id> --sync --restart
```

如果需要指定正式封面优先使用女生或男生审核图：

```bash
python3 scripts/review_scene_pipeline.py approve <scene_id> --cover-gender female --sync
python3 scripts/review_scene_pipeline.py approve <scene_id> --cover-gender male --sync
```

驳回：

```bash
python3 scripts/review_scene_pipeline.py reject <scene_id> --reason "审核图不稳定"
```

归档目录：

- 通过：`storage/scene_pipeline/approved/`
- 驳回：`storage/scene_pipeline/rejected/`

## 模板真实样片流水线

仓库已支持给发型模板和场景模板批量生成真实样片，并在审核通过后直接落到前端模板封面。

### 1. 生成审核包

场景模板：

```bash
set -a && source .env && set +a
python3 scripts/template_image_pipeline.py scenes
```

发型模板：

```bash
set -a && source .env && set +a
python3 scripts/template_image_pipeline.py hairstyles --ids male-forward-spikes,female-french-lazy-waves
```

输出目录：

- `storage/template_image_pipeline/review/scenes/<scene_id>/`
- `storage/template_image_pipeline/review/hairstyles/<hairstyle_id>/`

每个审核包会包含：

- `template_snapshot.json`
- `prompt.txt`
- `review_<gender>.*`
- `metadata.json`

### 2. 审核通过或驳回

通过并写入模板正式封面：

```bash
python3 scripts/review_template_image_pipeline.py approve scenes morning-window-softlight --sync
python3 scripts/review_template_image_pipeline.py approve hairstyles male-forward-spikes --sync
```

如需指定使用哪张审核图作为正式封面：

```bash
python3 scripts/review_template_image_pipeline.py approve scenes morning-window-softlight --cover-gender female --sync
```

驳回：

```bash
python3 scripts/review_template_image_pipeline.py reject hairstyles male-forward-spikes --reason "样片不稳定"
```

归档目录：

- 通过：`storage/template_image_pipeline/approved/`
- 驳回：`storage/template_image_pipeline/rejected/`
