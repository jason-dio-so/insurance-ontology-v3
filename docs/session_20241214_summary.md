# 작업 요약 (2024-12-14)

## 1. Coverage 필터 개선

### 문제점
Meritz 회사의 coverage가 120개로 과다 추출됨. 노이즈 데이터 포함:
- 플랜 타입: "영업용 운전자형", "보험료 납입면제형"
- PDF 파싱 오류: "비급 여 (전 액본 인부 담포 함) 치료"
- 조항번호 포함: "153 뇌혈관질환진단비"
- 너무 일반적인 항목: "2종수술", "80세만기"

### 해결
`ingestion/parsers/carrier_parsers/base_parser.py`의 `is_valid_coverage_name()` 함수에 필터 추가:

```python
# 1. 띄어쓰기 비율 체크 (25% 초과 시 제외)
if space_ratio > 0.25:
    return False

# 2. 깨진 한글 패턴
if re.search(r'[가-힣]\s[가-힣]\s[가-힣]', text):
    return False

# 3. 플랜 타입 패턴
plan_type_patterns = [r'운전자형$', r'납입면제.*형$', r'가전제품.*비용$']

# 4. 수술 종류 패턴
if re.match(r'^\d+종수술$', text):
    return False

# 5. (급여) suffix
if text.endswith('(급여)'):
    return False

# 6. 법률비용 패턴
if '법률비용' in text:
    return False
```

### 결과
| 회사 | 개선 전 | 개선 후 |
|------|---------|---------|
| meritz | 120개 | 31개 |
| hanwha | 85개 | 46개 |
| lotte | 75개 | 38개 |
| **총합** | **533개** | **290개** |

---

## 2. 스키마 비교 및 통합 (v3 ← r1)

### 비교 결과
r1에만 있는 테이블 4개:

| 테이블 | 설명 |
|--------|------|
| `risk_event` | 위험 이벤트 (진단, 수술, 입원, 사망 등) |
| `benefit_risk_event` | 급부-위험이벤트 M:N 매핑 |
| `plan` | 가입설계서 메타데이터 |
| `plan_coverage` | 가입설계-담보 연결 (가입금액, 보험료) |

### 적용
r1 스키마를 v3에 복사:
```bash
cp insurance-ontology-r1/db_refactoring/postgres/001_initial_schema.sql \
   insurance-ontology-v3/db_refactoring/postgres/001_initial_schema.sql
```

### 데이터 파이프라인 실행
```bash
# Plan 추출
python -m ingestion.proposal_plan_extractor

# Risk Event 추출
python -m ingestion.risk_event_extractor
```

### 결과
| 테이블 | 레코드 수 |
|--------|----------|
| plan | 10개 |
| plan_coverage | 614개 |
| risk_event | 572개 |
| benefit_risk_event | 0개 |

---

## 3. clause_number 추출 수정

### 문제점
coverage 테이블의 `clause_number` 컬럼이 항상 NULL.

**원인**: `base_parser.py`에서 숫자로 시작하는 coverage_name을 필터링:
```python
# 이 필터가 "119 뇌졸중진단비" 형태를 제외시킴
if re.match(r'^\d+\s+', text):
    return False
```

### 해결
필터를 주석 처리하여 `coverage_pipeline._clean_coverage_name()`에서 처리하도록 변경:

```python
# base_parser.py
# NOTE: 숫자 prefix는 coverage_pipeline._clean_coverage_name()에서 clause_number로 분리
# if re.match(r'^\d+\s+', text):
#     return False
```

### 결과
```
clause_number가 있는 coverage: 8개

[  2] 상해사망                          (lotte)
[ 21] 질병사망                          (lotte)
[ 97] 카티(CAR-T)항암약물허가치료비        (lotte)
[123] 뇌경색증(I63) 혈전용해치료비         (lotte)
[136] 급성심근경색증(I21) 혈전용해치료비    (lotte)
[180] 혈전용해치료비Ⅱ(특정심장질환)        (meritz)
[633] (10년갱신)갱신형 표적항암약물허가치료비Ⅱ (meritz)
[801] 자동갱신특약                        (meritz)
```

> 대부분의 회사 PDF에서 조항번호가 coverage_name에 포함되지 않아 8개만 추출됨

---

## 4. 파일 수정 목록

| 파일 | 변경 내용 |
|------|----------|
| `ingestion/parsers/carrier_parsers/base_parser.py` | 노이즈 필터 추가, 숫자 prefix 필터 비활성화 |
| `ingestion/coverage_pipeline.py` | 필드명 수정 (coverage_amount, period) |
| `ingestion/proposal_plan_extractor.py` | 경로 매핑 추가 (company_code → 한글 디렉토리) |
| `db_refactoring/postgres/001_initial_schema.sql` | r1 스키마로 교체 (4개 테이블 추가) |
| `.gitignore` | data/, *.docx, *.xlsx 추가 |

---

## 5. 최종 데이터 현황

### 테이블별 레코드 수
| 테이블 | 수량 |
|--------|------|
| company | 8개 |
| product | 8개 |
| document | 38개 |
| document_clause | ~80,000개 |
| coverage | 294개 |
| plan | 10개 |
| plan_coverage | 614개 |
| risk_event | 572개 |

### 회사별 Coverage
| 회사 | Coverage 수 |
|------|-------------|
| hyundai | 48개 |
| hanwha | 46개 |
| lotte | 38개 |
| samsung | 36개 |
| kb | 35개 |
| db | 32개 |
| meritz | 31개 |
| heungkuk | 24개 |

---

## 6. 실행 명령어 참고

```bash
# 전체 재ingestion
python -m ingestion.ingest_v3 data/documents_metadata.json

# Coverage 추출
python -m ingestion.coverage_pipeline

# Plan 추출
python -m ingestion.proposal_plan_extractor

# Risk Event 추출
python -m ingestion.risk_event_extractor
```
