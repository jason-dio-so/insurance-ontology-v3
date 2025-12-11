# Phase 2 개선 사항 및 향후 작업

## 완료된 개선 (2025-12-11)

### 한국어 금액 파싱 (Option 2 - Benefit Extraction 단계)

**문제**:
- 한국어 금액 표기(`'3,000만원'`, `'1천만원'`) 파싱 실패
- 519개 clause 중 99개만 benefit 생성 (420개 실패)

**해결**:
- `ingestion/extract_benefits.py`에 `parse_korean_amount()` 함수 추가
- 한국어 단위 변환: `만`, `천만`, `백만` 등

**결과**:
- **99개 → 384개** benefit 생성 성공 (285개 개선)
- 135개는 non-amount 값으로 정상 스킵 (`'적용이율'`, `'20년납 100세만기'` 등)

**구현 위치**:
- File: `ingestion/extract_benefits.py`
- Method: `BenefitExtractor.parse_korean_amount()` (lines 30-80)
- Usage: `extract_benefits()` method (lines 150-157)

**지원 형식**:
```python
'3,000만원' → 30,000,000
'1천만원'   → 10,000,000
'5백만원'   → 5,000,000
'10만원'    → 100,000
'2만원'     → 20,000
```

---

## 향후 개선 (Option 1 - Table Parsing 단계)

### 목적
Phase 1 재실행 시 테이블 파싱 단계에서 금액을 정규화하여 DB에 저장.
현재는 Phase 2.2에서 후처리 방식으로 해결 중.

### 구현 방법

#### 1. Carrier-Specific Parser 수정

**위치**: `ingestion/parsers/carrier_parsers/base_parser.py`

**추가할 메서드**:
```python
class BaseCarrierParser(ABC):
    # ... existing methods ...

    @staticmethod
    def parse_korean_amount(text: str) -> float:
        """
        Parse Korean amount format to numeric value

        Examples:
            '3,000만원' → 30000000.0
            '1천만원' → 10000000.0

        Returns:
            Numeric amount or None if unparseable
        """
        if not text or not isinstance(text, str):
            return None

        # Remove commas, spaces, and '원'
        text = text.replace(',', '').replace(' ', '').replace('원', '')

        # Skip non-amount strings
        skip_keywords = ['이율', '적용', '회한', '납', '만기', '형',
                        '급', '등급', '직', '년', '전화', ':']
        if any(kw in text for kw in skip_keywords):
            return None

        try:
            # Pattern 1: Pure numbers
            if text.isdigit():
                return float(text)

            # Pattern 2: Korean units
            text = text.replace('천만', '*10000000')  # 천만 = 10,000,000
            text = text.replace('백만', '*1000000')   # 백만 = 1,000,000
            text = text.replace('만', '*10000')       # 만 = 10,000
            text = text.replace('천', '*1000')        # 천 = 1,000
            text = text.replace('백', '*100')         # 백 = 100

            result = eval(text)
            return float(result)

        except:
            return None
```

#### 2. parse_coverage_row() 메서드 수정

각 carrier parser의 `parse_coverage_row()` 메서드에서 금액 추출 후 바로 변환:

```python
def parse_coverage_row(self, cells: List[str]) -> Optional[Dict]:
    """Parse coverage row from table cells"""
    # ... existing parsing logic ...

    # Extract coverage amount (original text)
    coverage_amount_text = cells[1]  # Example column

    # Convert to numeric using parser
    coverage_amount = self.parse_korean_amount(coverage_amount_text)

    return {
        'coverage_name': coverage_name,
        'coverage_amount': coverage_amount,      # Numeric value
        'coverage_amount_text': coverage_amount_text  # Original text
    }
```

#### 3. 구현 순서

**Step 1**: `base_parser.py`에 `parse_korean_amount()` 메서드 추가

**Step 2**: 8개 carrier parser 수정
- `samsung_parser.py`
- `db_parser.py`
- `lotte_parser.py`
- `meritz_parser.py`
- `kb_parser.py`
- `hanwha_parser.py`
- `hyundai_parser.py`
- `heungkuk_parser.py`

**Step 3**: Phase 1 재실행
```bash
cd /Users/cheollee/insurance-ontology-v2
export POSTGRES_URL="postgresql://postgres:postgres@localhost:5432/insurance_ontology_test"

# DB 초기화
docker exec -i $(docker ps -q -f name=insurance-postgres) \
  psql -U postgres -d insurance_ontology_test \
  -c "TRUNCATE TABLE document_clause, document CASCADE;"

# Checkpoint 제거
rm -f data/checkpoints/phase1_progress.json

# 재실행 (NORMAL 또는 STRICT 모드)
python3 scripts/batch_ingest.py --all --batch-size 5
```

**Step 4**: Phase 2 재실행
```bash
# Phase 2.1-2.4 순서대로 재실행
python -m ingestion.coverage_pipeline --carrier all
python -m ingestion.link_clauses --method all
python -m ingestion.extract_benefits  # 파싱 에러 없이 모두 성공할 것
python -m ingestion.load_disease_codes
```

**소요 시간**: 약 15-20분 (Phase 1 ingestion 10분 포함)

---

## 권장 타이밍

### 지금 (Phase 2 완료 시점)
✅ **Option 2 적용 완료** - `extract_benefits.py`에서 후처리
- 빠른 해결 (1분)
- Phase 3-4 진행 가능

### 나중 (Phase 1 재실행 필요 시)
⏳ **Option 1 적용 예정** - Table parsing 단계에서 정규화
- **시점 1**: STRICT 모드로 전환 시
- **시점 2**: Phase 5 정확도 개선 필요 시
- **시점 3**: Production 배포 전 최종 정리

---

## Trade-off 분석

| 항목 | Option 1 (Table Parsing) | Option 2 (Benefit Extraction) |
|------|-------------------------|------------------------------|
| 구현 위치 | carrier parsers | extract_benefits.py |
| 적용 시점 | Phase 1 | Phase 2.2 |
| DB 저장 형태 | Numeric (정규화) | Text (원본) |
| Phase 1 재실행 | 필요 (~10분) | 불필요 |
| 구현 복잡도 | 8개 parser 수정 | 1개 파일 수정 |
| 현재 상태 | 미적용 | ✅ 적용 완료 |
| 권장 시점 | STRICT 모드 전환 시 | 지금 (완료) |

---

## 현재 상태 (2025-12-11)

### Phase 2 완료 상태
- **Phase 2.1**: Coverage Pipeline ✅ (384 coverages)
- **Phase 2.2**: Extract Benefits ✅ (384 benefits, 한국어 파싱 적용)
- **Phase 2.3**: Link Clauses ✅ (674 mappings)
- **Phase 2.4**: Load Disease Codes ✅ (131 codes)

### 다음 단계
- **Phase 3**: Graph Sync (Neo4j)
- **Phase 4**: Vector Index (embeddings)

---

**마지막 업데이트**: 2025-12-11 02:00 KST
**작성자**: Claude
**목적**: Phase 2 개선 사항 및 향후 작업 가이드
