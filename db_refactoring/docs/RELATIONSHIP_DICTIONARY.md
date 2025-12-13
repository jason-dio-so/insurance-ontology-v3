# 관계 사전 (Relationship Dictionary)

> 작성일: 2025-12-13

## 개요

Neo4j 그래프 데이터베이스의 관계 타입별 정의입니다.

---

## 1. HAS_PRODUCT

**보험사가 상품을 보유**

### 정의

| 항목 | 값 |
|------|-----|
| 시작 노드 | Company |
| 끝 노드 | Product |
| 방향 | Company → Product |
| 카디널리티 | 1:N |
| 수량 | 8 |

### Cypher 예시

```cypher
-- 생성
MATCH (c:Company {company_code: 'samsung'})
MATCH (p:Product {product_code: 'myhealthpartner'})
MERGE (c)-[:HAS_PRODUCT]->(p)

-- 조회: 삼성의 모든 상품
MATCH (c:Company {company_code: 'samsung'})-[:HAS_PRODUCT]->(p:Product)
RETURN p.product_name
```

### 속성

없음 (관계 자체에 속성 없음)

---

## 2. HAS_VARIANT

**상품이 변형을 보유**

### 정의

| 항목 | 값 |
|------|-----|
| 시작 노드 | Product |
| 끝 노드 | ProductVariant |
| 방향 | Product → ProductVariant |
| 카디널리티 | 1:N |
| 수량 | 4 |

### Cypher 예시

```cypher
-- 조회: 롯데 상품의 변형
MATCH (c:Company {company_code: 'lotte'})-[:HAS_PRODUCT]->(p:Product)
      -[:HAS_VARIANT]->(v:ProductVariant)
RETURN v.variant_name, v.target_gender
```

### 비고

- 롯데: 남성용/여성용 (성별 분리)
- DB: 40세 이하/41세 이상 (연령 분리)

---

## 3. OFFERS

**상품이 담보를 제공**

### 정의

| 항목 | 값 |
|------|-----|
| 시작 노드 | Product |
| 끝 노드 | Coverage |
| 방향 | Product → Coverage |
| 카디널리티 | 1:N |
| 수량 | 363 |

### Cypher 예시

```cypher
-- 조회: 특정 상품의 모든 담보
MATCH (p:Product {product_code: 'myhealthpartner'})-[:OFFERS]->(c:Coverage)
RETURN c.coverage_name, c.coverage_category
ORDER BY c.coverage_name

-- 조회: 암진단 카테고리 담보
MATCH (p:Product)-[:OFFERS]->(c:Coverage)
WHERE c.coverage_category = '암진단'
RETURN p.product_name, c.coverage_name
```

### 비고

- 한 상품당 평균 45개 담보

---

## 4. HAS_BENEFIT

**담보가 급부를 포함**

### 정의

| 항목 | 값 |
|------|-----|
| 시작 노드 | Coverage |
| 끝 노드 | Benefit |
| 방향 | Coverage → Benefit |
| 카디널리티 | 1:N |
| 수량 | 357 |

### Cypher 예시

```cypher
-- 조회: 담보의 급부 목록
MATCH (c:Coverage {coverage_name: '암진단금'})-[:HAS_BENEFIT]->(b:Benefit)
RETURN b.benefit_name, b.benefit_type, b.benefit_amount

-- 조회: 진단금 타입 급부
MATCH (c:Coverage)-[:HAS_BENEFIT]->(b:Benefit {benefit_type: 'diagnosis'})
RETURN c.coverage_name, b.benefit_name, b.benefit_amount
ORDER BY b.benefit_amount DESC
```

---

## 5. HAS_DOCUMENT

**보험사가 문서를 발행**

### 정의

| 항목 | 값 |
|------|-----|
| 시작 노드 | Company |
| 끝 노드 | Document |
| 방향 | Company → Document |
| 카디널리티 | 1:N |
| 수량 | ~38 |

### Cypher 예시

```cypher
-- 조회: 보험사의 모든 문서
MATCH (c:Company {company_code: 'samsung'})-[:HAS_DOCUMENT]->(d:Document)
RETURN d.doc_type, d.document_id

-- 조회: 약관 문서만
MATCH (c:Company)-[:HAS_DOCUMENT]->(d:Document {doc_type: 'terms'})
RETURN c.company_name, d.document_id
```

---

## 6. CONTAINS

**질병코드 집합이 코드를 포함**

### 정의

| 항목 | 값 |
|------|-----|
| 시작 노드 | DiseaseCodeSet |
| 끝 노드 | DiseaseCode |
| 방향 | DiseaseCodeSet → DiseaseCode |
| 카디널리티 | 1:N |
| 수량 | 131 |

### Cypher 예시

```cypher
-- 조회: 악성신생물 코드 목록
MATCH (s:DiseaseCodeSet {set_name: '악성신생물'})-[:CONTAINS]->(d:DiseaseCode)
RETURN d.code, d.description_kr
ORDER BY d.code

-- 조회: C34 코드가 속한 집합
MATCH (s:DiseaseCodeSet)-[:CONTAINS]->(d:DiseaseCode {code: 'C34'})
RETURN s.set_name, d.description_kr
```

---

## 미구현 관계 (향후 추가 예정)

### PARENT_OF

**담보 계층 관계**

| 항목 | 값 |
|------|-----|
| 시작 노드 | Coverage |
| 끝 노드 | Coverage |
| 방향 | Parent → Child |
| 예상 수량 | 52 |

```cypher
-- 예시: 일반암 → 고액암, 소액암
(Coverage:일반암)-[:PARENT_OF]->(Coverage:고액암)
(Coverage:일반암)-[:PARENT_OF]->(Coverage:소액암)
```

### HAS_CONDITION

**담보의 보장 조건**

| 항목 | 값 |
|------|-----|
| 시작 노드 | Coverage |
| 끝 노드 | Condition |
| 방향 | Coverage → Condition |

### HAS_EXCLUSION

**담보의 제외 사항**

| 항목 | 값 |
|------|-----|
| 시작 노드 | Coverage |
| 끝 노드 | Exclusion |
| 방향 | Coverage → Exclusion |

---

## 관계 요약

### 현재 구현

| 관계 | From → To | 수량 | 상태 |
|------|-----------|------|------|
| HAS_PRODUCT | Company → Product | 8 | ✅ |
| HAS_VARIANT | Product → ProductVariant | 4 | ✅ |
| OFFERS | Product → Coverage | 363 | ✅ |
| HAS_BENEFIT | Coverage → Benefit | 357 | ✅ |
| HAS_DOCUMENT | Company → Document | ~38 | ✅ |
| CONTAINS | DiseaseCodeSet → DiseaseCode | 131 | ✅ |

### 미구현

| 관계 | From → To | 우선순위 |
|------|-----------|----------|
| PARENT_OF | Coverage → Coverage | 높음 |
| HAS_CONDITION | Coverage → Condition | 중간 |
| HAS_EXCLUSION | Coverage → Exclusion | 중간 |
| TRIGGERS | Benefit → RiskEvent | 낮음 |

---

## 참고 문서

- [GRAPH_SCHEMA.md](./GRAPH_SCHEMA.md) - 그래프 스키마 개요
- [NODE_DICTIONARY.md](./NODE_DICTIONARY.md) - 노드 속성 정의
- [GRAPH_PATTERNS.md](./GRAPH_PATTERNS.md) - Cypher 쿼리 패턴
