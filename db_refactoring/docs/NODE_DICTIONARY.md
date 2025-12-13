# 노드 사전 (Node Dictionary)

> 작성일: 2025-12-13

## 개요

Neo4j 그래프 데이터베이스의 노드 레이블별 속성 정의입니다.

---

## 1. Company (보험사)

**수량**: 8개

### 속성

| 속성 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| pg_id | Integer | Y | PostgreSQL ID | 67 |
| company_code | String | Y | 회사 코드 (유니크) | "samsung" |
| company_name | String | Y | 회사명 | "삼성" |
| business_type | String | N | 사업 유형 | "손해보험" |

### 제약조건

```cypher
CREATE CONSTRAINT company_code IF NOT EXISTS
FOR (c:Company) REQUIRE c.company_code IS UNIQUE;
```

### 예시 데이터

| company_code | company_name |
|--------------|--------------|
| samsung | 삼성 |
| db | DB |
| lotte | 롯데 |
| kb | KB |
| hyundai | 현대 |
| hanwha | 한화 |
| heungkuk | 흥국 |
| meritz | 메리츠 |

---

## 2. Product (상품)

**수량**: 8개

### 속성

| 속성 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| pg_id | Integer | Y | PostgreSQL ID | 1 |
| product_code | String | Y | 상품 코드 | "myhealthpartner" |
| product_name | String | Y | 상품명 | "(무)마이헬스파트너건강보험" |
| version | String | N | 상품 버전 | "2024.09" |
| effective_date | Date | N | 적용일 | 2024-09-01 |

### 제약조건

```cypher
CREATE CONSTRAINT product_id IF NOT EXISTS
FOR (p:Product) REQUIRE p.pg_id IS UNIQUE;
```

---

## 3. ProductVariant (상품 변형)

**수량**: 4개

### 속성

| 속성 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| pg_id | Integer | Y | PostgreSQL ID | 1 |
| variant_code | String | N | 변형 코드 | "male", "age_40_under" |
| variant_name | String | N | 변형명 | "남성용", "40세 이하" |
| target_gender | String | N | 대상 성별 | "male", "female" |
| target_age_range | String | N | 대상 연령대 | "≤40", "≥41" |

### 현재 데이터

| 보험사 | variant_code | 설명 |
|--------|--------------|------|
| 롯데 | male | 남성용 |
| 롯데 | female | 여성용 |
| DB | age_40_under | 40세 이하 |
| DB | age_41_over | 41세 이상 |

---

## 4. Coverage (담보)

**수량**: 363개

### 속성

| 속성 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| pg_id | Integer | Y | PostgreSQL ID | 100 |
| coverage_code | String | N | 담보 코드 | "cancer_diag_basic" |
| coverage_name | String | Y | 담보명 | "암진단금(기본형)" |
| coverage_category | String | N | 담보 카테고리 | "암진단" |
| renewal_type | String | N | 갱신 유형 | "갱신형", "비갱신형" |
| is_basic | Boolean | N | 기본형 여부 | true |

### 제약조건

```cypher
CREATE CONSTRAINT coverage_id IF NOT EXISTS
FOR (c:Coverage) REQUIRE c.pg_id IS UNIQUE;
```

### 보험사별 분포

| 보험사 | 담보 수 |
|--------|---------|
| 메리츠 | 98 |
| 한화 | 64 |
| 롯데 | 63 |
| 삼성 | 39 |
| KB | 36 |
| 흥국 | 23 |
| DB | 22 |
| 현대 | 18 |

---

## 5. Benefit (급부)

**수량**: 357개

### 속성

| 속성 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| pg_id | Integer | Y | PostgreSQL ID | 200 |
| benefit_name | String | Y | 급부명 | "암진단금" |
| benefit_type | String | N | 급부 타입 | "diagnosis", "surgery" |
| benefit_amount | Decimal | N | 지급 금액 | 3000000 |
| payment_frequency | String | N | 지급 빈도 | "1회", "진단시 1회" |

### 제약조건

```cypher
CREATE CONSTRAINT benefit_id IF NOT EXISTS
FOR (b:Benefit) REQUIRE b.pg_id IS UNIQUE;
```

### 타입별 분포

| benefit_type | 수량 | 비율 |
|--------------|------|------|
| diagnosis | 118 | 33.1% |
| other | 78 | 21.8% |
| treatment | 74 | 20.7% |
| surgery | 67 | 18.8% |
| death | 20 | 5.6% |

---

## 6. Document (문서)

**수량**: 38개

### 속성

| 속성 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| pg_id | Integer | Y | PostgreSQL ID | 1 |
| document_id | String | Y | 문서 ID | "samsung-myhealthpartner-terms-v1" |
| doc_type | String | Y | 문서 타입 | "terms", "proposal" |
| doc_subtype | String | N | 서브타입 | "male", "age_40_under" |
| total_pages | Integer | N | 총 페이지 수 | 150 |

### 문서 타입

| doc_type | 수량 | 설명 |
|----------|------|------|
| proposal | 10 | 가입설계서 |
| terms | 9 | 약관 |
| business_spec | 9 | 사업방법서 |
| product_summary | 9 | 상품요약서 |
| easy_summary | 1 | 쉬운요약서 |

---

## 7. DiseaseCodeSet (질병코드 집합)

**수량**: 9개

### 속성

| 속성 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| pg_id | Integer | Y | PostgreSQL ID | 10 |
| set_name | String | Y | 집합명 | "악성신생물" |
| description | String | N | 설명 | "암(악성신생물) 분류표" |
| version | String | N | 버전 | "KCD-8" |

### 현재 데이터

| set_name | 설명 |
|----------|------|
| 악성신생물 | 암(C코드) |
| 제자리신생물 | D00-D09 |
| 기타피부암 | C44 |
| 갑상선암 | C73 |
| 뇌출혈 | 뇌내출혈 등 |
| 뇌경색 | I63 |
| 뇌졸중 | 뇌혈관질환 |
| 급성심근경색 | I21 |
| 허혈성심장질환 | I20-I25 |

---

## 8. DiseaseCode (질병 코드)

**수량**: 131개

### 속성

| 속성 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| pg_id | Integer | Y | PostgreSQL ID | 50 |
| code | String | Y | 질병 코드 | "C34" |
| code_type | String | N | 코드 체계 | "KCD", "ICD" |
| description_kr | String | N | 한글 설명 | "기관지 및 폐의 악성 신생물" |

---

## 속성 명명 규칙

| 규칙 | 예시 |
|------|------|
| PostgreSQL ID | `pg_id` |
| 코드 속성 | `*_code` (company_code, coverage_code) |
| 이름 속성 | `*_name` (company_name, coverage_name) |
| 타입 속성 | `*_type` (benefit_type, doc_type) |
| 날짜 속성 | `*_date` (effective_date) |

---

## 참고 문서

- [GRAPH_SCHEMA.md](./GRAPH_SCHEMA.md) - 그래프 스키마 개요
- [RELATIONSHIP_DICTIONARY.md](./RELATIONSHIP_DICTIONARY.md) - 관계 타입 정의
