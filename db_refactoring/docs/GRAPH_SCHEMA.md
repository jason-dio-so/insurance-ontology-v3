# Neo4j 그래프 스키마 (Graph Schema)

> 작성일: 2025-12-13

## 1. 개요

### 1.1 시스템 역할

Neo4j는 **PostgreSQL의 보조 데이터베이스**로, 다음 목적으로 사용됩니다:

| 용도 | 설명 |
|------|------|
| 그래프 탐색 | 보험사 → 상품 → 담보 계층 탐색 |
| 관계 시각화 | 엔티티 간 관계 시각화 |
| 패턴 쿼리 | 복잡한 관계 패턴 조회 |

### 1.2 데이터 동기화

```
PostgreSQL (원본)
      ↓
ingestion/graph_loader.py
      ↓
Neo4j (복제본)
```

**원칙**: PostgreSQL이 단일 진실 소스(Single Source of Truth)

### 1.3 현재 상태

| 항목 | 값 |
|------|-----|
| 노드 수 | 640+ |
| 관계 수 | 623+ |
| 노드 레이블 | 12개 |
| 관계 타입 | 13개 |

---

## 2. 그래프 모델

### 2.1 전체 구조

```
(Company)──[:HAS_PRODUCT]──>(Product)──[:HAS_VARIANT]──>(ProductVariant)
     │                          │
     │                     [:OFFERS]
     │                          ↓
[:HAS_DOCUMENT]            (Coverage)──[:PARENT_OF]──>(Coverage)
     ↓                          │
(Document)               [:HAS_BENEFIT]──[:HAS_EXCLUSION]──>(Exclusion)
     ↑                          ↓
[:FROM_DOCUMENT]           (Benefit)
     │                          │
  (Plan)               [:TRIGGERS]──[:HAS_CONDITION]
     │                     ↓              ↓
[:FOR_PRODUCT]──>(Product)  (RiskEvent)  (Condition)
[:INCLUDES]──>(Coverage)

(DiseaseCodeSet)──[:CONTAINS]──>(DiseaseCode)
```

### 2.2 노드 레이블

| 레이블 | 설명 | 주요 속성 |
|--------|------|-----------|
| Company | 보험사 | id, code, name, business_type |
| Product | 보험 상품 | id, code, name, business_type |
| ProductVariant | 상품 변형 | id, code, name, target_gender, target_age_range |
| Coverage | 담보 | id, code, name, category, renewal_type, is_basic |
| Benefit | 급부 | id, name, amount, amount_text, type |
| Document | 문서 | id, document_id, doc_type, doc_subtype, version, total_pages |
| DiseaseCodeSet | 질병코드 집합 | id, name, description, version |
| DiseaseCode | 질병 코드 | id, code, type, description |
| RiskEvent | 위험 이벤트 | id, event_type, event_name, severity_level, icd_code_pattern |
| Condition | 급여 조건 | id, condition_type, value, unit |
| Exclusion | 면책 조건 | id, exclusion_type, description |
| Plan | 가입설계 | id, plan_name, target_gender, target_age, insurance_period, payment_period, total_premium |

### 2.3 관계 타입

| 관계 | 시작 노드 | 끝 노드 | 설명 |
|------|-----------|---------|------|
| HAS_PRODUCT | Company | Product | 보험사가 상품 보유 |
| HAS_VARIANT | Product | ProductVariant | 상품 변형 |
| OFFERS | Product | Coverage | 상품이 담보 제공 |
| HAS_BENEFIT | Coverage | Benefit | 담보가 급부 포함 |
| HAS_DOCUMENT | Company/Product/ProductVariant | Document | 문서 발행 |
| CONTAINS | DiseaseCodeSet | DiseaseCode | 질병코드 집합에 코드 포함 |
| PARENT_OF | Coverage | Coverage | 담보 계층 (부모-자식) |
| TRIGGERS | Benefit | RiskEvent | 급부가 위험이벤트 트리거 |
| HAS_CONDITION | Benefit | Condition | 급부의 조건 |
| HAS_EXCLUSION | Coverage | Exclusion | 담보의 면책 조건 |
| FOR_PRODUCT | Plan | Product | 가입설계가 속한 상품 |
| INCLUDES | Plan | Coverage | 가입설계에 포함된 담보 (속성: sum_insured, premium) |
| FROM_DOCUMENT | Plan | Document | 가입설계의 출처 문서 |

---

## 3. 설계 원칙

### 3.1 단방향 관계

모든 관계는 **논리적 방향**을 따릅니다:

```
Company → Product → Coverage → Benefit
(보유)    (제공)    (포함)
```

### 3.2 속성 최소화

- 노드: 핵심 식별 속성만 저장 (id, code, name)
- 상세 정보는 PostgreSQL에서 조회

### 3.3 동기화 원칙

| 원칙 | 설명 |
|------|------|
| 전체 동기화 | graph_loader.py는 전체 데이터 동기화 |
| 멱등성 | MERGE 사용으로 중복 방지 |
| PostgreSQL ID 사용 | Neo4j 노드에 pg_id 속성 저장 |

---

## 4. 제약조건 및 인덱스

### 4.1 제약조건 (UNIQUE)

```cypher
-- Company
CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT company_code IF NOT EXISTS FOR (c:Company) REQUIRE c.code IS UNIQUE;

-- Product
CREATE CONSTRAINT product_id IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT product_code IF NOT EXISTS FOR (p:Product) REQUIRE p.code IS UNIQUE;

-- ProductVariant
CREATE CONSTRAINT product_variant_id IF NOT EXISTS FOR (pv:ProductVariant) REQUIRE pv.id IS UNIQUE;

-- Coverage
CREATE CONSTRAINT coverage_id IF NOT EXISTS FOR (c:Coverage) REQUIRE c.id IS UNIQUE;

-- Benefit
CREATE CONSTRAINT benefit_id IF NOT EXISTS FOR (b:Benefit) REQUIRE b.id IS UNIQUE;

-- Document
CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT document_document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.document_id IS UNIQUE;

-- DiseaseCodeSet / DiseaseCode
CREATE CONSTRAINT disease_code_set_id IF NOT EXISTS FOR (dcs:DiseaseCodeSet) REQUIRE dcs.id IS UNIQUE;
CREATE CONSTRAINT disease_code_id IF NOT EXISTS FOR (dc:DiseaseCode) REQUIRE dc.id IS UNIQUE;

-- 확장 노드
CREATE CONSTRAINT risk_event_id IF NOT EXISTS FOR (re:RiskEvent) REQUIRE re.id IS UNIQUE;
CREATE CONSTRAINT condition_id IF NOT EXISTS FOR (cond:Condition) REQUIRE cond.id IS UNIQUE;
CREATE CONSTRAINT exclusion_id IF NOT EXISTS FOR (ex:Exclusion) REQUIRE ex.id IS UNIQUE;
CREATE CONSTRAINT plan_id IF NOT EXISTS FOR (pl:Plan) REQUIRE pl.id IS UNIQUE;
```

### 4.2 인덱스

```cypher
-- 이름 검색
CREATE INDEX company_name IF NOT EXISTS FOR (c:Company) ON (c.name);
CREATE INDEX product_name IF NOT EXISTS FOR (p:Product) ON (p.name);
CREATE INDEX coverage_name IF NOT EXISTS FOR (c:Coverage) ON (c.name);
CREATE INDEX coverage_category IF NOT EXISTS FOR (c:Coverage) ON (c.category);
CREATE INDEX benefit_name IF NOT EXISTS FOR (b:Benefit) ON (b.name);
CREATE INDEX benefit_type IF NOT EXISTS FOR (b:Benefit) ON (b.type);

-- 문서/코드 검색
CREATE INDEX document_doc_type IF NOT EXISTS FOR (d:Document) ON (d.doc_type);
CREATE INDEX disease_code_code IF NOT EXISTS FOR (dc:DiseaseCode) ON (dc.code);
CREATE INDEX disease_code_type IF NOT EXISTS FOR (dc:DiseaseCode) ON (dc.type);

-- 확장 노드 인덱스
CREATE INDEX risk_event_event_type IF NOT EXISTS FOR (re:RiskEvent) ON (re.event_type);
CREATE INDEX condition_condition_type IF NOT EXISTS FOR (cond:Condition) ON (cond.condition_type);
CREATE INDEX exclusion_exclusion_type IF NOT EXISTS FOR (ex:Exclusion) ON (ex.exclusion_type);
CREATE INDEX plan_product_id IF NOT EXISTS FOR (pl:Plan) ON (pl.product_id);
CREATE INDEX plan_target_gender IF NOT EXISTS FOR (pl:Plan) ON (pl.target_gender);
```

---

## 5. 데이터 흐름

### 5.1 동기화 프로세스

```python
# graph_loader.py 핵심 로직
1. PostgreSQL에서 데이터 조회
2. MERGE로 노드 생성/갱신
3. MERGE로 관계 생성

# 실행 순서
1. Company 노드 생성
2. Product 노드 + HAS_PRODUCT 관계
3. ProductVariant 노드 + HAS_VARIANT 관계
4. Coverage 노드 + OFFERS 관계
5. Benefit 노드 + HAS_BENEFIT 관계
6. Document 노드 + HAS_DOCUMENT 관계
7. DiseaseCodeSet, DiseaseCode 노드 + CONTAINS 관계
```

### 5.2 동기화 명령

```bash
# 전체 동기화
python ingestion/graph_loader.py --sync-all

# 개별 동기화
python ingestion/graph_loader.py --sync-companies
python ingestion/graph_loader.py --sync-products
python ingestion/graph_loader.py --sync-coverages
python ingestion/graph_loader.py --sync-benefits
```

---

## 6. 스키마 확장 이력

### 6.1 구현된 확장 관계

| 관계 | 시작 | 끝 | 상태 | 설명 |
|------|------|-----|------|------|
| PARENT_OF | Coverage | Coverage | ✅ 구현됨 | 담보 계층 (52개 자식 담보) |
| HAS_CONDITION | Benefit | Condition | ✅ 구현됨 | 급부 조건 |
| HAS_EXCLUSION | Coverage | Exclusion | ✅ 구현됨 | 제외 사항 |
| TRIGGERS | Benefit | RiskEvent | ✅ 구현됨 | 보험사고 연결 |
| FOR_PRODUCT | Plan | Product | ✅ 구현됨 | 가입설계 상품 연결 |
| INCLUDES | Plan | Coverage | ✅ 구현됨 | 가입설계 담보 포함 |
| FROM_DOCUMENT | Plan | Document | ✅ 구현됨 | 가입설계 출처 문서 |

### 6.2 구현된 확장 노드

| 노드 | 상태 | 설명 |
|------|------|------|
| RiskEvent | ✅ 구현됨 | 보험사고 (진단, 사망 등) |
| Condition | ✅ 구현됨 | 보장 조건 |
| Exclusion | ✅ 구현됨 | 제외 사항 |
| Plan | ✅ 구현됨 | 가입설계서 |

---

## 7. 연결 정보

```bash
# Neo4j 연결
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme123
```

---

## 8. 구현 파일

이 설계 문서는 다음 파일로 구현됩니다:

| 구현 파일 | 설명 | 상태 |
|-----------|------|------|
| [`../neo4j/001_graph_schema.cypher`](../neo4j/001_graph_schema.cypher) | Neo4j DDL (제약조건, 인덱스) | ✅ 구현됨 |
| [`../../ingestion/graph_loader.py`](../../ingestion/graph_loader.py) | PostgreSQL → Neo4j 동기화 스크립트 | ✅ 구현됨 |

### 설계 → 구현 흐름

```
GRAPH_SCHEMA.md (이 문서)
    │
    ├── NODE_DICTIONARY.md (노드 속성 상세)
    ├── RELATIONSHIP_DICTIONARY.md (관계 타입 상세)
    ├── GRAPH_PATTERNS.md (Cypher 쿼리 패턴)
    └── ONTOLOGY_GAP_ANALYSIS.md (갭 분석)
            │
            ↓ 구현
    neo4j/001_graph_schema.cypher (DDL)
    ingestion/graph_loader.py (동기화)
            │
            ↓ 적용
    Neo4j 데이터베이스
```

---

## 참고 문서

- [NODE_DICTIONARY.md](./NODE_DICTIONARY.md) - 노드별 속성 정의
- [RELATIONSHIP_DICTIONARY.md](./RELATIONSHIP_DICTIONARY.md) - 관계 타입 정의
- [GRAPH_PATTERNS.md](./GRAPH_PATTERNS.md) - 자주 사용되는 Cypher 패턴
- [ONTOLOGY_GAP_ANALYSIS.md](./ONTOLOGY_GAP_ANALYSIS.md) - 온톨로지 갭 분석
