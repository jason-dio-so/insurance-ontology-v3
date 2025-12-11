#!/bin/bash

# 보험 온톨로지 프론트엔드 시작 스크립트

echo "🚀 보험 온톨로지 AI 챗봇 프론트엔드를 시작합니다..."
echo ""

cd frontend

# node_modules가 없으면 설치
if [ ! -d "node_modules" ]; then
    echo "📦 의존성 패키지를 설치합니다..."
    npm install
    echo ""
fi

echo "✅ 프론트엔드 개발 서버를 시작합니다..."
echo "   URL: http://localhost:5173"
echo ""
echo "⚠️  백엔드 서버도 실행되어 있어야 합니다!"
echo "   별도 터미널에서 다음 명령 실행:"
echo "   ./start_backend.sh"
echo ""

npm run dev
