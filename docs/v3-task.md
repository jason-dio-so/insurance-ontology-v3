# Insurance Ontology v3 - 신규 구축 가이드

**작성일**: 2025-12-13
**목적**: 완전히 새로운 환경에서 시스템을 처음부터 구축할 때의 작업 계획
**대상**: 신규 개발자, 새 환경 구축, 시스템 재구축

---

## 개요

이 문서는 Insurance Ontology 시스템을 **처음부터 완전히 새롭게 구축**할 때 필요한 모든 단계를 정리합니다.

### 기존 task.md와의 차이점

| 항목 | task.md (리팩토링) | v3-task.md (신규 구축) |
|------|-------------------|----------------------|
| 목적 | 기존 시스템 개선/정리 | 제로베이스 구축 |
| 데이터 | 기존 데이터 마이그레이션 | 원본 PDF부터 시작 |
| 스키마 | 기존 스키마 문서화 | 스키마 설계 → 생성 |
| 선행 조건 | 운영 중인 DB 존재 | 아무것도 없음 |

---

## 상태 범례

| 상태 | 설명 |
|------|------|
| ⬜ PENDING | 아직 시작하지 않음 |
| 🔄 IN_PROGRESS | 진행 중 |
| ✅ COMPLETED | 완료됨 |
| ❌ FAILED | 실패 |
| ⏸️ BLOCKED | 차단됨 |

---

## 전체 구축 흐름

```
Phase 0: 환경 준비
    │
    ▼
Phase 1: 인프라 구축
    ├── Docker 환경
    ├── PostgreSQL
    └── Neo4j
    │
    ▼
Phase 2: 스키마 생성
    ├── PostgreSQL 스키마
    ├── 시드 데이터
    └── Neo4j 제약조건
    │
    ▼
Phase 3: 문서 변환
    └── PDF → JSON (docling)
    │
    ▼
Phase 4: 데이터 수집 (Ingestion)
    ├── 문서 메타데이터
    ├── 문서 파싱
    └── document_clause 저장
    │
    ▼
Phase 5: 엔티티 추출
    ├── Coverage 추출
    ├── Benefit 추출
    ├── Disease Code 로드
    └── Clause-Coverage 매핑
    │
    ▼
Phase 6: 그래프 동기화
    └── PostgreSQL → Neo4j
    │
    ▼
Phase 7: 벡터 인덱스
    ├── 임베딩 생성
    └── HNSW 인덱스
    │
    ▼
Phase 8: 검색 시스템
    ├── Hybrid Retriever
    ├── Context Assembly
    └── NL Mapping
    │
    ▼
Phase 9: API 개발
    ├── REST API
    ├── CLI
    └── 비교 기능
    │
    ▼
Phase 10: 검증 및 배포
    ├── QA 테스트
    ├── 성능 벤치마크
    └── 문서화
    │
    ▼
Phase 11: CI/CD 통합
    └── GitHub Actions
    │
    ▼
Phase 12: 온톨로지 확장
    ├── RiskEvent, Condition, Exclusion
    └── Plan 노드
```

---

## Phase 0: 환경 준비 (Day 0)

**목표**: 개발 환경 및 필수 도구 설치
**소요 시간**: 1-2시간

| ID | Task | 상태 | 설명 |
|----|------|------|------|
| 0.1 | Python 3.11+ 설치 | ⬜ | `pyenv install 3.11` |
| 0.2 | Docker Desktop 설치 | ⬜ | PostgreSQL, Neo4j 컨테이너용 |
| 0.3 | 프로젝트 클론 | ⬜ | `git clone ...` |
| 0.4 | 가상환경 생성 | ⬜ | `python -m venv venv` |
| 0.5 | 의존성 설치 | ⬜ | `pip install -r requirements.txt` |
| 0.6 | `.env` 파일 생성 | ⬜ | 환경변수 설정 |

### 0.6 `.env` 파일 템플릿

```bash
# PostgreSQL
POSTGRES_URL=postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=insurance_ontology
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Neo4j
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# OpenAI (임베딩용)
OPENAI_API_KEY=sk-xxx
EMBEDDING_BACKEND=openai
```

---

## Phase 1: 인프라 구축 (Day 1)

**목표**: Docker 기반 데이터베이스 환경 구축
**소요 시간**: 2-3시간

| ID | Task | 상태 | 선행 | 명령어/설명 |
|----|------|------|------|------------|
| 1.1 | docker-compose.yml 작성 | ⬜ | 0.2 | PostgreSQL + Neo4j 정의 |
| 1.2 | PostgreSQL 컨테이너 시작 | ⬜ | 1.1 | `docker-compose up -d postgres` |
| 1.3 | pgvector 확장 설치 | ⬜ | 1.2 | `CREATE EXTENSION vector;` |
| 1.4 | Neo4j 컨테이너 시작 | ⬜ | 1.1 | `docker-compose up -d neo4j` |
| 1.5 | 연결 테스트 | ⬜ | 1.2, 1.4 | psql, cypher-shell 접속 확인 |

### 1.1 docker-compose.yml 예시

```yaml
version: '3.8'
services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: insurance-postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: insurance_ontology
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  neo4j:
    image: neo4j:5.15-community
    container_name: insurance-neo4j
    environment:
      NEO4J_AUTH: neo4j/password
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data

volumes:
  postgres_data:
  neo4j_data:
```

### 검증 기준

- [ ] PostgreSQL 접속: `psql -h localhost -U postgres -d insurance_ontology`
- [ ] pgvector 확장: `SELECT * FROM pg_extension WHERE extname = 'vector';`
- [ ] Neo4j 접속: http://localhost:7474

---

## Phase 2: 스키마 생성 (Day 1-2)

**목표**: 데이터베이스 스키마 및 초기 데이터 생성
**소요 시간**: 3-4시간

| ID | Task | 상태 | 선행 | 파일/명령어 |
|----|------|------|------|------------|
| 2.1 | PostgreSQL 스키마 적용 | ⬜ |  - | `db_refactoring/postgres/001_initial_schema.sql` |
| 2.2 | 시드 데이터 적용 | ⬜ | 2.1 | `db_refactoring/postgres/002_seed_data.sql` |
| 2.3 | Alembic 초기화 | ⬜ | 2.2 | `alembic stamp head` |
| 2.4 | Neo4j 스키마 적용 생성 | ⬜ | 2.3 | `001_graph_schema.cypher`|
| 2.5 | 초기화 스크립트  | ⬜| 2.4 |  | `init_neo4j.sh` | 
| 2.6 | 스키마 검증 | ⬜ | 2.1, 2.5 | 테이블/노드 수 확인 |

### 2.1-2.3 스키마 적용 (자동화 스크립트 사용)

```bash
# 방법 1: 자동화 스크립트 (권장)
./db_refactoring/scripts/init_db.sh

# 방법 2: 수동 실행
psql $POSTGRES_URL -f db_refactoring/postgres/001_initial_schema.sql
psql $POSTGRES_URL -f db_refactoring/postgres/002_seed_data.sql
cd db_refactoring && alembic stamp head
```

### 2.4-2.5 Neo4j 초기화

```bash
# Neo4j 스키마 적용
./db_refactoring/scripts/init_neo4j.sh

# 또는 수동 실행
cypher-shell -u neo4j -p $NEO4J_PASSWORD -f db_refactoring/neo4j/001_graph_schema.cypher
```

### 2.6 스키마 검증

```bash
# PostgreSQL 스키마 검증
python db_refactoring/scripts/verify_schema.py

# 기대 결과: 19개 테이블, pgvector 확장 설치됨
```

### 사용 가능한 스크립트

| 스크립트 | 설명 | 사용법 |
|----------|------|--------|
| `init_db.sh` | PostgreSQL 초기화 | `./init_db.sh [--drop-existing]` |
| `init_neo4j.sh` | Neo4j 초기화 | `./init_neo4j.sh` |
| `migrate.sh` | Alembic 래퍼 | `./migrate.sh upgrade/downgrade/history` |
| `verify_schema.py` | 스키마 검증 | `python verify_schema.py [-v]` |
| `verify_neo4j_sync.py` | PG↔Neo4j 동기화 검증 | `python verify_neo4j_sync.py` |

## Phase 3: 문서 변환 (Day 2-3)

**목표**: 원본 PDF 문서를 JSON 형식으로 변환
**소요 시간**: 4-6시간 (38개 문서 기준)

| ID | Task | 상태 | 선행 | 설명 |
|----|------|------|------|------|
| 3.1 | 원본 PDF 수집 | ⬜ | - | `data/raw/` 디렉토리에 배치 |
| 3.2 | docling 설치 | ⬜ | 0.5 | `pip install docling` |
| 3.3 | 문서 메타데이터 작성 | ⬜ | 3.1 | `data/documents_metadata.json` |
| 3.4 | PDF → JSON 변환 | ⬜ | 3.2, 3.3 | docling 실행 |
| 3.5 | 변환 결과 검증 | ⬜ | 3.4 | text.json, tables 확인 |

### 3.3 문서 메타데이터 형식

```json
[
  {
    "document_id": "samsung_myhealth_proposal_male",
    "company_code": "samsung",
    "company_name": "삼성",
    "product_code": "myhealth",
    "product_name": "마이헬스파트너",
    "doc_type": "proposal",
    "doc_subtype": "male",
    "version": "2024-01",
    "file_path": "data/raw/samsung/마이헬스파트너_가입설계서_남.pdf"
  }
]
```

### 3.4 변환 명령어

```bash
python scripts/convert_documents.py --input data/raw --output data/converted
```

### 검증 기준

- [ ] 38개 문서 디렉토리 생성
- [ ] 각 디렉토리에 `metadata.json`, `text.json` 존재
- [ ] 테이블 포함 문서에 `tables/` 디렉토리 존재

---

## Phase 4: 데이터 수집 - Ingestion (Day 3-4)

**목표**: 변환된 문서를 파싱하여 PostgreSQL에 저장
**소요 시간**: 2-3시간

| ID | Task | 상태 | 선행 | 명령어 |
|----|------|------|------|--------|
| 4.1 | 문서 수집 실행 | ⬜ | 3.5, 2.5 | `python -m ingestion.ingest_v3` |
| 4.2 | 파싱 품질 확인 | ⬜ | 4.1 | clause_type 분포 확인 |
| 4.3 | 오류 문서 재처리 | ⬜ | 4.2 | 필요시 개별 재실행 |

### 4.1 수집 명령어

```bash
# 전체 문서 수집
python -m ingestion.ingest_v3 data/documents_metadata.json

# 또는 배치 수집
python scripts/batch_ingest.py --all --batch-size 5
```

### 검증 기준

| 항목 | 기대값 |
|------|--------|
| document | 38개 |
| document_clause | ~80,000개 이상 |
| clause_type='table_row' | ~500개 이상 |
| clause_type='article' | 다수 |

---

## Phase 5: 엔티티 추출 (Day 4-5)

**목표**: 문서에서 담보, 급여, 질병코드 등 엔티티 추출
**소요 시간**: 3-4시간

| ID | Task | 상태 | 선행 | 명령어 |
|----|------|------|------|--------|
| 5.1 | Coverage 추출 | ⬜ | 4.1 | `python -m ingestion.coverage_pipeline` |
| 5.2 | Clause-Coverage 매핑 | ⬜ | 5.1 | `python -m ingestion.link_clauses --method all` |
| 5.3 | Benefit 추출 | ⬜ | 5.2 | `python -m ingestion.extract_benefits` |
| 5.4 | Disease Code 로드 | ⬜ | 2.2 | `python -m ingestion.load_disease_codes` |

### 실행 순서

```bash
# 1. Coverage 추출
python -m ingestion.coverage_pipeline --carrier all

# 2. Clause-Coverage 매핑 (3단계)
python -m ingestion.link_clauses --method exact
python -m ingestion.link_clauses --method fuzzy
python -m ingestion.link_clauses --method llm --limit 100

# 3. Benefit 추출
python -m ingestion.extract_benefits

# 4. Disease Code 로드
python -m ingestion.load_disease_codes
```

### 검증 기준

| 항목 | 기대값 |
|------|--------|
| coverage | 300개 이상 |
| benefit | 300개 이상 |
| clause_coverage | 500개 이상 |
| disease_code_set | 9개 |
| disease_code | 130개 이상 |

---

## Phase 6: 그래프 동기화 및 Neo4j 스키마 관리 (Day 5-6)

**목표**: Neo4j 그래프 스키마 정의 및 PostgreSQL 동기화
**소요 시간**: 3-4시간

| ID | Task | 상태 | 선행 | 설명 |
|----|------|------|------|------|
| 6.1 | 전체 동기화 실행 | ⬜ | 5.4 | `graph_loader --all` |
| 6.2 | 동기화 검증 실행 | ⬜ | 6.1 | `verify_neo4j_sync.py` |

### 6.1 전체 동기화 실행

```bash
# 전체 엔티티 동기화 (Company, Product, Coverage, Benefit, Document 등)
python -m ingestion.graph_loader --all

# 개별 엔티티 동기화 (필요시)
python -m ingestion.graph_loader --sync-companies
python -m ingestion.graph_loader --sync-products
python -m ingestion.graph_loader --sync-coverages
python -m ingestion.graph_loader --sync-benefits
python -m ingestion.graph_loader --sync-documents
python -m ingestion.graph_loader --sync-disease-codes
```

### 6.2 동기화 검증

```bash
# PostgreSQL ↔ Neo4j 엔티티 수 일치 검증
python db_refactoring/scripts/verify_neo4j_sync.py
```

### 검증 기준

| 엔티티 | PostgreSQL | Neo4j | 관계 |
|--------|-----------|-------|------|
| Company | 8 | 8 | HAS_PRODUCT |
| Product | 8 | 8 | HAS_VARIANT, OFFERS |
| Coverage | 363 | 363 | HAS_BENEFIT, PARENT_OF |
| Benefit | 357 | 357 | - |
| Document | 38 | 38 | HAS_DOCUMENT |
| DiseaseCode | 131 | 131 | CONTAINS |

## Phase 7: 벡터 인덱스 및 pgvector 관리 (Day 5-6)

**목표**: 문서 임베딩 생성, 벡터 검색 인덱스 구축 및 성능 관리
**소요 시간**: 4-6시간

| ID | Task | 상태 | 선행 | 설명 |
|----|------|------|------|------|
| 7.1 | OpenAI API 키 설정 | ⬜ | 0.6 | `.env`에 OPENAI_API_KEY 설정 |
| 7.2 | `003_pgvector_setup.sql` 생성 | ⬜ | 2.1 | pgvector 확장, HNSW 인덱스 정의 |
| 7.3 | 임베딩 생성 | ⬜ | 4.1, 7.1 | `python -m vector_index.build_index` |
| 7.4 | HNSW 인덱스 확인 | ⬜ | 7.3 | 인덱스 통계 조회 |
| 7.5 | HNSW 파라미터 가이드 문서화 | ⬜ | 7.4 | m, ef_construction, ef_search 튜닝 |
| 7.6 | `monitor_vector_search.py` 작성 | ⬜ | 7.4 | 벤치마크, 인덱스 통계 조회 |
| 7.7 | 임베딩 모델 변경 마이그레이션 템플릿 | ⬜ | 7.5 | 모델 교체 절차 문서화 |
| 7.8 | 벡터 검색 벤치마크 실행 | ⬜ | 7.6 | 성능 기준선 수립 |

### 7.2 pgvector 설정 파일 (`db_refactoring/postgres/003_pgvector_setup.sql`)

```sql
-- pgvector 확장 설치
CREATE EXTENSION IF NOT EXISTS vector;

-- 임베딩 테이블 (이미 001_initial_schema.sql에 포함)
-- clause_embedding: embedding vector(1536)

-- HNSW 인덱스 생성 (코사인 유사도)
CREATE INDEX IF NOT EXISTS clause_embedding_hnsw_idx
ON clause_embedding USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 검색 시 ef_search 설정
-- SET hnsw.ef_search = 40;
```

### 7.3 임베딩 생성 명령어

```bash
# OpenAI 임베딩 (text-embedding-3-small, 1536차원)
python -m vector_index.build_index

# 또는 로컬 임베딩 (fastembed)
EMBEDDING_BACKEND=fastembed python -m vector_index.build_index
```

### 7.5 HNSW 파라미터 가이드

| 파라미터 | 설명 | 권장값 (10만건) | 권장값 (100만건) |
|----------|------|-----------------|------------------|
| m | 그래프 연결 수 | 16 | 32 |
| ef_construction | 인덱스 빌드 정확도 | 64 | 128 |
| ef_search | 검색 정확도 | 40 | 100 |

### 7.6 monitor_vector_search.py

```python
# 벡터 검색 벤치마크 및 인덱스 통계 조회
# - 검색 지연시간 측정 (p50, p95, p99)
# - recall@k 측정
# - 인덱스 크기 및 빌드 시간 기록
```

### 7.7 임베딩 모델 변경 체크리스트

1. 새 임베딩 모델 테스트 (소규모 샘플)
2. 차원 수 확인 및 스키마 변경
3. 전체 임베딩 재생성
4. HNSW 인덱스 재빌드
5. 검색 품질 검증 (recall 비교)

### 검증 기준

| 항목 | 기대값 |
|------|--------|
| clause_embedding 레코드 | document_clause와 동일 (~134,844) |
| embedding 차원 | 1536 (OpenAI) 또는 384 (fastembed) |
| HNSW 인덱스 | 생성됨 |
| 검색 지연시간 (p95) | < 50ms |
| recall@10 | > 0.9 |

---

## Phase 8: 검색 시스템 (Day 6-7)

**목표**: 하이브리드 검색 시스템 구축 및 테스트
**소요 시간**: 2-3시간

| ID | Task | 상태 | 선행 | 설명 |
|----|------|------|------|------|
| 8.1 | NL Mapper 테스트 | ⬜ | 5.4 | 자연어 → 엔티티 매핑 |
| 8.2 | Vector Retriever 테스트 | ⬜ | 7.2 | 벡터 검색 동작 확인 |
| 8.3 | Hybrid Retriever 테스트 | ⬜ | 8.1, 8.2 | 통합 검색 테스트 |
| 8.4 | Context Assembly 테스트 | ⬜ | 8.3 | LLM 컨텍스트 생성 |

### 테스트 코드

```python
from retrieval.hybrid_retriever import HybridRetriever

retriever = HybridRetriever()
results = retriever.search("삼성 암진단비 3000만원", top_k=5)
print(f"Found {len(results)} results")
```

---

## Phase 9: API 개발 (Day 7-8)

**목표**: REST API 및 CLI 인터페이스 구축
**소요 시간**: 3-4시간

| ID | Task | 상태 | 선행 | 설명 |
|----|------|------|------|------|
| 9.1 | FastAPI 서버 테스트 | ⬜ | 8.4 | `uvicorn api.server:app` |
| 9.2 | /api/hybrid-search 테스트 | ⬜ | 9.1 | 검색 API 동작 확인 |
| 9.3 | /api/compare 테스트 | ⬜ | 9.1 | 비교 API 동작 확인 |
| 9.4 | CLI 테스트 | ⬜ | 8.4 | `python -m api.cli` |

### 9.1 서버 실행

```bash
uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
```

### API 테스트

```bash
# 헬스 체크
curl http://localhost:8000/health

# 검색 테스트
curl -X POST http://localhost:8000/api/hybrid-search \
  -H "Content-Type: application/json" \
  -d '{"query": "삼성 암진단비"}'
```

---

## Phase 10: 검증 및 배포 (Day 8-10)

**목표**: 시스템 품질 검증 및 배포 준비
**소요 시간**: 4-6시간

| ID | Task | 상태 | 선행 | 설명 |
|----|------|------|------|------|
| 10.1 | QA 테스트셋 준비 | ⬜ | - | `data/gold_qa_set_50.json` |
| 10.2 | QA 평가 실행 | ⬜ | 9.4, 10.1 | 정확도 측정 |
| 10.3 | 벡터 검색 벤치마크 | ⬜ | 7.3 | 지연시간, recall 측정 |
| 10.4 | 배포 가이드 작성 | ⬜ | 10.2 | PRODUCTION_DEPLOY.md |
| 10.5 | 최종 검증 | ⬜ | 10.4 | `scripts/verify_production_deploy.sh` |

### 10.2 QA 평가

```bash
python scripts/evaluate_qa.py \
  --qa-set data/gold_qa_set_50.json \
  --output evaluation/results/evaluation.json
```

### 검증 기준

| 항목 | 목표 |
|------|------|
| QA 정확도 | ≥ 86% |
| 벡터 검색 지연 | < 100ms (p99) |
| API 응답 시간 | < 2초 |

---

## Phase 11: CI/CD 통합 (Day 10-11)

**목표**: GitHub Actions를 통한 자동 스키마 검증 및 테스트
**소요 시간**: 3-4시간

| ID | Task | 상태 | 선행 | 설명 |
|----|------|------|------|------|
| 11.1 | `.github/workflows/schema-check.yml` 작성 | ⬜ | 10.5 | 스키마 검증 워크플로우 |
| 11.2 | `.github/workflows/test.yml` 작성 | ⬜ | 11.1 | 단위/통합 테스트 워크플로우 |
| 11.3 | PR 테스트 (자동 검증 확인) | ⬜ | 11.2 | 워크플로우 동작 확인 |
| 11.4 | 마이그레이션 가이드 문서 작성 | ⬜ | 11.3 | 개발자용 가이드 |

### 11.1 GitHub Actions 워크플로우

```yaml
# .github/workflows/schema-check.yml
name: Schema Check
on:
  pull_request:
    paths:
      - 'db_refactoring/**'
      - 'ingestion/**'
      - 'alembic/**'
jobs:
  schema-check:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432
    steps:
      - uses: actions/checkout@v4
      - name: Apply schema
        run: psql $POSTGRES_URL -f db_refactoring/postgres/001_initial_schema.sql
      - name: Run Alembic check
        run: cd db_refactoring && alembic check
```

### 검증 기준

- [ ] db_refactoring/, ingestion/ 변경 시 자동 실행
- [ ] 스키마 적용 성공/실패 케이스 모두 검증
- [ ] PR 머지 전 필수 통과 설정

---

## Phase 12: 온톨로지 확장 (Day 11-13)

**목표**: ontology_concept.md 기반 Neo4j/PostgreSQL 스키마 확장
**소요 시간**: 6-8시간

| ID | Task | 상태 | 선행 | 설명 |
|----|------|------|------|------|
| 12.1 | `risk_event` 테이블 (Alembic) | ⬜ | 6.2 | event_type, severity_level, icd_pattern |
| 12.2 | `condition` 테이블 | ⬜ | - | 001_initial_schema.sql에 포함 |
| 12.3 | `exclusion` 테이블 | ⬜ | - | 001_initial_schema.sql에 포함 |
| 12.4 | `plan`, `plan_coverage` 테이블 (Alembic) | ⬜ | 12.1 | 가입설계 정보 저장 |
| 12.5 | Neo4j 노드 추가 | ⬜ | 12.4 | RiskEvent, Condition, Exclusion, Plan |
| 12.6 | graph_loader.py 확장 | ⬜ | 12.5 | sync 메서드 추가 |

### 12.1, 12.4 Alembic 마이그레이션 적용

```bash
# 마이그레이션 이력 확인
./db_refactoring/scripts/migrate.sh history

# 마이그레이션 적용 (온톨로지 확장 테이블)
./db_refactoring/scripts/migrate.sh upgrade

# 마이그레이션 파일 목록:
# - dafe7c48833f_initial_schema_baseline.py (베이스라인)
# - b3192d16d07b_add_ontology_extension_tables.py (risk_event, benefit_risk_event)
# - e70cdd9c14e8_add_plan_tables.py (plan, plan_coverage)
```

### 12.5-12.6 Neo4j 스키마 및 동기화

```bash
# Neo4j 스키마 적용 (001_graph_schema.cypher에 포함됨)
# - RiskEvent, Condition, Exclusion, Plan 노드 제약조건/인덱스

# 온톨로지 확장 엔티티 동기화
python -m ingestion.graph_loader --sync-risk-events
python -m ingestion.graph_loader --sync-conditions
python -m ingestion.graph_loader --sync-exclusions
python -m ingestion.graph_loader --sync-plans
```

### 노드 및 관계 구조

```
Benefit --[TRIGGERS]--> RiskEvent
Benefit --[HAS_CONDITION]--> Condition
Coverage --[HAS_EXCLUSION]--> Exclusion
Plan --[FOR_PRODUCT]--> Product
Plan --[HAS_VARIANT]--> ProductVariant
Plan --[INCLUDES {sum_insured, premium}]--> Coverage
Plan --[FROM_DOCUMENT]--> Document
```

### 검증 기준

| 항목 | 기대값 |
|------|--------|
| risk_event 테이블 | 생성됨 (Alembic) |
| plan, plan_coverage 테이블 | 생성됨 (Alembic) |
| condition, exclusion 테이블 | 생성됨 (초기 스키마) |
| Neo4j 노드 타입 | 14개 (기존 8 + 신규 6) |
| graph_loader CLI | --sync-risk-events, --sync-conditions, --sync-exclusions, --sync-plans |

---

## 전체 일정 요약

| Phase | 작업 | 소요 시간 | 누적 일수 |
|-------|------|----------|----------|
| Phase 0 | 환경 준비 | 2시간 | Day 0 |
| Phase 1 | 인프라 구축 | 3시간 | Day 1 |
| Phase 2 | 스키마 생성 | 4시간 | Day 1-2 |
| Phase 3 | 문서 변환 | 6시간 | Day 2-3 |
| Phase 4 | 데이터 수집 | 3시간 | Day 3-4 |
| Phase 5 | 엔티티 추출 | 4시간 | Day 4-5 |
| Phase 6 | 그래프 동기화 | 4시간 | Day 5-6 |
| Phase 7 | 벡터 인덱스 | 6시간 | Day 5-6 |
| Phase 8 | 검색 시스템 | 3시간 | Day 6-7 |
| Phase 9 | API 개발 | 4시간 | Day 7-8 |
| Phase 10 | 검증 및 배포 | 6시간 | Day 8-10 |
| Phase 11 | CI/CD 통합 | 4시간 | Day 10-11 |
| Phase 12 | 온톨로지 확장 | 8시간 | Day 11-13 |
| **총계** | | **~57시간** | **~13일** |

---

## 트러블슈팅

### 자주 발생하는 문제

| 문제 | 원인 | 해결 방법 |
|------|------|----------|
| `POSTGRES_URL not set` | .env 미설정 | `.env` 파일 생성 및 환경변수 확인 |
| `connection refused` | Docker 미실행 | `docker-compose up -d` |
| `extension vector not found` | pgvector 미설치 | pgvector 이미지 사용 확인 |
| 임베딩 생성 느림 | API 레이트 리밋 | 배치 크기 조정, 대기 시간 추가 |
| Neo4j 연결 실패 | 인증 오류 | NEO4J_PASSWORD 확인 |

---

## 참고 문서

- [database_refactoring.md](./database_refactoring.md) - 스키마 상세 설명
- [task_upgrade.md](./task_upgrade.md) - 기존 시스템 전환 가이드
- [PRODUCTION_DEPLOY.md](./PRODUCTION_DEPLOY.md) - 배포 체크리스트
- [db_refactoring/docs/](../db_refactoring/docs/) - 설계 문서

---

**문서 버전**: 1.1
**최종 수정**: 2025-12-13
**변경 이력**:
- v1.0 (2025-12-13): 초기 작성
- v1.1 (2025-12-13): task.md 작업 결과 반영 - 스크립트 사용법, 검증 기준, Alembic 마이그레이션 정보 추가
