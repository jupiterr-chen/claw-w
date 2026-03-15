# claw-w

微博数据自动化采集与归档系统（Python, Intel Mac 兼容）。

## 功能
- 按 UID 抓取微博（增量抓取）
- 自动处理正文文本（含 HTML 清洗）
- 自动提取并下载原图（可关闭）
- 支持本地 OCR（tesseract / paddle，可选）
- 输出 **Raw + Curated 两层数据结构**，便于后续分析
- 支持本机运行与 Docker 运行

## 数据目录（两层存储）
```text
weibo_data/
  raw/
    posts.jsonl          # 每条微博一行原始记录
    ocr.jsonl            # 每张图片 OCR 一行记录
    images/
      <post_id>/img_1.jpg ...
  curated/
    signals.jsonl        # 结构化信号（可聚合）
    daily_summary.md     # 每日汇总（本轮）
    weekly_summary.md    # 周汇总模板
  history.db
  logs/
```

## 1) 本机使用步骤（macOS Intel）

### 1. 准备环境
```bash
cd claw-w
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# 若开启 tesseract OCR，需要本机安装：
brew install tesseract tesseract-lang
```

### 2. 配置
```bash
cp config.example.yaml config.yaml
```
编辑 `config.yaml`：
- `auth.cookie`：微博登录 Cookie
- `targets.user_ids`：目标 UID 列表
- `targets.since_date`：可选，`YYYY-MM-DD`
- `download.images`：是否下载图片
- `ocr.enabled`：是否开启 OCR（开启后写入 `raw/ocr.jsonl`）
- `ocr.engine`：推荐 `paddle`（默认用于 Docker/高性能机器）
- `ocr.use_gpu`：Paddle 模式下可选开启 GPU（需宿主机支持 NVIDIA）
- `ocr.reprocess_download_images`：`reprocess-ocr` 模式下是否重新下载图片。设为 `false` 可实现“第二次只做 OCR、不下载”

### 3. 执行（单次）
```bash
python main.py --config config.yaml --mode once
```

### 3.1 强制重跑 OCR（已处理微博也会重下图片并重识别）
```bash
python main.py --config config.yaml --mode once --reprocess-ocr
```

### 3.1 覆盖存储目录（大容量磁盘推荐）
```bash
python main.py --config config.yaml --mode once --base-dir /path/to/weibo_data
```
说明：`--base-dir` 会同时覆盖 `history.db` 与日志路径。

### 4. 守护模式（每天定时）
```bash
python main.py --config config.yaml --mode daemon
```
执行时间由 `config.yaml` 中 `task.run_at` 控制（默认 `00:05`）。

## 2) Docker 方案

### OCR 两套可选方案（适用于 Windows 新机器）

#### 方案 A：Paddle（推荐，当前默认）
- 优点：效果更强，适合后续结构化提取
- 缺点：首次下载模型较慢
- 配置：`config.yaml` 中设置 `ocr.engine: "paddle"`
- CPU 启动：
```bash
docker compose up -d --build
```
- GPU 启动（可选）：
```bash
# config.yaml 里设置 ocr.use_gpu: true
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

#### 方案 B：Tesseract（稳定、轻量）
- 优点：依赖清晰，运行稳定
- 缺点：中文识别效果通常弱于 Paddle
- 配置：`config.yaml` 中设置 `ocr.engine: "tesseract"`
- 启动（使用 tesseract 专用镜像）：
```bash
docker compose -f docker-compose.tesseract.yml up -d --build
```

### 1. 准备配置
```bash
cp config.example.yaml config.yaml
# 编辑 config.yaml
```

### 2. 启动
```bash
docker compose up -d --build
```

> 说明：Dockerfile 默认使用镜像源 `m.daocloud.io/docker.io/python:3.11-slim-bookworm`，用于规避部分网络环境下拉取 `docker.io` 的 size validation 错误与 apt 源 404 问题。
>
> 若构建需要代理（Windows/WSL 常见），请不要填 `127.0.0.1`，应使用 `host.docker.internal`：
> ```bash
> export APT_HTTP_PROXY=http://host.docker.internal:10809
> export APT_HTTPS_PROXY=http://host.docker.internal:10809
> export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
> docker compose build --no-cache --pull
> ```

### 2.1 新机器一键初始化（推荐）
```bash
bash scripts/bootstrap_new_machine.sh
# 或初始化后直接启动
bash scripts/bootstrap_new_machine.sh --run
```
脚本会自动：
- 检查 Docker / Docker Compose
- 初始化 `weibo_data/raw|curated|logs` 目录
- 自动生成 `config.yaml`（若不存在）
- WSL 环境下自动清理 `localhost/127.0.0.1` 代理变量（避免 NAT 代理问题）
- 预构建镜像并给出下一步指令

### 3. Docker 中手动执行一次（推荐用于首轮抓取）
```bash
docker compose run --rm weibo-crawler \
  python main.py --config config.yaml --mode once
```

### 3.1 第二次仅 OCR（不下载图片）
先在 `config.yaml` 设置：
```yaml
ocr:
  enabled: true
  reprocess_download_images: false
```
然后执行：
```bash
docker compose run --rm weibo-crawler \
  python main.py --config config.yaml --mode once --reprocess-ocr
```

> 说明：此模式会复用 `weibo_data/raw/images/<本地post_id>/` 的已有图片，只做 OCR。
>
> 若使用 tesseract 专用编排，请把命令前缀替换为：
> `docker compose -f docker-compose.tesseract.yml run --rm weibo-crawler`

### 4. 查看日志
```bash
docker compose logs -f weibo-crawler
```

### 5. 停止
```bash
docker compose down
```

## 3) 测试
```bash
pytest -q
```

## 4) Git 远端
项目远端仓库：
```text
git@github.com:jupiterr-chen/claw-w.git
```
