# 테이블 컬럼 레퍼런스

**생성일**: 2025-12-14

각 테이블의 컬럼별 실제 데이터와 데이터 소스를 정리합니다.

---

## 1. company (보험사 마스터)

### 데이터 소스
`ingestion/ingest_v3.py` → `_get_or_create_company()`

### 컬럼 상세

| 컬럼 | 타입 | 예시 값 | 소스 |
|------|------|---------|------|
| id | int | 55 | 자동생성 |
| company_code | varchar(20) | `heungkuk` | `documents_metadata.json` → company_code |
| company_name | varchar(100) | `흥국` | company_code에서 매핑 (COMPANY_NAMES 딕셔너리) |
| business_type | varchar(50) | `NULL` ❌ | 미구현 - 수동 입력 필요 |

### 샘플 데이터
```
id: 55, company_code: heungkuk, company_name: 흥국, business_type: NULL
id: 59, company_code: meritz,   company_name: 메리츠, business_type: NULL
id: 63, company_code: hyundai,  company_name: 현대, business_type: NULL
```

### 소스 코드
```python
# ingestion/ingest_v3.py:150-170
COMPANY_NAMES = {
    'samsung': '삼성', 'db': 'DB', 'lotte': '롯데', 'kb': 'KB',
    'hyundai': '현대', 'hanwha': '한화', 'heungkuk': '흥국', 'meritz': '메리츠'
}

def _get_or_create_company(self, company_code: str) -> int:
    # company_code로 조회 또는 생성
```

---

## 2. product (보험 상품 마스터)

### 데이터 소스
`ingestion/ingest_v3.py` → `_get_or_create_product()`

### 컬럼 상세

| 컬럼 | 타입 | 예시 값 | 소스 |
|------|------|---------|------|
| id | int | 1 | 자동생성 |
| company_id | int | 39 | FK → company.id |
| product_code | varchar(50) | `healthguard` | `documents_metadata.json` → product_code |
| product_name | varchar(200) | `무배당 롯데손해보험 건강보험` | `documents_metadata.json` → product_name |
| business_type | varchar(50) | `NULL` ❌ | 미구현 |
| version | varchar(20) | `2508` | `documents_metadata.json` → version |
| effective_date | date | `NULL` ❌ | 미구현 |

### 샘플 데이터
```
id: 1, product_code: healthguard, product_name: 무배당 롯데손해보험 건강보험, version: 2508
id: 9, product_code: healthinsurance, product_name: 무배당 한화손해보험 건강보험, version: 2508
```

---

## 3. product_variant (상품 변형)

### 데이터 소스
`ingestion/ingest_v3.py` → `_get_or_create_variant()`

### 컬럼 상세

| 컬럼 | 타입 | 예시 값 | 소스 |
|------|------|---------|------|
| id | int | 3 | 자동생성 |
| product_id | int | 1 | FK → product.id |
| variant_name | varchar(100) | `male` | `documents_metadata.json` → variant (male/female/age_40_under) |
| variant_code | varchar(50) | `male` | variant_name과 동일 |
| target_gender | varchar(10) | `male` | variant에서 파싱 (male/female → target_gender) |
| target_age_range | varchar(20) | `≤40` | variant에서 파싱 (age_40_under → ≤40) |
| min_age | int | `0` | `_parse_age_range()` (age_40_under → 0) |
| max_age | int | `40` | `_parse_age_range()` (age_40_under → 40) |
| attributes | jsonb | `{'target_gender': 'male'}` | variant 정보를 JSON으로 저장 |

### 샘플 데이터
```
id: 3, variant_code: male, target_gender: male, min_age: NULL, max_age: NULL
id: 25, variant_code: age_40_under, target_age_range: ≤40, min_age: 0, max_age: 40
id: 26, variant_code: age_41_over, target_age_range: >40, min_age: 41, max_age: 100
```

---

## 4. coverage (담보/특별약관)

### 데이터 소스
`ingestion/coverage_pipeline.py` → `save_coverages()`

### 컬럼 상세

| 컬럼 | 타입 | 예시 값 | 소스 |
|------|------|---------|------|
| id | int | 1754 | 자동생성 |
| product_id | int | 57 | FK → product.id (document_clause에서) |
| group_id | int | `12` | coverage_group FK (company + category 기반, 100%) |
| coverage_code | varchar(200) | `뇌졸중진단비` | `_generate_coverage_code()` - coverage_name 정제 |
| coverage_name | text | `뇌졸중진단비` | document_clause.structured_data → coverage_name |
| coverage_category | varchar(100) | `major_disease_diagnosis` | `_infer_coverage_category()` - 이름에서 추론 |
| renewal_type | varchar(20) | `갱신형` / `NULL` | `_extract_renewal_type()` 또는 `_clean_coverage_name()` |
| is_basic | boolean | `false` | coverage_name에 '기본계약' 포함 여부 |
| clause_number | varchar(50) | `123` / `NULL` | `_clean_coverage_name()` - "123 뇌졸중진단비" 파싱 |
| coverage_period | varchar(100) | `20년/100세` | `structured_data.period` (71% 채워짐) |
| parent_coverage_id | int | `42` | 담보명mapping자료.xlsx 기반 계층 (38건, 13%) |
| standard_code | varchar(20) | `A4200_1` | 신정원 표준코드 (198건, 67%) |

### 샘플 데이터
```
id: 1754, coverage_name: 뇌졸중진단비, coverage_category: major_disease_diagnosis
id: 1756, coverage_name: 뇌출혈진단비, coverage_category: major_disease_diagnosis
id: 1758, coverage_name: 심근병증진단비, coverage_category: specific_disease_diagnosis
```

### 카테고리 추론 로직
```python
# coverage_pipeline.py:204-233
def _infer_coverage_category(self, coverage_name: str) -> str:
    if '암' in coverage_name and '진단' in coverage_name:
        return 'cancer_diagnosis'
    elif ('뇌' in coverage_name or '심근경색' in coverage_name):
        return 'major_disease_diagnosis'
    elif '사망' in coverage_name or '장해' in coverage_name:
        return 'death_disability'
    # ...
```

---

## 5. document (문서)

### 데이터 소스
`ingestion/ingest_v3.py` → `_save_document()`

### 컬럼 상세

| 컬럼 | 타입 | 예시 값 | 소스 |
|------|------|---------|------|
| id | int | 12 | 자동생성 |
| document_id | varchar(100) | `hanwha-terms` | `documents_metadata.json` → document_id |
| company_id | int | 47 | FK → company.id |
| product_id | int | 9 | FK → product.id |
| variant_id | int | `NULL` / 3 | FK → product_variant.id (variant가 있는 경우만) |
| doc_type | varchar(50) | `terms` | `documents_metadata.json` → doc_type |
| doc_subtype | varchar(50) | `male` / `NULL` | `documents_metadata.json` → variant |
| version | varchar(50) | `2508` | `documents_metadata.json` → version |
| file_path | varchar(500) | `/Users/.../한화_약관.pdf` | `documents_metadata.json` → original_path |
| total_pages | int | 1065 | `documents_metadata.json` → total_pages |
| attributes | jsonb | `NULL` | 추가 메타데이터 (미사용) |

### 샘플 데이터
```
id: 12, document_id: hanwha-terms, doc_type: terms, total_pages: 1065
id: 13, document_id: kb-business_spec, doc_type: business_spec, total_pages: 91
id: 14, document_id: kb-proposal, doc_type: proposal, total_pages: 15
```

---

## 6. document_clause (문서 조항/청크)

### 데이터 소스
`ingestion/ingest_v3.py` → `_save_clauses()`
- terms → `text_parser.py`
- proposal → `table_parser.py` (carrier별 parser 사용)
- business_spec, product_summary → `hybrid_parser_v2.py`

### 컬럼 상세

| 컬럼 | 타입 | 예시 값 | 소스 |
|------|------|---------|------|
| id | int | 385893 | 자동생성 |
| document_id | int | 41 | FK → document.id |
| clause_number | varchar(50) | `제9조` | text_parser: 조항 번호 추출 |
| clause_title | varchar(500) | `중도인출` | text_parser: 조항 제목 추출 |
| clause_text | text | `(중도인출),...` | 파서별 본문 텍스트 |
| clause_type | varchar(50) | `article` / `table_row` | 파서 종류에 따라 결정 |
| structured_data | jsonb | `{coverage_name, premium, ...}` | table_parser에서 생성 (proposal) |
| section_type | varchar(100) | `NULL` ❌ | 미구현 (보통약관/특별약관 구분) |
| page_number | int | 298 | 원본 PDF 페이지 번호 |
| hierarchy_level | int | 0 | 계층 레벨 (미사용) |
| parent_clause_id | int | `NULL` | 부모 조항 (미구현) |

### clause_type 별 데이터

| clause_type | 소스 파서 | structured_data |
|-------------|----------|-----------------|
| `article` | text_parser.py | NULL |
| `table_row` | table_parser.py + carrier_parsers | `{coverage_name, coverage_amount, premium, period}` |
| `text_block` | hybrid_parser_v2.py | NULL |

### structured_data 예시 (proposal의 table_row)
```json
{
  "coverage_name": "뇌졸중진단비",
  "coverage_amount": "1,000만원",
  "premium": "132",
  "period": "20년/100세"
}
```

---

## 7. plan (가입설계)

### 데이터 소스
`ingestion/proposal_plan_extractor.py` → `_insert_plan()`

### 컬럼 상세

| 컬럼 | 타입 | 예시 값 | 소스 |
|------|------|---------|------|
| id | int | 47 | 자동생성 |
| document_id | int | 57 | FK → document.id (proposal 문서) |
| product_id | int | 57 | FK → product.id |
| variant_id | int | 25 / `NULL` | FK → product_variant.id |
| plan_name | varchar(200) | `여성 40세 20년납` | 자동 생성 (gender + age + payment_period) |
| target_gender | varchar(10) | `female` | 주민번호 또는 "남/여" 텍스트에서 추출 |
| target_age | int | 40 | "40세" 패턴에서 추출 |
| insurance_period | varchar(50) | `100세만기` | "100세만기" 패턴에서 추출 |
| payment_period | varchar(50) | `20년납` | "20년납" 패턴에서 추출 |
| payment_cycle | varchar(20) | `NULL` ❌ | 미구현 (월납/연납) |
| total_premium | numeric | 162843.00 | "합계" 행에서 추출 |
| attributes | jsonb | `NULL` | 추가 속성 (미사용) |

### 샘플 데이터
```
id: 47, plan_name: 여성 40세 20년납, target_gender: female, target_age: 40
      insurance_period: 100세만기, payment_period: 20년납, total_premium: 162843.00
```

### 추출 로직
```python
# proposal_plan_extractor.py:166-305
def _extract_plan_metadata(self, tables, doc):
    # 1. 피보험자 정보에서 성별/연령 추출
    #    "고객(650407-1******) 60세" → gender: male, age: 60

    # 2. 보험기간/납입기간 추출
    #    "20년납/100세만기" 또는 "100세만기/20년납"

    # 3. 합계 보험료 추출
    #    "합계: 162,843원"
```

---

## 8. plan_coverage (가입설계-담보 연결)

### 데이터 소스
`ingestion/proposal_plan_extractor.py` → `_link_plan_coverages()`

### 컬럼 상세

| 컬럼 | 타입 | 예시 값 | 소스 |
|------|------|---------|------|
| id | int | 4058 | 자동생성 |
| plan_id | int | 47 | FK → plan.id |
| coverage_id | int | 1799 | FK → coverage.id (coverage_name 매칭) |
| sum_insured | numeric | `NULL` ❌ | 미구현 - coverage_amount 파싱 필요 |
| sum_insured_text | varchar(100) | `NULL` ❌ | 미구현 |
| premium | numeric | 132.00 / `NULL` | document_clause.structured_data → premium |
| is_basic | boolean | `NULL` ❌ | 미구현 |

### 샘플 데이터
```
id: 4058, plan_id: 47, coverage_id: 1799, sum_insured: NULL, premium: 132.00
id: 4059, plan_id: 47, coverage_id: 1794, sum_insured: NULL, premium: 142.00
```

### 연결 로직
```python
# proposal_plan_extractor.py:337-393
def _link_plan_coverages(self, plan_id, document_id, tables):
    # 1. document_clause에서 coverage_name으로 조회
    # 2. coverage 테이블에서 같은 이름 찾기
    # 3. plan_coverage에 INSERT
```

---

## 9. risk_event (위험 이벤트)

### 데이터 소스
`ingestion/risk_event_extractor.py` → `_insert_risk_event()`

### 컬럼 상세

| 컬럼 | 타입 | 예시 값 | 소스 |
|------|------|---------|------|
| id | int | 1 | 자동생성 |
| event_type | varchar(50) | `cancer` / `injury` / `hospitalization` | RISK_EVENT_PATTERNS 딕셔너리 |
| event_name | varchar(200) | `입원` | clause_title에서 "정의" 제거 |
| severity_level | varchar/int | `medium` | event_type별 기본값 |
| icd_code_pattern | varchar(100) | `C73, C44, C77` / `NULL` | clause_text에서 ICD 코드 추출 |
| description | text | `'입원'이라 함은 의사...` | clause_text 첫 500자 |

### 샘플 데이터
```
id: 1, event_type: injury, event_name: 입원, severity_level: medium
id: 2, event_type: hospitalization, event_name: 입원, severity_level: low
```

### event_type 분류
```python
# risk_event_extractor.py:31-126
RISK_EVENT_PATTERNS = {
    'cancer': {'patterns': ['암', '일반암', '갑상선암', ...], 'severity_default': 'high'},
    'cerebrovascular': {'patterns': ['뇌출혈', '뇌졸중', ...], 'severity_default': 'high'},
    'cardiovascular': {'patterns': ['급성심근경색', ...], 'severity_default': 'high'},
    'injury': {'patterns': ['중증화상', '골절', ...], 'severity_default': 'medium'},
    'treatment': {'patterns': ['항암방사선치료', ...], 'severity_default': 'medium'},
    'hospitalization': {'patterns': ['입원', ...], 'severity_default': 'low'},
}
```

---

## 10. coverage_category (담보 카테고리)

### 데이터 소스
`db_refactoring/scripts/seed_data.py` (초기 시드 데이터)

### 컬럼 상세

| 컬럼 | 타입 | 예시 값 | 소스 |
|------|------|---------|------|
| id | int | 10 | 자동생성 |
| category_code | varchar(50) | `death_disability` | 시드 데이터 |
| category_name_kr | varchar(100) | `사망/장해/장애군` | 시드 데이터 |
| category_name_en | varchar(100) | `Death/Disability/Handicap` | 시드 데이터 |
| description | text | `NULL` | 미입력 |
| display_order | int | 1 | 시드 데이터 |

### 전체 목록 (9개)
```
death_disability, dementia_long_term_care, cancer_diagnosis,
major_disease_diagnosis, specific_disease_diagnosis,
hospitalization, surgery, outpatient, other_benefits
```

---

## 11. disease_code_set / disease_code (질병코드)

### 데이터 소스
`db_refactoring/scripts/seed_data.py` (초기 시드 데이터)

### disease_code_set (9개)
```
악성신생물, 제자리신생물, 기타피부암, 갑상선암, 뇌출혈, 뇌졸중,
급성심근경색증, 말기신부전증, 말기간질환
```

### disease_code (131개)
- code: `C00`, `C01`, ... (KCD 코드)
- code_type: `KCD`
- description_kr: `NULL` ❌ (미입력)

---

## 데이터 없는 테이블

| 테이블 | 이유 | 필요 작업 |
|--------|------|----------|
| coverage_group | 추출 파이프라인 미구현 | 약관 목차 파싱 필요 |
| benefit | 추출 파이프라인 미구현 | 보장급부 파싱 필요 |
| condition | extractor 실행 필요 | `python -m ingestion.condition_extractor` |
| exclusion | extractor 실행 필요 | `python -m ingestion.exclusion_extractor` |
| clause_coverage | 조항-담보 매핑 미구현 | LLM 또는 규칙 기반 매핑 필요 |
| clause_embedding | 벡터 생성 미실행 | `python -m vector_index.embedder` |
| benefit_risk_event | benefit 데이터 필요 | benefit 추출 후 매핑 |

---

## 파이프라인 실행 순서

```bash
# 1. PDF 변환
python scripts/convert_documents.py --output-dir data/converted_v2

# 2. 기본 ingestion
python -m ingestion.ingest_v3 data/documents_metadata.json

# 3. Coverage 추출
python -m ingestion.coverage_pipeline

# 4. Plan 추출
python -m ingestion.proposal_plan_extractor

# 5. Risk Event 추출
python -m ingestion.risk_event_extractor

# 6. Condition/Exclusion 추출
python -m ingestion.condition_extractor
python -m ingestion.exclusion_extractor

# 7. (선택) 벡터 임베딩
python -m vector_index.embedder
```
