#!/bin/bash

# 보험 온톨로지 프론트엔드 시작 스크립트

echo "=========================================="
echo "  보험 온톨로지 AI 프론트엔드"
echo "=========================================="
echo ""

cd frontend

# node_modules가 없으면 설치
if [ ! -d "node_modules" ]; then
    echo "📦 의존성 패키지를 설치합니다..."
    npm install
    echo ""
fi

echo "📋 주요 기능:"
echo "   - 상품 비교: 다빈치로봇, 뇌출혈, 암진단비 등"
echo "   - 상품/담보 설명: 보장개시일, 가입나이, 면책사항"
echo "   - 자유 질문: 약관 정의, 보장 조건 등"
echo "   - 전체 보험사 비교 (8개 보험사 동시 비교)"
echo ""

echo "✅ 지원 보험사:"
echo "   삼성화재, 현대해상, DB손해보험, KB손해보험"
echo "   한화손해보험, 롯데손해보험, 메리츠화재, 흥국화재"
echo ""

echo "⚠️  백엔드 서버가 먼저 실행되어 있어야 합니다!"
echo "   별도 터미널에서: ./start_backend.sh"
echo ""

echo "🚀 프론트엔드 개발 서버를 시작합니다..."
echo "   URL: http://localhost:5173"
echo ""

npm run dev
