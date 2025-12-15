# Ontology 모듈

자연어 질의를 온톨로지 엔티티로 매핑하는 모듈입니다.

---

## nl_mapping.py

자연어 질의에서 보험 도메인 엔티티를 추출하고 DB 필터로 변환합니다.

### 주요 기능

| 기능 | 설명 |
|------|------|
| 회사명 추출 | 별칭 매핑 포함 (삼성화재 → 삼성, 동부화재 → DB) |
| 상품명 추출 | DB 상품 테이블 기반 매칭 |
| 담보명 추출 | coverage 테이블 + structured_data 기반 |
| 질병명 추출 | disease_code 테이블 기반 |
| 금액 필터 | "3000만원", "1억 이상" 등 파싱 |
| 성별 필터 | "남성", "여성" 추출 |
| 나이 필터 | "40세", "30세 이상" 등 파싱 |
| 키워드 추출 | 보험 도메인 용어 (암, 진단, 수술 등) |

### 사용법

```python
from ontology.nl_mapping import NLMapper

mapper = NLMapper()
entities = mapper.extract_entities("삼성화재 암진단금 3000만원은?")

print(entities)
# {
#     "companies": ["삼성"],
#     "products": [],
#     "coverages": ["암진단금"],
#     "diseases": [],
#     "keywords": ["암", "진단"],
#     "amount_filter": {"min": 30000000, "max": 30000000},
#     "gender_filter": None,
#     "age_filter": None,
#     "filters": {
#         "company_id": 1,
#         "amount": {"min": 30000000, "max": 30000000}
#     }
# }
```

### 회사명 별칭 매핑

```python
COMPANY_ALIASES = {
    '삼성화재': '삼성',
    '삼성생명': '삼성',
    '동부화재': 'DB',
    'DB손보': 'DB',
    '현대해상': '현대',
    '한화손보': '한화',
    '롯데손보': '롯데',
    'KB손보': 'KB',
    '메리츠화재': '메리츠',
    '흥국화재': '흥국',
    # ...
}
```

### 금액 파싱 예시

| 입력 | 결과 |
|------|------|
| `"3000만원"` | `{"min": 30000000, "max": 30000000}` |
| `"1억원"` | `{"min": 100000000, "max": 100000000}` |
| `"2천만원 이상"` | `{"min": 20000000, "max": None}` |
| `"5000만원 이하"` | `{"min": None, "max": 50000000}` |
| `"1억~2억"` | `{"min": 100000000, "max": 200000000}` |

### 클래스 구조

```
NLMapper
├── extract_entities(query)      # 메인 엔티티 추출
├── _extract_companies(query)    # 회사명 추출
├── _extract_products(query)     # 상품명 추출
├── _extract_coverages(query)    # 담보명 추출
├── _extract_diseases(query)     # 질병명 추출
├── _extract_keywords(query)     # 키워드 추출
├── _extract_amount(query)       # 금액 필터 추출
├── _extract_gender(query)       # 성별 필터 추출
├── _extract_age(query)          # 나이 필터 추출
├── get_filtered_search_params() # 벡터 검색 파라미터 생성
└── explain_entities(query)      # 추출 결과 설명 (디버깅용)
```

### 사용처

| 파일 | 용도 |
|------|------|
| `retrieval/hybrid_retriever.py` | 하이브리드 검색 시 엔티티 필터링 |
| `api/cli.py` | CLI 질의 처리 |
| `api/server.py` | API 서버 질의 처리 |

### 캐시 구조

성능 최적화를 위해 DB 조회 결과를 캐시합니다:

```python
self._company_cache   # 회사 정보 (id, company_name, company_code)
self._product_cache   # 상품 정보 (id, name, product_type, company_name)
self._coverage_cache  # 담보 정보 (id, name, coverage_group)
self._disease_cache   # 질병 코드 (code, name)
```

### 의존성

- PostgreSQL 연결 (`POSTGRES_URL` 환경변수)
- psycopg2
- python-dotenv
