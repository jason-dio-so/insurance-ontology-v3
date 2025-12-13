# 데이터 사전 (Data Dictionary)

> 자동 생성일: 2025-12-13 12:25

## 목차

- [benefit](#benefit) - 담보별 보장 급부
- [clause_coverage](#clause_coverage) - v2: 조항-담보 M:N 매핑 (필터링된 벡터 검색용)
- [clause_embedding](#clause_embedding) - v2: 조항 벡터 임베딩 (FastEmbed BGE-Small 384d)
- [company](#company) - 보험사 마스터
- [condition](#condition) - 담보별 보장 조건
- [coverage](#coverage) - 담보 (특별약관 단위)
- [coverage_category](#coverage_category) - 담보 카테고리 (암진단군, 2대질병진단군 등)
- [coverage_group](#coverage_group) - 특별약관군 (무배당암 진단 보장 특별약관군 등)
- [disease_code](#disease_code) - 질병코드 (KCD, ICD)
- [disease_code_set](#disease_code_set) - 질병코드 집합 (암, 뇌출혈, 급성심근경색 등)
- [document](#document) - 약관, 사업방법서, 상품요약서, 가입설계서 문서
- [document_clause](#document_clause) - 문서 조항/청크 (제n조 단위 + 테이블 행)
- [exclusion](#exclusion) - 담보별 보장 제외 사항
- [product](#product) - 보험 상품 마스터
- [product_variant](#product_variant) - 상품 변형 (성별/연령 분리, 1형/2형, 1종/3종/4종 등)

---

## benefit

**설명**: 담보별 보장 급부

### 컬럼

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id 🔑 | integer | N | nextval('benefit_id_seq'::r... | - |
| coverage_id | integer | N | - | - |
| benefit_name | varchar(200) | N | - | - |
| benefit_type | varchar(200) | Y | - | 급부 타입 (진단금, 수술비, 입원일당 등) |
| benefit_amount_text | text | Y | - | - |
| benefit_amount | numeric(15,2) | Y | - | - |
| payment_frequency | varchar(50) | Y | - | 지급 빈도 (1회, 연 1회, 진단시 1회 등) |
| description | text | Y | - | - |
| created_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |
| updated_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |

### 인덱스

| 인덱스명 | 타입 | 컬럼 | 유니크 |
|----------|------|------|--------|

---

## clause_coverage

**설명**: v2: 조항-담보 M:N 매핑 (필터링된 벡터 검색용)

### 컬럼

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id 🔑 | integer | N | nextval('clause_coverage_id... | - |
| clause_id | integer | N | - | - |
| coverage_id | integer | N | - | - |
| relevance_score | double precision | Y | 1.0 | 관련도 점수 (0.0~1.0) |
| extraction_method | varchar(50) | Y | - | 추출 방법 (exact_match, fuzzy_match, llm) |
| created_at | timestamp without time zone | Y | now() | - |

### 인덱스

| 인덱스명 | 타입 | 컬럼 | 유니크 |
|----------|------|------|--------|
| clause_coverage_clause_id_coverage_id_key | btree | clause_id, coverage_id | Y |
| idx_clause_coverage_clause | btree | clause_id | N |
| idx_clause_coverage_coverage | btree | coverage_id | N |

---

## clause_embedding

**설명**: v2: 조항 벡터 임베딩 (FastEmbed BGE-Small 384d)

### 컬럼

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id 🔑 | integer | N | nextval('clause_embedding_i... | - |
| clause_id | integer | N | - | - |
| embedding | vector | Y | - | 벡터 임베딩 (384차원) |
| model_name | varchar(100) | Y | - | - |
| metadata | jsonb | Y | - | v2: 검색 필터용 메타데이터 {coverage_ids, clause_type, doc_type, ...} |
| created_at | timestamp without time zone | Y | now() | - |

### 인덱스

| 인덱스명 | 타입 | 컬럼 | 유니크 |
|----------|------|------|--------|
| clause_embedding_clause_id_key | btree | clause_id | Y |
| idx_clause_embedding_clause | btree | clause_id | N |
| idx_clause_embedding_hnsw | hnsw | embedding | N |
| idx_clause_embedding_metadata_gin | gin | metadata | N |

---

## company

**설명**: 보험사 마스터

### 컬럼

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id 🔑 | integer | N | nextval('company_id_seq'::r... | - |
| company_code | varchar(20) | N | - | 회사 코드 (samsung, db, lotte, kb, hyundai, hanwha, heungkuk, meritz) |
| company_name | varchar(100) | N | - | - |
| business_type | varchar(50) | Y | - | 사업 유형 (손해보험, 생명보험) |
| created_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |
| updated_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |

### 인덱스

| 인덱스명 | 타입 | 컬럼 | 유니크 |
|----------|------|------|--------|
| company_company_code_key | btree | company_code | Y |
| idx_company_code | btree | company_code | N |

---

## condition

**설명**: 담보별 보장 조건

### 컬럼

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id 🔑 | integer | N | nextval('condition_id_seq':... | - |
| coverage_id | integer | N | - | - |
| condition_type | varchar(50) | Y | - | 조건 타입 (diagnosis, age, waiting_period 등) |
| condition_text | text | N | - | - |
| min_age | integer | Y | - | - |
| max_age | integer | Y | - | - |
| waiting_period_days | integer | Y | - | 면책/감액 기간 (일) |
| attributes | jsonb | Y | - | - |
| created_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |
| updated_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |

### 인덱스

| 인덱스명 | 타입 | 컬럼 | 유니크 |
|----------|------|------|--------|

---

## coverage

**설명**: 담보 (특별약관 단위)

### 컬럼

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id 🔑 | integer | N | nextval('coverage_id_seq'::... | - |
| product_id | integer | N | - | - |
| group_id | integer | Y | - | 소속 특별약관군 |
| coverage_code | varchar(200) | Y | - | - |
| coverage_name | varchar(200) | N | - | - |
| coverage_category | varchar(100) | Y | - | - |
| renewal_type | varchar(20) | Y | - | 갱신형, 비갱신형 |
| is_basic | boolean | Y | false | 기본형 담보 여부 |
| created_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |
| updated_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |
| parent_coverage_id | integer | Y | - | - |

### 인덱스

| 인덱스명 | 타입 | 컬럼 | 유니크 |
|----------|------|------|--------|
| coverage_product_id_coverage_code_key | btree | product_id, coverage_code | Y |
| idx_coverage_group | btree | group_id | N |
| idx_coverage_name | btree | coverage_name | N |
| idx_coverage_parent | btree | parent_coverage_id | N |
| idx_coverage_product | btree | product_id | N |

---

## coverage_category

**설명**: 담보 카테고리 (암진단군, 2대질병진단군 등)

### 컬럼

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id 🔑 | integer | N | nextval('coverage_category_... | - |
| category_code | varchar(50) | N | - | 카테고리 코드 (cancer_diagnosis, major_disease 등) |
| category_name_kr | varchar(100) | N | - | 카테고리명 (한글) |
| category_name_en | varchar(100) | Y | - | - |
| description | text | Y | - | - |
| display_order | integer | Y | - | - |
| created_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |
| updated_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |

### 인덱스

| 인덱스명 | 타입 | 컬럼 | 유니크 |
|----------|------|------|--------|
| coverage_category_category_code_key | btree | category_code | Y |

---

## coverage_group

**설명**: 특별약관군 (무배당암 진단 보장 특별약관군 등)

### 컬럼

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id 🔑 | integer | N | nextval('coverage_group_id_... | - |
| company_id | integer | Y | - | - |
| category_id | integer | Y | - | - |
| group_number | integer | Y | - | 약관 목차 번호 (예: 4, 5, ...) |
| group_code | varchar(50) | N | - | 약관군 코드 |
| group_name_kr | varchar(200) | N | - | - |
| group_name_en | varchar(200) | Y | - | - |
| is_renewable | boolean | Y | false | 갱신형 여부 |
| version | varchar(20) | Y | - | - |
| page_number | integer | Y | - | - |
| description | text | Y | - | - |
| created_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |
| updated_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |

### 인덱스

| 인덱스명 | 타입 | 컬럼 | 유니크 |
|----------|------|------|--------|
| coverage_group_company_id_group_code_version_key | btree | company_id, group_code, version | Y |

---

## disease_code

**설명**: 질병코드 (KCD, ICD)

### 컬럼

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id 🔑 | integer | N | nextval('disease_code_id_se... | - |
| code_set_id | integer | N | - | - |
| code | varchar(20) | N | - | - |
| code_type | varchar(10) | Y | - | 코드 체계 (KCD, ICD) |
| description_kr | varchar(500) | Y | - | - |
| description_en | varchar(500) | Y | - | - |
| created_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |

### 인덱스

| 인덱스명 | 타입 | 컬럼 | 유니크 |
|----------|------|------|--------|
| disease_code_code_set_id_code_key | btree | code_set_id, code | Y |

---

## disease_code_set

**설명**: 질병코드 집합 (암, 뇌출혈, 급성심근경색 등)

### 컬럼

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id 🔑 | integer | N | nextval('disease_code_set_i... | - |
| set_name | varchar(100) | N | - | - |
| description | text | Y | - | - |
| version | varchar(20) | Y | - | - |
| created_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |
| updated_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |

### 인덱스

| 인덱스명 | 타입 | 컬럼 | 유니크 |
|----------|------|------|--------|
| disease_code_set_set_name_key | btree | set_name | Y |

---

## document

**설명**: 약관, 사업방법서, 상품요약서, 가입설계서 문서

### 컬럼

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id 🔑 | integer | N | nextval('document_id_seq'::... | - |
| document_id | varchar(100) | N | - | 문서 고유 ID (예: samsung-myhealthpartner-terms-v1-20250901) |
| company_id | integer | Y | - | - |
| product_id | integer | Y | - | - |
| variant_id | integer | Y | - | 연결된 상품 변형 ID (롯데 성별/DB 연령 분리) |
| doc_type | varchar(50) | Y | - | 문서 타입 (terms, business_spec, product_summary, proposal, easy_summary) |
| doc_subtype | varchar(50) | Y | - | 문서 서브타입 (male, female, age_40_under, age_41_over 등) |
| version | varchar(50) | Y | - | - |
| file_path | varchar(500) | Y | - | - |
| total_pages | integer | Y | - | - |
| attributes | jsonb | Y | - | 추가 메타데이터 (JSONB) |
| created_at | timestamp without time zone | Y | now() | - |
| updated_at | timestamp without time zone | Y | now() | - |

### 인덱스

| 인덱스명 | 타입 | 컬럼 | 유니크 |
|----------|------|------|--------|
| document_document_id_key | btree | document_id | Y |
| idx_document_company | btree | company_id | N |
| idx_document_product | btree | product_id | N |
| idx_document_type | btree | doc_type | N |
| idx_document_variant | btree | variant_id | N |

---

## document_clause

**설명**: 문서 조항/청크 (제n조 단위 + 테이블 행)

### 컬럼

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id 🔑 | integer | N | nextval('document_clause_id... | - |
| document_id | integer | N | - | - |
| clause_number | varchar(50) | Y | - | - |
| clause_title | varchar(500) | Y | - | - |
| clause_text | text | N | - | - |
| clause_type | varchar(50) | Y | - | v2: Clause type (table_row, text_block, list_item, heading, article) |
| structured_data | jsonb | Y | - | v2: 구조화 데이터 {coverage_name, coverage_amount, premium, target_gender, target_age_range, ...} |
| section_type | varchar(100) | Y | - | 섹션 타입 (보통약관, 특별약관, 별표 등) |
| page_number | integer | Y | - | - |
| hierarchy_level | integer | Y | 0 | - |
| parent_clause_id | integer | Y | - | - |
| attributes | jsonb | Y | - | - |
| created_at | timestamp without time zone | Y | now() | - |
| updated_at | timestamp without time zone | Y | now() | - |

### 인덱스

| 인덱스명 | 타입 | 컬럼 | 유니크 |
|----------|------|------|--------|
| idx_clause_document | btree | document_id | N |
| idx_clause_parent | btree | parent_clause_id | N |
| idx_clause_section | btree | section_type | N |
| idx_clause_type | btree | clause_type | N |
| idx_structured_data_gin | gin | structured_data | N |

---

## exclusion

**설명**: 담보별 보장 제외 사항

### 컬럼

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id 🔑 | integer | N | nextval('exclusion_id_seq':... | - |
| coverage_id | integer | N | - | - |
| exclusion_type | varchar(50) | Y | - | 제외 타입 (disease, cause, situation 등) |
| exclusion_text | text | N | - | - |
| is_absolute | boolean | Y | true | 절대적 제외 여부 |
| attributes | jsonb | Y | - | - |
| created_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |
| updated_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |

### 인덱스

| 인덱스명 | 타입 | 컬럼 | 유니크 |
|----------|------|------|--------|

---

## product

**설명**: 보험 상품 마스터

### 컬럼

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id 🔑 | integer | N | nextval('product_id_seq'::r... | - |
| company_id | integer | N | - | - |
| product_code | varchar(50) | N | - | 상품 코드 |
| product_name | varchar(200) | N | - | - |
| business_type | varchar(50) | Y | - | 상품 유형 (장기손해, 장기상해 등) |
| version | varchar(20) | Y | - | 상품 버전 |
| effective_date | date | Y | - | 적용 시작일 |
| created_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |
| updated_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |

### 인덱스

| 인덱스명 | 타입 | 컬럼 | 유니크 |
|----------|------|------|--------|
| idx_product_code | btree | product_code | N |
| idx_product_company | btree | company_id | N |
| product_company_id_product_code_version_key | btree | company_id, product_code, version | Y |

---

## product_variant

**설명**: 상품 변형 (성별/연령 분리, 1형/2형, 1종/3종/4종 등)

### 컬럼

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| id 🔑 | integer | N | nextval('product_variant_id... | - |
| product_id | integer | N | - | - |
| variant_name | varchar(100) | Y | - | 변형명 (예: 남성용, 여성용, 40세이하) |
| variant_code | varchar(50) | Y | - | 변형 코드 (예: male, female, age_40_under) |
| target_gender | varchar(10) | Y | - | 대상 성별 (male, female, NULL) |
| target_age_range | varchar(20) | Y | - | 대상 연령대 (≤40, ≥41, 30-39, NULL) |
| min_age | integer | Y | - | - |
| max_age | integer | Y | - | - |
| attributes | jsonb | Y | - | 추가 속성 (JSONB): refund_type, jong_type 등 |
| created_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |
| updated_at | timestamp without time zone | Y | CURRENT_TIMESTAMP | - |

### 인덱스

| 인덱스명 | 타입 | 컬럼 | 유니크 |
|----------|------|------|--------|
| idx_variant_age_range | btree | target_age_range | N |
| idx_variant_gender | btree | target_gender | N |
| idx_variant_product | btree | product_id | N |
| product_variant_product_id_variant_code_key | btree | product_id, variant_code | Y |

---
