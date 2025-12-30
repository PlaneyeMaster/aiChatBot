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

# 기존 /app에 현재 디렉토리(.)를 추가하여 경로를 더 명확히 합니다.
ENV PYTHONPATH="/app:/app/apps:${PYTHONPATH}"

# CMD에서 uvicorn 실행 시 현재 경로를 다시 한번 확인
CMD ["sh", "-c", "uvicorn apps.gateway_api.main:app --host 0.0.0.0 --port $PORT"]