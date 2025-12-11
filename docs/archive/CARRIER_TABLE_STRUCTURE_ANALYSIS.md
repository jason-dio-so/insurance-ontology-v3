# Carrier Table Structure Analysis Report

**Date**: 2025-12-10
**Purpose**: Compare parser assumptions vs actual PDF table structures
**Scope**: 8 insurance carriers' proposal documents

---

## Executive Summary

### Critical Findings

**🔴 CRITICAL ISSUES**:
1. **All parsers missing header row skip logic** → "담보명", "보장내용" saved as coverage
2. **DB parser wrong column index** → cells[2] but actual is cells[0]
3. **Hyundai parser wrong table identified** → Using wrong table structure

**🟡 MODERATE ISSUES**:
4. Samsung, Meritz have secondary header rows ("보장보험료 합계")
5. KB table structure varies by page (13 cols vs 6 cols vs 4 cols)

**🟢 WORKING CORRECTLY**:
- Lotte, Hanwha, Heungkuk parsers match actual structures

---

## Detailed Analysis by Carrier

### 1. 🏢 Samsung (삼성화재)

**Proposal Document**: `samsung-proposal`
**Coverage Table**: `table_002_01.json` (31 rows, 5 columns)

#### Actual Table Structure

```
Row 0: [피보험자(1/1) : 통합고객, , , , ]  ← Meta row
Row 1: [담보가입현황, , 가입금액, 보험료(원), 납입기간/보험기간]  ← HEADER
Row 2: [진단, 보험료 납입면제대상Ⅱ, 10만원, 189, 20년납 100세만기]  ← Data
Row 3: [, 암 진단비(유사암 제외), 3,000만원, 40,620, 20년납 100세만기]
Row 4: [, 유사암 진단비(기타피부암)(1년50%), 600만원, 1,440, 20년납 100세만기]
```

**Column Mapping**:
- `cells[0]` = Category (진단, 수술, etc.) or blank
- `cells[1]` = **Coverage name** ✅
- `cells[2]` = Amount
- `cells[3]` = Premium
- `cells[4]` = Period

#### Parser Assumption

```python
# Parser says: [category/blank, coverage_name, amount, premium, period]
coverage_name = cells[1]  ✅ CORRECT
```

#### Issues

❌ **Issue 1**: Row 1 ("담보가입현황", "가입금액", "보험료(원)") is a HEADER but parser treats as data
- Result: "담보가입현황" (if not filtered) could be saved as coverage

❌ **Issue 2**: Some rows have category names in cells[0]:
- "진단", "수술", "입원", "통원" → Should be skipped as category headers

#### Fix Required

1. Add header row detection:
   - Skip rows where cells[1] contains keywords: "담보", "보장", "가입금액"
2. Add category row detection:
   - Skip rows where cells[0] is NOT empty and cells[1] IS empty
   - Known categories: "진단", "수술", "입원", "통원"

---

### 2. 🏢 DB Insurance (DB손해보험)

**Proposal Document**: `db-proposal-age_40_under`
**Coverage Table**: Varies (needs deeper investigation)

**⚠️ CRITICAL**: The largest table found is NOT a coverage table!

#### Actual Table Structure (from largest table)

```
Row 0: [지급사유, 보장기간, 보상한도금액]  ← HEADER
Row 1: [표적항암약물허가치료비, 100세, 최초 1회한 1,000 만]  ← Data
Row 2: [항암방사선약물치료비(유사암포함), 100세, 제자리암,경계성종양... 최초 1회한 60 만]
```

**Column Mapping**:
- Only **3 columns** (not 6!)
- `cells[0]` = **Coverage name** (지급사유) ✅
- `cells[1]` = Period (보장기간)
- `cells[2]` = Amount/Limit (보상한도금액)

#### Parser Assumption

```python
# Parser says: [number, blank, coverage_name, amount, premium, period]
# Example: ['1.', '', '상해사망·후유장해(20-100%)', '1백만원', '132', '20년/100세']
coverage_name = cells[2]  ❌ WRONG!
```

#### Issues

❌ **CRITICAL**: Parser assumes 6 columns but actual table has 3 columns!
❌ **CRITICAL**: Parser uses cells[2] but coverage is at cells[0]!

**Root Cause**: Parser was designed for a DIFFERENT table (likely from business_spec or terms)

#### Fix Required

1. **Urgent**: Identify which DB table contains the 6-column structure
2. Re-design DB parser after finding correct table
3. Add table type detection logic

---

### 3. 🏢 Lotte (롯데손해보험)

**Proposal Document**: `lotte-proposal-female`
**Coverage Table**: `table_002_03.json` (31 rows, 5 columns)

#### Actual Table Structure

```
Row 0: [순번, 담보명, 가입금액, 납기/만기, 보험료(원)]  ← HEADER
Row 1: [1, 상해후유장해(3~100%), 3,000만원, 20년/100세, 1,800]  ← Data
Row 2: [2, 상해사망, 1,000만원, 20년/100세, 290]
Row 3: [21, 질병사망, 1,000만원, 20년/80세, 4,800]
Row 4: [30, 일반암진단비Ⅱ, 3,000만원, 20년/100세, 38,760]
```

**Column Mapping**:
- `cells[0]` = Row number (1, 2, 21, 30, ...)
- `cells[1]` = **Coverage name** ✅
- `cells[2]` = Amount
- `cells[3]` = Period
- `cells[4]` = Premium

#### Parser Assumption

```python
# Parser says: [category, coverage_name, amount, period, premium]
# WAIT - parser says cells[0] is category, but actual is row number!
coverage_name = cells[1]  ✅ CORRECT (by luck)
```

#### Issues

⚠️ **Issue 1**: Parser comment says cells[0] is "category" but actual is "row number"
- Still works because parser skips cells[0] anyway

❌ **Issue 2**: Row 0 is HEADER ("순번", "담보명", "가입금액") but not skipped
- Result: "담보명" saved as coverage (if not filtered by validation)

#### Fix Required

1. Update parser comment (cells[0] is row number, not category)
2. Add header row skip: Skip if cells[1] == "담보명"

---

### 4. 🏢 Meritz (메리츠화재)

**Proposal Document**: `meritz-proposal`
**Coverage Table**: `table_003_03.json` (25 rows, 6 columns)

#### Actual Table Structure

```
Row 0: [가입담보, , , 가입금액, 보험료(원), 납기/만기]  ← HEADER
Row 1: [보장보험료 합계, , , , 123,623 원, ]  ← Summary row
Row 2: [기본계약, 1, 일반상해80%이상후유장해[기본계약], 1백만원, 8, 20년 / 100세]  ← Data
Row 3: [사망후유, 2, 일반상해사망, 1백만원, 60, 20년 / 100세]
Row 4: [, 3, 질병사망, 1천만원, 6,880, 20년 / 80세]
```

**Column Mapping**:
- `cells[0]` = Category (기본계약, 사망후유, 3대진단, etc.) or blank
- `cells[1]` = Row number (1, 2, 3, ...)
- `cells[2]` = **Coverage name** ✅
- `cells[3]` = Amount
- `cells[4]` = Premium
- `cells[5]` = Period

#### Parser Assumption

```python
# Parser says: [category, number, coverage_name, amount, premium, period]
coverage_name = cells[2]  ✅ CORRECT
```

#### Issues

❌ **Issue 1**: Row 0 is HEADER ("가입담보", "가입금액") but not skipped

❌ **Issue 2**: Row 1 is summary row ("보장보험료 합계") but not skipped
- cells[2] = blank → likely filtered by is_empty_or_whitespace()

⚠️ **Issue 3**: Category names in cells[0] should be excluded:
- "기본계약", "사망후유", "3대진단" are category headers

#### Fix Required

1. Add header row skip: Skip if cells[0] == "가입담보" or cells[2] is empty
2. Add summary row skip: Skip if cells[0] contains "보험료 합계"
3. Consider: Should category rows (cells[0] not empty, cells[2] empty) be skipped?

---

### 5. 🏢 KB Insurance (KB손해보험)

**Proposal Document**: `kb-proposal`
**Coverage Table**: `table_004_03.json` (9 rows, **13 columns** raw)

#### Actual Table Structure

```
Row 0: [, 통합고객님 피보험자님의 가입내용, (30세|남|1급|...), , , 예약담보, , , ...]  ← Meta
Row 1: [보장명 및 보장내용, , , 가입금액, , , , 보험료(원), ...]  ← HEADER
Row 2: [1, 일반상해사망(기본), , 1천만원, , , , 700, ...]  ← Data
Row 3: [2, 일반상해후유장해(3-100%), , 1천만원, , , , 300, ...]
```

**Raw Columns**: 13 (with many empty columns)

**After Filtering Empty Columns**:
- `filtered[0]` = Row number (1, 2, 3, ...)
- `filtered[1]` = **Coverage name** ✅
- `filtered[2]` = Amount
- `filtered[3]` = Premium

#### Parser Assumption

```python
# Parser says: After filtering → [number, coverage_name, amount, premium]
coverage_name = filtered[1]  ✅ CORRECT
```

#### Issues

⚠️ **Issue 1**: KB has MULTIPLE table structures:
- `table_004_03.json`: 13 columns (main coverage table) ✅
- `table_002_04.json`: 4 columns (different structure)
- `table_003_01.json`: 4 columns
- Need to identify which tables to parse

❌ **Issue 2**: Row 1 is HEADER ("보장명 및 보장내용", "가입금액") but not skipped
- After filtering: ["보장명 및 보장내용", "가입금액", "보험료(원)"]
- Should skip this row

#### Fix Required

1. Add header row skip after filtering:
   - Skip if filtered[0] == "보장명" or filtered[0] contains "보장명 및"
2. Consider: Add table type detection (13-col vs 4-col)

---

### 6. 🏢 Hanwha (한화손해보험)

**Proposal Document**: `hanwha-proposal`
**Coverage Table**: `table_003_02.json` (33 rows, 5 columns)

#### Actual Table Structure

```
Row 0: [순번, 가입담보, 가입금액, 보험료, 만기/납기]  ← HEADER
Row 1: [1, 보통약관(상해사망), 1,000만원, 590원, 100세만기 / 20년납]  ← Data
Row 2: [2, 보험료납입면제대상보장(8대사유), 10만원, 218원, 100세만기 / 20년납]
Row 3: [6, 상해후유장해(3-100%), 1,000만원, 500원, 100세만기 / 20년납]
```

**Column Mapping**:
- `cells[0]` = Row number (1, 2, 6, 10, ...)
- `cells[1]` = **Coverage name** ✅
- `cells[2]` = Amount
- `cells[3]` = Premium
- `cells[4]` = Period

#### Parser Assumption

```python
# Parser says: [number, coverage_name, amount, premium, period]
coverage_name = cells[1]  ✅ CORRECT
```

#### Issues

❌ **Issue 1**: Row 0 is HEADER ("순번", "가입담보") but not skipped
- Result: "가입담보" saved as coverage (if not filtered)

✅ **Otherwise**: Parser structure matches actual table perfectly!

#### Fix Required

1. Add header row skip: Skip if cells[0] == "순번" or cells[1] == "가입담보"

---

### 7. 🏢 Hyundai (현대해상)

**Proposal Document**: `hyundai-proposal`
**Coverage Table**: `table_002_03.json` (28 rows, **5 columns**) ✅

#### Actual Table Structure (CORRECT TABLE)

```
Row 0: [가입담보, , 가입금액, 보험료(원), 납기/만기]  ← HEADER
Row 1: [1., 기본계약(상해사망), 1천만원, 448, 20년납100세만기]  ← Data
Row 2: [2., 기본계약(상해후유장해), 1천만원, 550, 20년납100세만기]
Row 3: [3., 보험료납입면제대상담보, 10만원, 35, 전기납20년만기]
```

**Column Mapping**:
- `cells[0]` = Row number (1., 2., 3., ...)
- `cells[1]` = **Coverage name** ✅
- `cells[2]` = Amount
- `cells[3]` = Premium
- `cells[4]` = Period

#### Parser Assumption

```python
# Parser says: [number, coverage_name, amount, premium, period]
coverage_name = cells[1]  ✅ CORRECT
```

#### Issues

❌ **CRITICAL**: During initial analysis, we found "위험보장 및 보험금 지급내용" saved as coverage
- This comes from `table_004_03.json` (8 columns, not 5!)
- **Root cause**: Wrong table was being parsed!

❌ **Issue 1**: `table_004_03.json` structure (8 columns):
```
Row 4: [●, 위험보장 및 보험금 지급내용, , , , , , ]  ← Section header
Row 5: [담보명 및 보장내용, , , , , 납기/만기, 가입금액, 보험료(원)]  ← HEADER
Row 6: [1., , 기본계약(상해사망), , , 20년납100세만기, 1천만원, 448]  ← Data
```

In this table:
- cells[1] = "" or section header → Wrong!
- cells[2] = Coverage name (actual)

**Conclusion**: Hyundai has TWO different table structures in the same document!

#### Fix Required

1. **Urgent**: Add table structure detection
   - If table has 5 columns → use cells[1]
   - If table has 8 columns → use cells[2]
2. Add header row skip for both structures
3. Add section header skip: Skip if cells[0] == "●" or cells[1] contains "위험보장"

---

### 8. 🏢 Heungkuk (흥국화재)

**Proposal Document**: `heungkuk-proposal`
**Coverage Table**: `table_007_03.json` (25 rows, 5 columns)

#### Actual Table Structure

```
Row 0: [피보험자(1/1), , , , ]  ← Meta row
Row 1: [구분, 담 보 명, 납입 및 만기, 가입금액, 보험료(원)]  ← HEADER
Row 2: [, 일반상해후유장해(80%이상), 20년납 100세만기, 1,000만원, 130]  ← Data
Row 3: [, 질병후유장해(80%이상)(감액없음), 20년납 100세만기, 100만원, 147]
```

**Column Mapping**:
- `cells[0]` = Category (mostly blank) or "구분"
- `cells[1]` = **Coverage name** ✅
- `cells[2]` = Period
- `cells[3]` = Amount
- `cells[4]` = Premium

#### Parser Assumption

```python
# Parser says: [blank, coverage_name, period, amount, premium]
coverage_name = cells[1]  ✅ CORRECT
```

#### Issues

❌ **Issue 1**: Row 1 is HEADER ("구분", "담 보 명") but not skipped
- Result: "담 보 명" saved as coverage (if not filtered)

✅ **Otherwise**: Parser structure matches actual table perfectly!

#### Fix Required

1. Add header row skip: Skip if cells[0] == "구분" or cells[1] == "담 보 명"

---

## Summary Table: Parser Accuracy

| Carrier | Column Match | Header Skip | Issues Found | Status |
|---------|--------------|-------------|--------------|--------|
| **Samsung** | ✅ Correct | ❌ Missing | 2 issues | 🟡 Moderate |
| **DB** | ❌ **WRONG** | ❌ Missing | **CRITICAL** | 🔴 Broken |
| **Lotte** | ✅ Correct | ❌ Missing | 2 issues | 🟡 Moderate |
| **Meritz** | ✅ Correct | ❌ Missing | 3 issues | 🟡 Moderate |
| **KB** | ✅ Correct | ❌ Missing | 2 issues | 🟡 Moderate |
| **Hanwha** | ✅ Correct | ❌ Missing | 1 issue | 🟢 Good |
| **Hyundai** | ⚠️ Partial | ❌ Missing | **2 table types** | 🔴 Critical |
| **Heungkuk** | ✅ Correct | ❌ Missing | 1 issue | 🟢 Good |

---

## Root Cause Analysis

### Issue 1: Universal Header Row Problem ❌

**Impact**: ALL 8 carriers
**Severity**: 🔴 CRITICAL

**Problem**:
- Tabula extracts tables INCLUDING header row (expected behavior)
- Parsers assume first data row but don't skip header
- Result: "담보명", "보장내용", "가입담보" saved as coverage names

**Examples**:
- Lotte: Row 0 = ["순번", "담보명", "가입금액", ...] → "담보명" becomes coverage
- Hanwha: Row 0 = ["순번", "가입담보", ...] → "가입담보" becomes coverage
- Hyundai: Row 4 = ["●", "위험보장 및 보험금 지급내용", ...] → Becomes coverage

**Evidence from DB**:
```sql
coverage_name = '위험보장 및 보험금 지급내용' | cnt = 4  ← Hyundai
coverage_name = '담보명' (if found)
coverage_name = '가입담보' (if found)
```

**Solution**:
1. Add `is_header_row()` method to `BaseCarrierParser`
2. Each parser calls it before processing
3. Common header keywords: "담보명", "보장내용", "가입금액", "보험료", "순번", "구분"

---

### Issue 2: DB Parser Wrong Column Index ❌

**Impact**: DB Insurance only
**Severity**: 🔴 CRITICAL

**Problem**:
- Parser assumes 6-column table: [number, blank, coverage_name, amount, premium, period]
- Actual table has 3 columns: [coverage_name, period, amount]
- Parser uses cells[2] but coverage is at cells[0]

**Result**:
- 0% of DB coverage names extracted correctly
- DB queries in Phase 5 fail completely

**Solution**:
1. Find the CORRECT table in DB proposal that matches 6-column structure
2. OR redesign DB parser for 3-column structure
3. Add table validation: Check column count before parsing

---

### Issue 3: Hyundai Multiple Table Structures ❌

**Impact**: Hyundai only
**Severity**: 🔴 CRITICAL

**Problem**:
- Same document has TWO different table structures:
  - 5-column table: [number, coverage_name, amount, premium, period] → cells[1] ✅
  - 8-column table: [number, "", coverage_name, "", "", period, amount, premium] → cells[2] ✅
- Current parser only handles 5-column
- 8-column tables produce wrong data ("위험보장 및 보험금 지급내용")

**Solution**:
1. Add dynamic column detection in parser
2. Detect structure based on column count or header pattern
3. Route to appropriate parsing logic

---

### Issue 4: Category Header Rows (Samsung, Meritz)

**Impact**: Samsung, Meritz
**Severity**: 🟡 MODERATE

**Problem**:
- Some tables have category grouping rows:
  - Samsung: cells[0] = "진단", cells[1] = blank
  - Meritz: cells[0] = "기본계약", cells[1] = row number, cells[2] = blank
- These should be skipped but aren't

**Evidence**:
```
Samsung Row 2: [진단, 보험료 납입면제대상Ⅱ, ...] ← Data
Samsung Row X: [진단, , , , ] ← Category header (blank cells[1])

Meritz Row 2: [기본계약, 1, 일반상해80%이상후유장해..., ...] ← Data
Meritz Row X: [사망후유, , , , , ] ← Category header (blank cells[2])
```

**Solution**:
- Skip rows where coverage_name column (cells[1] or cells[2]) is empty
- Already partially handled by `is_empty_or_whitespace()` check

---

### Issue 5: KB Multiple Table Types

**Impact**: KB only
**Severity**: 🟡 MODERATE

**Problem**:
- KB proposal has multiple table formats:
  - 13-column table (coverage table) ✅
  - 4-column tables (refund table, summary table)
- Current parser tries to parse ALL tables
- Non-coverage tables produce garbage data

**Solution**:
1. Add table type detection before parsing
2. Only parse tables with coverage-related headers
3. Skip refund tables, summary tables

---

## Recommended Fix Strategy

### Phase 1: Critical Fixes (P0) - 2-3 hours

**Target**: Fix 3 critical issues that cause complete failure

1. **Add header row skip to BaseParser** (30min)
   ```python
   def is_header_row(self, cells: List[str]) -> bool:
       """Detect if row is a table header"""
       text = ' '.join(cells).lower()
       header_keywords = ['담보명', '보장내용', '가입금액', '보험료', '순번', '구분', '가입담보']
       return any(kw in text for kw in header_keywords)
   ```

2. **Fix DB Parser** (1 hour)
   - Find correct 6-column table OR redesign for 3-column
   - Add table validation

3. **Fix Hyundai Parser** (1 hour)
   - Add column count detection
   - Route to correct parsing logic based on structure
   - Add section header skip

### Phase 2: Moderate Fixes (P1) - 1-2 hours

4. **Add summary row skip** (30min)
   - Meritz: "보장보험료 합계"
   - Skip rows with "합계", "총", "전체" in coverage column

5. **Add KB table type detection** (30min)
   - Only parse tables with "보장명" header
   - Skip refund/summary tables

6. **Add category header skip** (30min)
   - Samsung, Meritz category grouping rows
   - Already partially working

### Phase 3: Validation & Testing (P2) - 2-3 hours

7. **Update unit tests** (1 hour)
   - Add header row skip tests
   - Add multi-structure tests (Hyundai, KB)

8. **Re-run Phase 1** (30min)
   - Ingest all documents
   - Verify coverage count: 508 → 240-260

9. **Manual validation** (1 hour)
   - Sample 80 coverage names
   - Verify 0 header rows, 0 section headers

### Phase 4: Re-execution (P3) - 2-3 hours

10. **Phase 2-5 re-execution**
11. **Phase 5 QA evaluation** → Target 85-90%

---

## Expected Improvements

### Coverage Count Reduction

**Before** (current):
- Total unique coverages: 508
- Invalid (headers, metadata): ~248-268 (49%)

**After** (with fixes):
- Total unique coverages: 240-260
- Invalid: <10 (4%)

**Reduction**: ~50% garbage elimination

### Phase 5 Accuracy Improvement

**Before** (current):
- Overall: 54% (27/50)
- Amount queries: 16.7% (2/12)
- DB queries: 0% (0/4)

**After** (estimated):
- Overall: 85-90% (43-45/50)
- Amount queries: 80%+ (10/12)
- DB queries: 75%+ (3/4)

**Improvement**: +31-36 percentage points

---

## Validation Checklist

After implementing fixes:

- [ ] No header keywords in coverage table: "담보명", "보장내용", "가입금액", "보험료"
- [ ] No section headers: "위험보장", "계약정보", "피보험자"
- [ ] No summary rows: "보험료 합계", "보장보험료 합계"
- [ ] DB coverage count > 0 (currently 22, should stay ~20-25)
- [ ] Hyundai no "위험보장 및 보험금 지급내용" coverage
- [ ] Total unique coverages: 240-260 range
- [ ] All unit tests pass (54-60 tests expected)

---

## Appendix: Table Structure Reference

### Column Order Patterns

**Pattern A** (5 carriers): `[number, coverage_name, amount, premium, period]`
- Samsung (with category prefix), Hanwha, Hyundai-5col, Lotte

**Pattern B** (2 carriers): `[category, number, coverage_name, amount, premium, period]`
- Meritz (6 cols)

**Pattern C** (1 carrier): `[blank, coverage_name, period, amount, premium]`
- Heungkuk (period before amount)

**Pattern D** (1 carrier): `[coverage_name, period, amount]` (3 cols only!)
- DB ← Needs investigation

**Pattern E** (1 carrier): `[number, coverage_name, amount, premium]` (after filtering)
- KB (13 raw → 4 filtered)

---

**Report Generated**: 2025-12-10
**Next Action**: Implement Phase 1 Critical Fixes
**Expected Completion**: Phase 1-2 fixes within 3-5 hours
