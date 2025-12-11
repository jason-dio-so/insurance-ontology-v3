# 신정원 담보명 매핑 자료 분석

**분석 일자**: 2025-12-11
**자료 출처**: `examples/담보명mapping자료.xlsx`
**목적**: 보험사별 담보명 표준화 매핑 활용 가능성 검토

---

## 📋 자료 개요

### 구조
- **행 수**: 264개
- **보험사**: 8개 (메리츠, 한화, 롯데, 흥국, 삼성, 현대, KB, DB)
- **신정원 표준 코드**: 28개
- **회사별 담보명**: 194개 (unique)

### 컬럼 구조
```
ins_cd        : 보험사 코드 (N01, N02, ...)
보험사명       : 보험사 이름
cre_cvr_cd    : 신정원 표준 담보 코드 (A4200_1, A4102, ...)
신정원코드명   : 표준 담보 명칭
담보명(가입설계서): 각 보험사의 실제 담보명
```

### 신정원 표준 코드 28개 목록

| 코드 | 표준 명칭 | 회사 수 |
|------|----------|---------|
| A4104_1 | 심장질환진단비 | 22 |
| A4210 | 유사암진단비 | 15 |
| A9630_1 | 다빈치로봇암수술비 | 14 |
| A9619_1 | 표적항암약물허가치료비(최초1회한) | 14 |
| A9617_1 | 항암방사선약물치료비(최초1회한) | 14 |
| A9640_1 | 혈전용해치료비 | 12 |
| A5298_001 | 유사암수술비 | 11 |
| A5300 | 상해수술비 | 10 |
| A5100 | 질병수술비 | 10 |
| A5104_1 | 뇌혈관질환수술비 | 9 |
| A4105 | 허혈성심장질환진단비 | 8 |
| A4200_1 | 암진단비(유사암제외) | 8 |
| A4101 | 뇌혈관질환진단비 | 8 |
| A4103 | 뇌졸중진단비 | 8 |
| A4102 | 뇌출혈진단비 | 7 |
| A1100 | 질병사망 | 8 |
| A1300 | 상해사망 | 8 |
| ... | ... | ... |

---

## 🔍 매핑 예시

### 1. 암진단비(유사암제외) [A4200_1]

8개 보험사의 naming variation:
```
메리츠  : 암진단비(유사암제외)
한화   : 암(4대유사암제외)진단비
롯데   : 일반암진단비Ⅱ
흥국   : 암진단비(유사암제외)
삼성   : 암진단비(유사암제외)
현대   : 암진단Ⅱ(유사암제외)담보
KB    : 암진단비(유사암제외)
DB    : 암진단비Ⅱ(유사암제외)
```

**분석**: 동일한 담보이지만 회사마다 다른 표현
- 롯데: "일반암"으로 표현
- 한화: "4대유사암제외"로 명시
- 현대: "담보" suffix 사용
- DB: "Ⅱ" 버전 표기

### 2. 유사암진단비 [A4210]

15개 entry (한화, 삼성은 세부 분류):
```
메리츠  : 유사암진단비
한화   : 4대유사암진단비(기타피부암)
한화   : 4대유사암진단비(갑상선암)
한화   : 4대유사암진단비(제자리암)
한화   : 4대유사암진단비(경계성종양)
롯데   : 갑상선암·기타피부암·유사암진단비
흥국   : 유사암진단비
삼성   : 유사암 진단비(기타피부암)(1년50%)
삼성   : 유사암 진단비(갑상선암)(1년50%)
삼성   : 유사암 진단비(대장점막내암)(1년50%)
삼성   : 유사암 진단비(제자리암)(1년50%)
삼성   : 유사암 진단비(경계성종양)(1년50%)
현대   : 유사암진단Ⅱ(양성뇌종양포함)담보
KB    : 유사암진단비
DB    : 유사암진단비Ⅱ(1년감액지급)
```

**분석**: 가장 복잡한 variation
- 한화, 삼성: 유사암을 4-5개로 세분화
- 롯데, 메리츠, KB: 단일 담보
- 표준화 매핑이 가장 필요한 케이스

### 3. 뇌출혈진단비 [A4102]

7개 보험사 (variation 적음):
```
메리츠  : 뇌출혈진단비
롯데   : 뇌출혈진단비
흥국   : 뇌출혈진단비
삼성   : 뇌출혈진단비
현대   : 뇌출혈진단담보
KB    : 뇌출혈진단비
DB    : 뇌출혈진단비
```

**분석**: 비교적 통일된 naming
- 현대만 "담보" suffix 사용
- 나머지는 동일

---

## 📊 현재 시스템과의 비교

### Coverage 개수 비교

**신정원 매핑 자료**:
```
삼성    : 40개
KB     : 38개
롯데    : 35개
한화    : 35개
흥국    : 34개
DB     : 30개
현대    : 27개
메리츠   : 25개
```

**우리 DB**:
```
메리츠   : 83개
한화    : 49개
현대    : 49개
DB     : 47개
KB     : 45개
삼성    : 43개
롯데    : 41개
흥국    : 27개
```

**분석**:
- 우리 DB가 신정원 자료보다 많은 담보 포함
- 신정원 자료는 **주요 28개 담보만** 표준화
- 우리 DB는 proposal에서 추출한 **전체 담보**

### 매칭률

- **신정원 담보명**: 194개
- **우리 DB 담보명**: 326개
- **정확 일치**: 131개 (**67.5%** 매칭)
- **우리 DB에만**: 195개
- **신정원에만**: 63개

**분석**:
- 67.5% 매칭은 꽤 높은 편
- 우리 DB에 195개 더 많은 이유:
  - Proposal에서 추출한 모든 담보 (갱신형, 세부 옵션 포함)
  - 예: "(10년갱신)갱신형 다빈치로봇 암수술비"
- 신정원에 63개 더 있는 이유:
  - 우리가 아직 처리하지 않은 문서의 담보
  - 예: "4대유사암진단비(갑상선암)" 등 세분화된 담보

---

## 💡 시스템 개선 활용 방안

### ✅ 방안 1: Coverage Normalization Layer (추천)

**목적**: Cross-company comparison 개선

**구현**:
1. 신정원 표준 코드를 normalization layer로 활용
2. DB 스키마 확장:
   ```sql
   ALTER TABLE coverage
   ADD COLUMN standard_coverage_code VARCHAR(20);
   ADD COLUMN standard_coverage_name VARCHAR(100);
   ```

3. 매핑 테이블 import:
   ```sql
   CREATE TABLE coverage_standard_mapping (
       company_code VARCHAR(10),
       coverage_name VARCHAR(200),
       standard_code VARCHAR(20),
       standard_name VARCHAR(100),
       PRIMARY KEY (company_code, coverage_name)
   );
   ```

**활용**:
- Cross-company comparison 쿼리:
  ```sql
  -- "암진단비" 표준 코드로 모든 회사 비교
  SELECT c.company_name, cov.coverage_name, b.benefit_amount
  FROM coverage cov
  JOIN coverage_standard_mapping csm ON cov.coverage_name = csm.coverage_name
  WHERE csm.standard_code = 'A4200_1'
  ```

**예상 효과**:
- Comparison 쿼리 정확도 향상
- "삼성과 롯데의 암진단비 비교" → 표준 코드로 정확히 매칭
- Phase 5 Comparison category 이미 100%이지만 더 robust해짐

**소요 시간**: 2-3시간

---

### ✅ 방안 2: NL Query Mapping 개선

**목적**: Amount/Coverage query 정확도 향상

**구현**:
1. `ontology/nl_mapping.py` 개선
2. 표준 명칭을 fallback으로 사용:
   ```python
   def _extract_coverages(self, query):
       # 기존 로직으로 담보명 추출
       found = self._exact_match(query)

       # 못 찾으면 표준 명칭으로 재시도
       if not found:
           found = self._standard_name_match(query)

       return found
   ```

3. 신정원 표준 명칭을 coverage alias로 활용

**예상 효과**:
- "일반암진단비" (롯데 표현) 쿼리 → "암진단비(유사암제외)" 표준 명칭으로 매칭
- Amount category 정확도 향상 (현재 50% → 60-70%)

**소요 시간**: 2-3시간

---

### ⚠️ 방안 3: Coverage Deduplication (선택적)

**목적**: Coverage 중복 제거 및 정규화

**문제**:
- 현재 우리 DB: 326개 unique coverages
- 신정원 표준: 28개 core coverages
- 많은 variation이 사실상 동일 담보

**예시**:
```
우리 DB:
- 4대유사암진단비(갑상선암)
- 4대유사암진단비(기타피부암)
- 4대유사암진단비(제자리암)
- 4대유사암진단비(경계성종양)

신정원 표준:
- 유사암진단비 [A4210]
```

**구현**:
1. 표준 코드로 grouping
2. 세부 분류는 metadata로 저장
3. Coverage entity는 표준 명칭 사용

**주의**:
- 현재 구조 대폭 변경 필요
- Benefit amount가 세부 분류별로 다를 수 있음
- **권장하지 않음** (현재 구조 유지가 더 정확)

---

## 🎯 권장 사항

### 우선순위 1: Coverage Normalization Layer (⭐ 강력 추천)

**Why**:
1. 현재 시스템 구조 변경 최소화
2. Cross-company comparison 명확히 개선
3. 67.5% 매칭률로 즉시 활용 가능
4. 표준 코드 28개만 매핑하면 됨

**How**:
1. `coverage_standard_mapping` 테이블 생성
2. 신정원 엑셀 데이터 import
3. Coverage query에서 standard_code 활용
4. Comparison 쿼리 개선

**Expected Impact**:
- Comparison category: 100% 유지 (더 robust)
- Amount category: 50% → 60-70% (+10-20%)
- Cross-company 쿼리 정확도 향상

**Effort**: 2-3 hours

---

### 우선순위 2: NL Query Mapping에 표준 명칭 활용

**Why**:
1. Amount query 실패 원인 중 하나가 담보명 variation
2. 표준 명칭을 alias로 추가하면 매칭률 향상
3. Minimal code change

**How**:
1. 표준 명칭 28개를 coverage alias로 추가
2. NL mapper에서 fallback으로 사용
3. 예: "암진단금" → "암진단비(유사암제외)" 표준 명칭 매칭

**Expected Impact**:
- Amount category: 50% → 60% (+10%)
- Coverage extraction 정확도 향상

**Effort**: 2 hours

---

## 📝 다음 단계 제안

### Phase 5 개선 후속 작업

**현재 상태**:
- Phase 5 v3: 80% accuracy
- Amount category: 50% (primary blocker)
- Gap to goal: -10% (5 queries)

**Option A**: 신정원 매핑 먼저 적용 (2-3시간)
- Coverage normalization layer 구축
- Amount/Comparison 쿼리 개선
- Phase 5 v4 재실행
- **예상**: 80% → 85% (+5%)

**Option B**: Amount zero-result 먼저 해결 (2시간)
- Q006, Q008, Q009 fallback search
- Phase 5 v4 재실행
- **예상**: 80% → 86% (+6%)

**Option C**: 둘 다 순차 실행 (4-5시간)
- Option B → Option A 순서
- **예상**: 80% → 88-90% (목표 달성 가능)

**권장**: **Option C** (둘 다 실행)
- Amount zero-result는 빠른 승리 (quick win)
- Coverage normalization은 장기적 품질 개선
- 합치면 목표 90% 달성 가능성 높음

---

## 📊 데이터 품질 평가

### 신정원 매핑 자료의 강점
✅ **표준화**: 28개 core coverage 명확히 정의
✅ **Coverage**: 8개 주요 보험사 모두 포함
✅ **정확성**: 67.5% 우리 DB와 매칭
✅ **실용성**: 주요 담보 위주 (암, 뇌, 심장, 수술, 입원)

### 신정원 매핑 자료의 한계
⚠️ **Scope**: 28개 담보만 (우리 DB는 326개)
⚠️ **최신성**: 업데이트 시기 불명 (갱신형 일부 누락)
⚠️ **세분화**: 유사암 등 세부 분류 불일치

### 종합 평가
**활용 가치**: ⭐⭐⭐⭐☆ (4/5)

**결론**: 주요 28개 담보에 대해서는 매우 유용. Cross-company comparison과 query normalization에 즉시 활용 가능.

---

**Last Updated**: 2025-12-11 10:30 KST
**Next Action**: Option C 실행 (Amount zero-result + Coverage normalization)
**Expected Outcome**: Phase 5 accuracy 80% → 88-90% (goal achieved!)
