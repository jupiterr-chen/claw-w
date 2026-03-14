ARG BASE_IMAGE=m.daocloud.io/docker.io/python:3.11-slim-bookworm
FROM ${BASE_IMAGE}

WORKDIR /app

# PaddleOCR 首次会检查模型源连通性；在容器中可跳过以减少冷启动噪音
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
ENV PYTHONUNBUFFERED=1

# 可选构建代理（示例：http://host.docker.internal:10809）
ARG APT_HTTP_PROXY=
ARG APT_HTTPS_PROXY=
ARG PIP_INDEX_URL=

COPY requirements.txt /app/requirements.txt
RUN if [ -n "$APT_HTTP_PROXY" ]; then echo "Acquire::http::Proxy \"$APT_HTTP_PROXY\";" > /etc/apt/apt.conf.d/99proxy; fi \
    && if [ -n "$APT_HTTPS_PROXY" ]; then echo "Acquire::https::Proxy \"$APT_HTTPS_PROXY\";" >> /etc/apt/apt.conf.d/99proxy; fi \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/* \
    && if [ -n "$PIP_INDEX_URL" ]; then pip install --no-cache-dir -i "$PIP_INDEX_URL" -r requirements.txt; else pip install --no-cache-dir -r requirements.txt; fi
COPY . /app

# 默认执行一次，可用 docker compose 覆盖
CMD ["python", "main.py", "--config", "config.yaml", "--mode", "once"]
