#!/bin/bash
# =============================================================================
# Neo4j 초기화 스크립트
# =============================================================================
# 용도: Neo4j 스키마 적용 및 PostgreSQL 데이터 동기화
# 실행: ./db_refactoring/scripts/init_neo4j.sh
# =============================================================================

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 프로젝트 루트 경로
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# .env 파일 로드
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
    echo -e "${GREEN}✓ .env 파일 로드 완료${NC}"
else
    echo -e "${RED}✗ .env 파일을 찾을 수 없습니다${NC}"
    exit 1
fi

# 환경 변수 확인
if [ -z "$NEO4J_URI" ] || [ -z "$NEO4J_USER" ] || [ -z "$NEO4J_PASSWORD" ]; then
    echo -e "${RED}✗ NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD 환경 변수가 필요합니다${NC}"
    exit 1
fi

echo ""
echo "========================================"
echo "Neo4j 초기화 스크립트"
echo "========================================"
echo "NEO4J_URI: $NEO4J_URI"
echo ""

# 1. Neo4j 연결 테스트
echo -e "${YELLOW}[1/3] Neo4j 연결 테스트...${NC}"
python3 -c "
from neo4j import GraphDatabase
import os

uri = os.getenv('NEO4J_URI')
user = os.getenv('NEO4J_USER')
password = os.getenv('NEO4J_PASSWORD')

driver = GraphDatabase.driver(uri, auth=(user, password))
with driver.session() as session:
    result = session.run('RETURN 1 as test')
    print('  Neo4j 연결 성공')
driver.close()
" || {
    echo -e "${RED}✗ Neo4j 연결 실패${NC}"
    exit 1
}
echo -e "${GREEN}✓ Neo4j 연결 확인${NC}"

# 2. 스키마 적용 (Cypher 파일 실행)
echo ""
echo -e "${YELLOW}[2/3] Neo4j 스키마 적용...${NC}"
SCHEMA_FILE="$PROJECT_ROOT/db_refactoring/neo4j/001_graph_schema.cypher"

if [ ! -f "$SCHEMA_FILE" ]; then
    echo -e "${RED}✗ 스키마 파일을 찾을 수 없습니다: $SCHEMA_FILE${NC}"
    exit 1
fi

# Python으로 Cypher 파일 실행 (cypher-shell 대신)
python3 << EOF
from neo4j import GraphDatabase
import os
import re

uri = os.getenv('NEO4J_URI')
user = os.getenv('NEO4J_USER')
password = os.getenv('NEO4J_PASSWORD')

driver = GraphDatabase.driver(uri, auth=(user, password))

# 스키마 파일 읽기
with open('$SCHEMA_FILE', 'r') as f:
    content = f.read()

# 주석 제거 및 명령어 파싱
statements = []
for line in content.split('\n'):
    line = line.strip()
    # 주석 무시
    if line.startswith('//') or not line:
        continue
    # CREATE/SHOW 문만 실행
    if line.startswith('CREATE ') or line.startswith('SHOW '):
        statements.append(line)

# 각 명령어 실행
with driver.session() as session:
    success_count = 0
    for stmt in statements:
        try:
            session.run(stmt)
            success_count += 1
        except Exception as e:
            # 이미 존재하는 제약/인덱스 무시
            if 'already exists' in str(e).lower():
                success_count += 1
            else:
                print(f'  경고: {stmt[:50]}... -> {e}')

    print(f'  {success_count}개 스키마 명령 실행 완료')

driver.close()
EOF

echo -e "${GREEN}✓ Neo4j 스키마 적용 완료${NC}"

# 3. PostgreSQL → Neo4j 동기화
echo ""
echo -e "${YELLOW}[3/3] PostgreSQL → Neo4j 데이터 동기화...${NC}"
cd "$PROJECT_ROOT"
python -m ingestion.graph_loader --all

echo ""
echo "========================================"
echo -e "${GREEN}✓ Neo4j 초기화 완료${NC}"
echo "========================================"

# 최종 통계
echo ""
echo "Neo4j 노드/관계 통계:"
python3 << EOF
from neo4j import GraphDatabase
import os

uri = os.getenv('NEO4J_URI')
user = os.getenv('NEO4J_USER')
password = os.getenv('NEO4J_PASSWORD')

driver = GraphDatabase.driver(uri, auth=(user, password))

with driver.session() as session:
    # 노드 수
    result = session.run("MATCH (n) RETURN count(n) as count")
    print(f"  총 노드 수: {result.single()['count']}")

    # 관계 수
    result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
    print(f"  총 관계 수: {result.single()['count']}")

    # 제약조건 수
    result = session.run("SHOW CONSTRAINTS")
    constraints = list(result)
    print(f"  제약조건 수: {len(constraints)}")

    # 인덱스 수
    result = session.run("SHOW INDEXES")
    indexes = list(result)
    print(f"  인덱스 수: {len(indexes)}")

driver.close()
EOF
