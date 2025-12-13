# 데이터베이스 현황 분석 리포트

**작성일**: 2025-12-13
**DB 생성일**: 2025-12-09
**마지막 마이그레이션**: 2025-12-11

---

## 1. 시스템 개요

이 시스템은 한국 보험 상품 문서를 처리하기 위한 **Hybrid RAG 시스템**으로, 두 가지 데이터베이스를 사용합니다:
- **PostgreSQL**: 주 데이터 저장소 (관계형 + 벡터 인덱스)
- **Neo4j**: 그래프 쿼리 보조 (PostgreSQL에서 동기화)

---

## 2. 데이터베이스 연결 정보

`.env` 파일에서 설정:

```bash
# PostgreSQL
POSTGRES_URL=postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme123
```

### 연결 방법

**PostgreSQL (Python)**:
```python
from dotenv import load_dotenv
import psycopg2
import os

load_dotenv()
conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
```

**Neo4j (Python)**:
```python
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()
driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
)
```

---

## 3. 개념 설계 → 구현 단계

### 3.1 설계 단계별 흐름

```
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 0: 개념 설계                                                   │
│ └─ docs/design/DESIGN.md (통합 설계 문서)                            │
│    - E-R 다이어그램 정의                                             │
│    - 도메인 모델 설계: Company → Product → Coverage → Benefit         │
│    - 문서 도메인 설계: Document → DocumentClause → ClauseEmbedding   │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 1: 물리적 스키마 구현                                          │
│ └─ 테이블은 Python 코드에서 동적 생성 (ON CONFLICT 사용)              │
│    - ingestion/ingest_v3.py: company, product, document, clause     │
│    - ingestion/coverage_pipeline.py: coverage                        │
│    - ingestion/extract_benefits.py: benefit                          │
│    - vector_index/build_index.py: clause_embedding                   │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 2-3: 스키마 진화 (마이그레이션)                                 │
│ └─ db/migrations/20251211_add_parent_coverage.sql                    │
│    - coverage.parent_coverage_id 컬럼 추가                           │
│    - 6개 부모 담보 생성 (일반암, 뇌혈관질환 등)                        │
│    - 52개 자식 담보 매핑                                             │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 DB 생성 시점과 방법

| 항목 | 생성 시점 | 생성 방법 |
|------|----------|----------|
| **테이블 스키마** | 최초 실행 시 | Python 코드의 `CREATE TABLE IF NOT EXISTS` 또는 `ON CONFLICT` |
| **기초 데이터** | Phase 1 | `python -m ingestion.ingest_v3` |
| **Coverage/Benefit** | Phase 2 | `python -m ingestion.coverage_pipeline`, `extract_benefits.py` |
| **벡터 인덱스** | Phase 4 | `python -m vector_index.build_index` |
| **Neo4j 동기화** | Phase 3 | `python -m ingestion.graph_loader --all` |

---

## 4. DB 생성 타임라인

| 일자 | 작업 |
|------|------|
| **2025-12-09** | 전체 DB 초기 생성 |
| **2025-12-11** | coverage 계층 구조 마이그레이션 추가 |

### 상세 시간순

```
2025-12-09 13:37 ~ 13:47  테이블 스키마 생성 (company, coverage_group 등)
2025-12-09 13:38 ~ 13:47  company 8개 적재
2025-12-09 15:28 ~ 15:56  document 38개 적재
2025-12-09                document_clause 134,844건 적재
2025-12-09                clause_embedding 134,644건 생성
2025-12-09                coverage, clause_coverage 초기 적재

2025-12-11                coverage 마이그레이션 (parent_coverage_id 추가)
                          → 6개 부모 담보 생성, 52개 자식 매핑
```

---

## 5. PostgreSQL 상세 분석

### 5.1 테이블 구조 및 현재 데이터

| 테이블 | 행 수 | 컬럼 수 | 설명 |
|--------|-------|--------|------|
| **document_clause** | 134,844 | 14 | 문서 조항 (핵심 데이터) |
| **clause_embedding** | 134,644 | 6 | 벡터 임베딩 (1536차원) |
| **clause_coverage** | 4,903 | 6 | 조항↔담보 매핑 |
| **coverage** | 363 | 11 | 담보 정보 |
| **benefit** | 357 | 10 | 보장 혜택 |
| **disease_code** | 131 | 7 | 질병 코드 |
| **document** | 38 | 13 | 문서 메타데이터 |
| **coverage_category** | 9 | 8 | 담보 카테고리 |
| **disease_code_set** | 9 | 6 | 질병코드 세트 |
| **company** | 8 | 6 | 보험사 |
| **product** | 8 | 9 | 상품 |
| **product_variant** | 4 | 11 | 상품 변형 (성별/연령) |
| **coverage_group** | 0 | 13 | 담보 그룹 (미사용) |
| **condition** | 0 | 10 | 조건 (미사용) |
| **exclusion** | 0 | 8 | 면책사항 (미사용) |

### 5.2 핵심 테이블 스키마

#### company (보험사)
```sql
CREATE TABLE company (
    id SERIAL PRIMARY KEY,
    company_code VARCHAR(20) UNIQUE NOT NULL,  -- 'samsung', 'db', 'lotte'...
    company_name VARCHAR(100) NOT NULL,        -- '삼성', 'DB', '롯데'...
    business_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**현재 데이터**:
| company_code | company_name |
|--------------|--------------|
| lotte | 롯데 |
| hanwha | 한화 |
| kb | KB |
| heungkuk | 흥국 |
| meritz | 메리츠 |
| hyundai | 현대 |
| samsung | 삼성 |
| db | DB |

#### document_clause (문서 조항 - 핵심)
```sql
CREATE TABLE document_clause (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES document(id),
    clause_number VARCHAR(50),          -- '제15조'
    clause_title VARCHAR(500),          -- '보험금의 지급사유'
    clause_text TEXT NOT NULL,          -- 전문
    clause_type VARCHAR(50),            -- 'article', 'text_block', 'table_row'
    structured_data JSONB,              -- 구조화된 데이터 (table_row용)
    page_number INTEGER,
    hierarchy_level INTEGER DEFAULT 0,
    ...
);
-- 인덱스: GIN(structured_data), clause_type, document_id
```

#### clause_embedding (벡터 인덱스)
```sql
CREATE TABLE clause_embedding (
    id SERIAL PRIMARY KEY,
    clause_id INTEGER UNIQUE NOT NULL REFERENCES document_clause(id),
    embedding vector(1536),             -- OpenAI text-embedding-3-small
    model_name VARCHAR(100),
    metadata JSONB,                     -- {clause_type, doc_type, coverage_ids}
    ...
);
-- HNSW 인덱스: idx_clause_embedding_hnsw (vector_cosine_ops)
```

#### coverage (담보)
```sql
CREATE TABLE coverage (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES product(id),
    coverage_name VARCHAR(200) NOT NULL,    -- '암진단비(유사암 제외)'
    coverage_category VARCHAR(100),         -- 'diagnosis', 'surgery'
    parent_coverage_id INTEGER REFERENCES coverage(id),  -- 계층 구조
    ...
);
```

### 5.3 조항 타입 분포

```
clause_type   | count   | 비율
--------------+---------+-------
article       | 129,667 | 96.2%  ← 약관 조항 (TextParser)
text_block    |   4,286 |  3.2%  ← 혼합문서 텍스트 (HybridParser)
table_row     |     891 |  0.7%  ← 구조화 테이블 (TableParser) ⭐ structured_data
```

### 5.4 조항-담보 매핑 방법

```
extraction_method       | count | 비율
------------------------+-------+------
parent_coverage_linking | 3,889 | 79.3%  ← 부모 담보 계층 자동 매핑
exact_match             |   829 | 16.9%  ← structured_data 정확 매칭
fuzzy_match             |   185 |  3.8%  ← 문자열 유사도 매칭
```

---

## 6. Neo4j 그래프 구조

### 6.1 노드 및 관계 (PostgreSQL → Neo4j 동기화)

```
┌─────────────────────────────────────────────────────────┐
│ Neo4j Graph Model (ingestion/graph_loader.py)           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  (Company)──[:HAS_PRODUCT]──>(Product)                  │
│       │                          │                      │
│       │                    [:HAS_VARIANT]               │
│       │                          ↓                      │
│  [:HAS_DOCUMENT]           (ProductVariant)             │
│       ↓                          │                      │
│  (Document)                 [:OFFERS]                   │
│                                  ↓                      │
│                             (Coverage)                  │
│                                  │                      │
│                            [:HAS_BENEFIT]               │
│                                  ↓                      │
│                             (Benefit)                   │
│                                                         │
│  (DiseaseCodeSet)──[:CONTAINS]──>(DiseaseCode)         │
│                                                         │
└─────────────────────────────────────────────────────────┘

설계 통계:
- Total Nodes: 640
- Total Relationships: 623
```

### 6.2 동기화 명령어

```bash
python -m ingestion.graph_loader --all

# 선택적 동기화
python -m ingestion.graph_loader --sync-products    # Company, Product, ProductVariant
python -m ingestion.graph_loader --sync-coverage    # Coverage
python -m ingestion.graph_loader --sync-benefits    # Benefit
python -m ingestion.graph_loader --sync-documents   # Document
python -m ingestion.graph_loader --sync-disease-codes  # DiseaseCodeSet, DiseaseCode
```

---

## 7. 데이터 흐름 다이어그램

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        데이터 파이프라인                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  38 PDFs (8 보험사)                                                       │
│       ↓                                                                  │
│  [scripts/convert_documents.py]  PDF → JSON (text + tables)              │
│       ↓                                                                  │
│  data/converted/{carrier}/{document_id}/text.json                        │
│       ↓                                                                  │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Phase 1: ingestion/ingest_v3.py                                   │   │
│  │  - TextParser (약관 → article)                                    │   │
│  │  - HybridParser (사업방법서/요약서 → text_block)                  │   │
│  │  - TableParser (가입설계서 → table_row + structured_data)         │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│       ↓                                                                  │
│  PostgreSQL: company(8), product(8), document(38), document_clause(134K) │
│       ↓                                                                  │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Phase 2: Entity Extraction                                        │   │
│  │  - coverage_pipeline.py → coverage(363)                           │   │
│  │  - extract_benefits.py → benefit(357)                             │   │
│  │  - link_clauses.py → clause_coverage(4,903)                       │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│       ↓                                                                  │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Phase 3: graph_loader.py → Neo4j (640 nodes, 623 rels)            │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│       ↓                                                                  │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Phase 4: build_index.py → clause_embedding(134K, 1536d)           │   │
│  │  - Model: OpenAI text-embedding-3-small                           │   │
│  │  - Index: HNSW (vector_cosine_ops)                                │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│       ↓                                                                  │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Phase 5: Hybrid RAG (retrieval/hybrid_retriever.py)               │   │
│  │  - 5-tier fallback vector search                                  │   │
│  │  - Context assembly + LLM (GPT-4o-mini)                           │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 8. 스키마 관리 방식의 문제점

현재 시스템은 **명시적 스키마 파일 없이 코드 기반으로 DB를 관리**하고 있어 다음 문제가 발생할 수 있습니다:

### 8.1 스키마 불일치 (Schema Drift)
```python
# 개발자 A가 컬럼 추가
cur.execute("INSERT INTO coverage (..., new_column) VALUES ...")

# 개발자 B의 로컬 DB에는 new_column이 없음 → 에러
```
- 팀원마다 DB 상태가 달라질 수 있음
- 프로덕션 vs 개발 환경 불일치

### 8.2 마이그레이션 추적 불가
- 시간순으로 어떤 변경이 있었는지 알 수 없음
- 언제 parent_coverage_id가 추가됐는지?
- 어떤 인덱스가 있어야 하는지?

### 8.3 롤백 어려움
- 명시적 마이그레이션 파일이 없으면 이전 버전으로 되돌리기 어려움
- 데이터 손실 위험

### 8.4 초기 테이블 생성 의존성
```python
# ON CONFLICT는 테이블이 이미 존재해야 동작
# 누군가 먼저 CREATE TABLE을 실행해야 함
cur.execute("""
    INSERT INTO company ... ON CONFLICT (company_code) DO UPDATE ...
""")
# 테이블이 없으면 → ERROR: relation "company" does not exist
```

### 8.5 제약조건/인덱스 누락
- 코드에서 암묵적으로 생성하면 FK, UNIQUE, INDEX가 빠질 수 있음
- 성능 저하 및 데이터 무결성 문제

### 8.6 권장 해결책

```bash
# 1. 명시적 스키마 파일 생성
db/postgres/
  ├── 001_initial_schema.sql      # 초기 테이블
  ├── 002_add_coverage.sql        # coverage 테이블
  └── 003_add_parent_coverage.sql # 마이그레이션

# 2. 마이그레이션 도구 사용
alembic (Python), Flyway, Liquibase 등
```

---

## 9. 요약

| 항목 | 값 |
|------|-----|
| **주 데이터베이스** | PostgreSQL 15 + pgvector |
| **그래프 DB** | Neo4j (보조, PostgreSQL에서 동기화) |
| **총 테이블** | 15개 |
| **핵심 데이터** | document_clause (134,844건) |
| **벡터 임베딩** | 134,644건 (1536차원, HNSW) |
| **스키마 관리** | Python 코드 내 암묵적 생성 + 마이그레이션 SQL |
| **DB 생성일** | 2025-12-09 |
| **마지막 마이그레이션** | 2025-12-11 (parent_coverage_id 추가) |
| **성능** | 86% QA 정확도 (Phase 5 완료) |

---

## 10. 관련 파일

| 파일 | 설명 |
|------|------|
| `docs/design/DESIGN.md` | 통합 설계 문서 |
| `db/migrations/20251211_add_parent_coverage.sql` | Coverage 계층 마이그레이션 |
| `ingestion/ingest_v3.py` | 문서 적재 파이프라인 |
| `ingestion/graph_loader.py` | Neo4j 동기화 |
| `vector_index/build_index.py` | 벡터 인덱스 생성 |
| `api/server.py` | API 서버 (DB 연결) |
| `.env` | 데이터베이스 연결 정보 |
