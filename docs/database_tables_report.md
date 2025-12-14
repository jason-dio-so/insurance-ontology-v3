# 데이터베이스 테이블 상태 보고서

**생성일**: 2025-12-14
**데이터베이스**: insurance_ontology_test (PostgreSQL)

---

## 요약

| 테이블 | 행 수 | 상태 |
|--------|-------|------|
| company | 8 | ✅ |
| product | 8 | ✅ |
| product_variant | 4 | ✅ |
| document | 38 | ✅ |
| document_clause | 80,602 | ✅ |
| coverage | 294 | ✅ |
| coverage_group | 110 | ✅ |
| coverage_category | 9 | ✅ |
| plan | 10 | ✅ |
| plan_coverage | 571 | ✅ |
| risk_event | 572 | ✅ |
| exclusion | 2 | ⚠️ |
| condition | 196 | ✅ |
| clause_coverage | 623 | ✅ |
| disease_code_set | 9 | ✅ |
| disease_code | 131 | ✅ |
| benefit | 0 | ⬜ 미사용 |
| benefit_risk_event | 0 | ⬜ 미사용 |
| clause_embedding | 0 | ⬜ 벡터용 |

---

## 1. company (보험사)

**행 수**: 8

### 컬럼
| 컬럼명 | 타입 |
|--------|------|
| id | integer |
| company_code | varchar |
| company_name | varchar |
| business_type | varchar |
| created_at | timestamp |
| updated_at | timestamp |

### 샘플 데이터
```
id | company_code | company_name | business_type
---+--------------+--------------+---------------
55 | heungkuk     | 흥국         |
59 | meritz       | 메리츠       |
63 | hyundai      | 현대         |
```

---

## 2. product (보험 상품)

**행 수**: 8

### 컬럼
| 컬럼명 | 타입 |
|--------|------|
| id | integer |
| company_id | integer (FK → company) |
| product_code | varchar |
| product_name | varchar |
| business_type | varchar |
| version | varchar |
| effective_date | date |
| created_at | timestamp |
| updated_at | timestamp |

### 샘플 데이터
```
id | company_id | product_code    | product_name
---+------------+-----------------+--------------------------------
 1 |         39 | healthguard     | 무배당 롯데손해보험 건강보험
 9 |         47 | healthinsurance | 무배당 한화손해보험 건강보험
13 |         51 | realhealthcare  | 무배당 KB손해보험 실속건강보험
```

---

## 3. product_variant (상품 변형)

**행 수**: 4

### 컬럼
| 컬럼명 | 타입 |
|--------|------|
| id | integer |
| product_id | integer (FK → product) |
| variant_name | varchar |
| variant_code | varchar |
| target_gender | varchar |
| target_age_range | varchar |
| min_age | integer |
| max_age | integer |
| attributes | jsonb |
| created_at | timestamp |
| updated_at | timestamp |

### 샘플 데이터
```
id | product_id | variant_code | target_gender | target_age_range | min_age | max_age
---+------------+--------------+---------------+------------------+---------+--------
 3 |          1 | male         | male          |                  |         |
 1 |          1 | female       | female        |                  |         |
25 |         57 | age_40_under |               | ≤40              |       0 |      40
```

---

## 4. document (문서)

**행 수**: 38

### 컬럼
| 컬럼명 | 타입 |
|--------|------|
| id | integer |
| document_id | varchar |
| company_id | integer (FK → company) |
| product_id | integer (FK → product) |
| variant_id | integer (FK → product_variant) |
| doc_type | varchar |
| doc_subtype | varchar |
| version | varchar |
| file_path | varchar |
| total_pages | integer |
| attributes | jsonb |
| created_at | timestamp |
| updated_at | timestamp |

### 샘플 데이터
```
id | document_id      | company_id | product_id | doc_type      | doc_subtype | total_pages
---+------------------+------------+------------+---------------+-------------+------------
12 | hanwha-terms     |         47 |          9 | terms         |             |       1065
13 | kb-business_spec |         51 |         13 | business_spec |             |         91
14 | kb-proposal      |         51 |         13 | proposal      |             |         15
```

---

## 5. document_clause (문서 조항)

**행 수**: 80,602

### 컬럼
| 컬럼명 | 타입 |
|--------|------|
| id | integer |
| document_id | integer (FK → document) |
| clause_number | varchar |
| clause_title | varchar |
| clause_text | text |
| clause_type | varchar |
| structured_data | jsonb |
| section_type | varchar |
| page_number | integer |
| hierarchy_level | integer |
| parent_clause_id | integer |
| attributes | jsonb |
| created_at | timestamp |
| updated_at | timestamp |

### 샘플 데이터
```
id     | document_id | clause_type | clause_number | title
-------+-------------+-------------+---------------+-------------------
385893 |          41 | article     | 제9조         | 중도인출
385894 |          41 | article     | 제11조        | 만기환급금의 지급
385895 |          41 | article     | 제1조         | 보험금의 지급사유
```

---

## 6. coverage (담보/특약)

**행 수**: 294

### 컬럼
| 컬럼명 | 타입 |
|--------|------|
| id | integer |
| product_id | integer (FK → product) |
| group_id | integer (FK → coverage_group) |
| coverage_code | varchar |
| coverage_name | varchar |
| coverage_category | varchar |
| renewal_type | varchar |
| is_basic | boolean |
| clause_number | varchar |
| coverage_period | varchar |
| standard_code | varchar |
| parent_coverage_id | integer (FK → coverage) |
| notes | text |
| created_at | timestamp |
| updated_at | timestamp |

### 샘플 데이터
```
id   | product_id | group_id | coverage_name                           | coverage_category | standard_code
-----+------------+----------+-----------------------------------------+-------------------+--------------
2612 |         57 |       43 | 다빈치로봇암수술비(연간1회한,특정암제외) | surgery           | A9630_1
2613 |         57 |       43 | 다빈치로봇암수술비(연간1회한,특정암)     | surgery           | A9630_1
2614 |         57 |       43 | 상해수술비(동일사고당1회지급)            | surgery           | A5300
```

---

## 7. coverage_group (담보 그룹)

**행 수**: 110

### 컬럼
| 컬럼명 | 타입 |
|--------|------|
| id | integer |
| company_id | integer (FK → company) |
| category_id | integer (FK → coverage_category) |
| group_number | integer |
| group_code | varchar |
| group_name_kr | varchar |
| group_name_en | varchar |
| is_renewable | boolean |
| version | varchar |
| page_number | integer |
| description | text |
| created_at | timestamp |
| updated_at | timestamp |

### 샘플 데이터
```
id | company_id | category_id | group_code                 | group_name_kr
---+------------+-------------+----------------------------+------------------
 1 |         59 |          10 | death_disability           | 사망/장해/장애군
 2 |         47 |          15 | hospitalization            | 입원군
 3 |         63 |          14 | specific_disease_diagnosis | 특정질병진단군
```

---

## 8. coverage_category (담보 카테고리)

**행 수**: 9 (시드 데이터)

### 컬럼
| 컬럼명 | 타입 |
|--------|------|
| id | integer |
| category_code | varchar |
| category_name_kr | varchar |
| category_name_en | varchar |
| description | text |
| display_order | integer |
| created_at | timestamp |
| updated_at | timestamp |

### 샘플 데이터
```
id | category_code           | category_name_kr   | category_name_en
---+-------------------------+--------------------+---------------------------
10 | death_disability        | 사망/장해/장애군   | Death/Disability/Handicap
11 | dementia_long_term_care | 치매 및 장기요양군 | Dementia & Long-term Care
12 | cancer_diagnosis        | 암진단군           | Cancer Diagnosis
```

---

## 9. plan (가입 플랜)

**행 수**: 10

### 컬럼
| 컬럼명 | 타입 |
|--------|------|
| id | integer |
| document_id | integer (FK → document) |
| product_id | integer (FK → product) |
| variant_id | integer (FK → product_variant) |
| plan_name | varchar |
| target_gender | varchar |
| target_age | integer |
| insurance_period | varchar |
| payment_period | varchar |
| payment_cycle | varchar |
| total_premium | numeric |
| attributes | jsonb |
| created_at | timestamp |
| updated_at | timestamp |

### 샘플 데이터
```
id | document_id | product_id | plan_name        | target_gender | target_age | total_premium
---+-------------+------------+------------------+---------------+------------+--------------
77 |          57 |         57 | 여성 40세 20년납 | female        |         40 |     162843.00
78 |          59 |         57 | 여성 41세 20년납 | female        |         41 |     164955.00
79 |           9 |          9 | 남성 30세 20년납 | male          |         30 |      99218.00
```

---

## 10. plan_coverage (플랜-담보 연결)

**행 수**: 571

### 컬럼
| 컬럼명 | 타입 |
|--------|------|
| id | integer |
| plan_id | integer (FK → plan) |
| coverage_id | integer (FK → coverage) |
| sum_insured | numeric |
| sum_insured_text | varchar |
| premium | numeric |
| is_basic | boolean |
| created_at | timestamp |

### 샘플 데이터
```
id   | plan_id | coverage_id | sum_insured  | sum_insured_text | premium
-----+---------+-------------+--------------+------------------+--------
5887 |      77 |        2624 |              | 1백만원          |  132.00
5888 |      77 |        2619 |    100000.00 | 10만원           |  142.00
5889 |      77 |        2626 | 10000000.00  | 1천만원          |  740.00
```

---

## 11. risk_event (위험 이벤트)

**행 수**: 572

### 컬럼
| 컬럼명 | 타입 |
|--------|------|
| id | integer |
| event_type | varchar |
| event_name | varchar |
| severity_level | varchar |
| icd_code_pattern | varchar |
| description | text |
| created_at | timestamp |
| updated_at | timestamp |

### 샘플 데이터
```
id | event_type      | event_name | severity_level | icd_code_pattern
---+-----------------+------------+----------------+-----------------
 1 | injury          | 입원       | medium         |
 2 | hospitalization | 입원       | low            |
 3 | injury          | 입원 등    | medium         |
```

---

## 12. exclusion (면책 조항)

**행 수**: 2

### 컬럼
| 컬럼명 | 타입 |
|--------|------|
| id | integer |
| coverage_id | integer (FK → coverage) |
| exclusion_type | varchar |
| exclusion_text | text |
| is_absolute | boolean |
| attributes | jsonb |
| created_at | timestamp |
| updated_at | timestamp |

### 샘플 데이터
```
id | coverage_id | exclusion_type | is_absolute | exclusion_text (일부)
---+-------------+----------------+-------------+----------------------------------
29 |        2748 | general        | true        | (제1회 보험료 및 회사의 보장개시)...
30 |        2748 | general        | true        | (제1회 보험료 및 회사의 보장개시)...
```

---

## 13. condition (보장 조건)

**행 수**: 196

### 컬럼
| 컬럼명 | 타입 |
|--------|------|
| id | integer |
| coverage_id | integer (FK → coverage) |
| condition_type | varchar |
| condition_text | text |
| min_age | integer |
| max_age | integer |
| waiting_period_days | integer |
| attributes | jsonb |
| created_at | timestamp |
| updated_at | timestamp |

### 샘플 데이터
```
id | coverage_id | condition_type | waiting_period_days | condition_text (일부)
---+-------------+----------------+---------------------+---------------------------------------
63 |        2748 | waiting_period |                     | (제1회 보험료 및 회사의 보장개시)...
64 |        2748 | waiting_period |                  90 | (제1회 보험료 및 회사의 보장개시)...
65 |        2748 | waiting_period |                     | (제1회 보험료 및 회사의 보장개시)...
```

---

## 14. clause_coverage (조항-담보 연결)

**행 수**: 623

### 컬럼
| 컬럼명 | 타입 |
|--------|------|
| id | integer |
| clause_id | integer (FK → document_clause) |
| coverage_id | integer (FK → coverage) |
| relevance_score | double precision |
| extraction_method | varchar |
| created_at | timestamp |

### 샘플 데이터
```
id   | clause_id | coverage_id | extraction_method | relevance_score
-----+-----------+-------------+-------------------+----------------
4904 |    392191 |        2687 | exact_match       |              1
4905 |    392192 |        2707 | exact_match       |              1
4906 |    392193 |        2709 | exact_match       |              1
```

---

## 15. disease_code_set (질병코드 집합)

**행 수**: 9

### 컬럼
| 컬럼명 | 타입 |
|--------|------|
| id | integer |
| set_name | varchar |
| description | text |
| version | varchar |
| created_at | timestamp |
| updated_at | timestamp |

### 샘플 데이터
```
id | set_name     | description                | version
---+--------------+----------------------------+--------
10 | 악성신생물   | 암(악성신생물) 분류표      | KCD-8
11 | 제자리신생물 | 제자리신생물 및 양성신생물 | KCD-8
12 | 기타피부암   | 기타피부암                 | KCD-8
```

---

## 16. disease_code (질병 코드)

**행 수**: 131

### 컬럼
| 컬럼명 | 타입 |
|--------|------|
| id | integer |
| code_set_id | integer (FK → disease_code_set) |
| code | varchar |
| code_type | varchar |
| description_kr | varchar |
| description_en | varchar |
| created_at | timestamp |

### 샘플 데이터
```
id  | code_set_id | code | code_type | description_kr
----+-------------+------+-----------+---------------
132 |          10 | C00  | KCD       |
133 |          10 | C01  | KCD       |
134 |          10 | C02  | KCD       |
```

---

## 17. benefit (급부) - 미사용

**행 수**: 0

### 컬럼
| 컬럼명 | 타입 |
|--------|------|
| id | integer |
| coverage_id | integer (FK → coverage) |
| benefit_name | varchar |
| benefit_type | varchar |
| benefit_amount_text | text |
| benefit_amount | numeric |
| payment_frequency | varchar |
| description | text |
| created_at | timestamp |
| updated_at | timestamp |

---

## 18. benefit_risk_event (급부-위험이벤트 연결) - 미사용

**행 수**: 0

---

## 19. clause_embedding (조항 임베딩) - 벡터 검색용

**행 수**: 0

### 컬럼
| 컬럼명 | 타입 |
|--------|------|
| id | integer |
| clause_id | integer (FK → document_clause) |
| embedding | vector |
| model_name | varchar |
| metadata | jsonb |
| created_at | timestamp |

---

## ER 다이어그램 관계

```
company (1) ──< product (N)
product (1) ──< product_variant (N)
product (1) ──< document (N)
product (1) ──< coverage (N)

document (1) ──< document_clause (N)
document (1) ──< plan (N)

coverage (1) ──< plan_coverage (N)
coverage (1) ──< clause_coverage (N)
coverage (1) ──< exclusion (N)
coverage (1) ──< condition (N)
coverage (N) >── coverage_group (1)
coverage (N) >── coverage (1) [parent_coverage_id]

plan (1) ──< plan_coverage (N)

document_clause (1) ──< clause_coverage (N)
document_clause (1) ──< clause_embedding (N)

disease_code_set (1) ──< disease_code (N)

coverage_category (1) ──< coverage_group (N)
```
