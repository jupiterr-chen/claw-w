# claw-w

微博数据自动化采集与归档系统（Python, Intel Mac 兼容）。

## 功能
- 按 UID 抓取微博（增量抓取）
- 自动处理正文文本（含 HTML 清洗）
- 自动提取并下载原图（可关闭）
- 支持本地 OCR（tesseract / paddle，可选）
- 按日期归档（可按 UID 分组）：`YYYY-MM-DD/UID_xxx/Post_HHMMSS_ShortID/`
- 每日写入 `summary.json`
- 支持本机运行与 Docker 运行

## 目录结构
```text
claw-w/
  crawler/
  storage/
  tracking/
  utils/
  tests/
  weibo_data/
  main.py
  config.example.yaml
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
- `auth.cookie`：填入微博小号 Cookie
- `targets.user_ids`：目标 UID 列表
- `targets.since_date`：可选，`YYYY-MM-DD`
- `download.images`：是否下载图片
- `storage.organize_by_uid`：是否按 UID 分组目录（推荐 `true`）
- `ocr.enabled`：是否开启 OCR（开启后会写入 `weibo_data/ocr/ocr_results.jsonl`）

### 3. 执行（单次）
```bash
python main.py --config config.yaml --mode once
```

### 3.1 覆盖存储目录（大容量磁盘推荐）
```bash
python main.py --config config.yaml --mode once --base-dir /path/to/weibo_data
```
说明：`--base-dir` 会同时覆盖默认的 `history.db` 和日志文件路径到该目录下。

### 4. 守护模式（每天定时）
```bash
python main.py --config config.yaml --mode daemon
```
执行时间由 `config.yaml` 中 `task.run_at` 控制（默认 `00:05`）。

## 2) Docker 方案

### 1. 准备配置
```bash
cp config.example.yaml config.yaml
# 编辑 config.yaml
```

### 2. 启动
```bash
docker compose up -d --build
```

### 3. 查看日志
```bash
docker compose logs -f weibo-crawler
```

### 4. 停止
```bash
docker compose down
```

## 3) 测试
```bash
pytest -q
```

## 4) 数据输出格式
每条微博一个目录：
- `content.txt`：正文
- `img_1.jpg`, `img_2.jpg` ...：配图
- `ocr.txt`：该微博图片 OCR 合并文本（仅 OCR 开启且有识别内容时生成）

每天目录下：
- `summary.json`：当天抓取统计

全局 OCR 汇总：
- `weibo_data/ocr/ocr_results.jsonl`：每张图片一条识别记录（含 ok/error）

## 5) Git 远端
项目远端仓库：
```text
git@github.com:jupiterr-chen/claw-w.git
```
