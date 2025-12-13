#!/bin/bash
# =============================================================================
# Alembic 마이그레이션 래퍼 스크립트
# =============================================================================
# 설명: Alembic 마이그레이션 명령을 간편하게 실행
# 사용:
#   ./migrate.sh upgrade      # 최신 버전으로 업그레이드
#   ./migrate.sh downgrade    # 한 단계 다운그레이드
#   ./migrate.sh history      # 마이그레이션 이력 조회
#   ./migrate.sh current      # 현재 버전 확인
#   ./migrate.sh heads        # 최신 버전 확인
#   ./migrate.sh create <name> # 새 마이그레이션 생성
# =============================================================================

set -e  # 오류 시 즉시 종료

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 스크립트 디렉토리
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DB_REFACTORING_DIR="$PROJECT_ROOT/db_refactoring"

# .env 파일 로드
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
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
export DATABASE_URL

# 사용법 출력
usage() {
    echo "사용법: $0 <command> [options]"
    echo ""
    echo "명령어:"
    echo "  upgrade [revision]   - 지정 버전으로 업그레이드 (기본: head)"
    echo "  downgrade [revision] - 지정 버전으로 다운그레이드 (기본: -1)"
    echo "  history              - 마이그레이션 이력 조회"
    echo "  current              - 현재 버전 확인"
    echo "  heads                - 최신 버전 확인"
    echo "  create <name>        - 새 마이그레이션 생성"
    echo "  stamp <revision>     - 버전 스탬프 (마이그레이션 실행 없이)"
    echo "  check                - 스키마 변경 확인"
    echo ""
    echo "예시:"
    echo "  $0 upgrade           # 최신 버전으로 업그레이드"
    echo "  $0 upgrade abc123    # 특정 버전으로 업그레이드"
    echo "  $0 downgrade -1      # 한 단계 다운그레이드"
    echo "  $0 create add_user   # add_user 마이그레이션 생성"
    exit 1
}

# 명령어 확인
if [ $# -lt 1 ]; then
    usage
fi

COMMAND=$1
shift

# Alembic 디렉토리로 이동
cd "$DB_REFACTORING_DIR"

echo "=========================================="
echo -e "${BLUE}Alembic 마이그레이션${NC}"
echo "=========================================="
echo "작업 디렉토리: $DB_REFACTORING_DIR"
echo ""

case $COMMAND in
    upgrade)
        REVISION="${1:-head}"
        echo -e "${YELLOW}[INFO]${NC} 업그레이드: $REVISION"
        python -m alembic upgrade "$REVISION"
        echo -e "${GREEN}[OK]${NC} 업그레이드 완료"
        ;;

    downgrade)
        REVISION="${1:--1}"
        echo -e "${YELLOW}[INFO]${NC} 다운그레이드: $REVISION"
        read -p "정말 다운그레이드하시겠습니까? (y/N): " confirm
        if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
            python -m alembic downgrade "$REVISION"
            echo -e "${GREEN}[OK]${NC} 다운그레이드 완료"
        else
            echo -e "${YELLOW}[CANCEL]${NC} 취소됨"
        fi
        ;;

    history)
        echo -e "${YELLOW}[INFO]${NC} 마이그레이션 이력:"
        python -m alembic history --verbose
        ;;

    current)
        echo -e "${YELLOW}[INFO]${NC} 현재 버전:"
        python -m alembic current
        ;;

    heads)
        echo -e "${YELLOW}[INFO]${NC} 최신 버전:"
        python -m alembic heads
        ;;

    create)
        if [ -z "$1" ]; then
            echo -e "${RED}[ERROR]${NC} 마이그레이션 이름을 지정해주세요"
            echo "예시: $0 create add_user_table"
            exit 1
        fi
        NAME=$1
        echo -e "${YELLOW}[INFO]${NC} 새 마이그레이션 생성: $NAME"
        python -m alembic revision --autogenerate -m "$NAME"
        echo -e "${GREEN}[OK]${NC} 마이그레이션 생성 완료"
        echo ""
        echo "생성된 파일을 확인하고 수정하세요:"
        ls -la migrations/versions/*.py | tail -1
        ;;

    stamp)
        REVISION="${1:-head}"
        echo -e "${YELLOW}[INFO]${NC} 버전 스탬프: $REVISION"
        python -m alembic stamp "$REVISION"
        echo -e "${GREEN}[OK]${NC} 스탬프 완료"
        ;;

    check)
        echo -e "${YELLOW}[INFO]${NC} 스키마 변경 확인:"
        python -m alembic check || {
            echo -e "${YELLOW}[WARN]${NC} 스키마 변경이 감지되었습니다"
            exit 0
        }
        echo -e "${GREEN}[OK]${NC} 스키마가 최신 상태입니다"
        ;;

    *)
        echo -e "${RED}[ERROR]${NC} 알 수 없는 명령어: $COMMAND"
        usage
        ;;
esac

echo ""
echo "=========================================="
echo -e "${GREEN}완료${NC}"
echo "=========================================="
