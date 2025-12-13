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
| 노드 수 | 640 |
| 관계 수 | 623 |
| 노드 레이블 | 8개 |
| 관계 타입 | 6개 |

---

## 2. 그래프 모델

### 2.1 전체 구조

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

### 2.2 노드 레이블

| 레이블 | 수량 | 설명 |
|--------|------|------|
| Company | 8 | 보험사 |
| Product | 8 | 보험 상품 |
| ProductVariant | 4 | 상품 변형 |
| Coverage | 363 | 담보 |
| Benefit | 357 | 급부 |
| Document | 38 | 문서 |
| DiseaseCodeSet | 9 | 질병코드 집합 |
| DiseaseCode | 131 | 질병 코드 |

### 2.3 관계 타입

| 관계 | 시작 노드 | 끝 노드 | 수량 | 설명 |
|------|-----------|---------|------|------|
| HAS_PRODUCT | Company | Product | 8 | 보험사가 상품 보유 |
| HAS_VARIANT | Product | ProductVariant | 4 | 상품 변형 |
| OFFERS | Product | Coverage | 363 | 상품이 담보 제공 |
| HAS_BENEFIT | Coverage | Benefit | 357 | 담보가 급부 포함 |
| HAS_DOCUMENT | Company | Document | ~38 | 보험사가 문서 발행 |
| CONTAINS | DiseaseCodeSet | DiseaseCode | 131 | 질병코드 집합에 코드 포함 |

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

### 4.1 현재 제약조건

```cypher
-- 유니크 제약 (자동 인덱스 생성)
CREATE CONSTRAINT company_code IF NOT EXISTS
FOR (c:Company) REQUIRE c.company_code IS UNIQUE;

CREATE CONSTRAINT product_id IF NOT EXISTS
FOR (p:Product) REQUIRE p.pg_id IS UNIQUE;

CREATE CONSTRAINT coverage_id IF NOT EXISTS
FOR (c:Coverage) REQUIRE c.pg_id IS UNIQUE;

CREATE CONSTRAINT benefit_id IF NOT EXISTS
FOR (b:Benefit) REQUIRE b.pg_id IS UNIQUE;
```

### 4.2 권장 추가 인덱스

```cypher
-- 이름 검색용
CREATE INDEX coverage_name IF NOT EXISTS
FOR (c:Coverage) ON (c.coverage_name);

-- 코드 검색용
CREATE INDEX disease_code IF NOT EXISTS
FOR (d:DiseaseCode) ON (d.code);
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

## 6. 확장 계획

### 6.1 미구현 관계

| 관계 | 시작 | 끝 | 우선순위 | 설명 |
|------|------|-----|----------|------|
| PARENT_OF | Coverage | Coverage | 높음 | 담보 계층 (52개 자식 담보) |
| HAS_CONDITION | Coverage | Condition | 중간 | 보장 조건 |
| HAS_EXCLUSION | Coverage | Exclusion | 중간 | 제외 사항 |
| TRIGGERS | Benefit | RiskEvent | 낮음 | 보험사고 연결 |

### 6.2 미구현 노드

| 노드 | 우선순위 | 설명 |
|------|----------|------|
| RiskEvent | 높음 | 보험사고 (진단, 사망 등) |
| Condition | 중간 | 보장 조건 |
| Exclusion | 중간 | 제외 사항 |
| Plan | 낮음 | 가입설계서 |

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
| [`../neo4j/001_graph_schema.cypher`](../neo4j/001_graph_schema.cypher) | Neo4j DDL (제약조건, 인덱스) | ⬜ Phase 4.1에서 생성 예정 |
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

### 구현 우선순위 (Phase 4)

| 태스크 | 파일 | 우선순위 |
|--------|------|----------|
| 4.1 | 001_graph_schema.cypher | 높음 |
| 4.5 | graph_loader.py에 PARENT_OF 관계 추가 | 높음 |

---

## 참고 문서

- [NODE_DICTIONARY.md](./NODE_DICTIONARY.md) - 노드별 속성 정의
- [RELATIONSHIP_DICTIONARY.md](./RELATIONSHIP_DICTIONARY.md) - 관계 타입 정의
- [GRAPH_PATTERNS.md](./GRAPH_PATTERNS.md) - 자주 사용되는 Cypher 패턴
- [ONTOLOGY_GAP_ANALYSIS.md](./ONTOLOGY_GAP_ANALYSIS.md) - 온톨로지 갭 분석
