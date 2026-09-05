# 猫咪短视频工作台 / Cat Shorts Workbench

Personal single-admin bench: phone clips land in Google Drive (or a local inbox),
you crop/trim in the browser, then the worker burns English captions + a CC0 music
bed, uploads a **private YouTube draft**, and waits for **one explicit click**
before going public.

This repo is P0: end-to-end in Docker Compose, including a fully offline mock path.

---

## 产品范围 / Scope

**In**

1. Upload phone videos to a Drive folder (or drop them in the mock inbox)
2. System syncs them into the app (idempotent on file id / source key)
3. Web UI crop + trim + basic vertical framing; you confirm
4. After confirm: FFmpeg render (1080×1920, H.264, ~30fps, ≤59s) with burned-in English captions and CC0 bed music
5. Technical check (exists + decodable + codec/size/duration) **before** upload
6. Upload result to YouTube as a **private** draft (or mock)
7. Later: one **发布公开** button sets that draft public

**Out (do not add here)**

Gemini/Grok analysis agents, B/C/D candidate search, budget ledger, ZapCap,
multi-tenant, other social platforms, auto-public without a click.

---

## 本地一键演示 / Offline demo (`docker compose up`)

No Google credentials required.

```bash
cp .env.example .env          # optional; defaults work
docker compose up --build
```

Open **http://localhost:8080**

| 项 | 默认 |
| --- | --- |
| 账号 | `admin` |
| 密码 | `changeme` |
| Drive | `DRIVE_MODE=mock` 扫描 `/data/inbox` |
| YouTube | `YOUTUBE_MODE=mock` 写本地 JSON 草稿 |

Compose 启动时会：

- 跑 Alembic 建表
- 生成 CC0 配乐 `cozy_afternoon.wav`（若缺失）
- 放入演示竖屏 `sample-cat.mp4` 到收件箱

然后：

1. 登录 → 点 **同步素材**（调度器约 3 秒后也会自动扫一次）
2. 打开任务 → 调起点/终点和取景 → **确认裁剪并生成**
3. Worker 自动：渲染字幕+配乐 → 技术检查 → mock 私密草稿
4. 点 **发布公开**（只改这一条草稿的可见性）

也可点 **上传本地演示视频**，完全不依赖 inbox。

模拟 YouTube 记录在数据卷 `/data/youtube_mock/mock_*.json`。

---

## 服务构成 / Compose services

| 服务 | 作用 |
| --- | --- |
| `web` | Nginx + React UI，`:8080`，反代 `/api` |
| `api` | FastAPI |
| `worker` | 独立进程，按阶段推进渲染/检查/上传/发布 |
| `scheduler` | 独立进程，定时 Drive / inbox 同步 |
| `postgres` | PostgreSQL 16 |

Secrets live in env / `.env`. `.env.example` has **no real keys**.

---

## 环境变量 / Environment

See `.env.example`. Important ones:

| 变量 | 说明 |
| --- | --- |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 唯一管理员 |
| `SECRET_KEY` | JWT |
| `DATABASE_URL` | SQLAlchemy + psycopg |
| `DRIVE_MODE` | `mock` \| `live` |
| `DRIVE_INBOX_DIR` | mock 收件箱 |
| `DRIVE_FOLDER_ID` | live 文件夹 ID |
| `GOOGLE_CLIENT_SECRETS_FILE` / `GOOGLE_TOKEN_FILE` | Drive OAuth |
| `YOUTUBE_MODE` | `mock` \| `live` |
| `YOUTUBE_CLIENT_SECRETS_FILE` / `YOUTUBE_TOKEN_FILE` | YouTube OAuth |
| `RENDER_MAX_SECONDS` | 默认 59 |
| `MUSIC_BED_PATH` | CC0 配乐 |

---

## 幂等与重试 / Idempotency & retry

| 步骤 | 幂等键 |
| --- | --- |
| 同步 | `assets.source_key`（`drive:{id}` 或 `mock:{filename}`）已存在则跳过 |
| 渲染 | 同 `job` + `crop_fingerprint` 且成片文件仍在 → 跳过 |
| 上传 | 已有 `youtube_video_id` → 跳过 |
| 发布 | `youtube_privacy == public` → 跳过 |

失败停在**当前阶段**（`RENDERING` / `CHECKING` / `UPLOADING` / `PUBLISHING`…），
**不会**重置回 `NEW`。界面「从当前阶段重试」只把 `status` 设回 `pending`。

阶段：

`NEW` → `CROP_CONFIRMED` → `RENDERING` → `RENDERED` → `CHECKING` → `CHECKED` → `UPLOADING` → `DRAFT` →（人工点击）→ `PUBLISHING` → `PUBLIC`

---

## 字幕 / 配乐合同（给后续 AI）

见 [`docs/CAPTION_CONTRACT.md`](docs/CAPTION_CONTRACT.md)。

- 输入：用户确认后的竖屏 MP4（h264+aac，≤60s）
- 输出：烧字幕 MP4 + 可选 SRT
- 英文 3–6 句短行
- 配乐：捆绑的原创 CC0 循环 `backend/assets/music/cozy_afternoon.wav`（`scripts/generate_bed.py` 生成，无第三方采样）

P0 **不依赖任何 AI 站**。现在的字幕是确定性英文兜底句，FFmpeg 路径本身可独立跑通。

---

## 正式 Google 路径 / Live OAuth

### 共用：Google Cloud 项目

1. 新建项目，启用 **Google Drive API** 与 **YouTube Data API v3**
2. OAuth 同意屏幕（External / Testing 即可，把自己加为测试用户）
3. 凭证 → 创建 **OAuth 客户端 ID** → 应用类型 **桌面应用**
4. 下载 JSON

把 JSON 挂进数据卷（compose 已挂 `/data`）：

```text
/data/secrets/google_client_secrets.json
/data/secrets/youtube_client_secrets.json   # 可用同一份客户端
```

本机授权一次（需要浏览器；在已登录 Google 的机器上跑）：

```bash
# 在 backend 容器或本地 venv，工作目录 backend/
export GOOGLE_CLIENT_SECRETS_FILE=/data/secrets/google_client_secrets.json
export GOOGLE_TOKEN_FILE=/data/secrets/google_token.json
python -m app.tools.oauth_drive

export YOUTUBE_CLIENT_SECRETS_FILE=/data/secrets/youtube_client_secrets.json
export YOUTUBE_TOKEN_FILE=/data/secrets/youtube_token.json
python -m app.tools.oauth_youtube
```

`.env`：

```env
DRIVE_MODE=live
DRIVE_FOLDER_ID=你的文件夹ID
YOUTUBE_MODE=live
```

重启 `api` / `worker` / `scheduler`。

- Drive：只读列出文件夹内视频并下载新文件
- YouTube：`videos.insert` `privacyStatus=private`；发布按钮只对该 id 调 `videos.update` → `public`
- 没有 token / 不想联网时保持 `*_MODE=mock`

文件夹 ID：浏览器打开 Drive 文件夹，URL 里 `folders/` 后面那一段。

---

## 开发（不用 Compose 前端镜像时）

```bash
# API
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://catshort:catshort@localhost:5432/catshort
alembic upgrade head
uvicorn app.main:app --reload --port 8000
python -m app.worker
python -m app.scheduler

# UI
cd frontend
npm install
npm run dev    # http://localhost:5173  代理 /api → :8000
```

单元测试：`cd backend && pip install pytest && pytest`

---

## English (short)

Personal cat-shorts workbench. Compose brings up web, API, worker, scheduler, and Postgres.

**Demo without Google:** `docker compose up --build` → http://localhost:8080 → `admin` / `changeme` → sync (sample inbox clip) or upload a local mp4 → crop/trim → confirm → FFmpeg hard-subs + CC0 bed → mock private YouTube draft → Publish sets that draft public.

**Live:** OAuth desktop clients + token files as above; `DRIVE_MODE=live` + folder id; `YOUTUBE_MODE=live`. Uploads are always private until you click publish.

**Caption contract** for a later AI: `docs/CAPTION_CONTRACT.md`. The FFmpeg path does not need an AI station.

**Idempotency:** sync by `source_key`, render by crop fingerprint, upload/publish by stored YouTube id/privacy. Retry is stage-based, never reset-to-NEW.
