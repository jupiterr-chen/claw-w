# claw-w

微博数据自动化采集与归档系统（Python, Intel Mac 兼容）。

## 功能
- 按 UID 抓取微博（增量抓取）
- 自动处理正文文本（含 HTML 清洗）
- 自动提取并下载原图（可关闭）
- 按日期归档：`YYYY-MM-DD/Post_HHMMSS_ShortID/`
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

### 3. 执行（单次）
```bash
python main.py --config config.yaml --mode once
```

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

每天目录下：
- `summary.json`：当天抓取统计

## 5) Git 远端
项目远端仓库：
```text
git@github.com:jupiterr-chen/claw-w.git
```
