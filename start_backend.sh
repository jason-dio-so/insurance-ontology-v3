#!/bin/bash

# 보험 온톨로지 백엔드 시작 스크립트

echo "=========================================="
echo "  보험 온톨로지 AI 백엔드 서버"
echo "=========================================="
echo ""

# 환경변수 체크
if [ ! -f ".env" ]; then
    echo "❌ .env 파일이 없습니다!"
    echo "   필수 환경변수:"
    echo "   - POSTGRES_URL: PostgreSQL 연결 문자열"
    echo "   - OPENAI_API_KEY: OpenAI API 키"
    echo ""
    echo "   .env.example을 참고하여 .env 파일을 생성해주세요."
    exit 1
fi

# 필수 환경변수 확인
source .env
if [ -z "$POSTGRES_URL" ]; then
    echo "❌ POSTGRES_URL이 설정되지 않았습니다!"
    exit 1
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  OPENAI_API_KEY가 설정되지 않았습니다."
    echo "   LLM 응답 생성 기능이 제한될 수 있습니다."
    echo ""
fi

echo "📋 주요 기능:"
echo "   - 하이브리드 검색 (벡터 + 온톨로지)"
echo "   - 전체 보험사 비교 (8개 보험사)"
echo "   - 상품/담보 정보 조회"
echo "   - 자유 질문 (RAG 기반)"
echo ""

echo "🔗 API 엔드포인트:"
echo "   - POST /api/hybrid-search: 하이브리드 검색"
echo "   - GET  /api/companies: 보험사 목록"
echo "   - GET  /api/coverages: 전체 담보 목록"
echo ""

echo "✅ 백엔드 API 서버를 시작합니다..."
echo "   URL: http://localhost:8000"
echo "   Docs: http://localhost:8000/docs"
echo ""

# FastAPI 서버 시작
uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
