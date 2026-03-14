FROM python:3.11-slim

WORKDIR /app

# PaddleOCR 首次会检查模型源连通性；在容器中可跳过以减少冷启动噪音
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

COPY . /app

# 默认执行一次，可用 docker compose 覆盖
CMD ["python", "main.py", "--config", "config.yaml", "--mode", "once"]
