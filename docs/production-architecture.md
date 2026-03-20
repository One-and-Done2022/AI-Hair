# 后端生产架构说明

## 目标

第一版生产架构保留 `FastAPI + 小程序轮询`，但把重活拆出去：

- API 进程只负责登录、上传、创建任务、查询任务
- 数据库存用户、上传、任务状态
- Redis 只做调度队列
- Worker 独立进程消费生图任务
- OSS 存原图、预览图、候选图、最终图

这版的重点不是“极致复杂”，而是先把 API、任务执行、文件存储解耦，保证后面能横向扩容。

## 组件职责

### 1. FastAPI

- 微信登录、上传校验、模板下发
- 写入 `jobs` 表
- 把 `job_id` 推入队列
- 提供 `/api/jobs/{job_id}` 给小程序轮询

### 2. PostgreSQL / MySQL

- 保存 `users`、`auth_tokens`、`uploads`、`jobs`
- 任务状态始终以数据库为准
- 当前代码通过 `DATABASE_URL` 支持：
  - PostgreSQL：`postgresql+psycopg://...`
  - MySQL：`mysql+pymysql://...`

### 3. Redis 队列

- `pending` 列表保存待处理任务
- `processing` 列表保存已领取未确认任务
- Worker 重启时会先恢复未确认任务，避免任务直接丢失

### 4. Worker

- 独立进程拉取任务
- 读取参考图、组装提示词、调用 Seedream
- 支持多 API key 调度、冷却、永久失效下线
- 支持“先返回首图预览，再异步补齐候选图”

### 5. OSS

- 上传图和结果图不再放数据库
- 数据库只存对象 key
- 对外返回 CDN 或 OSS 公网 URL

## 请求链路

1. 小程序上传照片到 API
2. API 校验后把原图写入 OSS
3. API 写入 `jobs` 表，状态为 `pending`
4. API 把 `job_id` 推入 Redis
5. Worker 拉任务并更新状态：`processing -> preview_ready -> succeeded/failed`
6. 小程序继续轮询 `/api/jobs/{job_id}` 拿结果

## 当前代码里的生产能力

- `backend/app/db.py`：已切到 SQLAlchemy，可直连 PostgreSQL / MySQL
- `backend/app/services/dispatch_queue.py`：已支持本地队列与 Redis 队列
- `backend/app/worker.py`：已支持独立 Worker 进程
- `backend/app/services/storage.py`：已支持本地存储与阿里云 OSS
- `deploy/systemd/aiface-worker.service`：已提供 Worker 常驻模板

## 环境变量建议

生产模式至少配置：

- `DATABASE_URL`
- `JOB_QUEUE_BACKEND=redis`
- `REDIS_URL`
- `RUN_EMBEDDED_WORKER=false`
- `OBJECT_STORAGE_BACKEND=aliyun_oss`
- `OSS_*`
- `ARK_API_KEYS`

数据库连接池已支持：

- `DB_POOL_SIZE`
- `DB_MAX_OVERFLOW`
- `DB_POOL_TIMEOUT_SECONDS`
- `DB_POOL_RECYCLE_SECONDS`

## 本地兼容模式

如果机器上暂时没有 Redis / PostgreSQL，也可以先跑兼容模式：

- `DATABASE_URL=` 留空，使用 `DATABASE_PATH`
- `JOB_QUEUE_BACKEND=local`
- `RUN_EMBEDDED_WORKER=true`
- `OBJECT_STORAGE_BACKEND=local`

这适合本地联调和 mock 压测，不建议作为正式生产部署方案。

## Mock 压测结果

压测环境：

- `USE_MOCK_GENERATOR=true`
- `JOB_QUEUE_BACKEND=local`
- `RUN_EMBEDDED_WORKER=true`
- `JOB_WORKER_CONCURRENCY=4`
- `OBJECT_STORAGE_BACKEND=local`
- `DATABASE_URL=sqlite:////tmp/aiface-mock-pressure/app.db`

压测命令：

```bash
python3 scripts/load_test.py \
  --host http://127.0.0.1:8013 \
  --image "/home/lcy/AIFace/微信图片_20260318192652_461_95.jpg" \
  --users 16 \
  --jobs-per-user 1 \
  --poll-interval 0.2 \
  --job-timeout 80 \
  --random-templates
```

结果一：8 并发 / 8 任务

- 全部成功，0 失败
- 总耗时 `15.06s`
- 吞吐 `0.53 job/s`
- `preview_ready` p50 `9.28s`
- 最终完成 p50 `14.44s`

结果二：16 并发 / 16 任务

- 全部成功，0 失败
- 总耗时 `29.62s`
- 吞吐 `0.54 job/s`
- `preview_ready` p50 `16.66s`
- 最终完成 p50 `21.60s`
- 最终完成 p95 `28.97s`

## 如何理解这些结果

- 这说明当前“API + 队列 + Worker + 轮询”链路在 mock 模式下是稳定的
- 吞吐基本锁在 `0.54 job/s`，瓶颈来自 `4` 个 worker 的处理能力，而不是 API 层
- 并发翻倍后没有失败，说明任务排队和状态流转是正常的
- 这组数据不能等价于真实 Seedream 时延，因为真实生图耗时主要取决于模型侧和网络

## 当前边界

- 本轮只完成了第一版生产架构代码，不包含 Redis / PostgreSQL / OSS 的系统安装
- Redis 队列已做重启恢复，但更复杂的死信、重试次数上限、监控告警还没加
- 真正上线前，建议再补：
  - Redis / PostgreSQL 实例监控
  - Worker 进程数和 key 并发配额联动
  - OSS 生命周期和成本控制
  - 任务超时回收与告警
