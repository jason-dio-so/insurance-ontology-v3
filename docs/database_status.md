# 데이터베이스 현황 분석 리포트

**작성일**: 2025-12-13
**마지막 검증일**: 2025-12-13 (실제 DB 연결 확인)
**DB 생성일**: 2025-12-09
**마지막 마이그레이션**: 2025-12-11

---

## 1. 시스템 개요

**Hybrid RAG 시스템**: 한국 보험 상품 문서를 처리하기 위한 시스템

| 항목 | 내용 |
|------|------|
| **PostgreSQL** | 주 데이터 저장소 (관계형 + pgvector 벡터 인덱스) |
| **Neo4j** | 그래프 쿼리 보조 (PostgreSQL에서 동기화) |
| **QA 정확도** | 86% (43/50 질의) |
| **무결과율** | 0% (5-Tier Fallback) |

---

## 2. 데이터베이스 연결 정보

```bash
# PostgreSQL
POSTGRES_URL=postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme123
```

---

## 3. 온톨로지 구현 현황

### 3.1 엔티티 구현 상태

| 구분 | 개수 | 비율 | 상태 |
|------|------|------|------|
| **완전 구현** | 7/10 | 70% | ✅ |
| **부분 구현** | 1/10 | 10% | ⚠️ |
| **미구현** | 2/10 | 20% | ❌ |
| **추가 구현** | 4개 | - | ➕ |

### 3.2 엔티티별 상세

| 초기 개념 | 실제 구현 | 레코드 수 | 상태 | 비고 |
|-----------|----------|----------|------|------|
| Company | `company` | 8 | ✅ 100% | - |
| Product | `product` | 8 | ✅ 100% | - |
| ProductVariant | `product_variant` | 4 | ✅ 100% | 롯데(성별), DB(연령) |
| Coverage | `coverage` | 363 | ✅ 100% | parent_coverage_id 추가 |
| Benefit | `benefit` | 357 | ✅ 100% | - |
| Condition/Exclusion | `condition`, `exclusion` | 0 | ✅ 100% | 스키마만 존재, 미사용 |
| Disease/Code | `disease_code_set`, `disease_code` | 9/131 | ✅ 100% | - |
| Document/Clause | `document`, `document_clause` | 38/134,844 | ⚠️ 70% | DocumentSection 미구현 |
| RiskEvent | ❌ | - | ❌ 0% | Phase 6 계획 |
| Plan | ❌ | - | ❌ 0% | Phase 6 계획 |

### 3.3 추가 구현 (초기 개념에 없음)

| 추가 구현 | 레코드 수 | 목적 |
|-----------|----------|------|
| `clause_embedding` | 134,644 | 벡터 검색 (1536차원, HNSW) |
| `clause_coverage` | 4,903 | 조항↔담보 N:M 매핑 |
| `coverage.parent_coverage_id` | 52 자식 | 담보 계층 구조 |
| `coverage_category` | 9 | 담보 분류 |

---

## 4. PostgreSQL 상세 분석 (실제 DB 검증)

### 4.1 테이블 현황

| 테이블 | 행 수 | 컬럼 수 | 설명 | 상태 |
|--------|-------|--------|------|------|
| **document_clause** | 134,844 | 14 | 문서 조항 (핵심) | ✅ 사용 중 |
| **clause_embedding** | 134,644 | 6 | 벡터 임베딩 | ✅ 사용 중 |
| **clause_coverage** | 4,903 | 6 | 조항↔담보 매핑 | ✅ 사용 중 |
| **coverage** | 363 | 11 | 담보 정보 | ✅ 사용 중 |
| **benefit** | 357 | 10 | 보장 혜택 | ✅ 사용 중 |
| **disease_code** | 131 | 7 | 질병 코드 | ✅ 사용 중 |
| **document** | 38 | 13 | 문서 메타데이터 | ✅ 사용 중 |
| **coverage_category** | 9 | 8 | 담보 카테고리 | ✅ 사용 중 |
| **disease_code_set** | 9 | 6 | 질병코드 세트 | ✅ 사용 중 |
| **product** | 8 | 9 | 상품 | ✅ 사용 중 |
| **company** | 8 | 6 | 보험사 | ✅ 사용 중 |
| **product_variant** | 4 | 11 | 상품 변형 | ✅ 사용 중 |
| **coverage_group** | 0 | 13 | 담보 그룹 | ⚠️ 미사용 |
| **condition** | 0 | 10 | 조건 | ⚠️ 미사용 |
| **exclusion** | 0 | 8 | 면책사항 | ⚠️ 미사용 |

### 4.2 보험사 현황

| company_code | company_name | 담보 수 |
|--------------|--------------|---------|
| meritz | 메리츠 | 98 |
| hanwha | 한화 | 64 |
| lotte | 롯데 | 63 |
| samsung | 삼성 | 39 |
| kb | KB | 36 |
| heungkuk | 흥국 | 23 |
| db | DB | 22 |
| hyundai | 현대 | 18 |

### 4.3 조항 타입 분포

| clause_type | 수량 | 비율 | 출처 |
|-------------|------|------|------|
| article | 129,667 | 96.2% | TextParser (약관) |
| text_block | 4,286 | 3.2% | HybridParserV2 (사업방법서/상품요약서) |
| table_row | 891 | 0.7% | Carrier-Specific Parsers (가입설계서) |

### 4.4 문서 타입 분포

| doc_type | 수량 | 설명 |
|----------|------|------|
| proposal | 10 | 가입설계서 (DB 연령분리, 롯데 성별분리 포함) |
| terms | 9 | 약관 |
| business_spec | 9 | 사업방법서 |
| product_summary | 9 | 상품요약서 |
| easy_summary | 1 | 삼성 쉬운요약서 |

### 4.5 조항-담보 매핑 방법

| extraction_method | 수량 | 비율 | 설명 |
|-------------------|------|------|------|
| parent_coverage_linking | 3,889 | 79.3% | 부모 담보 계층 자동 매핑 |
| exact_match | 829 | 16.9% | structured_data 정확 매칭 |
| fuzzy_match | 185 | 3.8% | 문자열 유사도 매칭 |

### 4.6 담보 계층 구조

| 유형 | 수량 | 설명 |
|------|------|------|
| 부모 담보 (is_basic=true) | 9 | 일반암, 뇌혈관질환, 뇌졸중, 뇌출혈, 허혈심장질환, 급성심근경색, 기본계약(3개) |
| 자식 담보 | 52 | parent_coverage_id 연결 |
| 독립 담보 | 302 | 부모/자식 관계 없음 |

**부모 담보 목록**:
| ID | coverage_name | coverage_code |
|----|---------------|---------------|
| 405 | 일반암 | general_cancer |
| 406 | 뇌혈관질환 | cerebrovascular |
| 407 | 뇌졸중 | stroke |
| 408 | 뇌출혈 | cerebral_hemorrhage |
| 409 | 허혈심장질환 | ischemic_heart |
| 410 | 급성심근경색 | acute_mi |
| 121 | 기본계약(상해후유장해) | 기본계약상해후유장해 |
| 123 | 기본계약(상해사망) | 기본계약상해사망 |
| 175 | 기본계약 | 기본계약 |

### 4.7 급부 타입 분포

| benefit_type | 수량 | 비율 |
|--------------|------|------|
| diagnosis | 118 | 33.1% |
| other | 78 | 21.8% |
| treatment | 74 | 20.7% |
| surgery | 67 | 18.8% |
| death | 20 | 5.6% |

### 4.8 상품 변형 현황

| variant_name | company | target_gender | target_age_range |
|--------------|---------|---------------|------------------|
| female | 롯데 | female | - |
| male | 롯데 | male | - |
| age_40_under | DB | - | ≤40 |
| age_41_over | DB | - | ≥41 |

---

## 5. 인덱스 현황

### 5.1 총 인덱스: 52개

### 5.2 주요 인덱스

| 테이블 | 인덱스 | 유형 | 용도 |
|--------|--------|------|------|
| clause_embedding | idx_clause_embedding_hnsw | HNSW | 벡터 유사도 검색 |
| clause_embedding | idx_clause_embedding_metadata_gin | GIN | 메타데이터 필터링 |
| document_clause | idx_structured_data_gin | GIN | JSONB 검색 |
| document_clause | idx_structured_coverage_amount | B-tree | 금액 필터링 |
| document_clause | idx_structured_premium | B-tree | 보험료 필터링 |
| coverage | idx_coverage_parent | B-tree | 계층 조회 |
| coverage | idx_coverage_name | B-tree | 담보명 검색 |

### 5.3 pgvector 설정

| 항목 | 값 |
|------|-----|
| Extension | pgvector 0.8.1 |
| 차원 | 1536 (OpenAI text-embedding-3-small) |
| 인덱스 | HNSW (m=16, ef_construction=64) |
| 거리 함수 | vector_cosine_ops |

---

## 6. Neo4j 그래프 구조

### 6.1 노드 및 관계

```
(Company)──[:HAS_PRODUCT]──>(Product)
     │                          │
     │                    [:HAS_VARIANT]
     │                          ↓
[:HAS_DOCUMENT]           (ProductVariant)
     ↓                          │
(Document)                 [:OFFERS]
                               ↓
                          (Coverage)
                               │
                         [:HAS_BENEFIT]
                               ↓
                          (Benefit)

(DiseaseCodeSet)──[:CONTAINS]──>(DiseaseCode)
```

### 6.2 통계

| 항목 | 수량 |
|------|------|
| 노드 | 640 |
| 관계 | 623 |

---

## 7. 데이터 파이프라인

```
38 PDFs (8 보험사)
      ↓
Phase 1: ingestion/ingest_v3.py
  → Parser: TextParser / HybridParserV2 / Carrier-Specific
  → PostgreSQL: document(38), document_clause(134,844)
      ↓
Phase 2: Entity Extraction
  → coverage_pipeline.py: coverage(363)
  → extract_benefits.py: benefit(357)
  → load_disease_codes.py: disease_code_set(9), disease_code(131)
  → link_clauses.py: clause_coverage(4,903)
      ↓
Phase 3: ingestion/graph_loader.py
  → Neo4j: 640 nodes, 623 relationships
      ↓
Phase 4: vector_index/build_index.py
  → PostgreSQL pgvector: clause_embedding(134,644)
  → Model: OpenAI text-embedding-3-small (1536d)
      ↓
Phase 5: retrieval/hybrid_retriever.py
  → 5-tier fallback search + LLM (GPT-4o-mini)
```

---

## 8. 스키마 관리 현황 및 문제점

### 8.1 현재 상태

| 항목 | 상태 | 설명 |
|------|------|------|
| 스키마 파일 | ❌ 없음 | Python 코드에서 동적 생성 |
| 마이그레이션 추적 | ⚠️ 부분 | 1개 파일만 존재 |
| 롤백 가능성 | ❌ 없음 | 명시적 downgrade 없음 |

### 8.2 현재 디렉토리 구조

```
db/
└── migrations/
    └── 20251211_add_parent_coverage.sql  # 유일한 마이그레이션 파일
```

### 8.3 문제점

| 문제 | 영향 | 심각도 |
|------|------|--------|
| 명시적 스키마 파일 없음 | 초기 설치 시 테이블 생성 불가 | **높음** |
| 마이그레이션 추적 불가 | 스키마 변경 이력 파악 어려움 | **높음** |
| 롤백 불가능 | 문제 발생 시 복구 어려움 | **중간** |
| 환경별 스키마 불일치 | 개발/스테이징/프로덕션 차이 발생 | **높음** |

---

## 9. ONTOLOGY_IMPLEMENTATION_ANALYSIS.md 대비 차이점

### 9.1 일치하는 항목 ✅

| 항목 | 문서 값 | 실제 DB 값 | 상태 |
|------|---------|-----------|------|
| document_clause | 134,844 | 134,844 | ✅ 일치 |
| clause_embedding | 134,644 | 134,644 | ✅ 일치 |
| clause_coverage | 4,903 | 4,903 | ✅ 일치 |
| coverage | 363 | 363 | ✅ 일치 |
| benefit | 357 | 357 | ✅ 일치 |
| disease_code | 131 | 131 | ✅ 일치 |
| document | 38 | 38 | ✅ 일치 |
| company | 8 | 8 | ✅ 일치 |
| product | 8 | 8 | ✅ 일치 |
| product_variant | 4 | 4 | ✅ 일치 |
| 자식 담보 | 52 | 52 | ✅ 일치 |
| clause_type 분포 | 96.2%/3.2%/0.7% | 96.2%/3.2%/0.7% | ✅ 일치 |
| extraction_method 분포 | 79.3%/16.9%/3.8% | 79.3%/16.9%/3.8% | ✅ 일치 |

### 9.2 차이가 있는 항목 ⚠️

| 항목 | 문서 값 | 실제 DB 값 | 설명 |
|------|---------|-----------|------|
| 부모 담보 | 6개 | 9개 | 기본계약(3개) 추가됨 |
| 독립 담보 | 305개 | 302개 | 부모 담보 수 차이로 조정 |
| doc_type | product_summary에 easy_summary 포함 | easy_summary 별도 유형 | 실제로는 5개 유형 |
| 보험사별 담보 수 | Meritz 126, Lotte 57... | 메리츠 98, 롯데 63... | 수치 차이 |

---

## 10. 요약

| 항목 | 값 |
|------|-----|
| **주 데이터베이스** | PostgreSQL 15 + pgvector 0.8.1 |
| **그래프 DB** | Neo4j (보조, PostgreSQL에서 동기화) |
| **총 테이블** | 15개 (12개 사용 중, 3개 미사용) |
| **핵심 데이터** | document_clause (134,844건) |
| **벡터 임베딩** | 134,644건 (1536차원, HNSW) |
| **스키마 관리** | ⚠️ Python 코드 내 암묵적 생성 |
| **마이그레이션** | 1개 파일만 존재 |
| **온톨로지 구현율** | 70% 완전 구현, 10% 부분 구현 |
| **QA 정확도** | 86% (43/50 질의) |

---

## 11. 관련 파일

| 파일 | 설명 |
|------|------|
| `docs/design/ONTOLOGY_IMPLEMENTATION_ANALYSIS.md` | 온톨로지 개념 vs 구현 분석 |
| `docs/design/DESIGN.md` | 통합 설계 문서 |
| `db/migrations/20251211_add_parent_coverage.sql` | Coverage 계층 마이그레이션 |
| `ingestion/ingest_v3.py` | 문서 적재 파이프라인 |
| `ingestion/graph_loader.py` | Neo4j 동기화 |
| `vector_index/build_index.py` | 벡터 인덱스 생성 |

---

**문서 버전**: 2.0
**최종 수정**: 2025-12-13
**변경 이력**:
- v1.0 (2025-12-13): 초기 작성
- v2.0 (2025-12-13): 실제 DB 연결 검증, ONTOLOGY_IMPLEMENTATION_ANALYSIS.md 대비 차이점 추가
