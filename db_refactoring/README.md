# DB Refactoring 작업 디렉토리

**생성일**: 2025-12-13
**목적**: 운영 DB에 영향 없이 데이터베이스 리팩토링 작업 수행

---

## 중요: 격리 정책

### 핵심 원칙

1. **운영 DB 절대 접근 금지**
   - 운영 DB: `postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology`
   - 이 디렉토리의 모든 작업은 Docker 컨테이너 내 테스트 DB에서만 수행

2. **독립 Docker 환경 사용**
   - PostgreSQL: `localhost:15432` (테스트용)
   - Neo4j: `localhost:17474` (테스트용)
   - 운영 포트(5432, 7474)와 완전 분리

3. **스키마만 복제, 데이터 미복제**
   - 운영 DB에서 스키마(DDL)만 추출
   - 실제 데이터는 복제하지 않음
   - 테스트 데이터는 별도 생성

---

## 디렉토리 구조

```
db_refactoring/
├── README.md                    # 이 파일 (격리 정책 문서)
├── docker/
│   ├── docker-compose.yml       # 테스트 DB 환경
│   └── .env                     # Docker 환경변수
├── postgres/
│   ├── 001_initial_schema.sql   # 추출된 스키마
│   ├── 002_seed_data.sql        # 시드 데이터
│   └── 003_pgvector_setup.sql   # pgvector 설정
├── neo4j/
│   └── 001_graph_schema.cypher  # Neo4j 스키마
├── docs/
│   ├── ER_DIAGRAM.md
│   ├── DATA_DICTIONARY.md
│   ├── RELATIONSHIP_MAP.md
│   ├── DOMAIN_MODEL.md
│   ├── GRAPH_SCHEMA.md
│   ├── NODE_DICTIONARY.md
│   ├── RELATIONSHIP_DICTIONARY.md
│   ├── GRAPH_PATTERNS.md
│   └── ONTOLOGY_GAP_ANALYSIS.md
├── migrations/
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
├── scripts/
│   ├── init_db.sh
│   ├── verify_schema.py
│   ├── migrate.sh
│   └── generate_docs.py
└── test_results/
    └── (검증 결과 저장)
```

---

## 테스트 환경 접속 정보

| 서비스 | 운영 | 테스트 (Docker) |
|--------|------|-----------------|
| PostgreSQL Host | 127.0.0.1 | 127.0.0.1 |
| PostgreSQL Port | 5432 | **15432** |
| PostgreSQL DB | insurance_ontology | insurance_ontology_test |
| Neo4j HTTP | 7474 | **17474** |
| Neo4j Bolt | 7687 | **17687** |

**테스트 DB 연결 문자열**:
```
POSTGRES_TEST_URL=postgresql://postgres:postgres@127.0.0.1:15432/insurance_ontology_test
NEO4J_TEST_URI=bolt://127.0.0.1:17687
```

---

## 작업 절차

### 1. Docker 환경 시작
```bash
cd db_refactoring/docker
docker-compose up -d
```

### 2. 스키마 테스트
```bash
# 테스트 DB에 스키마 적용
psql "$POSTGRES_TEST_URL" -f ../postgres/001_initial_schema.sql
```

### 3. 검증
```bash
python ../scripts/verify_schema.py --test
```

### 4. 정리
```bash
docker-compose down -v  # 볼륨 포함 삭제
```

---

## 주의사항

- 모든 스크립트는 `--test` 또는 `TEST_MODE=1` 환경변수로 테스트 DB 사용
- 운영 DB 연결 문자열을 이 디렉토리 내 파일에 하드코딩 금지
- 검증 완료 후에만 메인 프로젝트에 파일 복사

---

## 진행 기록

| 날짜 | 작업 | 결과 |
|------|------|------|
| 2025-12-13 | 격리 디렉토리 생성 | 완료 |
| 2025-12-13 | Docker 환경 구성 | - |
| 2025-12-13 | Phase 1 스키마 추출 | - |

---

**이 문서는 항상 최신 상태로 유지되어야 합니다.**
