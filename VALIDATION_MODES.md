# Coverage Validation Modes

## 개요

Coverage name validation은 2가지 모드를 지원합니다:
- **NORMAL** (기본값): Balanced filtering (348 unique coverages)
- **STRICT**: Aggressive filtering (target: 250-270 unique coverages)

## 모드별 특징

### NORMAL Mode (Default)
**현재 결과**:
- Unique coverages: 348개
- False positive: 낮음 (~5%)
- 보험사별 분포:
  - Meritz: 91
  - Hanwha: 53
  - Samsung: 52
  - Others: 27-49

**장점**:
- Valid coverage를 잘못 제외할 위험 낮음
- 보험사별 naming variations 보존
- Phase 2.3 (link_clauses)에서 자연스럽게 정리

**단점**:
- 일부 generic/duplicate names 포함 가능
- Phase 5 정확도에 약간 영향 가능

**추천 시나리오**:
- ✅ Phase 2-4 진행 시 (기본 사용)
- ✅ Coverage 데이터 최대한 보존 필요 시
- ✅ False negative 최소화 필요 시

---

### STRICT Mode
**예상 결과**:
- Unique coverages: 250-270개 (30% 감소)
- False positive: 거의 없음 (~1%)
- Meritz: 91 → ~60개

**추가 필터 규칙** (NORMAL 대비):
1. **짧은 coverage names (≤5자)**
   - 예: "화상진단비", "상해수술비" → 제외
   - 이유: 너무 generic, 더 구체적인 버전 존재

2. **(급여) suffix**
   - 예: "CT촬영(급여)", "양전자단층촬영(PET)(급여)" → 제외
   - 이유: 의료 시술, coverage name 아님

3. **추가 generic terms**
   - 항암방사선치료비, 항암약물치료비
   - 질병수술비, 상해수술비
   - 화재벌금

4. **담보 suffix variations**
   - 예: "뇌출혈진단담보" (≤10자) → 제외
   - 이유: "뇌출혈진단비"와 중복

5. **Meritz-specific filter**
   - "암 ", "기타피부암", "양전자" 등으로 시작하는 짧은 이름 (<8자)

**장점**:
- Phase 5 QA 정확도 향상 (예상: 54% → 60-65%)
- 중복/generic names 최소화
- DB query 성능 향상

**단점**:
- False negative 위험 (~10-15%)
- 일부 valid coverage 제외 가능
- 보험사별 특수 naming 손실 가능

**추천 시나리오**:
- ✅ Phase 5 정확도가 목표에 미달할 때 (54% → 85% 목표)
- ✅ Production 배포 전 최종 정리
- ⚠️ Phase 2-3 완료 후 적용 권장 (데이터 손실 방지)

---

## 사용 방법

### 1. NORMAL Mode (현재 상태, 기본값)
```bash
# 환경변수 설정 없이 실행 (기본값)
cd /Users/cheollee/insurance-ontology-v2
export POSTGRES_URL="postgresql://postgres:postgres@localhost:5432/insurance_ontology_test"
python3 scripts/batch_ingest.py --all --batch-size 5
```

**결과**: 348 unique coverages

---

### 2. STRICT Mode 활성화

#### 방법 1: 환경변수 설정 (일시적)
```bash
# STRICT 모드로 실행
cd /Users/cheollee/insurance-ontology-v2
export COVERAGE_VALIDATION_STRICT=1
export POSTGRES_URL="postgresql://postgres:postgres@localhost:5432/insurance_ontology_test"

# DB 초기화
docker exec -i $(docker ps -q -f name=insurance-postgres) \
  psql -U postgres -d insurance_ontology_test \
  -c "TRUNCATE TABLE document_clause, document CASCADE;"

# Checkpoint 제거
rm -f data/checkpoints/phase1_progress.json

# 재실행
python3 scripts/batch_ingest.py --all --batch-size 5
```

**결과**: 250-270 unique coverages (예상)

#### 방법 2: .env 파일에 영구 설정
```bash
# .env 파일에 추가
echo "COVERAGE_VALIDATION_STRICT=1" >> .env

# 이후 모든 ingestion에서 자동 적용
python3 scripts/batch_ingest.py --all --batch-size 5
```

#### 방법 3: 코드에서 직접 설정
```python
# ingestion/parsers/carrier_parsers/base_parser.py 수정
class BaseCarrierParser(ABC):
    # 36번째 줄 수정
    STRICT_MODE = True  # os.getenv(...) 대신 직접 True 설정
```

---

### 3. 결과 비교

#### NORMAL vs STRICT 비교 실행
```bash
# 1. NORMAL 모드 실행 (현재)
cd /Users/cheollee/insurance-ontology-v2
export POSTGRES_URL="postgresql://postgres:postgres@localhost:5432/insurance_ontology_test"
python3 scripts/batch_ingest.py --all --batch-size 5

# 결과 저장
psql $POSTGRES_URL -c "SELECT COUNT(DISTINCT structured_data->>'coverage_name') FROM document_clause WHERE clause_type='table_row';" > normal_result.txt

# 2. STRICT 모드 실행
# DB 초기화
docker exec -i $(docker ps -q -f name=insurance-postgres) \
  psql -U postgres -d insurance_ontology_test \
  -c "TRUNCATE TABLE document_clause, document CASCADE;"
rm -f data/checkpoints/phase1_progress.json

# STRICT 모드로 재실행
export COVERAGE_VALIDATION_STRICT=1
python3 scripts/batch_ingest.py --all --batch-size 5

# 결과 저장
psql $POSTGRES_URL -c "SELECT COUNT(DISTINCT structured_data->>'coverage_name') FROM document_clause WHERE clause_type='table_row';" > strict_result.txt

# 비교
echo "=== NORMAL Mode ===" && cat normal_result.txt
echo "=== STRICT Mode ===" && cat strict_result.txt
```

---

## 권장 워크플로우

### Phase 2-4: NORMAL Mode 사용 (현재)
```
Phase 1 (Ingestion)      → NORMAL (348 coverages) ✅ 완료
Phase 2 (Coverage Extraction) → NORMAL 유지
Phase 3 (Graph Sync)     → NORMAL 유지
Phase 4 (Vector Index)   → NORMAL 유지
Phase 5 (QA Eval)        → 정확도 측정
```

### Phase 5 정확도 검증 후 결정
```
IF Phase 5 accuracy < 75%:
  → STRICT 모드 활성화 고려
  → Phase 1 재실행 (STRICT)
  → Phase 2-5 재실행
  → 정확도 재측정

ELSE IF Phase 5 accuracy ≥ 75%:
  → NORMAL 모드 유지 (현재 상태)
  → Production 배포
```

---

## 검증 쿼리

### 모드별 결과 확인
```sql
-- 1. 전체 unique coverage count
SELECT COUNT(DISTINCT structured_data->>'coverage_name') AS unique_coverages
FROM document_clause
WHERE clause_type = 'table_row' AND structured_data->>'coverage_name' IS NOT NULL;

-- 2. 보험사별 분포
SELECT
    SPLIT_PART(d.document_id, '-', 1) AS carrier,
    COUNT(DISTINCT dc.structured_data->>'coverage_name') AS unique_coverages
FROM document d
JOIN document_clause dc ON d.id = dc.document_id
WHERE dc.clause_type = 'table_row' AND dc.structured_data->>'coverage_name' IS NOT NULL
GROUP BY carrier
ORDER BY unique_coverages DESC;

-- 3. Top 20 coverage names
SELECT
    structured_data->>'coverage_name' AS coverage,
    COUNT(*) AS count
FROM document_clause
WHERE clause_type = 'table_row'
GROUP BY coverage
ORDER BY count DESC
LIMIT 20;

-- 4. 짧은 coverage names (STRICT 모드에서 제외될 것들)
SELECT
    structured_data->>'coverage_name' AS coverage,
    LENGTH(structured_data->>'coverage_name') AS len,
    COUNT(*) AS count
FROM document_clause
WHERE clause_type = 'table_row'
  AND LENGTH(structured_data->>'coverage_name') <= 5
GROUP BY coverage
ORDER BY count DESC
LIMIT 20;
```

---

## Trade-off 요약

| 항목 | NORMAL Mode | STRICT Mode |
|------|-------------|-------------|
| Unique coverages | 348개 | 250-270개 (예상) |
| False positive | ~5% | ~1% |
| False negative | ~0% | ~10-15% |
| Phase 5 정확도 (예상) | 65-75% | 75-85% |
| Data completeness | High | Medium |
| 추천 시점 | Phase 2-4 | Phase 5 정확도 부족 시 |

---

## 현재 상태 (2025-12-11)

**Mode**: NORMAL (default)
**Result**: 348 unique coverages
**Status**: ✅ Ready for Phase 2

**Next Steps**:
1. Phase 2 (Coverage Pipeline) 진행 → NORMAL 모드 유지
2. Phase 5 (QA Evaluation) 결과 확인
3. 필요 시 STRICT 모드 활성화

**Files**:
- Validation code: `ingestion/parsers/carrier_parsers/base_parser.py`
- STRICT filters: Lines 408-441 (conditional, currently inactive)
- Control: `COVERAGE_VALIDATION_STRICT` environment variable
