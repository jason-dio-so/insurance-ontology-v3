# Parser Improvement Analysis

**Date**: 2025-12-11
**Focus**: business_spec & product_summary structured_data extraction

---

## Current State

### structured_data Coverage by Document Type

| Document Type | Structured Data | Total Clauses | Percentage |
|---------------|-----------------|---------------|------------|
| **proposal** | 690 | 690 | **100.0%** ✅ Perfect |
| **product_summary** | 198 | 1,942 | **10.2%** 🔶 Partial |
| **business_spec** | 3 | 2,524 | **0.1%** 🔶 Minimal |
| **terms** | 0 | 129,667 | 0.0% ✅ By design |

### Clause Type Distribution

```
business_spec:
  text_block:  2,521 clauses (99.9%)
  table_row:       3 clauses (0.1%)

product_summary:
  text_block:  1,744 clauses (89.8%)
  table_row:     198 clauses (10.2%)
```

---

## Analysis

### 1. Why is business_spec coverage so low?

**Root Causes:**
1. **Document Structure**: business_spec documents are primarily narrative text explaining:
   - Product features
   - Underwriting guidelines
   - General coverage descriptions
   - BUT: Rarely include specific amounts in tables

2. **Table Content**: Tables in business_spec typically contain:
   - Age ranges (not amounts)
   - Coverage categories (not specific values)
   - Eligibility criteria (not monetary data)

3. **Current Parser**: `hybrid_parser_v2.py` correctly identifies text blocks vs table rows, but business_spec tables don't match the structured_data schema (which expects `coverage_amount`, `premium`, etc.)

**Example business_spec Table**:
```
┌─────────────────┬───────────────┐
│ 가입나이        │ 15세 ~ 70세   │
│ 보험기간        │ 100세 만기    │
│ 납입기간        │ 10/15/20년납  │
└─────────────────┴───────────────┘
```
→ No coverage amounts or premiums!

### 2. Is product_summary coverage sufficient?

**Current Status**: 10.2% (198/1,942)

**Analysis**:
- product_summary tables often include coverage amounts
- 198 structured clauses is reasonable for summary documents
- These documents serve as "overviews" rather than detailed specs

**Example product_summary Table**:
```
┌──────────────────────┬─────────────┐
│ 담보명               │ 가입금액    │
│ 암진단비             │ 1천~5천만원 │
│ 뇌출혈진단비         │ 500~3천만원 │
└──────────────────────┴─────────────┘
```
→ Has amounts, but often in ranges (not exact)

---

## ROI Analysis

### Cost of Improvement

**Effort Required**: Medium-High
- Extend `hybrid_parser_v2.py` to handle:
  - Range parsing (e.g., "1천~5천만원")
  - Eligibility table extraction (age/period info)
  - Mixed table formats (text + amounts)
- Test across 9 business_spec + 9 product_summary documents
- Update structured_data schema to support new fields

**Estimated Time**: 2-3 days

### Benefit Analysis

**Current System Performance**:
- Overall accuracy: 86% (43/50 queries)
- Amount queries: 50% (6/12) - **already known limitation**
- Other query types: 90-100% accuracy

**Expected Improvement**:
- Amount query improvement: +10-15% (to 60-65%)
  - Still won't reach 90% (proposal documents are primary source)
  - business_spec tables don't contain specific amounts
- Overall improvement: +2-3% (to 88-89%)

**Alternative Approach**:
- LLM model upgrade (gpt-4o → gpt-4-turbo): Expected +5-10% overall
- Prompt engineering: Expected +2-5% overall
- Both are lower effort than parser rewrite

---

## Recommendation

### Priority: **LOW**

**Rationale**:
1. **Current system is production-ready** (86% accuracy)
2. **Proposal documents (100% structured_data) are the primary source** for amount queries
3. **business_spec tables don't contain specific amounts** - they're eligibility/category tables
4. **Better ROI alternatives exist**:
   - LLM upgrade: Lower effort, higher benefit
   - Prompt engineering: Already proven (+6% in Phase 5 v5)

### If Improvement is Pursued

**Phased Approach**:

**Phase 1: product_summary Enhancement** (1 day)
- Focus: Extract amount ranges from tables
- Target: 10.2% → 30-40% structured_data
- Schema addition:
  ```json
  {
    "coverage_amount_min": 10000000,
    "coverage_amount_max": 50000000,
    "amount_type": "range"
  }
  ```

**Phase 2: business_spec Metadata** (1 day)
- Focus: Extract eligibility info (not amounts)
- Target: 0.1% → 10-15% structured_data
- Schema addition:
  ```json
  {
    "eligibility": {
      "age_range": "15세 ~ 70세",
      "policy_term": "100세 만기",
      "payment_terms": ["10년납", "15년납", "20년납"]
    }
  }
  ```

**Phase 3: Integration & Testing** (0.5 day)
- Update hybrid_retriever.py to use new fields
- Test on Gold QA Set

**Total Effort**: 2.5 days
**Expected Benefit**: +2-3% overall accuracy (88-89%)

---

## Alternative Recommendations (Higher ROI)

### 1. LLM Model Upgrade

**Option A**: gpt-4o → gpt-4-turbo
- Cost: +2x API cost
- Effort: 0.5 day (config change + testing)
- Expected: +5-10% accuracy

**Option B**: gpt-4o-mini → gpt-4o
- Cost: +10x API cost
- Effort: 0.5 day
- Expected: +8-15% accuracy

### 2. Prompt Engineering

**Already Proven**:
- Phase 5 v4 → v5: Prompt changes only → +6% accuracy
- Further optimization possible

**Effort**: 1-2 days
**Expected**: +3-5% accuracy (to 89-91%)

### 3. Post-Processing Amount Extraction

**Concept**: If LLM answer contains amounts but doesn't match structured_data, validate via regex
- Effort: 1 day
- Expected: +5-10% on amount queries (current 50% → 60%)

---

## Conclusion

**Parser improvement is NOT recommended as next priority.**

**Recommended Next Steps** (in order):
1. ✅ **Done**: Design verification and documentation update
2. **Prompt Engineering**: Optimize existing prompts (1-2 days, +3-5%)
3. **LLM Model Test**: A/B test gpt-4o vs gpt-4-turbo (0.5 day, +5-10%)
4. **Post-Processing**: Amount extraction validation (1 day, +5-10% on amounts)
5. **Parser Enhancement**: Only if above steps don't reach 90% (2.5 days, +2-3%)

**Target**: 90% overall accuracy (currently 86%)
**Most Efficient Path**: Steps 1-3 above (3.5 days total effort)

---

**Document Version**: 1.0
**Author**: Design Verification Team
**Status**: Recommendation - Low Priority
