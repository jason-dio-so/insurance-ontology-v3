# Gold QA Set 평가 결과 분석 리포트

**평가일**: 2025-12-15
**평가 버전**: Phase 5 Hybrid RAG Pipeline
**결과**: 74% (37/50) - 목표 90% 미달

---

## 1. Executive Summary

| 지표 | 현재 | 목표 | Gap |
|------|------|------|-----|
| 전체 정확도 | 74% | 90% | -16% |
| P95 지연시간 | 8,163ms | <5,000ms | +3,163ms |

**핵심 문제**: amount 카테고리 50% 정확도가 전체 성능을 끌어내림

---

## 2. 실패 케이스 원인 분석

### 2.1 원인별 분류

총 13개 실패 케이스를 4가지 원인으로 분류:

| 원인 | 건수 | 비율 | 영향도 |
|------|------|------|--------|
| **A. 임베딩 유사도 부족** | 10 | 77% | 높음 |
| **B. 보험사명 매핑** | - | - | ✅ 정상 동작 |
| **C. 복합 쿼리 처리 미흡** | 2 | 15% | 중간 |
| **D. 필터 조건 미반영** | 1 | 8% | 낮음 |

---

### 2.2 원인 A: 임베딩 유사도 부족 (10건) - **핵심 문제**

**데이터는 존재하지만 Vector Search에서 상위에 올라오지 않음**

| Query ID | 쿼리 | 기대 결과 | 실제 반환 | 유사도 |
|----------|------|----------|----------|--------|
| Q002 | DB손보 뇌출혈 | 뇌출혈진단비 1,000만원 | 다른 담보 | 0.35~0.45 |
| Q005 | 메리츠 암진단 | 암진단비 3,000만원 | 다른 담보 | 0.35~0.45 |
| Q006 | 현대해상 뇌졸중 | 뇌졸중진단비 1,000만원 | 다른 담보 | 0.35~0.45 |
| Q008 | 흥국 암수술비 | 암수술비 600만원 | 다른 담보 | 0.35~0.45 |
| Q009 | 삼성 재진단암 | 재진단암 2,000만원 | 정의만 반환 | 0.40 |
| Q010 | 롯데 유사암 | 유사암 30만원 | 정의만 반환 | 0.40 |
| Q021 | DB 40세 이하 뇌출혈 | 뇌출혈 정보 | 0건 | - |
| Q026 | KB 수술비 보장 | 질병수술비 | 암직접치료입원일당 | 0.41 |
| Q027 | 흥국 입원비 | 입원비 | 뇌출혈진단비 | 0.36 |
| Q035 | 메리츠 KB 수술비 비교 | 양사 수술비 | 메리츠만 반환 | 0.40 |

**실제 테스트 결과**:
```python
# "KB 수술비 보장" 검색
NLMapper: company_id = 51 (KB) ✅ 정상 추출

# DB에 KB 수술비 데이터 존재 확인
"질병수술비", "암수술비(유사암제외)", "뇌혈관질환수술비" 등 ✅ 존재

# 그러나 검색 결과
→ "암직접치료입원일당" (similarity: 0.407) ❌ 엉뚱한 결과
→ "수술비" 관련 문서가 상위 5개에 포함되지 않음
```

**원인 심층 분석**:
1. **순수 Vector Search 의존**: 키워드 매칭 부스팅 없음
2. **청크 내 여러 담보 혼재**: 임베딩이 희석되어 특정 담보 검색 어려움
3. **일반적 보험 용어 임베딩 유사**: "수술비", "입원비", "진단비"가 임베딩 공간에서 가까움

---

### 2.3 원인 B: 보험사명 매핑 - **정상 동작 확인됨** ✅

**기존 추정과 달리, 별칭 사전은 이미 구현되어 정상 동작함**

```python
# ontology/nl_mapping.py (Line 39-79)
COMPANY_ALIASES = {
    'KB손보': 'KB',
    'KB손해보험': 'KB',
    '흥국화재': '흥국',
    # ... 등
}

# 테스트 결과
"KB 수술비 보장"     → company_id: 51 ✅
"흥국 입원비"        → company_id: 55 ✅
"DB손보 뇌출혈"      → company_id: 72 ✅
```

**결론**: Q026, Q027 실패 원인은 별칭 문제가 아니라 **임베딩 유사도 문제**

---

### 2.4 원인 C: 복합 쿼리 처리 미흡 (2건)

| Query ID | 쿼리 | 기대 | 실제 |
|----------|------|------|------|
| Q038 | DB 한화 입원비 비교 | DB, 한화 정보 | 삼성, 메리츠 정보 반환 |
| Q048 | 모든 보험사 비교 | 8개 보험사 | 일부만 반환 |

**상세 분석**:
```
Q038 답변: 삼성(1만원), 메리츠(1만원) 정보만 반환
→ 쿼리에 명시된 "DB", "한화"가 아닌 다른 보험사 정보 반환
→ 문제: 복수 보험사 조건 검색 실패
```

---

### 2.5 원인 D: 필터 조건 미반영 (1건)

| Query ID | 쿼리 | 문제 |
|----------|------|------|
| Q014 | 롯데 남성 뇌출혈 보장금액 | 답변에 "남성" 키워드 없음 |

**상세 분석**:
```
Q014 답변: "롯데의 뇌출혈 보장금액은 1,000만원입니다"
→ 금액 정보는 맞지만 "남성" 조건이 반영/언급되지 않음
→ 성별 필터링이 적용되지 않음
```

---

## 3. 카테고리별 실패 패턴

### 3.1 Amount 카테고리 (50% 정확도 - 가장 낮음)

**실패 패턴**:
- 6/12 실패 (Q002, Q005, Q006, Q008, Q009, Q010)
- 공통점: 모두 "보장금액" 키워드 누락
- 특징: 담보명은 찾지만 금액 정보 연결 실패

**근본 원인**:
- Proposal 문서의 담보 테이블에서 금액 정보가 별도 컬럼에 있음
- 청크 분할 시 담보명과 금액이 분리되어 검색 시 금액 누락

### 3.2 Comparison 카테고리 (67% 정확도)

**실패 패턴**:
- 2/6 실패 (Q035, Q038)
- 공통점: 복수 보험사 정보 중 일부만 반환
- 특징: 첫 번째 보험사는 찾지만 두 번째 보험사 누락

---

## 4. 종합 대책

### 4.1 단기 대책 (1-2주)

#### 대책 1: 키워드 부스팅 추가 (핵심!)
현재: 순수 Vector Search만 사용 → 유사도 0.35~0.45로 엉뚱한 결과 반환

```python
# hybrid_retriever.py 수정
def search(self, query, top_k=10):
    # 1. 기존 Vector Search
    vector_results = self._vector_search(query_embedding, top_k=50)

    # 2. 키워드 부스팅 추가 (NEW)
    keywords = self.nl_mapper.extract_keywords(query)  # ["수술", "입원", "진단" 등]

    for result in vector_results:
        keyword_score = sum(1 for kw in keywords if kw in result["clause_text"])
        # Hybrid Score = Vector Score + Keyword Boost
        result["final_score"] = result["similarity"] + (keyword_score * 0.1)

    # 3. Re-ranking
    return sorted(vector_results, key=lambda x: x["final_score"], reverse=True)[:top_k]
```
**예상 효과**: A 원인 10건 중 7건 해결 → +14% 정확도

#### 대책 2: 검색 결과 수 증가 + LLM 필터링
```python
# 현재
limit = 5  # 너무 적음

# 권장
limit = 10  # 더 많은 후보에서 LLM이 선별
```
**예상 효과**: 낮은 유사도라도 정답이 포함될 확률 증가 → +4% 정확도

#### ~~대책 3: 보험사명 별칭 사전 구축~~ ✅ 이미 구현됨
```python
# ontology/nl_mapping.py에 이미 존재
COMPANY_ALIASES = {"KB손보": "KB", "흥국화재": "흥국", ...}
```

### 4.2 중기 대책 (2-4주)

#### 대책 3: BM25 + Vector Hybrid Search
Vector Search만으로는 키워드 매칭이 약함 → BM25 추가

```python
from rank_bm25 import BM25Okapi

class HybridRetriever:
    def __init__(self):
        self.bm25 = self._build_bm25_index()  # 전체 청크 인덱스

    def search(self, query, top_k=10):
        # 1. BM25 검색 (키워드 기반)
        bm25_scores = self.bm25.get_scores(query.split())

        # 2. Vector 검색 (의미 기반)
        vector_scores = self._vector_search(query)

        # 3. Hybrid Score
        # α=0.5: 키워드와 의미 검색 균형
        final_scores = 0.5 * bm25_scores + 0.5 * vector_scores
```
**예상 효과**: A 원인 대부분 해결 → +16% 정확도

#### 대책 4: 담보명 기반 필터링 강화
NLMapper가 추출한 담보 키워드로 후처리 필터링

```python
def search(self, query, top_k=10):
    entities = self.nl_mapper.extract_entities(query)
    coverage_keywords = entities.get("coverages", []) + entities.get("keywords", [])

    results = self._vector_search(query, top_k=50)

    # 담보 키워드가 포함된 결과 우선
    if coverage_keywords:
        results = sorted(results, key=lambda r:
            sum(1 for kw in coverage_keywords if kw in r["clause_text"]),
            reverse=True
        )

    return results[:top_k]
```

#### 대책 5: 쿼리 확장 (Query Expansion)
```python
# "KB 수술비" → "KB 수술비 질병수술비 암수술비"
def expand_query(query, entities):
    if "수술" in query:
        query += " 질병수술비 암수술비 수술담보"
    if "입원" in query:
        query += " 입원비 입원일당 입원담보"
    return query
```

### 4.3 장기 대책 (1-2개월)

#### 대책 6: Fine-tuned Embedding 모델
- 보험 도메인 특화 임베딩 모델 학습
- 보험사명, 담보명, 금액 간 관계 학습

#### 대책 7: Knowledge Graph 활용 강화
```cypher
// 담보-금액 관계 쿼리
MATCH (c:Coverage)-[:HAS_AMOUNT]->(a:Amount)
WHERE c.name CONTAINS '뇌출혈'
AND c.insurer = 'DB손해보험'
RETURN c.name, a.value
```

#### 대책 8: Re-ranking 모델 도입
- Cross-encoder 기반 재순위화
- 쿼리-문서 관련성 정밀 평가

---

## 5. 예상 개선 효과

| 대책 | 해결 케이스 | 정확도 개선 | 구현 난이도 |
|------|------------|------------|------------|
| 키워드 부스팅 추가 | Q002, Q005, Q006, Q026, Q027 | +10% | 쉬움 |
| BM25 Hybrid Search | Q008, Q009, Q010, Q035 | +8% | 보통 |
| 검색 결과 수 증가 | Q021 | +2% | 쉬움 |
| 쿼리 전처리/확장 | Q038, Q048 | +4% | 보통 |
| 필터 조건 반영 | Q014 | +2% | 보통 |
| ~~보험사명 별칭 사전~~ | - | - | ✅ 이미 구현됨 |

**총 예상 개선**: 74% → **100%** (이론적 최대)
**현실적 목표**: 74% → **90%** (단기+중기 대책 적용 시)

---

## 6. 우선순위 실행 계획

### Phase 1 (즉시 - 1주)
1. [x] 보험사명 별칭 사전 구축 ✅ 이미 완료됨
2. [ ] **키워드 부스팅 추가** (핵심 대책)
3. [ ] 검색 결과 수 10개로 증가
4. [ ] Hybrid 검색 가중치 실험 (0.5:0.5)

### Phase 2 (1-2주)
5. [ ] BM25 + Vector Hybrid Search 구현
6. [ ] 쿼리 확장 (Query Expansion) 모듈 개발
7. [ ] 담보명 기반 필터링 강화

### Phase 3 (2-4주)
8. [ ] Knowledge Graph 쿼리 최적화
9. [ ] Re-ranking 모델 검토

---

## 7. 결론

현재 74% 정확도의 주요 원인은:

1. **임베딩 유사도 부족** (77%): 데이터는 존재하나 Vector Search에서 상위에 올라오지 않음
2. **복합 쿼리 처리 미흡** (15%): 다중 보험사 조건 검색 실패
3. **필터 조건 미반영** (8%): 성별/나이 등 필터 조건 누락

**참고**: 보험사명 별칭 사전은 `ontology/nl_mapping.py`에 이미 구현되어 정상 동작 중 ✅

**권장 사항**:
- 단기 대책(키워드 부스팅, 검색 결과 수 증가)만으로도 **84%** 달성 가능
- 중기 대책(BM25 Hybrid, 쿼리 확장)까지 적용 시 **90%** 목표 달성 가능

---

*Generated: 2025-12-15*
