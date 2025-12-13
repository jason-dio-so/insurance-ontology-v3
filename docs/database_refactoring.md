# 데이터베이스 리팩토링 계획

**작성일**: 2025-12-13
**기준 문서**: database_status.md (2025-12-13 실제 DB 검증)
**목표 완료일**: 2025-12-24
**상태**: 계획 수립 완료

---

## 1. 현재 상태 요약

### 1.1 데이터베이스 현황

| 항목 | 현재 값 |
|------|---------|
| PostgreSQL | 15 + pgvector 0.8.1 |
| 테이블 | 15개 (12개 사용 중, 3개 미사용) |
| 핵심 데이터 | document_clause 134,844건 |
| 벡터 임베딩 | 134,644건 (1536차원, HNSW) |
| 인덱스 | 52개 |
| Neo4j | 640 노드, 623 관계 |

### 1.2 스키마 관리 현황

| 항목 | 상태 | 문제 |
|------|------|------|
| 스키마 파일 | ❌ 없음 | Python 코드에서 동적 생성 |
| 마이그레이션 | ⚠️ 1개 파일만 존재 | 추적 불가 |
| 롤백 | ❌ 불가 | downgrade 스크립트 없음 |
| 환경 일관성 | ❌ 보장 안됨 | 개발/프로덕션 차이 가능 |

### 1.3 현재 디렉토리 구조

```
db/
└── migrations/
    └── 20251211_add_parent_coverage.sql  # 유일한 파일
```

---

## 2. 리팩토링 목표

### 2.1 단기 목표 (1주)

- [ ] 현재 스키마를 SQL 파일로 추출
- [ ] **개념적 설계 문서 생성** (E-R 다이어그램, 데이터 딕셔너리, 관계 문서)
- [ ] 마이그레이션 버전 관리 체계 수립
- [ ] 스키마 검증 스크립트 작성
- [ ] Neo4j 그래프 스키마 정의

### 2.2 중기 목표 (2주)

- [ ] Alembic 마이그레이션 도구 도입
- [ ] CI/CD 파이프라인에 스키마 검증 추가
- [ ] 개발 환경 초기화 자동화
- [ ] pgvector HNSW 인덱스 튜닝 가이드 작성

### 2.3 장기 목표 (1개월)

- [ ] 테스트 데이터베이스 자동 생성
- [ ] 스키마 변경 자동 감지 및 알림
- [ ] PostgreSQL ↔ Neo4j 동기화 검증 자동화

---

## 3. 목표 디렉토리 구조

```
db/
├── postgres/
│   ├── 001_initial_schema.sql        # PostgreSQL 초기 스키마
│   ├── 002_seed_data.sql             # 시드 데이터 (coverage_category 등)
│   └── 003_pgvector_setup.sql        # pgvector 설정 및 인덱스
│
├── neo4j/
│   └── 001_graph_schema.cypher       # Neo4j 그래프 스키마
│
├── migrations/
│   ├── versions/                      # Alembic 마이그레이션
│   │   ├── 001_initial.py
│   │   └── 002_add_parent_coverage.py
│   ├── env.py
│   └── alembic.ini
│
├── docs/                              # 개념적 설계 문서
│   ├── ER_DIAGRAM.md                  # E-R 다이어그램
│   ├── DATA_DICTIONARY.md             # 데이터 딕셔너리
│   ├── RELATIONSHIP_MAP.md            # 테이블 관계 문서
│   └── DOMAIN_MODEL.md                # 도메인 모델 설명
│
└── scripts/
    ├── init_db.sh                     # PostgreSQL 초기화
    ├── init_neo4j.sh                  # Neo4j 초기화
    ├── migrate.sh                     # 마이그레이션 실행
    ├── verify_schema.py               # PostgreSQL 스키마 검증
    ├── verify_neo4j_sync.py           # Neo4j 동기화 검증
    └── generate_docs.py               # 설계 문서 자동 생성
```

---

## 4. 실행 계획

### Phase 1: 스키마 추출 (Day 1-2)

#### 4.1.1 현재 스키마 덤프

```bash
# 전체 스키마 덤프
pg_dump "postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology" \
    --schema-only --no-owner --no-privileges \
    > db/postgres/001_initial_schema.sql
```

#### 4.1.2 시드 데이터 추출

```bash
# coverage_category 데이터 추출
psql "$POSTGRES_URL" -c "COPY coverage_category TO STDOUT WITH CSV HEADER" \
    > db/postgres/seed/coverage_category.csv

# disease_code_set 데이터 추출
psql "$POSTGRES_URL" -c "COPY disease_code_set TO STDOUT WITH CSV HEADER" \
    > db/postgres/seed/disease_code_set.csv
```

#### 4.1.3 체크리스트

- [ ] 현재 스키마 덤프 실행
- [ ] `db/postgres/001_initial_schema.sql` 생성
- [ ] `db/postgres/002_seed_data.sql` 생성
- [ ] 디렉토리 구조 정립

---

### Phase 1.5: 개념적 설계 문서 생성 (Day 2-3)

#### 4.1.5.1 생성할 문서 목록

**PostgreSQL 설계 문서**:

| 문서 | 파일명 | 내용 |
|------|--------|------|
| E-R 다이어그램 | `db/docs/ER_DIAGRAM.md` | Mermaid 기반 엔티티-관계 다이어그램 |
| 데이터 딕셔너리 | `db/docs/DATA_DICTIONARY.md` | 테이블/컬럼 정의, 타입, 제약조건 |
| 관계 문서 | `db/docs/RELATIONSHIP_MAP.md` | 외래키 관계, 카디널리티 |
| 도메인 모델 | `db/docs/DOMAIN_MODEL.md` | 비즈니스 도메인 설명 |

**Neo4j 그래프 설계 문서**:

| 문서 | 파일명 | 내용 |
|------|--------|------|
| 그래프 스키마 개요 | `db/docs/GRAPH_SCHEMA.md` | Neo4j 그래프 모델 개요 및 설계 원칙 |
| 노드 딕셔너리 | `db/docs/NODE_DICTIONARY.md` | 노드 레이블별 속성 정의 |
| 관계 딕셔너리 | `db/docs/RELATIONSHIP_DICTIONARY.md` | 관계 타입별 정의 및 방향성 |
| 그래프 쿼리 패턴 | `db/docs/GRAPH_PATTERNS.md` | 자주 사용되는 Cypher 쿼리 패턴 |
| 온톨로지 갭 분석 | `db/docs/ONTOLOGY_GAP_ANALYSIS.md` | ontology_concept.md 대비 구현 갭 |

#### 4.1.5.2 Neo4j 현재 구현 상태 (graph_loader.py 기준)

**현재 구현된 노드 레이블 (8종)**:

| 노드 | PostgreSQL 테이블 | 속성 | 현재 수량 |
|------|------------------|------|----------|
| Company | company | id, name, code, business_type | 8 |
| Product | product | id, name, code, business_type | 8 |
| ProductVariant | product_variant | id, name, code, target_gender, target_age_range | 4 |
| Coverage | coverage | id, name, code, category, renewal_type, is_basic | 363 |
| Benefit | benefit | id, name, amount, amount_text, type | 357 |
| Document | document | id, document_id, doc_type, doc_subtype, version, total_pages | 38 |
| DiseaseCodeSet | disease_code_set | id, name, description, version | 9 |
| DiseaseCode | disease_code | id, code, type, description | 131 |

**현재 구현된 관계 (6종)**:

| 관계 | 시작 노드 | 종료 노드 | 설명 |
|------|----------|----------|------|
| HAS_PRODUCT | Company | Product | 보험사 → 상품 |
| HAS_VARIANT | Product | ProductVariant | 상품 → 변형 |
| OFFERS | Product | Coverage | 상품 → 담보 |
| HAS_BENEFIT | Coverage | Benefit | 담보 → 급부 |
| HAS_DOCUMENT | Company/Product/ProductVariant | Document | 엔티티 → 문서 |
| CONTAINS | DiseaseCodeSet | DiseaseCode | 코드셋 → 코드 |

**현재 그래프 규모**: 640 노드, 623 관계

#### 4.1.5.3 ontology_concept.md 대비 갭 분석

**미구현 노드 (ontology_concept.md에 정의됨)**:

| 노드 | 설명 | 우선순위 | 구현 난이도 |
|------|------|----------|------------|
| RiskEvent | 보장 이벤트 (암진단, 뇌졸중, 사망, 장해 등) | 높음 | 중 |
| Condition | 지급 조건 (waiting_period, survival_period) | 높음 | 중 |
| Exclusion | 면책/부지급 사유 | 높음 | 중 |
| Plan | 가입설계 결과 (선택 담보, 보험료) | 중간 | 낮음 |
| ExplanationResource | 설명 리소스 (요약서 등) | 낮음 | 낮음 |
| ComplaintPattern | 민원 패턴 | 낮음 | 높음 |

**미구현 관계**:

| 관계 | 설명 | 의존 노드 |
|------|------|----------|
| TRIGGERS | Benefit → RiskEvent (급부가 리스크 이벤트 보장) | RiskEvent |
| HAS_CONDITION | Coverage → Condition (담보의 지급 조건) | Condition |
| HAS_EXCLUSION | Coverage → Exclusion (담보의 면책 사유) | Exclusion |
| APPLIES_TO | DiseaseCodeSet → Coverage (코드셋이 담보에 적용) | - |
| PARENT_OF | Coverage → Coverage (담보 계층 구조) | - |

#### 4.1.5.4 추가 구현 제안 모델

**Phase 1: 핵심 관계 추가 (즉시 구현 가능)**

```cypher
// Coverage 계층 관계 (parent_coverage_id 활용)
MATCH (parent:Coverage), (child:Coverage)
WHERE child.parent_coverage_id = parent.id
MERGE (parent)-[:PARENT_OF]->(child)

// DiseaseCodeSet → Coverage 적용 관계
// (PostgreSQL에 매핑 테이블 필요)
```

**Phase 2: RiskEvent 노드 추가**

```cypher
// RiskEvent 노드 예시
CREATE (:RiskEvent {
  id: 1,
  event_type: 'diagnosis',      // diagnosis, surgery, hospitalization, death
  event_name: '암 진단',
  severity_level: 'severe',     // mild, moderate, severe, terminal
  icd_code_pattern: 'C%'        // ICD-10 패턴
})

// Benefit → RiskEvent 관계
MATCH (b:Benefit), (re:RiskEvent)
WHERE b.type = re.event_type
MERGE (b)-[:TRIGGERS]->(re)
```

**Phase 3: Condition/Exclusion 노드 추가**

```cypher
// Condition 노드 예시
CREATE (:Condition {
  id: 1,
  condition_type: 'waiting_period',
  value: 90,
  unit: 'days',
  description: '90일 면책기간'
})

// Exclusion 노드 예시
CREATE (:Exclusion {
  id: 1,
  exclusion_type: 'pre_existing',
  description: '계약 전 알릴 의무 위반',
  clause_reference: '제12조'
})

// Coverage → Condition/Exclusion 관계
MATCH (cov:Coverage), (cond:Condition)
MERGE (cov)-[:HAS_CONDITION {mandatory: true}]->(cond)
```

**Phase 4: Plan 노드 추가 (가입설계서 파싱 후)**

```cypher
// Plan 노드 (가입설계 결과)
CREATE (:Plan {
  id: 1,
  plan_date: date('2025-11-01'),
  insured_name: '홍길동',
  insured_age: 35,
  insured_gender: 'male',
  total_premium: 50000,
  payment_period: '20년납',
  coverage_period: '100세만기'
})

// Plan → Coverage (선택된 담보)
MATCH (plan:Plan {id: 1}), (cov:Coverage {name: '암 진단비'})
MERGE (plan)-[:INCLUDES {sum_insured: 30000000, premium: 15000}]->(cov)
```

#### 4.1.5.5 E-R 다이어그램 (Mermaid)

**db/docs/ER_DIAGRAM.md**:
```markdown
# E-R 다이어그램

## 전체 구조

\`\`\`mermaid
erDiagram
    COMPANY ||--o{ PRODUCT : has
    PRODUCT ||--o{ PRODUCT_VARIANT : has
    PRODUCT ||--o{ COVERAGE : offers
    COVERAGE ||--o{ BENEFIT : has
    COVERAGE ||--o| COVERAGE : parent_of
    COVERAGE }o--o{ COVERAGE_CATEGORY : belongs_to

    DOCUMENT }o--|| COMPANY : belongs_to
    DOCUMENT }o--|| PRODUCT : belongs_to
    DOCUMENT ||--o{ DOCUMENT_CLAUSE : contains
    DOCUMENT_CLAUSE ||--o| CLAUSE_EMBEDDING : has
    DOCUMENT_CLAUSE }o--o{ COVERAGE : maps_to

    DISEASE_CODE_SET ||--o{ DISEASE_CODE : contains
\`\`\`

## 도메인별 상세

### 보험 도메인
\`\`\`mermaid
erDiagram
    COMPANY {
        int id PK
        varchar company_code UK
        varchar company_name
        varchar business_type
        timestamp created_at
        timestamp updated_at
    }
    PRODUCT {
        int id PK
        int company_id FK
        varchar product_code
        varchar product_name
        varchar business_type
        varchar version
        date effective_date
    }
    COVERAGE {
        int id PK
        int product_id FK
        int parent_coverage_id FK
        varchar coverage_code
        varchar coverage_name
        varchar coverage_category
        varchar renewal_type
        boolean is_basic
    }
\`\`\`
```

#### 4.1.5.6 데이터 딕셔너리

**db/docs/DATA_DICTIONARY.md**:
```markdown
# 데이터 딕셔너리

## 보험 도메인

### company (보험사)
| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id | SERIAL | NO | - | PK |
| company_code | VARCHAR(20) | NO | - | 보험사 코드 (UK) |
| company_name | VARCHAR(100) | NO | - | 보험사 한글명 |
| business_type | VARCHAR(50) | YES | - | 업종 |
| created_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | 생성일시 |
| updated_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | 수정일시 |

### coverage (담보)
| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id | SERIAL | NO | - | PK |
| product_id | INTEGER | NO | - | FK → product.id |
| parent_coverage_id | INTEGER | YES | - | FK → coverage.id (자기참조) |
| coverage_code | VARCHAR(200) | YES | - | 담보 코드 |
| coverage_name | VARCHAR(200) | NO | - | 담보명 |
| coverage_category | VARCHAR(100) | YES | - | 카테고리 (diagnosis/surgery 등) |
| renewal_type | VARCHAR(20) | YES | - | 갱신 유형 |
| is_basic | BOOLEAN | YES | false | 기본 담보 여부 |

## 문서 도메인

### document_clause (문서 조항)
| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id | SERIAL | NO | - | PK |
| document_id | INTEGER | NO | - | FK → document.id |
| clause_type | VARCHAR(50) | YES | - | article/text_block/table_row |
| clause_text | TEXT | NO | - | 조항 본문 |
| structured_data | JSONB | YES | - | 구조화 데이터 (table_row용) |
| page_number | INTEGER | YES | - | 페이지 번호 |

### clause_embedding (벡터 임베딩)
| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id | SERIAL | NO | - | PK |
| clause_id | INTEGER | NO | - | FK → document_clause.id (UK) |
| embedding | VECTOR(1536) | YES | - | OpenAI 임베딩 벡터 |
| model_name | VARCHAR(100) | YES | - | 사용 모델명 |
| metadata | JSONB | YES | - | 메타데이터 |
```

#### 4.1.5.7 관계 문서

**db/docs/RELATIONSHIP_MAP.md**:
```markdown
# 테이블 관계 문서

## 외래키 관계

| 테이블 | 컬럼 | 참조 테이블 | 참조 컬럼 | 카디널리티 | 설명 |
|--------|------|------------|----------|-----------|------|
| product | company_id | company | id | N:1 | 상품 → 보험사 |
| product_variant | product_id | product | id | N:1 | 변형 → 상품 |
| coverage | product_id | product | id | N:1 | 담보 → 상품 |
| coverage | parent_coverage_id | coverage | id | N:1 | 자식 → 부모 담보 |
| benefit | coverage_id | coverage | id | N:1 | 급부 → 담보 |
| document | company_id | company | id | N:1 | 문서 → 보험사 |
| document | product_id | product | id | N:1 | 문서 → 상품 |
| document_clause | document_id | document | id | N:1 | 조항 → 문서 |
| clause_embedding | clause_id | document_clause | id | 1:1 | 임베딩 → 조항 |
| clause_coverage | clause_id | document_clause | id | N:M | 조항 ↔ 담보 |
| clause_coverage | coverage_id | coverage | id | N:M | 조항 ↔ 담보 |
| disease_code | code_set_id | disease_code_set | id | N:1 | 코드 → 코드셋 |

## N:M 관계 (매핑 테이블)

### clause_coverage
- document_clause ↔ coverage 다대다 관계
- 추가 속성: relevance_score, extraction_method
```

#### 4.1.5.8 도메인 모델 문서

**db/docs/DOMAIN_MODEL.md**:
```markdown
# 도메인 모델

## 1. 보험 도메인 (Insurance Domain)

### 개요
보험사(Company) → 상품(Product) → 담보(Coverage) → 급부(Benefit) 계층 구조

### 엔티티 설명

| 엔티티 | 역할 | 레코드 수 |
|--------|------|----------|
| Company | 8개 보험사 (삼성, DB, 롯데, 메리츠, KB, 한화, 현대, 흥국) | 8 |
| Product | 각 보험사별 1개 암보험 상품 | 8 |
| ProductVariant | 상품 변형 (롯데: 성별, DB: 연령) | 4 |
| Coverage | 담보 (부모 9, 자식 52, 독립 302) | 363 |
| Benefit | 급부 (진단, 수술, 치료, 사망, 기타) | 357 |

### 담보 계층 구조
- 부모 담보: 일반암, 뇌혈관질환, 뇌졸중, 뇌출혈, 허혈심장질환, 급성심근경색 + 기본계약(3)
- 자식 담보: 부모 담보를 세분화한 구체적 담보 (52개)

## 2. 문서 도메인 (Document Domain)

### 개요
PDF 문서 → 조항 단위 파싱 → 벡터 임베딩 → RAG 검색

### 문서 유형

| doc_type | 설명 | 파서 | 조항 수 |
|----------|------|------|---------|
| terms | 약관 | TextParser | 129,667 (article) |
| business_spec | 사업방법서 | HybridParserV2 | 4,286 (text_block) |
| product_summary | 상품요약서 | HybridParserV2 | - |
| proposal | 가입설계서 | Carrier-Specific | 891 (table_row) |
| easy_summary | 쉬운요약서 | HybridParserV2 | - |

## 3. 매핑 도메인 (Mapping Domain)

### clause_coverage
조항 ↔ 담보 N:M 매핑

| 매핑 방법 | 수량 | 비율 |
|-----------|------|------|
| parent_coverage_linking | 3,889 | 79.3% |
| exact_match | 829 | 16.9% |
| fuzzy_match | 185 | 3.8% |
```

#### 4.1.5.9 문서 자동 생성 스크립트

**db/scripts/generate_docs.py**:
```python
#!/usr/bin/env python3
"""DB 스키마에서 설계 문서 자동 생성"""
import os
import psycopg2

def generate_data_dictionary(conn):
    """데이터 딕셔너리 생성"""
    cur = conn.cursor()

    # 테이블 목록 조회
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cur.fetchall()]

    output = ["# 데이터 딕셔너리\n"]

    for table in tables:
        output.append(f"\n## {table}\n")
        output.append("| 컬럼명 | 타입 | NULL | 기본값 | 설명 |")
        output.append("|--------|------|------|--------|------|")

        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s AND table_schema = 'public'
            ORDER BY ordinal_position
        """, (table,))

        for col in cur.fetchall():
            nullable = "YES" if col[2] == "YES" else "NO"
            default = col[3] if col[3] else "-"
            output.append(f"| {col[0]} | {col[1].upper()} | {nullable} | {default} | - |")

    cur.close()
    return "\n".join(output)

def generate_relationship_map(conn):
    """관계 문서 생성"""
    cur = conn.cursor()

    cur.execute("""
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table,
            ccu.column_name AS foreign_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        ORDER BY tc.table_name
    """)

    output = ["# 테이블 관계 문서\n"]
    output.append("| 테이블 | 컬럼 | 참조 테이블 | 참조 컬럼 |")
    output.append("|--------|------|------------|----------|")

    for row in cur.fetchall():
        output.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |")

    cur.close()
    return "\n".join(output)

if __name__ == '__main__':
    conn = psycopg2.connect(os.getenv('POSTGRES_URL'))

    # 문서 생성
    os.makedirs('db/docs', exist_ok=True)

    with open('db/docs/DATA_DICTIONARY.md', 'w') as f:
        f.write(generate_data_dictionary(conn))

    with open('db/docs/RELATIONSHIP_MAP.md', 'w') as f:
        f.write(generate_relationship_map(conn))

    conn.close()
    print("✅ Design documents generated!")
```

#### 4.1.5.10 체크리스트

**PostgreSQL 설계 문서**:
- [ ] `db/docs/` 디렉토리 생성
- [ ] `db/docs/ER_DIAGRAM.md` 작성 (Mermaid 다이어그램)
- [ ] `db/docs/DATA_DICTIONARY.md` 생성 (자동 생성 스크립트 활용)
- [ ] `db/docs/RELATIONSHIP_MAP.md` 생성 (외래키 관계)
- [ ] `db/docs/DOMAIN_MODEL.md` 작성 (비즈니스 도메인 설명)
- [ ] `db/scripts/generate_docs.py` 작성 (자동 생성 도구)

**Neo4j 그래프 설계 문서**:
- [ ] `db/docs/GRAPH_SCHEMA.md` 작성 (그래프 모델 개요)
- [ ] `db/docs/NODE_DICTIONARY.md` 작성 (노드 속성 정의)
- [ ] `db/docs/RELATIONSHIP_DICTIONARY.md` 작성 (관계 타입 정의)
- [ ] `db/docs/GRAPH_PATTERNS.md` 작성 (Cypher 쿼리 패턴)
- [ ] `db/docs/ONTOLOGY_GAP_ANALYSIS.md` 작성 (ontology_concept.md 대비 갭)

**온톨로지 확장 작업 (Phase 7)**:
- [ ] `graph_loader.py`에 PARENT_OF 관계 추가
- [ ] PostgreSQL에 `risk_event`, `condition`, `exclusion` 테이블 설계
- [ ] Neo4j에 RiskEvent, Condition, Exclusion 노드 추가
- [ ] Plan 노드 추가 (가입설계서 파싱 연동)

---

### Phase 2: Alembic 마이그레이션 도입 (Day 4-5)

#### 4.2.1 Alembic 설치 및 초기화

```bash
pip install alembic
cd db
alembic init migrations
```

#### 4.2.2 환경 설정

**db/migrations/env.py**:
```python
import os
from dotenv import load_dotenv
from alembic import context

load_dotenv()
config = context.config
config.set_main_option('sqlalchemy.url', os.getenv('POSTGRES_URL'))
```

#### 4.2.3 기존 마이그레이션 변환

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

def upgrade():
    op.add_column('coverage',
        sa.Column('parent_coverage_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key('fk_coverage_parent', 'coverage', 'coverage',
        ['parent_coverage_id'], ['id'])
    op.create_index('idx_coverage_parent', 'coverage', ['parent_coverage_id'])

def downgrade():
    op.drop_index('idx_coverage_parent')
    op.drop_constraint('fk_coverage_parent', 'coverage')
    op.drop_column('coverage', 'parent_coverage_id')
```

#### 4.2.4 체크리스트

- [ ] Alembic 설치
- [ ] `alembic.ini` 설정
- [ ] `env.py` 설정
- [ ] 기존 마이그레이션 변환

---

### Phase 3: 스크립트 및 검증 도구 (Day 5-6)

#### 4.3.1 DB 초기화 스크립트

**db/scripts/init_db.sh**:
```bash
#!/bin/bash
set -e

POSTGRES_URL=${POSTGRES_URL:-"postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology"}

echo "======================================"
echo "Database Initialization"
echo "======================================"

echo "[1/3] Creating schema..."
psql "$POSTGRES_URL" -f db/postgres/001_initial_schema.sql

echo "[2/3] Loading seed data..."
psql "$POSTGRES_URL" -f db/postgres/002_seed_data.sql

echo "[3/3] Stamping migration version..."
cd db && alembic stamp head

echo "Database initialized successfully!"
```

#### 4.3.2 스키마 검증 스크립트

**db/scripts/verify_schema.py**:
```python
#!/usr/bin/env python3
"""현재 DB 스키마가 정의된 스키마와 일치하는지 검증"""
import os
import psycopg2

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

    # 테이블 검증
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    """)
    existing_tables = {row[0] for row in cur.fetchall()}

    for table in EXPECTED_TABLES:
        if table not in existing_tables:
            errors.append(f"Missing table: {table}")

    # pgvector 확장 검증
    cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
    if not cur.fetchone():
        errors.append("Missing extension: vector (pgvector)")

    cur.close()
    conn.close()

    if errors:
        print("❌ ERRORS:")
        for e in errors:
            print(f"  - {e}")
        return False
    else:
        print("✅ Schema verification passed!")
        return True

if __name__ == '__main__':
    import sys
    sys.exit(0 if verify_schema() else 1)
```

#### 4.3.3 체크리스트

- [ ] `db/scripts/init_db.sh` 작성
- [ ] `db/scripts/verify_schema.py` 작성
- [ ] `db/scripts/migrate.sh` 작성
- [ ] 로컬 테스트 완료

---

### Phase 4: Neo4j 스키마 관리 (Day 7-8)

#### 4.4.1 Neo4j 그래프 스키마 정의

**db/neo4j/001_graph_schema.cypher**:
```cypher
// ============================================================================
// Insurance Ontology Graph Schema
// ============================================================================

// CONSTRAINTS
CREATE CONSTRAINT company_id_unique IF NOT EXISTS
FOR (c:Company) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT product_id_unique IF NOT EXISTS
FOR (p:Product) REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT coverage_id_unique IF NOT EXISTS
FOR (cov:Coverage) REQUIRE cov.id IS UNIQUE;

CREATE CONSTRAINT benefit_id_unique IF NOT EXISTS
FOR (b:Benefit) REQUIRE b.id IS UNIQUE;

// INDEXES
CREATE INDEX company_name_index IF NOT EXISTS
FOR (c:Company) ON (c.name);

CREATE INDEX coverage_name_index IF NOT EXISTS
FOR (cov:Coverage) ON (cov.name);

// NODE SCHEMA (Reference)
// (Company) - id, name, code
// (Product) - id, name, code, business_type
// (ProductVariant) - id, name, code, target_gender, target_age_range
// (Coverage) - id, name, code, category, is_basic
// (Benefit) - id, name, amount, type
// (DiseaseCodeSet) - id, name, description
// (DiseaseCode) - id, code, description

// RELATIONSHIP SCHEMA
// (Company)-[:HAS_PRODUCT]->(Product)
// (Product)-[:HAS_VARIANT]->(ProductVariant)
// (Product)-[:OFFERS]->(Coverage)
// (Coverage)-[:HAS_BENEFIT]->(Benefit)
// (DiseaseCodeSet)-[:CONTAINS]->(DiseaseCode)
```

#### 4.4.2 Neo4j 동기화 검증 스크립트

**db/scripts/verify_neo4j_sync.py**:
```python
#!/usr/bin/env python3
"""PostgreSQL ↔ Neo4j 동기화 검증"""
import os
import psycopg2
from neo4j import GraphDatabase

ENTITY_MAPPING = [
    ('company', 'Company'),
    ('product', 'Product'),
    ('product_variant', 'ProductVariant'),
    ('coverage', 'Coverage'),
    ('benefit', 'Benefit'),
]

def verify_sync():
    pg_conn = psycopg2.connect(os.getenv('POSTGRES_URL'))
    neo4j_driver = GraphDatabase.driver(
        os.getenv('NEO4J_URI'),
        auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
    )

    errors = []
    for pg_table, neo4j_label in ENTITY_MAPPING:
        # PostgreSQL count
        cur = pg_conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {pg_table}")
        pg_count = cur.fetchone()[0]
        cur.close()

        # Neo4j count
        with neo4j_driver.session() as session:
            result = session.run(f"MATCH (n:{neo4j_label}) RETURN count(n) as count")
            neo4j_count = result.single()['count']

        if pg_count != neo4j_count:
            errors.append(f"{pg_table}: PostgreSQL={pg_count}, Neo4j={neo4j_count}")

    pg_conn.close()
    neo4j_driver.close()

    if errors:
        print("❌ SYNC ERRORS:")
        for e in errors:
            print(f"  - {e}")
        return False
    else:
        print("✅ All entities synced correctly!")
        return True

if __name__ == '__main__':
    import sys
    sys.exit(0 if verify_sync() else 1)
```

#### 4.4.3 체크리스트

- [ ] `db/neo4j/001_graph_schema.cypher` 생성
- [ ] `db/scripts/init_neo4j.sh` 작성
- [ ] `db/scripts/verify_neo4j_sync.py` 작성
- [ ] 동기화 검증 완료

---

### Phase 5: pgvector 인덱스 관리 (Day 9-10)

#### 4.5.1 현재 pgvector 설정

| 항목 | 현재 값 |
|------|---------|
| Extension | pgvector 0.8.1 |
| 차원 | 1536 (text-embedding-3-small) |
| 인덱스 | HNSW (m=16, ef_construction=64) |
| 데이터 수 | 134,644건 |

#### 4.5.2 HNSW 인덱스 튜닝 가이드

| 데이터 규모 | m | ef_construction | ef_search | 예상 Recall |
|------------|---|-----------------|-----------|-------------|
| <100K | 16 | 64 | 40 | 95%+ |
| 100K-1M | 24 | 128 | 100 | 95%+ |
| >1M | 32 | 200 | 200 | 95%+ |

**현재 데이터 (134,644건)**: m=16, ef_construction=64 → 적정

#### 4.5.3 인덱스 재생성 절차

```sql
-- 1. 기존 인덱스 삭제
DROP INDEX IF EXISTS idx_clause_embedding_hnsw;

-- 2. 새 인덱스 생성 (파라미터 변경 시)
CREATE INDEX idx_clause_embedding_hnsw
ON clause_embedding USING hnsw(embedding vector_cosine_ops)
WITH (m=24, ef_construction=128);

-- 3. 검색 성능 설정
SET hnsw.ef_search = 100;
```

#### 4.5.4 체크리스트

- [ ] `db/postgres/003_pgvector_setup.sql` 생성
- [ ] HNSW 파라미터 문서화
- [ ] 벡터 검색 벤치마크 스크립트 작성
- [ ] 기준선 성능 측정

---

### Phase 6: CI/CD 통합 (Day 11)

#### 4.6.1 GitHub Actions 워크플로우

**.github/workflows/schema-check.yml**:
```yaml
name: Schema Validation

on:
  push:
    paths: ['db/**', 'ingestion/**']
  pull_request:
    paths: ['db/**', 'ingestion/**']

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
        ports: ['5432:5432']

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install psycopg2-binary alembic python-dotenv

      - name: Initialize database
        env:
          POSTGRES_URL: postgresql://postgres:postgres@localhost:5432/insurance_ontology_test
        run: psql "$POSTGRES_URL" -f db/postgres/001_initial_schema.sql

      - name: Run migrations
        env:
          POSTGRES_URL: postgresql://postgres:postgres@localhost:5432/insurance_ontology_test
        run: cd db && alembic upgrade head

      - name: Verify schema
        env:
          POSTGRES_URL: postgresql://postgres:postgres@localhost:5432/insurance_ontology_test
        run: python db/scripts/verify_schema.py
```

#### 4.6.2 체크리스트

- [ ] GitHub Actions 워크플로우 작성
- [ ] PR 머지 시 자동 검증 확인
- [ ] 문서화 완료

---

## 5. 마이그레이션 규칙

### 5.1 버전 명명 규칙

```
{순번}_{설명}.py
예: 002_add_parent_coverage.py
```

### 5.2 작성 원칙

1. **항상 롤백 가능하게 작성** - upgrade/downgrade 모두 구현
2. **데이터 마이그레이션 분리** - 스키마 변경과 데이터 변경 별도
3. **트랜잭션 사용** - 원자적 실행 보장
4. **검증 쿼리 포함** - 마이그레이션 후 검증

---

## 6. 예상 리스크 및 대응

### 6.1 PostgreSQL 관련

| 리스크 | 영향 | 대응 방안 |
|--------|------|----------|
| 스키마 덤프 누락 | 일부 테이블/인덱스 빠짐 | 검증 스크립트로 확인 |
| 프로덕션 마이그레이션 실패 | 서비스 장애 | 스테이징에서 충분히 테스트 |
| 롤백 불완전 | 데이터 손실 | 백업 후 마이그레이션 실행 |

### 6.2 pgvector 관련

| 리스크 | 영향 | 대응 방안 |
|--------|------|----------|
| HNSW 인덱스 재생성 시간 | 134K 문서 → 수분 | 저트래픽 시간대 실행 |
| 임베딩 모델 변경 시 전체 재생성 | 3-4시간 + API 비용 | 배치 처리, 점진적 마이그레이션 |

### 6.3 Neo4j 관련

| 리스크 | 영향 | 대응 방안 |
|--------|------|----------|
| PostgreSQL ↔ Neo4j 불일치 | 잘못된 쿼리 결과 | 동기화 검증 스크립트 |
| 대량 동기화 시 성능 | Neo4j 부하 | 배치 처리 (1000건씩) |

---

## 7. 일정 요약

| Phase | 작업 | 기간 | 상태 |
|-------|------|------|------|
| Phase 1 | 스키마 추출 | Day 1-2 | 예정 |
| Phase 1.5 | 개념적 설계 문서 생성 (PostgreSQL + Neo4j) | Day 2-3 | 예정 |
| Phase 2 | Alembic 도입 | Day 4-5 | 예정 |
| Phase 3 | 스크립트 작성 | Day 6-7 | 예정 |
| Phase 4 | Neo4j 스키마 | Day 8-9 | 예정 |
| Phase 5 | pgvector 관리 | Day 10-11 | 예정 |
| Phase 6 | CI/CD 통합 | Day 12 | 예정 |
| **Phase 7** | **온톨로지 확장 (ontology_concept.md 반영)** | Day 13-15 | 예정 |

### 개념적 설계 문서 산출물

**PostgreSQL 문서**:

| 문서 | 설명 | 생성 방법 |
|------|------|----------|
| ER_DIAGRAM.md | E-R 다이어그램 (Mermaid) | 수동 작성 |
| DATA_DICTIONARY.md | 데이터 딕셔너리 | 자동 생성 (generate_docs.py) |
| RELATIONSHIP_MAP.md | 외래키 관계 | 자동 생성 (generate_docs.py) |
| DOMAIN_MODEL.md | 도메인 모델 설명 | 수동 작성 |

**Neo4j 문서**:

| 문서 | 설명 | 생성 방법 |
|------|------|----------|
| GRAPH_SCHEMA.md | 그래프 모델 개요 | 수동 작성 |
| NODE_DICTIONARY.md | 노드 레이블/속성 정의 | 수동 작성 |
| RELATIONSHIP_DICTIONARY.md | 관계 타입 정의 | 수동 작성 |
| GRAPH_PATTERNS.md | Cypher 쿼리 패턴 | 수동 작성 |
| ONTOLOGY_GAP_ANALYSIS.md | ontology_concept.md 대비 갭 분석 | 수동 작성 |

---

## 8. 참고 자료

- [Alembic 공식 문서](https://alembic.sqlalchemy.org/)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/current/)
- [database_status.md](./database_status.md) - 현재 DB 상태
- [ontology_concept.md](./design/ontology_concept.md) - 온톨로지 개념 설계
- [graph_loader.py](../ingestion/graph_loader.py) - Neo4j 동기화 구현체

---

**문서 버전**: 2.2
**최종 수정**: 2025-12-13
**변경 이력**:
- v1.0 (2025-12-13): 초기 작성
- v2.0 (2025-12-13): database_status.md 실제 DB 검증 결과 반영
- v2.1 (2025-12-13): Phase 1.5 개념적 설계 문서 생성 단계 추가
- v2.2 (2025-12-13): Neo4j 그래프 스키마 개념 분석 및 ontology_concept.md 대비 갭 분석 추가, Phase 7 온톨로지 확장 추가
