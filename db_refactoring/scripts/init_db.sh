#!/bin/bash
# =============================================================================
# PostgreSQL 초기화 스크립트
# =============================================================================
# 설명: 빈 PostgreSQL에 스키마, 시드 데이터 적용 및 Alembic 초기화
# 사용: ./init_db.sh [--drop-existing]
# =============================================================================

set -e  # 오류 시 즉시 종료

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 스크립트 디렉토리
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DB_REFACTORING_DIR="$PROJECT_ROOT/db_refactoring"

# .env 파일 로드
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
    echo -e "${GREEN}[OK]${NC} .env 파일 로드 완료"
else
    echo -e "${RED}[ERROR]${NC} .env 파일이 없습니다: $PROJECT_ROOT/.env"
    exit 1
fi

# DATABASE_URL 확인 (POSTGRES_URL fallback)
DATABASE_URL="${DATABASE_URL:-$POSTGRES_URL}"
if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}[ERROR]${NC} DATABASE_URL 또는 POSTGRES_URL 환경변수가 설정되지 않았습니다"
    exit 1
fi

echo "=========================================="
echo "PostgreSQL 초기화 스크립트"
echo "=========================================="
echo "DATABASE_URL: ${DATABASE_URL:0:60}..."
echo ""

# 옵션 파싱
DROP_EXISTING=false
for arg in "$@"; do
    case $arg in
        --drop-existing)
            DROP_EXISTING=true
            shift
            ;;
    esac
done

# 기존 테이블 삭제 (옵션)
if [ "$DROP_EXISTING" = true ]; then
    echo -e "${YELLOW}[WARN]${NC} 기존 테이블 삭제 중..."
    psql "$DATABASE_URL" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" 2>/dev/null || true
    echo -e "${GREEN}[OK]${NC} 기존 테이블 삭제 완료"
fi

# 1. pgvector 확장 설치
echo ""
echo -e "${YELLOW}[1/4]${NC} pgvector 확장 설치..."
psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || {
    echo -e "${RED}[ERROR]${NC} pgvector 확장 설치 실패. pgvector 이미지를 사용하고 있는지 확인하세요."
    exit 1
}
echo -e "${GREEN}[OK]${NC} pgvector 확장 설치 완료"

# 2. 스키마 적용
echo ""
echo -e "${YELLOW}[2/4]${NC} 스키마 적용 중..."
SCHEMA_FILE="$DB_REFACTORING_DIR/postgres/001_initial_schema.sql"
if [ -f "$SCHEMA_FILE" ]; then
    psql "$DATABASE_URL" -f "$SCHEMA_FILE" > /dev/null 2>&1 || {
        echo -e "${RED}[ERROR]${NC} 스키마 적용 실패"
        exit 1
    }
    echo -e "${GREEN}[OK]${NC} 스키마 적용 완료: $SCHEMA_FILE"
else
    echo -e "${RED}[ERROR]${NC} 스키마 파일 없음: $SCHEMA_FILE"
    exit 1
fi

# 3. 시드 데이터 적용
echo ""
echo -e "${YELLOW}[3/4]${NC} 시드 데이터 적용 중..."
SEED_FILE="$DB_REFACTORING_DIR/postgres/002_seed_data.sql"
if [ -f "$SEED_FILE" ]; then
    psql "$DATABASE_URL" -f "$SEED_FILE" > /dev/null 2>&1 || {
        echo -e "${RED}[ERROR]${NC} 시드 데이터 적용 실패"
        exit 1
    }
    echo -e "${GREEN}[OK]${NC} 시드 데이터 적용 완료: $SEED_FILE"
else
    echo -e "${YELLOW}[WARN]${NC} 시드 데이터 파일 없음 (건너뜀): $SEED_FILE"
fi

# 4. Alembic 스탬프
echo ""
echo -e "${YELLOW}[4/4]${NC} Alembic 버전 스탬프 중..."
cd "$DB_REFACTORING_DIR"
if [ -f "alembic.ini" ]; then
    python -m alembic stamp head > /dev/null 2>&1 || {
        echo -e "${RED}[ERROR]${NC} Alembic stamp 실패"
        exit 1
    }
    echo -e "${GREEN}[OK]${NC} Alembic stamp head 완료"
else
    echo -e "${YELLOW}[WARN]${NC} alembic.ini 없음 (건너뜀)"
fi

# 결과 요약
echo ""
echo "=========================================="
echo -e "${GREEN}초기화 완료!${NC}"
echo "=========================================="
echo ""

# 테이블 수 확인
TABLE_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" | xargs)
echo "생성된 테이블 수: $TABLE_COUNT"

# 시드 데이터 확인
echo ""
echo "시드 데이터 현황:"
psql "$DATABASE_URL" -t -c "SELECT 'company: ' || COUNT(*) FROM company;" 2>/dev/null | xargs || echo "company: 0"
psql "$DATABASE_URL" -t -c "SELECT 'coverage_category: ' || COUNT(*) FROM coverage_category;" 2>/dev/null | xargs || echo "coverage_category: 0"
psql "$DATABASE_URL" -t -c "SELECT 'disease_code_set: ' || COUNT(*) FROM disease_code_set;" 2>/dev/null | xargs || echo "disease_code_set: 0"

echo ""
echo "다음 단계: python -m ingestion.graph_loader --all (Neo4j 동기화)"
