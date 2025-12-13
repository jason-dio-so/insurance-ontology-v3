# 온톨로지 갭 분석 (Ontology Gap Analysis)

> 작성일: 2025-12-13

## 개요

`ontology_concept.md` 설계 문서와 현재 Neo4j/PostgreSQL 구현 간의 차이를 분석합니다.

---

## 1. 엔티티 구현 현황

### 1.1 구현 완료 (✅)

| 설계 엔티티 | 현재 구현 | Neo4j 노드 | PostgreSQL 테이블 | 수량 |
|-------------|-----------|------------|-------------------|------|
| Company | ✅ 완료 | Company | company | 8 |
| Product | ✅ 완료 | Product | product | 8 |
| ProductVariant | ✅ 완료 | ProductVariant | product_variant | 4 |
| Coverage | ✅ 완료 | Coverage | coverage | 363 |
| Benefit | ✅ 완료 | Benefit | benefit | 357 |
| Disease/Code | ✅ 완료 | DiseaseCode | disease_code | 131 |
| DiseaseCodeSet | ✅ 완료 | DiseaseCodeSet | disease_code_set | 9 |
| Document | ✅ 완료 | Document | document | 38 |
| DocumentSection/Clause | ✅ 완료 | - | document_clause | 134,844 |

### 1.2 미구현 (❌)

| 설계 엔티티 | 우선순위 | 설명 | 구현 난이도 |
|-------------|----------|------|-------------|
| **RiskEvent** | 높음 | 보험사고 (사망, 장해, 암진단, 뇌졸중 등) | 중간 |
| **Condition** | 중간 | 보장 조건 (대기기간, 생존기간 등) | 낮음 |
| **Exclusion** | 중간 | 제외 사항 (면책사유, 계약전 알릴의무 등) | 낮음 |
| **Plan** | 낮음 | 가입설계서 기반 견적 단위 | 높음 |

---

## 2. 관계 구현 현황

### 2.1 구현 완료 (✅)

| 설계 관계 | 현재 구현 | 방향 | 수량 |
|-----------|-----------|------|------|
| Company → Product | HAS_PRODUCT | → | 8 |
| Product → ProductVariant | HAS_VARIANT | → | 4 |
| Product → Coverage | OFFERS | → | 363 |
| Coverage → Benefit | HAS_BENEFIT | → | 357 |
| DiseaseCodeSet → DiseaseCode | CONTAINS | → | 131 |
| Company → Document | HAS_DOCUMENT | → | ~38 |

### 2.2 미구현 (❌)

| 설계 관계 | 시작 노드 | 끝 노드 | 우선순위 | 설명 |
|-----------|-----------|---------|----------|------|
| **PARENT_OF** | Coverage | Coverage | 높음 | 담보 계층 (52개 자식 담보) |
| **TRIGGERS** | Benefit | RiskEvent | 높음 | 급부가 발동하는 보험사고 |
| **HAS_CONDITION** | Coverage | Condition | 중간 | 보장 조건 |
| **HAS_EXCLUSION** | Coverage | Exclusion | 중간 | 제외 사항 |
| **APPLIES_TO** | Benefit | DiseaseCodeSet | 중간 | 급부 적용 질병코드 |
| **INCLUDES** | Plan | Coverage | 낮음 | 설계서에 포함된 담보 |

---

## 3. 상세 갭 분석

### 3.1 RiskEvent (보험사고) 노드

**설계 명세**:
```
RiskEvent / InsuredEvent
- event_type: 사망, 장해, 암진단, 뇌졸중진단, 급성심근경색, 치매진단, 골절, 화상, 배상책임 등
- severity_level: 경증/중등도/중증/말기
```

**현재 상태**: 미구현

**갭 영향**:
- Benefit → RiskEvent 관계 누락
- "암 진단 시 보장되는 급부" 같은 쿼리 불가
- 보험사고 기반 비교 분석 불가

**구현 제안**:
```sql
-- PostgreSQL
CREATE TABLE risk_event (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,  -- diagnosis, death, hospitalization
    event_name VARCHAR(200) NOT NULL,  -- 암진단, 뇌졸중진단
    severity_level VARCHAR(50),  -- mild, moderate, severe, terminal
    icd_code_pattern VARCHAR(100)  -- 연관 ICD 코드 패턴
);

CREATE TABLE benefit_risk_event (
    benefit_id INTEGER REFERENCES benefit(id),
    risk_event_id INTEGER REFERENCES risk_event(id),
    PRIMARY KEY (benefit_id, risk_event_id)
);
```

```cypher
-- Neo4j
CREATE (re:RiskEvent {
    pg_id: 1,
    event_type: "diagnosis",
    event_name: "암진단",
    severity_level: "severe"
})

MATCH (b:Benefit), (re:RiskEvent)
WHERE b.pg_id = 100 AND re.pg_id = 1
CREATE (b)-[:TRIGGERS]->(re)
```

---

### 3.2 Condition (보장 조건) 노드

**설계 명세**:
```
Condition / Exclusion
- waiting_period (대기기간)
- survival_period (생존기간)
```

**현재 상태**: 미구현

**갭 영향**:
- 담보별 대기기간, 감액기간 정보 누락
- "1년 미만 계약에서 50% 감액" 같은 조건 표현 불가

**구현 제안**:
```sql
CREATE TABLE condition (
    id SERIAL PRIMARY KEY,
    condition_type VARCHAR(50) NOT NULL,  -- waiting_period, reduction, age_limit
    value VARCHAR(100),  -- "90일", "1년", "50%"
    unit VARCHAR(20),  -- days, years, percent
    description TEXT
);

CREATE TABLE coverage_condition (
    coverage_id INTEGER REFERENCES coverage(id),
    condition_id INTEGER REFERENCES condition(id),
    PRIMARY KEY (coverage_id, condition_id)
);
```

---

### 3.3 Exclusion (제외 사항) 노드

**설계 명세**:
```
면책사유, 계약 전·후 알릴 의무 위반 등
```

**현재 상태**: 미구현

**갭 영향**:
- 면책 조항 구조화 누락
- "지급하지 않는 사유" 쿼리 불가

**구현 제안**:
```sql
CREATE TABLE exclusion (
    id SERIAL PRIMARY KEY,
    exclusion_type VARCHAR(50) NOT NULL,  -- pre_existing, intentional, waiting
    description TEXT NOT NULL,
    clause_reference VARCHAR(100)  -- 약관 조항 참조
);

CREATE TABLE coverage_exclusion (
    coverage_id INTEGER REFERENCES coverage(id),
    exclusion_id INTEGER REFERENCES exclusion(id),
    PRIMARY KEY (coverage_id, exclusion_id)
);
```

---

### 3.4 Coverage PARENT_OF 관계

**현재 상태**: PostgreSQL에 `parent_coverage_id` 컬럼 존재 (52개), Neo4j 미동기화

**갭 영향**:
- 담보 계층 탐색 불가
- 부모-자식 담보 관계 시각화 불가

**구현 제안**:
```cypher
-- graph_loader.py 수정
MATCH (parent:Coverage {pg_id: $parent_id})
MATCH (child:Coverage {pg_id: $child_id})
CREATE (parent)-[:PARENT_OF]->(child)
```

**예상 데이터**:
- 52개 자식 담보에 PARENT_OF 관계 생성

---

### 3.5 Plan (가입설계서) 노드

**설계 명세**:
```
Plan (가입설계 결과)
- selected_coverages, sum_insured_per_coverage, premium, period 등
```

**현재 상태**: 미구현

**갭 영향**:
- 가입설계서 파싱 결과 구조화 누락
- 설계서 검증, 추천 기능 불가

**구현 복잡도**: 높음 (가입설계서 PDF 파싱 필요)

---

## 4. 우선순위별 구현 로드맵

### Phase 1: 즉시 구현 가능 (PostgreSQL 데이터 활용)

| 태스크 | 예상 소요 | 효과 |
|--------|-----------|------|
| Coverage PARENT_OF 관계 | 0.5일 | 담보 계층 탐색 가능 |
| Benefit → DiseaseCodeSet 관계 | 1일 | 급부별 적용 질병 조회 |

### Phase 2: 단기 구현 (테이블 설계 + 데이터 수집)

| 태스크 | 예상 소요 | 효과 |
|--------|-----------|------|
| RiskEvent 테이블 + 노드 | 2일 | 보험사고 기반 쿼리 |
| Condition 테이블 + 노드 | 1일 | 보장 조건 쿼리 |
| Exclusion 테이블 + 노드 | 1일 | 면책 사유 쿼리 |

### Phase 3: 중기 구현 (PDF 파싱 개선 필요)

| 태스크 | 예상 소요 | 효과 |
|--------|-----------|------|
| Plan 테이블 + 노드 | 5일 | 설계서 검증/추천 |
| Condition/Exclusion 자동 추출 | 3일 | 데이터 품질 향상 |

---

## 5. 현재 구현 커버리지

```
설계 엔티티: 10개
구현 완료: 9개 (90%)
미구현: 4개 (RiskEvent, Condition, Exclusion, Plan)

설계 관계: 12개
구현 완료: 6개 (50%)
미구현: 6개 (PARENT_OF, TRIGGERS, HAS_CONDITION, HAS_EXCLUSION, APPLIES_TO, INCLUDES)
```

### 5.1 시각화

```
구현 완료 (✅)              미구현 (❌)
═══════════════════════════════════════════════════════════
Company ──┐
          │
          ├──> Product ──> ProductVariant
          │         │
          │         └──> Coverage ──> Benefit
          │                  │             │
          │                  │             └──> (RiskEvent) ❌
          │                  │
          │                  ├──> (Condition) ❌
          │                  └──> (Exclusion) ❌
          │
          └──> Document
                    │
                    └──> DocumentClause

DiseaseCodeSet ──> DiseaseCode

(Plan) ❌ ──> Coverage
```

---

## 6. 권장 사항

### 6.1 즉시 조치

1. **graph_loader.py 수정**: Coverage PARENT_OF 관계 추가
2. **동기화 검증 스크립트 작성**: PostgreSQL ↔ Neo4j 일관성 확인

### 6.2 단기 계획 (1-2주)

1. **RiskEvent 테이블 설계 및 구현**
   - 약관에서 보험사고 유형 추출
   - Benefit → RiskEvent 관계 매핑

2. **Condition/Exclusion 테이블 설계**
   - 약관에서 조건/면책 조항 추출
   - Coverage 연결

### 6.3 중기 계획 (1개월)

1. **Plan 엔티티 구현**
   - 가입설계서 파싱 고도화
   - Plan → Coverage 관계 구축

2. **온톨로지 확장 검증**
   - 확장된 스키마로 QA 정확도 측정
   - 사용자 쿼리 커버리지 분석

---

## 참고 문서

- [ontology_concept.md](../../docs/design/ontology_concept.md) - 온톨로지 설계 원본
- [GRAPH_SCHEMA.md](./GRAPH_SCHEMA.md) - 현재 Neo4j 스키마
- [NODE_DICTIONARY.md](./NODE_DICTIONARY.md) - 노드별 속성 정의
- [RELATIONSHIP_DICTIONARY.md](./RELATIONSHIP_DICTIONARY.md) - 관계 타입 정의
