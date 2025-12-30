FROM python:3.11-slim

# 시스템 의존성 설치 (필요한 경우)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# uvicorn이 requirements.txt에 있는지 꼭 확인하세요!
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
# Render에서 제공하는 PORT 환경변수를 사용합니다.
# bash -lc 대신 더 직관적인 쉘 실행 방식을 사용합니다.
CMD uvicorn apps.gateway_api.main:app --host 0.0.0.0 --port $PORT