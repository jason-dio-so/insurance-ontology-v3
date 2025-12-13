# Cypher 쿼리 패턴 (Graph Patterns)

> 작성일: 2025-12-13

## 개요

Neo4j 그래프 데이터베이스에서 자주 사용되는 Cypher 쿼리 패턴 모음입니다.

---

## 1. 기본 조회 패턴

### 1.1 노드 조회

```cypher
-- 모든 보험사 조회
MATCH (c:Company)
RETURN c.company_code, c.company_name
ORDER BY c.company_name;

-- 특정 보험사 조회
MATCH (c:Company {company_code: "samsung"})
RETURN c;

-- 이름으로 담보 검색 (부분 일치)
MATCH (c:Coverage)
WHERE c.coverage_name CONTAINS "암진단"
RETURN c.coverage_name, c.coverage_category
LIMIT 20;
```

### 1.2 노드 수량 확인

```cypher
-- 레이블별 노드 수
MATCH (n)
RETURN labels(n)[0] AS label, count(n) AS count
ORDER BY count DESC;

-- 보험사별 담보 수
MATCH (company:Company)-[:HAS_PRODUCT]->(product:Product)-[:OFFERS]->(coverage:Coverage)
RETURN company.company_name, count(coverage) AS coverage_count
ORDER BY coverage_count DESC;
```

---

## 2. 계층 탐색 패턴

### 2.1 회사 → 상품 → 담보 경로

```cypher
-- 특정 보험사의 전체 구조 조회
MATCH path = (company:Company {company_code: "samsung"})
              -[:HAS_PRODUCT]->(product:Product)
              -[:OFFERS]->(coverage:Coverage)
              -[:HAS_BENEFIT]->(benefit:Benefit)
RETURN path
LIMIT 50;
```

### 2.2 상품별 담보 조회

```cypher
-- 특정 상품의 모든 담보
MATCH (p:Product {product_code: "myhealthpartner"})-[:OFFERS]->(c:Coverage)
RETURN c.coverage_name, c.coverage_category, c.renewal_type
ORDER BY c.coverage_category, c.coverage_name;
```

### 2.3 담보별 급부 조회

```cypher
-- 특정 담보의 급부 목록
MATCH (c:Coverage)-[:HAS_BENEFIT]->(b:Benefit)
WHERE c.coverage_name CONTAINS "암진단금"
RETURN c.coverage_name, b.benefit_name, b.benefit_type, b.benefit_amount
ORDER BY c.coverage_name;
```

---

## 3. 비교 분석 패턴

### 3.1 보험사 간 담보 비교

```cypher
-- 두 보험사의 공통 담보 카테고리
MATCH (c1:Company {company_code: "samsung"})-[:HAS_PRODUCT]->()-[:OFFERS]->(cov1:Coverage)
MATCH (c2:Company {company_code: "db"})-[:HAS_PRODUCT]->()-[:OFFERS]->(cov2:Coverage)
WHERE cov1.coverage_category = cov2.coverage_category
RETURN DISTINCT cov1.coverage_category AS category
ORDER BY category;
```

### 3.2 카테고리별 담보 수 비교

```cypher
-- 보험사별, 카테고리별 담보 수
MATCH (company:Company)-[:HAS_PRODUCT]->(product:Product)-[:OFFERS]->(coverage:Coverage)
RETURN company.company_name, coverage.coverage_category, count(coverage) AS count
ORDER BY company.company_name, count DESC;
```

### 3.3 유사 담보 찾기

```cypher
-- 이름이 비슷한 담보 찾기
MATCH (c1:Coverage), (c2:Coverage)
WHERE c1.pg_id < c2.pg_id
  AND c1.coverage_name CONTAINS "암진단"
  AND c2.coverage_name CONTAINS "암진단"
RETURN c1.coverage_name, c2.coverage_name
LIMIT 20;
```

---

## 4. 관계 분석 패턴

### 4.1 경로 길이 조회

```cypher
-- 회사에서 급부까지의 경로
MATCH path = (company:Company)-[*..4]->(benefit:Benefit)
RETURN company.company_name,
       length(path) AS path_length,
       [node IN nodes(path) | labels(node)[0]] AS node_types
LIMIT 10;
```

### 4.2 관계 타입별 통계

```cypher
-- 관계 타입별 수량
MATCH ()-[r]->()
RETURN type(r) AS relationship_type, count(r) AS count
ORDER BY count DESC;
```

### 4.3 고아 노드 확인

```cypher
-- 관계가 없는 노드 찾기
MATCH (n)
WHERE NOT (n)--()
RETURN labels(n)[0] AS label, count(n) AS orphan_count;
```

---

## 5. 질병코드 패턴

### 5.1 질병코드 집합 조회

```cypher
-- 질병코드 집합과 코드 목록
MATCH (set:DiseaseCodeSet)-[:CONTAINS]->(code:DiseaseCode)
RETURN set.set_name, collect(code.code) AS codes
ORDER BY set.set_name;
```

### 5.2 특정 코드 검색

```cypher
-- 특정 질병코드가 속한 집합 찾기
MATCH (set:DiseaseCodeSet)-[:CONTAINS]->(code:DiseaseCode {code: "C34"})
RETURN set.set_name, code.description_kr;
```

---

## 6. 집계 및 통계 패턴

### 6.1 담보 카테고리별 통계

```cypher
-- 카테고리별 담보/급부 수
MATCH (c:Coverage)-[:HAS_BENEFIT]->(b:Benefit)
RETURN c.coverage_category,
       count(DISTINCT c) AS coverage_count,
       count(b) AS benefit_count
ORDER BY coverage_count DESC;
```

### 6.2 급부 타입별 통계

```cypher
-- 급부 타입별 평균 금액
MATCH (b:Benefit)
WHERE b.benefit_amount IS NOT NULL
RETURN b.benefit_type,
       count(b) AS count,
       avg(b.benefit_amount) AS avg_amount,
       max(b.benefit_amount) AS max_amount
ORDER BY count DESC;
```

### 6.3 문서 통계

```cypher
-- 보험사별 문서 수
MATCH (company:Company)-[:HAS_DOCUMENT]->(doc:Document)
RETURN company.company_name, doc.doc_type, count(doc) AS count
ORDER BY company.company_name, count DESC;
```

---

## 7. 동기화 검증 패턴

### 7.1 데이터 일관성 확인

```cypher
-- PostgreSQL ID 중복 확인
MATCH (c:Coverage)
WITH c.pg_id AS id, count(*) AS cnt
WHERE cnt > 1
RETURN id, cnt;
```

### 7.2 관계 무결성 확인

```cypher
-- 상품 없는 담보 찾기
MATCH (c:Coverage)
WHERE NOT ()-[:OFFERS]->(c)
RETURN c.pg_id, c.coverage_name;

-- 급부 없는 담보 찾기
MATCH (c:Coverage)
WHERE NOT (c)-[:HAS_BENEFIT]->()
RETURN c.pg_id, c.coverage_name
LIMIT 20;
```

### 7.3 엔티티 수량 검증

```cypher
-- 전체 엔티티 수량 (PostgreSQL과 비교용)
MATCH (n)
RETURN labels(n)[0] AS entity, count(n) AS count
ORDER BY entity;
```

---

## 8. 데이터 조작 패턴

### 8.1 노드 생성 (MERGE)

```cypher
-- 보험사 생성/갱신
MERGE (c:Company {company_code: "test"})
SET c.company_name = "테스트보험",
    c.pg_id = 999
RETURN c;
```

### 8.2 관계 생성

```cypher
-- 관계 생성
MATCH (company:Company {company_code: "samsung"})
MATCH (product:Product {pg_id: 1})
MERGE (company)-[:HAS_PRODUCT]->(product);
```

### 8.3 일괄 삭제

```cypher
-- 특정 보험사의 모든 데이터 삭제 (주의!)
MATCH (company:Company {company_code: "test"})-[*0..]->(n)
DETACH DELETE company, n;
```

---

## 9. 성능 최적화 패턴

### 9.1 인덱스 활용

```cypher
-- 인덱스가 있는 속성으로 조회 시작
MATCH (c:Coverage)
WHERE c.pg_id = 100  -- 인덱스 사용
RETURN c;

-- EXPLAIN으로 쿼리 계획 확인
EXPLAIN MATCH (c:Company)-[:HAS_PRODUCT]->(p:Product)
WHERE c.company_code = "samsung"
RETURN p;
```

### 9.2 결과 제한

```cypher
-- LIMIT 사용으로 불필요한 데이터 방지
MATCH (c:Coverage)-[:HAS_BENEFIT]->(b:Benefit)
RETURN c.coverage_name, b.benefit_name
LIMIT 100;
```

### 9.3 프로파일링

```cypher
-- PROFILE로 실행 계획 및 통계 확인
PROFILE MATCH path = (c:Company)-[:HAS_PRODUCT]->(p:Product)-[:OFFERS]->(cov:Coverage)
WHERE c.company_code = "samsung"
RETURN path;
```

---

## 10. 유용한 유틸리티 패턴

### 10.1 스키마 정보 조회

```cypher
-- 노드 레이블 목록
CALL db.labels();

-- 관계 타입 목록
CALL db.relationshipTypes();

-- 속성 키 목록
CALL db.propertyKeys();

-- 인덱스 목록
SHOW INDEXES;

-- 제약조건 목록
SHOW CONSTRAINTS;
```

### 10.2 데이터베이스 통계

```cypher
-- 전체 노드/관계 수
MATCH (n) RETURN count(n) AS total_nodes;
MATCH ()-[r]->() RETURN count(r) AS total_relationships;
```

---

## 참고 문서

- [GRAPH_SCHEMA.md](./GRAPH_SCHEMA.md) - 그래프 스키마 개요
- [NODE_DICTIONARY.md](./NODE_DICTIONARY.md) - 노드별 속성 정의
- [RELATIONSHIP_DICTIONARY.md](./RELATIONSHIP_DICTIONARY.md) - 관계 타입 정의
