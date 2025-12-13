# 데이터베이스 리팩토링 계획

**작성일**: 2025-12-13
**목표 완료일**: 2025-12-20
**상태**: 계획 수립 완료

---

## 1. 현재 문제점 요약

### 1.1 스키마 관리 부재

| 문제 | 영향 | 심각도 |
|------|------|--------|
| 명시적 스키마 파일 없음 | 초기 설치 시 테이블 생성 불가 | **높음** |
| 마이그레이션 추적 불가 | 스키마 변경 이력 파악 어려움 | **높음** |
| 롤백 불가능 | 문제 발생 시 복구 어려움 | **중간** |
| 환경별 스키마 불일치 | 개발/스테이징/프로덕션 차이 발생 | **높음** |

### 1.2 현재 상태

```
db/
├── migrations/
│   └── 20251211_add_parent_coverage.sql  # 유일한 마이그레이션 파일
└── postgres/                              # 비어있음 (스키마 파일 없음)
```

- **테이블 15개** 존재하지만 생성 스크립트 없음
- **인덱스 52개** 존재하지만 정의 파일 없음
- **FK 19개** 존재하지만 문서화 없음

### 1.3 pgvector 관련 문제

| 문제 | 영향 | 심각도 |
|------|------|--------|
| HNSW 인덱스 파라미터 문서화 없음 | 성능 튜닝 어려움 | **중간** |
| 임베딩 차원 변경 시 마이그레이션 없음 | 모델 변경 불가 | **높음** |
| 벡터 검색 성능 모니터링 없음 | 성능 저하 감지 어려움 | **중간** |

### 1.4 Neo4j 관련 문제

| 문제 | 영향 | 심각도 |
|------|------|--------|
| 그래프 스키마 정의 파일 없음 | 노드/관계 구조 불명확 | **높음** |
| PostgreSQL ↔ Neo4j 동기화 검증 없음 | 데이터 불일치 가능 | **높음** |
| 제약조건/인덱스 정의 없음 | 쿼리 성능 저하 | **중간** |
| 동기화 실패 시 복구 절차 없음 | 그래프 데이터 손실 | **중간** |

---

## 2. 목표

### 2.1 단기 목표 (1주)
- [ ] 현재 스키마를 SQL 파일로 추출
- [ ] 마이그레이션 버전 관리 체계 수립
- [ ] 스키마 검증 스크립트 작성
- [ ] **pgvector 인덱스 설정 문서화**
- [ ] **Neo4j 그래프 스키마 정의 (Cypher)**

### 2.2 중기 목표 (2주)
- [ ] Alembic 마이그레이션 도구 도입
- [ ] CI/CD 파이프라인에 스키마 검증 추가
- [ ] 개발 환경 초기화 자동화
- [ ] **pgvector HNSW 인덱스 튜닝 가이드 작성**
- [ ] **Neo4j 동기화 검증 스크립트 작성**

### 2.3 장기 목표 (1개월)
- [ ] 테스트 데이터베이스 자동 생성
- [ ] 스키마 변경 자동 감지 및 알림
- [ ] 데이터베이스 문서 자동 생성
- [ ] **벡터 임베딩 모델 변경 마이그레이션 절차 수립**
- [ ] **PostgreSQL ↔ Neo4j 실시간 동기화 검토**

---

## 3. 실행 계획

### Phase 1: 스키마 추출 및 문서화 (Day 1-2)

#### 3.1.1 현재 스키마 추출

```bash
# 1. 전체 스키마 덤프
pg_dump "$POSTGRES_URL" --schema-only --no-owner --no-privileges \
    > db/postgres/001_initial_schema.sql

# 2. 테이블별 분리 (선택사항)
pg_dump "$POSTGRES_URL" --schema-only --table=company > db/postgres/tables/company.sql
pg_dump "$POSTGRES_URL" --schema-only --table=product > db/postgres/tables/product.sql
# ... 각 테이블별
```

#### 3.1.2 디렉토리 구조 정립

```
db/
├── postgres/
│   ├── 001_initial_schema.sql        # 전체 초기 스키마
│   ├── 002_seed_data.sql             # 초기 시드 데이터 (coverage_category 등)
│   └── tables/                        # (선택) 테이블별 분리
│       ├── company.sql
│       ├── product.sql
│       └── ...
├── migrations/
│   ├── versions/                      # Alembic 마이그레이션
│   │   ├── 001_initial.py
│   │   └── 002_add_parent_coverage.py
│   ├── env.py
│   └── alembic.ini
└── scripts/
    ├── init_db.sh                     # DB 초기화 스크립트
    ├── migrate.sh                     # 마이그레이션 실행
    └── verify_schema.py               # 스키마 검증
```

#### 3.1.3 초기 스키마 파일 생성

**db/postgres/001_initial_schema.sql**:

```sql
-- ============================================================================
-- Insurance Ontology Database Schema
-- Version: 1.0.0
-- Created: 2025-12-09
-- ============================================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================================
-- CORE DOMAIN: Company & Product
-- ============================================================================

CREATE TABLE IF NOT EXISTS company (
    id SERIAL PRIMARY KEY,
    company_code VARCHAR(20) UNIQUE NOT NULL,
    company_name VARCHAR(100) NOT NULL,
    business_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES company(id),
    product_code VARCHAR(50) NOT NULL,
    product_name VARCHAR(200) NOT NULL,
    business_type VARCHAR(50),
    version VARCHAR(20),
    effective_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (company_id, product_code, version)
);

CREATE TABLE IF NOT EXISTS product_variant (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES product(id),
    variant_name VARCHAR(100),
    variant_code VARCHAR(50),
    target_gender VARCHAR(10),
    target_age_range VARCHAR(50),
    attributes JSONB,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (product_id, variant_code)
);

-- ============================================================================
-- COVERAGE DOMAIN
-- ============================================================================

CREATE TABLE IF NOT EXISTS coverage_category (
    id SERIAL PRIMARY KEY,
    category_code VARCHAR(50) UNIQUE NOT NULL,
    category_name_kr VARCHAR(100) NOT NULL,
    category_name_en VARCHAR(100),
    description TEXT,
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS coverage_group (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES company(id),
    category_id INTEGER REFERENCES coverage_category(id),
    group_code VARCHAR(50) NOT NULL,
    group_name VARCHAR(200) NOT NULL,
    description TEXT,
    version VARCHAR(20),
    is_active BOOLEAN DEFAULT true,
    display_order INTEGER DEFAULT 0,
    attributes JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (company_id, group_code, version)
);

CREATE TABLE IF NOT EXISTS coverage (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES product(id),
    group_id INTEGER REFERENCES coverage_group(id),
    coverage_code VARCHAR(200),
    coverage_name VARCHAR(200) NOT NULL,
    coverage_category VARCHAR(100),
    renewal_type VARCHAR(20),
    is_basic BOOLEAN DEFAULT false,
    parent_coverage_id INTEGER REFERENCES coverage(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (product_id, coverage_code)
);

CREATE TABLE IF NOT EXISTS benefit (
    id SERIAL PRIMARY KEY,
    coverage_id INTEGER NOT NULL REFERENCES coverage(id),
    benefit_name VARCHAR(200),
    benefit_type VARCHAR(50),
    benefit_amount NUMERIC(15,2),
    benefit_amount_text VARCHAR(100),
    benefit_unit VARCHAR(20),
    benefit_limit TEXT,
    conditions TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS condition (
    id SERIAL PRIMARY KEY,
    coverage_id INTEGER NOT NULL REFERENCES coverage(id),
    condition_type VARCHAR(50),
    condition_name VARCHAR(200),
    condition_text TEXT,
    min_value NUMERIC(15,2),
    max_value NUMERIC(15,2),
    unit VARCHAR(20),
    attributes JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exclusion (
    id SERIAL PRIMARY KEY,
    coverage_id INTEGER NOT NULL REFERENCES coverage(id),
    exclusion_type VARCHAR(50),
    exclusion_name VARCHAR(200),
    exclusion_text TEXT,
    attributes JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- DISEASE CODE DOMAIN
-- ============================================================================

CREATE TABLE IF NOT EXISTS disease_code_set (
    id SERIAL PRIMARY KEY,
    set_name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    version VARCHAR(20),
    source VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS disease_code (
    id SERIAL PRIMARY KEY,
    code_set_id INTEGER NOT NULL REFERENCES disease_code_set(id),
    code VARCHAR(20) NOT NULL,
    code_type VARCHAR(20),
    description_kr VARCHAR(500),
    description_en VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (code_set_id, code)
);

-- ============================================================================
-- DOCUMENT DOMAIN
-- ============================================================================

CREATE TABLE IF NOT EXISTS document (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(100) UNIQUE NOT NULL,
    company_id INTEGER REFERENCES company(id),
    product_id INTEGER REFERENCES product(id),
    variant_id INTEGER REFERENCES product_variant(id),
    doc_type VARCHAR(50),
    doc_subtype VARCHAR(50),
    version VARCHAR(50),
    file_path VARCHAR(500),
    total_pages INTEGER,
    attributes JSONB,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_clause (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    clause_number VARCHAR(50),
    clause_title VARCHAR(500),
    clause_text TEXT NOT NULL,
    clause_type VARCHAR(50),
    structured_data JSONB,
    section_type VARCHAR(100),
    page_number INTEGER,
    hierarchy_level INTEGER DEFAULT 0,
    parent_clause_id INTEGER REFERENCES document_clause(id),
    attributes JSONB,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- ============================================================================
-- MAPPING DOMAIN
-- ============================================================================

CREATE TABLE IF NOT EXISTS clause_coverage (
    id SERIAL PRIMARY KEY,
    clause_id INTEGER NOT NULL REFERENCES document_clause(id) ON DELETE CASCADE,
    coverage_id INTEGER NOT NULL REFERENCES coverage(id) ON DELETE CASCADE,
    relevance_score FLOAT DEFAULT 1.0,
    extraction_method VARCHAR(50),
    created_at TIMESTAMP DEFAULT now(),
    UNIQUE (clause_id, coverage_id)
);

-- ============================================================================
-- VECTOR INDEX DOMAIN
-- ============================================================================

CREATE TABLE IF NOT EXISTS clause_embedding (
    id SERIAL PRIMARY KEY,
    clause_id INTEGER UNIQUE NOT NULL REFERENCES document_clause(id) ON DELETE CASCADE,
    embedding vector(1536),
    model_name VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT now()
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Company
CREATE INDEX IF NOT EXISTS idx_company_code ON company(company_code);

-- Product
CREATE INDEX IF NOT EXISTS idx_product_code ON product(product_code);
CREATE INDEX IF NOT EXISTS idx_product_company ON product(company_id);

-- Product Variant
CREATE INDEX IF NOT EXISTS idx_variant_product ON product_variant(product_id);
CREATE INDEX IF NOT EXISTS idx_variant_gender ON product_variant(target_gender);
CREATE INDEX IF NOT EXISTS idx_variant_age_range ON product_variant(target_age_range);

-- Coverage
CREATE INDEX IF NOT EXISTS idx_coverage_product ON coverage(product_id);
CREATE INDEX IF NOT EXISTS idx_coverage_group ON coverage(group_id);
CREATE INDEX IF NOT EXISTS idx_coverage_name ON coverage(coverage_name);
CREATE INDEX IF NOT EXISTS idx_coverage_parent ON coverage(parent_coverage_id);

-- Document
CREATE INDEX IF NOT EXISTS idx_document_company ON document(company_id);
CREATE INDEX IF NOT EXISTS idx_document_product ON document(product_id);
CREATE INDEX IF NOT EXISTS idx_document_variant ON document(variant_id);
CREATE INDEX IF NOT EXISTS idx_document_type ON document(doc_type);

-- Document Clause
CREATE INDEX IF NOT EXISTS idx_clause_document ON document_clause(document_id);
CREATE INDEX IF NOT EXISTS idx_clause_type ON document_clause(clause_type);
CREATE INDEX IF NOT EXISTS idx_clause_section ON document_clause(section_type);
CREATE INDEX IF NOT EXISTS idx_clause_parent ON document_clause(parent_clause_id);
CREATE INDEX IF NOT EXISTS idx_structured_data_gin ON document_clause USING gin(structured_data) WHERE structured_data IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_structured_coverage_amount ON document_clause((structured_data->>'coverage_amount')) WHERE structured_data IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_structured_premium ON document_clause((structured_data->>'premium')) WHERE structured_data IS NOT NULL;

-- Clause Coverage
CREATE INDEX IF NOT EXISTS idx_clause_coverage_clause ON clause_coverage(clause_id);
CREATE INDEX IF NOT EXISTS idx_clause_coverage_coverage ON clause_coverage(coverage_id);

-- Clause Embedding
CREATE INDEX IF NOT EXISTS idx_clause_embedding_clause ON clause_embedding(clause_id);
CREATE INDEX IF NOT EXISTS idx_clause_embedding_metadata_gin ON clause_embedding USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_clause_embedding_hnsw ON clause_embedding USING hnsw(embedding vector_cosine_ops) WITH (m=16, ef_construction=64);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_company_updated_at BEFORE UPDATE ON company
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_product_updated_at BEFORE UPDATE ON product
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_coverage_updated_at BEFORE UPDATE ON coverage
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
```

---

### Phase 2: Alembic 마이그레이션 도입 (Day 3-4)

#### 3.2.1 Alembic 설치 및 초기화

```bash
# 1. 설치
pip install alembic

# 2. 초기화
cd db
alembic init migrations

# 3. alembic.ini 수정
# sqlalchemy.url = postgresql://postgres:postgres@localhost:5432/insurance_ontology
```

#### 3.2.2 환경 설정

**db/migrations/env.py**:

```python
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

load_dotenv()

config = context.config

# 환경변수에서 DB URL 가져오기
config.set_main_option('sqlalchemy.url', os.getenv('POSTGRES_URL'))

fileConfig(config.config_file_name)

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=None,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()
```

#### 3.2.3 기존 마이그레이션 변환

```bash
# 기존 SQL 마이그레이션을 Alembic으로 변환
alembic revision -m "add_parent_coverage_id"
```

**db/migrations/versions/002_add_parent_coverage.py**:

```python
"""add parent_coverage_id

Revision ID: 002
Revises: 001
Create Date: 2025-12-11

"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Add parent_coverage_id column
    op.add_column('coverage',
        sa.Column('parent_coverage_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_coverage_parent',
        'coverage', 'coverage',
        ['parent_coverage_id'], ['id']
    )
    op.create_index('idx_coverage_parent', 'coverage', ['parent_coverage_id'])

    # Insert parent coverages
    op.execute("""
        INSERT INTO coverage (product_id, coverage_name, coverage_code, coverage_category, is_basic)
        SELECT 1, '일반암', 'general_cancer', 'diagnosis', true
        WHERE NOT EXISTS (SELECT 1 FROM coverage WHERE coverage_name = '일반암' AND is_basic = true)
    """)
    # ... 나머지 부모 담보들


def downgrade():
    op.drop_index('idx_coverage_parent')
    op.drop_constraint('fk_coverage_parent', 'coverage')
    op.drop_column('coverage', 'parent_coverage_id')
```

---

### Phase 3: 스크립트 및 검증 도구 (Day 5-6)

#### 3.3.1 DB 초기화 스크립트 개선

**scripts/init_db.sh**:

```bash
#!/bin/bash
set -e

source .env

echo "======================================"
echo "Database Initialization"
echo "======================================"

# 1. 스키마 생성
echo "[1/3] Creating schema..."
psql "$POSTGRES_URL" -f db/postgres/001_initial_schema.sql

# 2. 시드 데이터 적재
echo "[2/3] Loading seed data..."
psql "$POSTGRES_URL" -f db/postgres/002_seed_data.sql

# 3. Alembic 마이그레이션 스탬프 (현재 버전 기록)
echo "[3/3] Stamping migration version..."
cd db && alembic stamp head

echo "======================================"
echo "Database initialized successfully!"
echo "======================================"
```

#### 3.3.2 스키마 검증 스크립트

**scripts/verify_schema.py**:

```python
#!/usr/bin/env python3
"""
스키마 검증 스크립트

현재 DB 스키마가 정의된 스키마와 일치하는지 검증합니다.
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()

EXPECTED_TABLES = [
    'company', 'product', 'product_variant',
    'coverage', 'coverage_category', 'coverage_group',
    'benefit', 'condition', 'exclusion',
    'disease_code_set', 'disease_code',
    'document', 'document_clause',
    'clause_coverage', 'clause_embedding'
]

EXPECTED_INDEXES = {
    'clause_embedding': ['idx_clause_embedding_hnsw', 'idx_clause_embedding_metadata_gin'],
    'document_clause': ['idx_clause_type', 'idx_structured_data_gin'],
    'coverage': ['idx_coverage_name', 'idx_coverage_parent'],
}


def verify_schema():
    conn = psycopg2.connect(os.getenv('POSTGRES_URL'))
    cur = conn.cursor()

    errors = []
    warnings = []

    # 1. 테이블 존재 확인
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    """)
    existing_tables = {row[0] for row in cur.fetchall()}

    for table in EXPECTED_TABLES:
        if table not in existing_tables:
            errors.append(f"Missing table: {table}")

    # 2. 인덱스 존재 확인
    cur.execute("SELECT indexname, tablename FROM pg_indexes WHERE schemaname = 'public'")
    existing_indexes = {}
    for row in cur.fetchall():
        existing_indexes.setdefault(row[1], []).append(row[0])

    for table, indexes in EXPECTED_INDEXES.items():
        for idx in indexes:
            if idx not in existing_indexes.get(table, []):
                warnings.append(f"Missing index: {idx} on {table}")

    # 3. pgvector 확장 확인
    cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
    if not cur.fetchone():
        errors.append("Missing extension: vector (pgvector)")

    cur.close()
    conn.close()

    # 결과 출력
    print("=" * 50)
    print("Schema Verification Report")
    print("=" * 50)

    if errors:
        print(f"\n❌ ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")

    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")

    if not errors and not warnings:
        print("\n✅ Schema verification passed!")

    return len(errors) == 0


if __name__ == '__main__':
    success = verify_schema()
    sys.exit(0 if success else 1)
```

#### 3.3.3 마이그레이션 실행 스크립트

**scripts/migrate.sh**:

```bash
#!/bin/bash
set -e

source .env

ACTION=${1:-upgrade}

case $ACTION in
    upgrade)
        echo "Upgrading to latest migration..."
        cd db && alembic upgrade head
        ;;
    downgrade)
        echo "Downgrading one version..."
        cd db && alembic downgrade -1
        ;;
    history)
        echo "Migration history:"
        cd db && alembic history
        ;;
    current)
        echo "Current migration version:"
        cd db && alembic current
        ;;
    *)
        echo "Usage: $0 [upgrade|downgrade|history|current]"
        exit 1
        ;;
esac

echo "Done!"
```

---

### Phase 4: CI/CD 통합 (Day 7)

#### 3.4.1 GitHub Actions 워크플로우

**.github/workflows/schema-check.yml**:

```yaml
name: Schema Validation

on:
  push:
    paths:
      - 'db/**'
      - 'ingestion/**'
  pull_request:
    paths:
      - 'db/**'
      - 'ingestion/**'

jobs:
  validate-schema:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: pgvector/pgvector:pg15
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: insurance_ontology_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install psycopg2-binary alembic python-dotenv

      - name: Initialize database
        env:
          POSTGRES_URL: postgresql://postgres:postgres@localhost:5432/insurance_ontology_test
        run: |
          psql "$POSTGRES_URL" -f db/postgres/001_initial_schema.sql

      - name: Run migrations
        env:
          POSTGRES_URL: postgresql://postgres:postgres@localhost:5432/insurance_ontology_test
        run: |
          cd db && alembic upgrade head

      - name: Verify schema
        env:
          POSTGRES_URL: postgresql://postgres:postgres@localhost:5432/insurance_ontology_test
        run: |
          python scripts/verify_schema.py
```

---

### Phase 5: pgvector 벡터 인덱스 관리 (Day 8-9)

#### 3.5.1 현재 pgvector 설정

```sql
-- 현재 설정
CREATE TABLE clause_embedding (
    id SERIAL PRIMARY KEY,
    clause_id INTEGER UNIQUE NOT NULL REFERENCES document_clause(id) ON DELETE CASCADE,
    embedding vector(1536),           -- OpenAI text-embedding-3-small
    model_name VARCHAR(100),          -- 'text-embedding-3-small'
    metadata JSONB,                   -- {clause_type, doc_type, coverage_ids}
    created_at TIMESTAMP DEFAULT now()
);

-- HNSW 인덱스 (현재)
CREATE INDEX idx_clause_embedding_hnsw
ON clause_embedding USING hnsw(embedding vector_cosine_ops)
WITH (m=16, ef_construction=64);
```

#### 3.5.2 pgvector 스키마 정의 파일

**db/postgres/003_pgvector_setup.sql**:

```sql
-- ============================================================================
-- pgvector Extension Setup
-- Version: 1.0.0
-- ============================================================================

-- 1. Extension 설치
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. 벡터 테이블 생성
CREATE TABLE IF NOT EXISTS clause_embedding (
    id SERIAL PRIMARY KEY,
    clause_id INTEGER UNIQUE NOT NULL REFERENCES document_clause(id) ON DELETE CASCADE,
    embedding vector(1536),
    model_name VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT now()
);

-- 3. 인덱스 생성
-- 메타데이터 GIN 인덱스 (필터링용)
CREATE INDEX IF NOT EXISTS idx_clause_embedding_metadata_gin
ON clause_embedding USING gin(metadata);

-- 벡터 HNSW 인덱스 (유사도 검색용)
-- 파라미터 설명:
--   m: 노드당 최대 연결 수 (높을수록 정확도↑, 메모리↑, 빌드시간↑)
--   ef_construction: 빌드 시 탐색 범위 (높을수록 정확도↑, 빌드시간↑)
CREATE INDEX IF NOT EXISTS idx_clause_embedding_hnsw
ON clause_embedding USING hnsw(embedding vector_cosine_ops)
WITH (m=16, ef_construction=64);

-- 4. 검색 성능 설정 (세션별)
-- ef_search: 검색 시 탐색 범위 (높을수록 정확도↑, 검색시간↑)
-- SET hnsw.ef_search = 100;  -- 기본값: 40

-- ============================================================================
-- HNSW 인덱스 튜닝 가이드
-- ============================================================================
--
-- | 데이터 규모 | m | ef_construction | ef_search | 예상 Recall |
-- |------------|---|-----------------|-----------|-------------|
-- | <100K      | 16| 64              | 40        | 95%+        |
-- | 100K-1M    | 24| 128             | 100       | 95%+        |
-- | >1M        | 32| 200             | 200       | 95%+        |
--
-- 현재 데이터: 134,644건 → m=16, ef_construction=64 적정
--
-- 인덱스 재생성 시:
-- DROP INDEX idx_clause_embedding_hnsw;
-- CREATE INDEX idx_clause_embedding_hnsw ON clause_embedding
--     USING hnsw(embedding vector_cosine_ops) WITH (m=24, ef_construction=128);
-- ============================================================================
```

#### 3.5.3 임베딩 모델 변경 마이그레이션

**db/migrations/versions/003_change_embedding_model.py** (템플릿):

```python
"""Change embedding model from text-embedding-3-small to new-model

Revision ID: 003
Revises: 002
Create Date: YYYY-MM-DD

⚠️  주의: 이 마이그레이션은 전체 임베딩 재생성이 필요합니다.
    예상 소요 시간: 134K 문서 × 0.1초 ≈ 3.7시간
    예상 비용: 134K × $0.00002 ≈ $2.68 (OpenAI 기준)
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'


def upgrade():
    # 1. 기존 임베딩 백업 (선택)
    op.execute("""
        CREATE TABLE clause_embedding_backup AS
        SELECT * FROM clause_embedding;
    """)

    # 2. 차원 변경이 필요한 경우
    # op.execute("ALTER TABLE clause_embedding ALTER COLUMN embedding TYPE vector(NEW_DIM);")

    # 3. 인덱스 삭제 (차원 변경 시 필수)
    op.drop_index('idx_clause_embedding_hnsw')

    # 4. 새 모델로 임베딩 재생성 (별도 스크립트로 실행)
    # python -m vector_index.build_index --backend openai --force-rebuild

    # 5. 인덱스 재생성
    op.execute("""
        CREATE INDEX idx_clause_embedding_hnsw
        ON clause_embedding USING hnsw(embedding vector_cosine_ops)
        WITH (m=16, ef_construction=64);
    """)


def downgrade():
    # 백업에서 복구
    op.execute("DROP TABLE clause_embedding;")
    op.execute("ALTER TABLE clause_embedding_backup RENAME TO clause_embedding;")
```

#### 3.5.4 벡터 검색 성능 모니터링

**scripts/monitor_vector_search.py**:

```python
#!/usr/bin/env python3
"""
pgvector 검색 성능 모니터링
"""
import os
import time
import psycopg2
import numpy as np
from dotenv import load_dotenv

load_dotenv()

def benchmark_vector_search(conn, num_queries=100):
    """벡터 검색 벤치마크"""
    cur = conn.cursor()

    # 랜덤 벡터로 테스트
    latencies = []
    for _ in range(num_queries):
        random_vector = np.random.rand(1536).tolist()

        start = time.time()
        cur.execute("""
            SELECT clause_id, 1 - (embedding <=> %s::vector) as similarity
            FROM clause_embedding
            ORDER BY embedding <=> %s::vector
            LIMIT 10
        """, (random_vector, random_vector))
        cur.fetchall()
        latencies.append((time.time() - start) * 1000)

    print("=" * 50)
    print("pgvector Search Benchmark")
    print("=" * 50)
    print(f"Queries: {num_queries}")
    print(f"Avg Latency: {np.mean(latencies):.2f}ms")
    print(f"P50 Latency: {np.percentile(latencies, 50):.2f}ms")
    print(f"P95 Latency: {np.percentile(latencies, 95):.2f}ms")
    print(f"P99 Latency: {np.percentile(latencies, 99):.2f}ms")

    cur.close()


def check_index_stats(conn):
    """인덱스 상태 확인"""
    cur = conn.cursor()

    cur.execute("""
        SELECT
            indexrelname as index_name,
            pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
            idx_scan as scans,
            idx_tup_read as tuples_read
        FROM pg_stat_user_indexes
        WHERE indexrelname LIKE '%embedding%'
    """)

    print("\n" + "=" * 50)
    print("Index Statistics")
    print("=" * 50)
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]}, scans={row[2]}, tuples={row[3]}")

    cur.close()


if __name__ == '__main__':
    conn = psycopg2.connect(os.getenv('POSTGRES_URL'))
    benchmark_vector_search(conn)
    check_index_stats(conn)
    conn.close()
```

---

### Phase 6: Neo4j 그래프 스키마 관리 (Day 10-11)

#### 3.6.1 Neo4j 그래프 스키마 정의

**db/neo4j/001_graph_schema.cypher**:

```cypher
// ============================================================================
// Insurance Ontology Graph Schema
// Version: 1.0.0
// Created: 2025-12-09
// ============================================================================

// ============================================================================
// CONSTRAINTS (Unique 제약)
// ============================================================================

// Company
CREATE CONSTRAINT company_id_unique IF NOT EXISTS
FOR (c:Company) REQUIRE c.id IS UNIQUE;

// Product
CREATE CONSTRAINT product_id_unique IF NOT EXISTS
FOR (p:Product) REQUIRE p.id IS UNIQUE;

// ProductVariant
CREATE CONSTRAINT variant_id_unique IF NOT EXISTS
FOR (pv:ProductVariant) REQUIRE pv.id IS UNIQUE;

// Coverage
CREATE CONSTRAINT coverage_id_unique IF NOT EXISTS
FOR (cov:Coverage) REQUIRE cov.id IS UNIQUE;

// Benefit
CREATE CONSTRAINT benefit_id_unique IF NOT EXISTS
FOR (b:Benefit) REQUIRE b.id IS UNIQUE;

// Document
CREATE CONSTRAINT document_id_unique IF NOT EXISTS
FOR (d:Document) REQUIRE d.id IS UNIQUE;

// DiseaseCodeSet
CREATE CONSTRAINT disease_code_set_id_unique IF NOT EXISTS
FOR (dcs:DiseaseCodeSet) REQUIRE dcs.id IS UNIQUE;

// DiseaseCode
CREATE CONSTRAINT disease_code_id_unique IF NOT EXISTS
FOR (dc:DiseaseCode) REQUIRE dc.id IS UNIQUE;


// ============================================================================
// INDEXES (검색 성능)
// ============================================================================

// Company 검색
CREATE INDEX company_name_index IF NOT EXISTS
FOR (c:Company) ON (c.name);

CREATE INDEX company_code_index IF NOT EXISTS
FOR (c:Company) ON (c.code);

// Product 검색
CREATE INDEX product_name_index IF NOT EXISTS
FOR (p:Product) ON (p.name);

// Coverage 검색 (가장 자주 사용)
CREATE INDEX coverage_name_index IF NOT EXISTS
FOR (cov:Coverage) ON (cov.name);

CREATE INDEX coverage_category_index IF NOT EXISTS
FOR (cov:Coverage) ON (cov.category);

// Benefit 검색
CREATE INDEX benefit_type_index IF NOT EXISTS
FOR (b:Benefit) ON (b.type);

// Document 검색
CREATE INDEX document_type_index IF NOT EXISTS
FOR (d:Document) ON (d.doc_type);


// ============================================================================
// NODE SCHEMA (참고용 - Cypher에서 강제되지 않음)
// ============================================================================

// Company {
//   id: INTEGER (PK, from PostgreSQL)
//   name: STRING
//   code: STRING
//   business_type: STRING
// }

// Product {
//   id: INTEGER (PK)
//   name: STRING
//   code: STRING
//   business_type: STRING
// }

// ProductVariant {
//   id: INTEGER (PK)
//   name: STRING
//   code: STRING
//   target_gender: STRING ('male', 'female', null)
//   target_age_range: STRING ('≤40', '≥41', null)
// }

// Coverage {
//   id: INTEGER (PK)
//   name: STRING
//   code: STRING
//   category: STRING ('diagnosis', 'surgery', 'treatment', etc.)
//   renewal_type: STRING
//   is_basic: BOOLEAN
// }

// Benefit {
//   id: INTEGER (PK)
//   name: STRING
//   amount: INTEGER
//   amount_text: STRING
//   type: STRING
// }

// Document {
//   id: INTEGER (PK)
//   document_id: STRING
//   doc_type: STRING
//   doc_subtype: STRING
//   version: STRING
//   total_pages: INTEGER
// }

// DiseaseCodeSet {
//   id: INTEGER (PK)
//   name: STRING
//   description: STRING
//   version: STRING
// }

// DiseaseCode {
//   id: INTEGER (PK)
//   code: STRING
//   type: STRING
//   description: STRING
// }


// ============================================================================
// RELATIONSHIP SCHEMA
// ============================================================================

// (Company)-[:HAS_PRODUCT]->(Product)
// (Product)-[:HAS_VARIANT]->(ProductVariant)
// (Product)-[:OFFERS]->(Coverage)
// (Coverage)-[:HAS_BENEFIT]->(Benefit)
// (Company)-[:HAS_DOCUMENT]->(Document)
// (Product)-[:HAS_DOCUMENT]->(Document)
// (ProductVariant)-[:HAS_DOCUMENT]->(Document)
// (DiseaseCodeSet)-[:CONTAINS]->(DiseaseCode)
// (Coverage)-[:PARENT_OF]->(Coverage)  // 계층 구조
```

#### 3.6.2 Neo4j 초기화 스크립트

**scripts/init_neo4j.sh**:

```bash
#!/bin/bash
set -e

source .env

echo "======================================"
echo "Neo4j Graph Database Initialization"
echo "======================================"

# Neo4j 연결 확인
echo "[1/4] Checking Neo4j connection..."
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "RETURN 1" > /dev/null 2>&1 || {
    echo "❌ Cannot connect to Neo4j. Please start Neo4j first."
    exit 1
}
echo "✅ Connected to Neo4j"

# 기존 데이터 삭제 (선택)
if [ "$1" == "--clear" ]; then
    echo "[2/4] Clearing existing data..."
    cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "MATCH (n) DETACH DELETE n"
    echo "✅ Cleared all nodes and relationships"
else
    echo "[2/4] Skipping clear (use --clear to clear existing data)"
fi

# 스키마 적용
echo "[3/4] Applying graph schema..."
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" < db/neo4j/001_graph_schema.cypher
echo "✅ Schema applied"

# PostgreSQL에서 동기화
echo "[4/4] Syncing data from PostgreSQL..."
python -m ingestion.graph_loader --all
echo "✅ Data synced"

echo "======================================"
echo "Neo4j initialized successfully!"
echo "======================================"

# 통계 출력
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "
CALL apoc.meta.stats() YIELD nodeCount, relCount, labels, relTypes
RETURN nodeCount, relCount, labels, relTypes
" 2>/dev/null || {
    # APOC 없는 경우 수동 카운트
    echo "Node counts:"
    cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "
    MATCH (n) RETURN labels(n)[0] as label, count(*) as count ORDER BY count DESC
    "
}
```

#### 3.6.3 PostgreSQL ↔ Neo4j 동기화 검증

**scripts/verify_neo4j_sync.py**:

```python
#!/usr/bin/env python3
"""
PostgreSQL ↔ Neo4j 동기화 검증 스크립트
"""
import os
import sys
import psycopg2
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

def verify_sync():
    """동기화 상태 검증"""

    # PostgreSQL 연결
    pg_conn = psycopg2.connect(os.getenv('POSTGRES_URL'))
    pg_cur = pg_conn.cursor()

    # Neo4j 연결
    neo4j_driver = GraphDatabase.driver(
        os.getenv('NEO4J_URI'),
        auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
    )

    errors = []

    # 엔티티별 카운트 비교
    entities = [
        ('company', 'Company'),
        ('product', 'Product'),
        ('product_variant', 'ProductVariant'),
        ('coverage', 'Coverage'),
        ('benefit', 'Benefit'),
        ('document', 'Document'),
        ('disease_code_set', 'DiseaseCodeSet'),
        ('disease_code', 'DiseaseCode'),
    ]

    print("=" * 60)
    print("PostgreSQL ↔ Neo4j Sync Verification")
    print("=" * 60)
    print(f"{'Entity':<20} {'PostgreSQL':>12} {'Neo4j':>12} {'Status':>10}")
    print("-" * 60)

    for pg_table, neo4j_label in entities:
        # PostgreSQL count
        pg_cur.execute(f"SELECT COUNT(*) FROM {pg_table}")
        pg_count = pg_cur.fetchone()[0]

        # Neo4j count
        with neo4j_driver.session() as session:
            result = session.run(f"MATCH (n:{neo4j_label}) RETURN count(n) as count")
            neo4j_count = result.single()['count']

        status = "✅" if pg_count == neo4j_count else "❌"
        if pg_count != neo4j_count:
            errors.append(f"{pg_table}: PostgreSQL={pg_count}, Neo4j={neo4j_count}")

        print(f"{pg_table:<20} {pg_count:>12} {neo4j_count:>12} {status:>10}")

    print("-" * 60)

    # 관계 검증
    print("\nRelationship counts:")
    with neo4j_driver.session() as session:
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as rel_type, count(*) as count
            ORDER BY count DESC
        """)
        for record in result:
            print(f"  {record['rel_type']}: {record['count']}")

    pg_cur.close()
    pg_conn.close()
    neo4j_driver.close()

    # 결과
    print("\n" + "=" * 60)
    if errors:
        print("❌ SYNC ERRORS FOUND:")
        for e in errors:
            print(f"  - {e}")
        return False
    else:
        print("✅ All entities synced correctly!")
        return True


if __name__ == '__main__':
    success = verify_sync()
    sys.exit(0 if success else 1)
```

#### 3.6.4 Neo4j 동기화 자동화 (선택)

**scripts/sync_neo4j.sh**:

```bash
#!/bin/bash
# PostgreSQL 변경 감지 시 Neo4j 동기화

source .env

# 마지막 동기화 시간 확인
LAST_SYNC_FILE=".neo4j_last_sync"
if [ -f "$LAST_SYNC_FILE" ]; then
    LAST_SYNC=$(cat "$LAST_SYNC_FILE")
else
    LAST_SYNC="1970-01-01"
fi

# PostgreSQL에서 변경된 레코드 확인
CHANGED=$(psql "$POSTGRES_URL" -t -c "
    SELECT COUNT(*) FROM (
        SELECT 1 FROM company WHERE updated_at > '$LAST_SYNC'
        UNION ALL
        SELECT 1 FROM product WHERE updated_at > '$LAST_SYNC'
        UNION ALL
        SELECT 1 FROM coverage WHERE updated_at > '$LAST_SYNC'
    ) changes
")

if [ "$CHANGED" -gt 0 ]; then
    echo "Detected $CHANGED changes since $LAST_SYNC"
    echo "Syncing to Neo4j..."
    python -m ingestion.graph_loader --all
    date -Iseconds > "$LAST_SYNC_FILE"
    echo "Sync completed!"
else
    echo "No changes detected. Skipping sync."
fi
```

---

## 4. 마이그레이션 버전 관리 규칙

### 4.1 버전 명명 규칙

```
{YYYYMMDD}_{순번}_{설명}.sql
예: 20251211_001_add_parent_coverage.sql
```

### 4.2 마이그레이션 작성 원칙

1. **항상 롤백 가능하게 작성**
   ```sql
   -- UPGRADE
   ALTER TABLE coverage ADD COLUMN parent_coverage_id INTEGER;

   -- DOWNGRADE (주석으로 명시)
   -- ALTER TABLE coverage DROP COLUMN parent_coverage_id;
   ```

2. **데이터 마이그레이션 분리**
   - 스키마 변경과 데이터 변경은 별도 파일로

3. **트랜잭션 사용**
   ```sql
   BEGIN;
   -- 변경 내용
   COMMIT;
   ```

4. **검증 쿼리 포함**
   ```sql
   -- VERIFICATION
   SELECT COUNT(*) FROM coverage WHERE parent_coverage_id IS NOT NULL;
   ```

### 4.3 브랜치별 마이그레이션 규칙

| 브랜치 | 마이그레이션 생성 | 적용 방식 |
|--------|------------------|----------|
| feature/* | 가능 | 로컬에서 테스트 |
| develop | 가능 | staging에 자동 적용 |
| main | 금지 (PR 머지만) | production에 수동 적용 |

---

## 5. 체크리스트

### Phase 1: 스키마 추출 (Day 1-2)
- [ ] 현재 스키마 덤프 실행
- [ ] `db/postgres/001_initial_schema.sql` 생성
- [ ] `db/postgres/002_seed_data.sql` 생성
- [ ] 디렉토리 구조 정립

### Phase 2: Alembic 도입 (Day 3-4)
- [ ] Alembic 설치
- [ ] `alembic.ini` 설정
- [ ] `env.py` 설정
- [ ] 기존 마이그레이션 변환

### Phase 3: 스크립트 작성 (Day 5-6)
- [ ] `scripts/init_db.sh` 개선
- [ ] `scripts/verify_schema.py` 작성
- [ ] `scripts/migrate.sh` 작성
- [ ] 로컬 테스트 완료

### Phase 4: CI/CD 통합 (Day 7)
- [ ] GitHub Actions 워크플로우 작성
- [ ] PR 머지 시 자동 검증 확인
- [ ] 문서화 완료

### Phase 5: pgvector 관리 (Day 8-9)
- [ ] `db/postgres/003_pgvector_setup.sql` 생성
- [ ] HNSW 인덱스 파라미터 문서화
- [ ] `scripts/monitor_vector_search.py` 작성
- [ ] 임베딩 모델 변경 마이그레이션 템플릿 작성
- [ ] 벡터 검색 벤치마크 실행 및 기준선 수립

### Phase 6: Neo4j 관리 (Day 10-11)
- [ ] `db/neo4j/001_graph_schema.cypher` 생성
- [ ] `scripts/init_neo4j.sh` 작성
- [ ] `scripts/verify_neo4j_sync.py` 작성
- [ ] PostgreSQL ↔ Neo4j 동기화 검증 완료
- [ ] (선택) `scripts/sync_neo4j.sh` 자동 동기화 스크립트

---

## 6. 예상 리스크 및 대응

### 6.1 PostgreSQL 관련

| 리스크 | 영향 | 대응 방안 |
|--------|------|----------|
| 스키마 덤프 누락 | 일부 테이블/인덱스 빠짐 | 검증 스크립트로 확인 |
| 프로덕션 마이그레이션 실패 | 서비스 장애 | 스테이징에서 충분히 테스트 |
| Alembic 학습 곡선 | 개발 속도 저하 | 문서화 및 예제 제공 |
| 롤백 불완전 | 데이터 손실 | 백업 후 마이그레이션 실행 |

### 6.2 pgvector 관련

| 리스크 | 영향 | 대응 방안 |
|--------|------|----------|
| HNSW 인덱스 재생성 시간 | 134K 문서 → 수분~수십분 | 저트래픽 시간대 실행 |
| 임베딩 모델 변경 시 전체 재생성 | 3-4시간 + API 비용 | 배치 처리, 점진적 마이그레이션 |
| 벡터 차원 변경 | 인덱스 호환 불가 | 새 테이블 생성 후 스왑 |
| 검색 성능 저하 | 응답 시간 증가 | 모니터링 + 인덱스 튜닝 |

### 6.3 Neo4j 관련

| 리스크 | 영향 | 대응 방안 |
|--------|------|----------|
| PostgreSQL ↔ Neo4j 불일치 | 잘못된 그래프 쿼리 결과 | 동기화 검증 스크립트 실행 |
| 동기화 실패 | 그래프 데이터 누락 | 재시도 로직 + 알림 |
| Neo4j 스키마 변경 | 기존 쿼리 실패 | Cypher 쿼리 테스트 |
| 대량 동기화 시 성능 | Neo4j 부하 | 배치 처리 (1000건씩) |

---

## 7. 참고 자료

### PostgreSQL & Alembic
- [Alembic 공식 문서](https://alembic.sqlalchemy.org/)
- [PostgreSQL 마이그레이션 베스트 프랙티스](https://www.postgresql.org/docs/current/ddl-alter.html)

### pgvector
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [HNSW 인덱스 튜닝 가이드](https://github.com/pgvector/pgvector#hnsw)
- [pgvector 성능 벤치마크](https://supabase.com/blog/pgvector-vs-pinecone)

### Neo4j
- [Neo4j 공식 문서](https://neo4j.com/docs/)
- [Cypher 쿼리 언어](https://neo4j.com/docs/cypher-manual/current/)
- [Neo4j Python Driver](https://neo4j.com/docs/python-manual/current/)
- [Neo4j 인덱스 및 제약조건](https://neo4j.com/docs/cypher-manual/current/indexes-for-search-performance/)

### OpenAI Embeddings
- [OpenAI Embeddings API](https://platform.openai.com/docs/guides/embeddings)
- [text-embedding-3-small 모델](https://openai.com/blog/new-embedding-models-and-api-updates)

---

## 8. 담당자 및 일정

| 작업 | 담당자 | 시작일 | 완료일 | 상태 |
|------|--------|--------|--------|------|
| Phase 1: 스키마 추출 | TBD | 2025-12-14 | 2025-12-15 | 예정 |
| Phase 2: Alembic 도입 | TBD | 2025-12-16 | 2025-12-17 | 예정 |
| Phase 3: 스크립트 작성 | TBD | 2025-12-18 | 2025-12-19 | 예정 |
| Phase 4: CI/CD 통합 | TBD | 2025-12-20 | 2025-12-20 | 예정 |
| Phase 5: pgvector 관리 | TBD | 2025-12-21 | 2025-12-22 | 예정 |
| Phase 6: Neo4j 관리 | TBD | 2025-12-23 | 2025-12-24 | 예정 |

---

## 9. 디렉토리 구조 (최종)

```
db/
├── postgres/
│   ├── 001_initial_schema.sql        # PostgreSQL 초기 스키마
│   ├── 002_seed_data.sql             # 시드 데이터
│   ├── 003_pgvector_setup.sql        # pgvector 설정
│   └── tables/                        # (선택) 테이블별 분리
│
├── neo4j/
│   └── 001_graph_schema.cypher       # Neo4j 그래프 스키마
│
├── migrations/
│   ├── versions/                      # Alembic 마이그레이션
│   │   ├── 001_initial.py
│   │   ├── 002_add_parent_coverage.py
│   │   └── 003_change_embedding_model.py (템플릿)
│   ├── env.py
│   └── alembic.ini
│
└── scripts/
    ├── init_db.sh                     # PostgreSQL 초기화
    ├── init_neo4j.sh                  # Neo4j 초기화
    ├── migrate.sh                     # 마이그레이션 실행
    ├── verify_schema.py               # PostgreSQL 스키마 검증
    ├── verify_neo4j_sync.py           # Neo4j 동기화 검증
    ├── monitor_vector_search.py       # pgvector 성능 모니터링
    └── sync_neo4j.sh                  # (선택) Neo4j 자동 동기화
```

---

**문서 버전**: 2.0
**최종 수정**: 2025-12-13
**변경 이력**:
- v1.0 (2025-12-13): 초기 작성 - PostgreSQL 스키마 관리
- v2.0 (2025-12-13): pgvector, Neo4j 관리 내용 추가
