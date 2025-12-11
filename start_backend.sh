#!/bin/bash

# 보험 온톨로지 백엔드 시작 스크립트

echo "🚀 보험 온톨로지 AI 챗봇 백엔드를 시작합니다..."
echo ""

# 환경변수 체크
if [ ! -f ".env" ]; then
    echo "⚠️  .env 파일이 없습니다!"
    echo "   .env 파일을 생성해주세요."
    exit 1
fi

echo "✅ 백엔드 API 서버를 시작합니다..."
echo "   URL: http://localhost:8000"
echo "   Docs: http://localhost:8000/docs"
echo ""

# FastAPI 서버 시작
uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
