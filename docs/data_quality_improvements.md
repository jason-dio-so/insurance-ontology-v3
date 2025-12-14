# 데이터 품질 개선 항목

**생성일**: 2025-12-14

---

## 개선 필요 항목 요약

| 우선순위 | 테이블 | 컬럼 | 현재 상태 | 난이도 |
|----------|--------|------|----------|--------|
| 🔴 High | plan_coverage | sum_insured, sum_insured_text | 0% | 중 |
| 🔴 High | plan_coverage | premium | 24% | 중 |
| 🟡 Medium | coverage | coverage_period | 0% | 하 |
| 🟡 Medium | coverage | group_id | 0% | 상 |
| 🟢 Low | company | business_type | 0% | 하 |
| 🟢 Low | product | business_type, effective_date | 0% | 하 |
| 🟢 Low | disease_code | description_kr, description_en | 0% | 중 |

---

## 1. plan_coverage.sum_insured (가입금액)

### 현재 상태
- 0/571 (0%) 입력됨
- proposal 테이블에 "1,000만원", "3,000만원" 등 텍스트로 존재

### 원인
`proposal_plan_extractor.py`의 `_link_plan_coverages()`에서 `coverage_amount`를 float으로 변환 시도하나, 텍스트 형식("1,000만원")이라 실패

### 해결안
```python
# proposal_plan_extractor.py 수정

def _parse_sum_insured(self, text: str) -> tuple:
    """
    가입금액 텍스트를 숫자와 텍스트로 분리

    Examples:
        "1,000만원" → (10000000.0, "1,000만원")
        "3천만원" → (30000000.0, "3천만원")
        "1억원" → (100000000.0, "1억원")
    """
    if not text:
        return None, None

    import re

    # 원본 텍스트 보존
    original = text.strip()

    # 숫자 추출
    cleaned = text.replace(',', '').replace(' ', '')

    # 패턴 매칭
    if '억' in cleaned:
        match = re.search(r'([\d.]+)억', cleaned)
        if match:
            return float(match.group(1)) * 100000000, original
    elif '천만' in cleaned:
        match = re.search(r'([\d.]+)천만', cleaned)
        if match:
            return float(match.group(1)) * 10000000, original
    elif '만' in cleaned:
        match = re.search(r'([\d.]+)만', cleaned)
        if match:
            return float(match.group(1)) * 10000, original

    return None, original
```

### 적용 위치
`ingestion/proposal_plan_extractor.py:370-390`

---

## 2. plan_coverage.premium (보험료)

### 현재 상태
- 136/571 (24%) 입력됨
- 일부 회사만 premium 컬럼이 파싱됨

### 원인
- 회사별 테이블 구조 차이
- 일부 회사는 premium이 별도 컬럼이 아닌 합계 행에만 존재

### 해결안
```python
# 각 carrier parser에서 premium 추출 로직 확인 필요

# 1. 현재 파싱 현황 확인
SELECT c.company_code,
       COUNT(*) as total,
       COUNT(pc.premium) as with_premium
FROM plan_coverage pc
JOIN plan p ON pc.plan_id = p.id
JOIN document d ON p.document_id = d.id
JOIN company c ON d.company_id = c.id
GROUP BY c.company_code;

# 2. 회사별 parser 수정
# - samsung_parser.py
# - db_parser.py
# - 등등
```

### 적용 위치
`ingestion/parsers/carrier_parsers/*.py`

---

## 3. coverage.coverage_period (보장기간)

### 현재 상태
- 0/294 (0%) 입력됨
- `_clean_coverage_name()`에서 추출은 되지만 저장 안됨

### 원인
`coverage_pipeline.py`의 `save_coverages()`에서 `coverage_period` 값을 INSERT하지만,
`_clean_coverage_name()`에서 period를 추출하는 패턴이 제한적

### 해결안
```python
# coverage_pipeline.py 확인

# _clean_coverage_name() 에서 coverage_period 추출 패턴 확장
# Pattern 4: Period prefix ("10년형 암진단비")
period_match = re.match(r'^(\d+년형?)\s+(.+)$', name)
if period_match:
    result['coverage_period'] = period_match.group(1)
    name = period_match.group(2).strip()

# 추가 패턴
# - "10년만기"
# - "80세만기"
# - "전기납"
```

### 적용 위치
`ingestion/coverage_pipeline.py:306-310`

---

## 4. coverage.group_id (특별약관군)

### 현재 상태
- 0/294 (0%) 입력됨
- coverage_group 테이블도 0개

### 원인
coverage_group 추출 파이프라인 미구현

### 해결안
```python
# 새 파이프라인 필요: coverage_group_extractor.py

"""
1. terms 문서에서 목차(TOC) 파싱
2. "제N장 특별약관" 패턴 추출
3. coverage_group 테이블에 INSERT
4. coverage.group_id 연결
"""

class CoverageGroupExtractor:
    def extract_from_toc(self, document_id: int) -> List[Dict]:
        # 약관 목차에서 특별약관군 추출
        # 예: "제4장 암 진단 보장 특별약관군"
        pass

    def link_coverages(self, group_id: int, coverage_names: List[str]):
        # coverage.group_id 업데이트
        pass
```

### 난이도
상 - 약관 목차 구조 파싱 필요

---

## 5. company.business_type (사업유형)

### 현재 상태
- 0/8 (0%) 입력됨

### 원인
메타데이터에서 추출하지 않음

### 해결안
```sql
-- 수동 업데이트 (8개 회사만)
UPDATE company SET business_type = '손해보험'
WHERE company_code IN ('samsung', 'db', 'lotte', 'kb', 'hyundai', 'hanwha', 'heungkuk', 'meritz');

-- 또는 생명보험사가 있다면
UPDATE company SET business_type = '생명보험'
WHERE company_code IN ('samsung_life', ...);
```

### 적용 위치
SQL 직접 실행 또는 seed 스크립트

---

## 6. product.business_type, effective_date

### 현재 상태
- business_type: 0/8 (0%)
- effective_date: 0/8 (0%)

### 원인
메타데이터에서 추출하지 않음

### 해결안
```python
# ingest_v3.py 수정 - 메타데이터에서 추출

# documents_metadata.json 구조 확인
{
    "document_id": "samsung-proposal",
    "product_type": "장기손해보험",  # → business_type
    "effective_date": "2024-11-01"   # → effective_date
}

# 또는 PDF 첫 페이지에서 추출
# "이 보험은 장기손해보험입니다"
# "시행일: 2024년 11월 1일"
```

### 적용 위치
`ingestion/ingest_v3.py` 또는 메타데이터 파일 확장

---

## 7. disease_code.description_kr/en

### 현재 상태
- 0/131 (0%) 입력됨
- code만 있고 설명 없음

### 원인
KCD 코드 설명 데이터 소스 없음

### 해결안
```python
# 외부 데이터 소스 활용

# Option 1: 건강보험심사평가원 KCD 코드표 다운로드
# https://www.hira.or.kr/

# Option 2: 약관 내 질병분류표에서 추출
# "C00 입술의 악성 신생물"

# Option 3: 수동 매핑 테이블
KCD_DESCRIPTIONS = {
    'C00': ('입술의 악성 신생물', 'Malignant neoplasm of lip'),
    'C01': ('혀밑부분의 악성 신생물', 'Malignant neoplasm of base of tongue'),
    ...
}
```

### 난이도
중 - 외부 데이터 필요

---

## 우선순위별 실행 계획

### Phase 1 (즉시 적용 가능)
1. ✅ company.business_type - SQL 수동 업데이트
2. ✅ coverage.coverage_period - 패턴 확장

### Phase 2 (코드 수정 필요)
3. 🔧 plan_coverage.sum_insured - `_parse_sum_insured()` 구현
4. 🔧 plan_coverage.premium - carrier parser 점검

### Phase 3 (신규 개발 필요)
5. 🆕 coverage.group_id - coverage_group_extractor.py
6. 🆕 disease_code.description - 외부 데이터 연동

---

## 실행 명령어

```bash
# Phase 1: 즉시 적용
psql $POSTGRES_URL -c "UPDATE company SET business_type = '손해보험'"

# Phase 2: 코드 수정 후
python -m ingestion.proposal_plan_extractor  # sum_insured 재추출
python -m ingestion.coverage_pipeline        # coverage_period 재추출

# Phase 3: 신규 개발 후
python -m ingestion.coverage_group_extractor
python -m ingestion.disease_code_loader
```
