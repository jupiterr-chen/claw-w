FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

# 默认执行一次，可用 docker compose 覆盖
CMD ["python", "main.py", "--config", "config.yaml", "--mode", "once"]
