#!/usr/bin/env bash
set -euo pipefail

# claw-w 新机器一键初始化脚本
# 用法：
#   bash scripts/bootstrap_new_machine.sh           # 仅初始化目录/配置
#   bash scripts/bootstrap_new_machine.sh --run     # 初始化后直接 docker compose up -d --build

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_AFTER_INIT=false
if [[ "${1:-}" == "--run" ]]; then
  RUN_AFTER_INIT=true
fi

is_wsl=false
if grep -qiE "microsoft|wsl" /proc/version 2>/dev/null; then
  is_wsl=true
fi

# WSL NAT 下 localhost 代理会导致网络请求异常，自动清理本次会话代理变量。
clear_proxy_if_localhost() {
  local hit=false
  for k in http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy; do
    local v="${!k:-}"
    if [[ -n "$v" && ("$v" == *"127.0.0.1"* || "$v" == *"localhost"*) ]]; then
      unset "$k" || true
      hit=true
    fi
  done

  if [[ "$hit" == true ]]; then
    echo "⚠️ 检测到 localhost 代理，已为当前脚本临时清理代理环境变量。"
    if [[ "$is_wsl" == true ]]; then
      echo "   提示：WSL NAT 模式不支持 localhost 代理镜像。"
      echo "   可长期修复：在 Windows ~/.wslconfig 中设置 networkingMode=mirrored, autoProxy=true，然后执行 wsl --shutdown。"
    fi
  fi
}

clear_proxy_if_localhost

echo "[1/6] 检查 Docker / Compose"
command -v docker >/dev/null 2>&1 || { echo "❌ docker 未安装"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "❌ docker compose 不可用"; exit 1; }

echo "[2/6] 初始化数据目录"
mkdir -p weibo_data/raw weibo_data/curated weibo_data/logs

echo "[3/6] 初始化配置"
if [[ ! -f config.yaml ]]; then
  cp config.example.yaml config.yaml
  echo "✅ 已创建 config.yaml（请务必填写 auth.cookie 和 targets.user_ids）"
else
  echo "ℹ️ 已存在 config.yaml，跳过复制"
fi

echo "[4/6] 配置提示"
if ! grep -q 'engine: "paddle"' config.yaml 2>/dev/null; then
  echo "⚠️ 建议在 config.yaml 中设置：ocr.engine: \"paddle\""
fi

echo "[5/6] 容器镜像预构建"
docker compose build

echo "[6/6] 完成"
echo "下一步："
echo "  1) 编辑 config.yaml（cookie/uid/since_date）"
echo "  2) 启动：docker compose up -d"
echo "  3) 查看日志：docker compose logs -f weibo-crawler"

if [[ "$RUN_AFTER_INIT" == "true" ]]; then
  echo "\n🚀 --run 已指定，开始启动服务..."
  docker compose up -d
  docker compose logs --tail=60 weibo-crawler
fi
