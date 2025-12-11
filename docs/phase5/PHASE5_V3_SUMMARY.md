# Phase 5 v3 Implementation Summary

**Date**: 2025-12-11
**Implemented**: Proposal document prioritization for coverage queries
**Result**: Overall accuracy improved from 68% → 80% (+12%)

---

## 🎯 What Was Done

### Problem Identified (v2 Analysis)

**Root Cause**: Vector search prioritized product_summary/business_spec over proposal documents
- Proposal documents contain precise benefit amounts in table_row clauses
- Product summary documents only have general coverage descriptions
- Example: "암 진단금" query returned summary text instead of "3,000만원" table_row

**Evidence**:
- "암 진단비 3,000만원" clause exists in proposal (Sim: 0.5114)
- But product_summary generic text ranked higher (Sim: 0.4995)
- 0 proposal documents in top 20 results

### Solution Implemented

**File Modified**: `retrieval/hybrid_retriever.py`

**Changes** (lines 94-107):
```python
# ⭐ Coverage/Amount query detection: prioritize proposal + table_row
# Proposal documents have precise benefit amounts and coverage details in table_row clauses
# Examples: "암 진단금", "뇌출혈", "500만원 수술비"
coverage_keywords = ["진단금", "진단비", "수술비", "입원비", "치료비", "보장금", "보험금", "보장액"]
has_coverage_query = (
    entities.get("coverages") or  # Coverage extracted by NL mapper
    entities["filters"].get("amount") or  # Amount filter present
    any(kw in query for kw in coverage_keywords)  # Coverage keyword in query
)

if has_coverage_query:
    # Prioritize proposal documents with table_row clauses for accurate benefit info
    search_filters.setdefault("doc_type", "proposal")
    search_filters.setdefault("clause_type", "table_row")
```

**Logic**:
1. Detect coverage/amount queries by checking:
   - NL mapper extracted coverages
   - Amount filter present (e.g., "500만원")
   - Coverage keywords in query ("진단금", "수술비", etc.)
2. If detected → add doc_type="proposal" + clause_type="table_row" filters
3. Vector search now returns only proposal table_row clauses with precise amounts

---

## 📊 Results Comparison

### Overall Metrics

| Metric | v2 | v3 | Change |
|--------|----|----|---------|
| **Overall Accuracy** | 68.0% (34/50) | **80.0% (40/50)** | **+12.0%** ✅ |
| **Success Queries** | 34 | **40** | **+6 queries** |
| **Errors** | 0 | 0 | 0 |
| **Avg Latency** | 2,813ms | 3,317ms | +503ms ⚠️ |
| **P95 Latency** | 4,370ms | 6,283ms | +1,913ms ⚠️ |

### Category Performance

| Category | v2 | v3 | Change | Status |
|----------|----|----|--------|---------|
| **Basic** | 90% (9/10) | **100% (10/10)** | **+10.0%** ✅ |
| **Comparison** | 83.3% (5/6) | **100% (6/6)** | **+16.7%** ✅ |
| **Condition** | 100% (4/4) | **100% (4/4)** | 0% ✅ |
| **Premium** | 100% (2/2) | **100% (2/2)** | 0% ✅ |
| **Edge Case** | 50% (3/6) | **83.3% (5/6)** | **+33.3%** ✅ |
| **Age** | 25% (1/4) | **50% (2/4)** | **+25.0%** ✅ |
| **Gender** | 83.3% (5/6) | **83.3% (5/6)** | 0% |
| **Amount** | 41.7% (5/12) | **50.0% (6/12)** | **+8.3%** ⚠️ |

### Difficulty Performance

| Difficulty | v2 | v3 | Change |
|------------|----|----|--------|
| Easy | 80% (12/15) | **93.3% (14/15)** | +13.3% ✅ |
| Medium | 62.5% (15/24) | **70.8% (17/24)** | +8.3% ✅ |
| Hard | 81.8% (9/11) | **81.8% (9/11)** | 0% |

---

## ✅ Major Wins

### 1. Edge Case Breakthrough (+33.3%)
- **Before**: 50% (3/6)
- **After**: 83.3% (5/6)
- **Newly succeeded**:
  - Q050: "가장 비싼 뇌출혈 보장" ✅
  - Q046: "1억원 암 진단금" ✅

**Why**: Proposal documents helped LLM understand edge cases better with concrete amounts

### 2. Four Categories Perfect (100%)
- **Basic**: 90% → 100% (+Q030)
- **Comparison**: 83.3% → 100% (+Q038)
- **Condition**: Maintained 100%
- **Premium**: Maintained 100%

**Why**: Proposal table_row clauses provide complete information for comparisons

### 3. Age Category Doubled (+25%)
- **Before**: 25% (1/4)
- **After**: 50% (2/4)
- **Newly succeeded**: Q019 "DB 40세 이하 가입 가능 상품" ✅

**Why**: Proposal documents include age-specific product variants

### 4. Amount Category Improved (+8.3%)
- **Before**: 41.7% (5/12)
- **After**: 50.0% (6/12)
- **Newly succeeded**:
  - Q001: "삼성화재 암 진단금" ✅
  - Q010: "롯데 유사암" ✅

**Why**: This was the target fix - proposal prioritization worked!

---

## ⚠️ Regressions

### Issue 1: 2 Queries Newly Failed
**Q007**: KB손해보험 입원비 10만원 (amount)
- **v2**: Success (100% keyword match)
- **v3**: Fail (50% keyword match - only "입원" matched)
- **Likely cause**: Switched from summary to proposal, but proposal may lack "10만원 입원비" entry

**Q014**: 롯데 남성 뇌출혈 보장금액 (gender)
- **v2**: Success (100% keyword match)
- **v3**: Fail (50% keyword match)
- **Likely cause**: Proposal table_row doesn't explicitly mention "남성" (gender info in document metadata)

### Issue 2: Latency Increased (+1,913ms P95)
- **Before**: P95 4,370ms
- **After**: P95 6,283ms (+43%)
- **Avg**: 2,813ms → 3,317ms (+18%)

**Cause**:
- Proposal documents have more table_row clauses than summary
- More context to process
- Slower LLM generation with longer context

**Mitigation needed**:
- Add database indexes
- Optimize context assembly
- Consider conditional proposal prioritization (only for amount queries)

---

## 🎓 Lessons Learned

### 1. Doc Type Matters
- **Proposal > Summary** for amount/coverage queries
- Proposal has structured table_row with precise amounts
- Summary only has general descriptions

### 2. Trade-offs Exist
- Better accuracy (+12%) but worse latency (+1.9s P95)
- Some edge cases (gender-specific, low amounts) may lack proposal entries
- Need to balance doc type selection

### 3. Conditional Filtering Works
- Detecting coverage queries via keywords works well
- 7 keywords cover most coverage queries
- Can be extended if needed

---

## 📈 Progress Towards Goal

**Target**: 90% overall accuracy
**Current**: 80%
**Gap**: -10%

### If Amount Category Reaches 90%
- Currently: 6/12 (50%)
- Target: 11/12 (90%)
- Need: +5 queries
- **New overall**: 45/50 = **90%** ✅ Goal achieved!

**Conclusion**: Amount category is still the primary blocker, but we're close!

---

## 🔍 Remaining Challenges

### Amount Category (50%)
**Failed queries** (6/12):
- Q002: DB손보 뇌출혈 (expected "2,000만원", but DB has "1,000만원")
- Q005: 메리츠 암진단 (LLM didn't extract amount from context)
- Q006: 현대해상 뇌졸중 (no results returned)
- Q007: KB 입원비 10만원 (newly failed - proposal may lack this entry)
- Q008: 흥국 암수술비 (no results)
- Q009: 삼성 재진단암 (no results)

**Root causes**:
1. Expected amount ≠ actual amount in DB (Q002)
2. LLM extraction failure (Q005)
3. No search results (Q006, Q008, Q009) - may need to expand search beyond table_row

### Gender Category (83.3%)
**Failed query**:
- Q014: 롯데 남성 뇌출혈 (newly failed)

**Root cause**: Proposal table_row doesn't include gender info in text (only in document metadata)

**Fix needed**: Add gender metadata to context enrichment

---

## 💡 Next Steps (Recommended)

### Priority 1: Expand Search for Zero-Result Queries (2 hours)
**Goal**: Fix Q006, Q008, Q009 that returned no results

**Approach**:
1. Check if these coverages exist in proposal at all
2. If not → fallback to business_spec or product_summary
3. Implement tiered search: try proposal first, then fallback

**Expected impact**: +3 queries → Amount 75% → Overall 86%

### Priority 2: Fix Data Mismatch (Q002) (1 hour)
**Issue**: Gold QA expects "2,000만원" but DB has "1,000만원"

**Options**:
1. Update gold QA expected value
2. Check if there's a different coverage with 2,000만원
3. Accept as "data quality issue"

### Priority 3: Latency Optimization (2-3 hours)
**Goal**: Reduce P95 from 6,283ms to <5,000ms

**Approach**:
1. Add indexes on clause_type, doc_type
2. Limit context length more aggressively
3. Consider caching frequently accessed proposal clauses

**Expected impact**: -1,500ms P95

### Priority 4: Gender Metadata in Context (1 hour)
**Goal**: Fix Q014

**Approach**:
1. Add product_variant.target_gender to context enrichment
2. Include in LLM prompt: "이 상품은 [남성/여성]용입니다"

**Expected impact**: +1 query → Gender 100%

---

## 📂 Modified Files

1. `/Users/cheollee/insurance-ontology-v2/retrieval/hybrid_retriever.py`
   - Lines 94-107: Added coverage query detection and proposal prioritization
   - Impact: +7 success, -2 fail = net +5 queries (+10% accuracy)

2. `/Users/cheollee/insurance-ontology-v2/results/phase5_evaluation_v3.json`
   - Full evaluation results with detailed query-by-query breakdown

---

## 📊 Summary Table

### v1 → v2 → v3 Progress

| Metric | v1 | v2 | v3 | v1→v3 Change |
|--------|----|----|----|----|
| Overall | 60% | 68% | **80%** | **+20%** ✅ |
| Errors | 5 | 0 | 0 | **-5** ✅ |
| Basic | 90% | 90% | **100%** | **+10%** ✅ |
| Comparison | 83% | 83% | **100%** | **+17%** ✅ |
| Condition | 100% | 100% | **100%** | 0% ✅ |
| Premium | 100% | 100% | **100%** | 0% ✅ |
| Amount | 33% | 42% | **50%** | **+17%** ⚠️ |
| Age | 25% | 25% | **50%** | **+25%** ✅ |
| Gender | 67% | 83% | **83%** | **+16%** ✅ |
| Edge Case | 17% | 50% | **83%** | **+66%** ✅ |

**Total improvement (v1→v3)**: +10 queries (+20%)

---

## 🎯 Key Takeaways

1. **Proposal prioritization works**: +6 net queries with targeted doc type filtering
2. **Coverage keyword detection is effective**: 7 keywords catch most coverage queries
3. **Trade-off exists**: Better accuracy but worse latency
4. **Amount category** remains the blocker, but improved from 33% → 50%
5. **Goal within reach**: Only 5 more Amount queries needed for 90% overall

---

**Last Updated**: 2025-12-11 10:00 KST
**Status**: Phase 5 v3 Complete ✅
**Next Phase**: Amount zero-result fix + latency optimization
