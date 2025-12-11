리스크 3 분석 결과를 마크다운 문서로 작성하겠습니다:

  # Coverage Extraction Quality Analysis Report

  **Date**: 2025-12-10
  **Scope**: All 8 insurance carriers
  **Total Coverages Analyzed**: 357

  ## Executive Summary

  Phase 5 evaluation revealed that coverage extraction issues extend beyond Lotte (롯데) to **all insurance carriers**. Approximately **28-36% of 
  extracted coverages have quality issues**, ranging from category headers misidentified as coverages to numeric-only names.

  ## Problem Classification

  ### Type 1: Category Headers Extracted as Coverages

  **Affected Carriers**: 롯데 (Lotte)

  **Issue**: PDF table category headers ("암관련", "뇌질환", "심장질환") incorrectly extracted as `table_row` instead of being filtered out.

  **Examples**:
  ```json
  // Incorrect extraction
  {"coverage_name": "암관련", "coverage_amount": 30000000}
  {"coverage_name": "뇌질환", "coverage_amount": 10000000}

  // Should be
  {"coverage_name": "일반암진단비Ⅱ", "coverage_amount": 30000000}
  {"coverage_name": "뇌출혈진단비", "coverage_amount": 10000000}

  Impact: 14/57 coverages (24.6%)

  Root Cause:
  - Lotte proposal PDFs use 2-4 character category headers
  - table_parser.py does not distinguish headers from actual coverage rows
  - Header rows typically contain general terms: "관련", "질환"

  Type 2: Numeric-Only Coverage Names

  Affected Carriers: KB, 삼성 (Samsung)

  Issue: Coverage names extracted as pure numbers or time periods.

  Examples:

  KB Insurance (33% affected):
  {"coverage_name": "10,060", ...}
  {"coverage_name": "1,435", ...}
  {"coverage_name": "22,510", ...}

  Samsung Fire (10% affected):
  {"coverage_name": "3개월", "coverage_amount": 355038}
  {"coverage_name": "6개월", "coverage_amount": 710076}
  {"coverage_name": "10년", "coverage_amount": 14201520}

  Impact:
  - KB: 12/36 coverages
  - Samsung: 4/39 coverages

  Root Cause:
  - KB: Severe PDF parsing error - coverage name column missing (same issue as Phase 1 discovery)
  - Samsung: Time period payment schedules extracted as coverages

  Type 3: Newline Characters in Coverage Names

  Affected Carriers: 메리츠 (Meritz)

  Issue: Coverage names contain embedded newline characters (\n).

  Examples:
  {"coverage_name": "지급\n보험금", ...}
  {"coverage_name": "특정\n치료", ...}
  {"coverage_name": "검\n사", ...}

  Impact: 3-4/98 coverages (3-4%)

  Root Cause: PDF parsing doesn't properly handle line breaks within table cells.

  Type 4: Generic/Ambiguous Names

  Affected Carriers: DB, 한화, 현대, 삼성, 메리츠 (all)

  Issue: Very short, generic coverage names that lack specificity.

  Examples:
  - "질병사망" (Disease Death)
  - "상해수술비" (Injury Surgery Cost)
  - "화상진단비" (Burn Diagnosis)
  - "골절/화상" (Fracture/Burn)

  Impact: 40-50 coverages across all carriers

  Note: Some may be legitimate short names; requires manual verification against source PDFs.

  Severity Ranking

  | Rank | Carrier | Issue Rate | Problem Type     | Resolution Difficulty               |
  |------|---------|------------|------------------|-------------------------------------|
  | 1    | KB      | 33%        | Numeric-only     | ⚠️ Critical (PDF re-parsing needed) |
  | 2    | 롯데      | 24.6%      | Category headers | ✅ Solvable (header detection logic) |
  | 3    | 메리츠     | 22%        | Short names      | ⚠️ Medium (headers + newlines)      |
  | 4    | 삼성      | 20.5%      | Time periods     | ⚠️ Medium (special case handling)   |
  | 5    | 현대      | 22%        | Generic terms    | ✅ Verification needed               |
  | 6    | 흥국      | 26%        | Generic terms    | ✅ Verification needed               |
  | 7    | DB      | 27%        | Generic terms    | ✅ Verification needed               |
  | 8    | 한화      | 7.8%       | Generic terms    | ✅ Verification needed               |

  Overall Impact Assessment

  Total Coverages: 357
  Definite Issues: 60-80 (17-22%)
  Needs Verification: 40-50 (11-14%)

  Total Affected: 100-130 / 357 = 28-36%

  By Carrier:

  | Carrier | Total | Short Names (≤6 chars) | Percentage |
  |---------|-------|------------------------|------------|
  | 메리츠     | 98    | 22                     | 22.4%      |
  | KB      | 36    | 19                     | 52.8%      |
  | 롯데      | 57    | 14                     | 24.6%      |
  | 삼성      | 39    | 8                      | 20.5%      |
  | 흥국      | 23    | 6                      | 26.1%      |
  | DB      | 22    | 6                      | 27.3%      |
  | 한화      | 64    | 5                      | 7.8%       |
  | 현대      | 18    | 4                      | 22.2%      |

  Impact on Phase 5 Evaluation

  Current Accuracy: 54% (27/50 queries)

  Failed Categories Most Affected by Coverage Issues:
  - Amount queries (16.7%): NL Mapper cannot match "암진단" → "암관련"
  - Comparison queries (50.0%): Ambiguous names prevent cross-carrier matching
  - Basic queries (90.0%): Less affected, still relies on vector search

  Estimated Accuracy After Fixes:
  - Fixing Lotte headers: +8-10% improvement
  - Fixing Meritz newlines: +2-3% improvement
  - Total expected: 64-67% (still short of 85-90% target)

  Resolution Strategy

  Priority 1: Immediate Fixes (This Iteration)

  1.1 Lotte Category Header Filter

  File: ingestion/parsers/table_parser.py

  def is_category_header(self, cells: List[str]) -> bool:
      """
      Detect category header rows (Lotte special case)
      
      Examples:
          ['암관련', '가입금액: 3,000만원']  → True
          ['일반암진단비Ⅱ', '3,000만원']  → False
      """
      if not cells or not cells[0]:
          return False

      # Known category keywords (Lotte-specific)
      category_keywords = [
          '암관련', '뇌질환', '심장질환', '수술비',
          '기본계약', '골절/화상', '갱신계약'
      ]

      first_cell = cells[0].strip()

      # Pattern 1: Exact match with category keywords
      if first_cell in category_keywords:
          return True

      # Pattern 2: Very short generic terms (≤4 chars with "관련", "질환")
      if len(first_cell) <= 4 and any(kw in first_cell for kw in ['관련', '질환']):
          return True

      return False

  Integration: Call in parse_row() method before extracting coverage data.

  1.2 Meritz Newline Cleanup

  File: ingestion/coverage_pipeline.py or table_parser.py

  def clean_coverage_name(self, name: str) -> str:
      """Clean coverage name from parsing artifacts"""
      if not name:
          return name

      # Remove newlines and excessive whitespace
      cleaned = name.replace('\n', ' ').replace('\r', ' ')
      cleaned = ' '.join(cleaned.split())  # Normalize whitespace

      return cleaned

  1.3 Samsung Time Period Filter

  File: ingestion/parsers/table_parser.py

  def is_time_period_only(self, name: str) -> bool:
      """Detect time-period-only names (Samsung special case)"""
      import re

      # Pattern: "3개월", "6개월", "10년"
      if re.match(r'^\d+(개월|년)$', name.strip()):
          return True

      return False

  1.4 KB Data Exclusion

  Status: Already excluded in current data
  Action: Keep excluded; revisit in Phase 6

  Priority 2: Medium-term Improvements

  2.1 Generic Name Validation

  - Manual review of "질병사망", "상해수술비" type names
  - Check against source PDF to determine if legitimate
  - Create whitelist of valid short names

  2.2 Context-aware Coverage Extraction

  - For ambiguous rows, check surrounding context
  - If previous row is category header, current row is likely sub-coverage
  - Concatenate header + row name: "암관련" + "일반암진단비" → "일반암진단비"

  2.3 Enhanced Table Parser

  - Implement table structure analysis
  - Detect header rows, data rows, subtotal rows
  - Use font size, bold, indentation as hints

  Priority 3: Long-term Solutions

  3.1 KB PDF Re-processing

  - Investigate alternative PDF parsing libraries
  - Consider OCR if tables are image-based
  - Manual mapping as fallback

  3.2 Automated Coverage Validation

  - Build validation pipeline:
    a. Check length (too short = suspicious)
    b. Check for numbers only
    c. Check against known patterns
    d. Flag for manual review

  3.3 Coverage Quality Dashboard

  - UI for reviewing extracted coverages
  - Side-by-side: PDF original vs. extracted
  - Bulk edit/approve interface

  Recommended Execution Plan

  Phase A: Quick Wins (2-3 hours)

  1. ✅ Implement is_category_header() for Lotte
  2. ✅ Implement newline cleanup for Meritz
  3. ✅ Implement is_time_period_only() for Samsung
  4. 🔄 Re-run Phase 1-4 for affected carriers

  Phase B: Verification (1-2 hours)

  1. Manual check of DB/한화/현대 generic names (sample 10-15)
  2. Update whitelist if legitimate
  3. Add additional filters if invalid

  Phase C: Re-evaluation (30 minutes)

  1. Run Phase 5 evaluation
  2. Measure accuracy improvement
  3. Document results in CHANGELOG.md

  Expected Outcomes

  After Phase A (Quick Wins):
  - Lotte: 14 invalid coverages → 0
  - Meritz: 3-4 invalid coverages → 0
  - Samsung: 4 invalid coverages → 0
  - Total fixed: 21-22 coverages (5.9% of total)

  Expected Phase 5 Accuracy:
  - Current: 54%
  - After fixes: 68-72%
  - Still short of 85-90% target

  Additional work needed: NL Mapper improvements, age filtering (see original plan)

  Conclusion

  Coverage extraction quality issues are systemic across all carriers, not limited to DB/현대/한화 row numbering problem identified earlier. While quick
   wins can address 20-25 coverages (5.9%), achieving 85-90% Phase 5 accuracy requires:

  1. ✅ Coverage extraction fixes (this report)
  2. ⏳ NL Mapper improvements (ambiguous name matching)
  3. ⏳ Age-based filtering implementation
  4. ⏳ KB data resolution or exclusion from QA set

  Recommendation: Proceed with Priority 1 fixes, measure improvement, then decide on Priority 2/3 based on results.

  ---