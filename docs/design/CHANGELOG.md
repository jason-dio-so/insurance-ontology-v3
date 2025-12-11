# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2025-12-10] - Phase 0R: Carrier-Specific Parsing Implementation

### Problem Statement
- **Phase 5 Current Accuracy**: 54% (27/50 queries) - Target: 85-90%
- **Root Cause**: Unified table parser cannot handle 8 different carrier table structures
- **Data Quality Issues**: 28-36% pollution (category headers, row numbers, metadata)

### Solution Implemented
Replaced unified `table_parser.py` with carrier-specific parsers for all 8 insurance carriers.

### Changes Made

#### 1. Created Parser Factory Pattern

**New Files**:
- `ingestion/parsers/parser_factory.py` (118 lines)
  - Routes table rows to appropriate carrier parser based on `company_code`
  - Supports all 8 carriers: Samsung, DB, Lotte, Meritz, KB, Hanwha, Hyundai, Heungkuk

**Example Usage**:
```python
from ingestion.parsers.parser_factory import ParserFactory

parsed_data = ParserFactory.parse_row(cells, company_code='samsung')
# Returns: {'coverage_name': '암진단비(유사암제외)', 'coverage_amount': '3,000만원', ...}
```

#### 2. Created Base Parser with Validation

**New File**: `ingestion/parsers/carrier_parsers/base_parser.py` (264 lines)

**Key Features**:
- Abstract base class for all carrier parsers
- Common utility methods:
  - `clean_coverage_name()`: Remove newlines, normalize whitespace
  - `is_row_number()`: Detect row numbers ("1", "1.", "13.")
  - `is_empty_or_whitespace()`: Check for empty cells
  - `filter_empty_cells()`: Remove empty columns (KB special case)
  - **`is_valid_coverage_name()`**: Comprehensive validation (lines 150-264)

**Validation Filters** (11 rules):
1. Length validation: 2-150 characters
2. Metadata keywords: "월납", "납입주기", "가입금액", "보험료", "환급금", "구분"
3. Date patterns: `^\d{4}-\d{2}-\d{2}`
4. Pure numbers: `^[\d,\.]+$`
5. Phone numbers: `^\d{4}-\d{4}$`
6. Document codes: `^[A-Z]{2}\d{2}-\d+$`
7. URLs: Contains "www.", ".co.kr", ".com"
8. Percentage values: `^[\d\.]+%?$`
9. Year markers: `^\d+년경과$`
10. Month markers: `^\d+월$`
11. Age markers: `^\d+세만기$`

#### 3. Implemented 8 Carrier-Specific Parsers

**Table Structure Variations**:

| Carrier | Table Structure | Coverage Column | Special Handling |
|---------|----------------|-----------------|------------------|
| Samsung | `[category, coverage_name, amount, premium, period]` | cells[1] | Filter time periods ("3개월", "10년") |
| DB | `[number, blank, coverage_name, amount, premium, period]` | cells[2] | Skip row numbers at cells[0] |
| Lotte | `[category, coverage_name, amount, period, premium]` | cells[1] | Filter category headers ("암관련", "뇌질환") |
| Meritz | `[category, number, coverage_name, amount, premium, period]` | cells[2] | Clean newlines in names |
| KB | `[number, coverage_name, EMPTY*9, amount, EMPTY*5, premium]` | filtered[1] | Filter 9 empty columns |
| Hanwha | `[number, coverage_name, amount, premium, period]` | cells[1] | Row numbers without period |
| Hyundai | `[number, coverage_name, amount, premium, period]` | cells[1] | Row numbers with period ("1.") |
| Heungkuk | `[blank, coverage_name, period, amount, premium]` | cells[1] | Period before amount |

**New Parser Files** (8):
- `ingestion/parsers/carrier_parsers/samsung_parser.py` (70 lines)
- `ingestion/parsers/carrier_parsers/db_parser.py` (57 lines)
- `ingestion/parsers/carrier_parsers/lotte_parser.py` (93 lines)
- `ingestion/parsers/carrier_parsers/meritz_parser.py` (59 lines)
- `ingestion/parsers/carrier_parsers/kb_parser.py` (70 lines)
- `ingestion/parsers/carrier_parsers/hanwha_parser.py` (56 lines)
- `ingestion/parsers/carrier_parsers/hyundai_parser.py` (57 lines)
- `ingestion/parsers/carrier_parsers/heungkuk_parser.py` (64 lines)

#### 4. Integrated with Ingestion Pipeline

**Modified**: `ingestion/ingest_documents_v2.py` (line 257)

```python
# Before
parsed_data = old_table_parser.parse(row)

# After
from ingestion.parsers.parser_factory import ParserFactory
parsed_data = ParserFactory.parse_row(row, company_code)
```

#### 5. Added Comprehensive Unit Tests

**New File**: `tests/test_carrier_parsers.py` (16223 bytes)

**Test Coverage**: 44 tests, 100% pass rate ✅
- Parser Factory: 11 tests (routing, instantiation, listing)
- 8 Carrier Parsers: 33 tests (valid rows, edge cases, error handling)
- Base Parser Utilities: 4 tests

**Example Test**:
```python
def test_samsung_parse_valid_row():
    parser = SamsungParser()
    cells = ['진단', '암 진단비(유사암 제외)', '3,000만원', '40,620', '20년납 100세만기']
    result = parser.parse_coverage_row(cells)

    assert result['coverage_name'] == '암 진단비(유사암 제외)'
    assert result['coverage_amount'] == '3,000만원'
```

#### 6. Schema Modification

**Database**: `insurance_ontology_test.coverage`

**Change**: `coverage_name VARCHAR(200)` → `coverage_name TEXT`

**Reason**: Some valid coverage names exceed 200 characters (e.g., "표적항암약물허가치료(갱신형)담보 안내 표적항암제는...")

**Migration**:
```sql
ALTER TABLE coverage ALTER COLUMN coverage_name TYPE TEXT;
```

### Phase 1 Re-ingestion Results

**Command**:
```bash
export POSTGRES_URL="postgresql://postgres:postgres@localhost:5432/insurance_ontology_test"
python3 -m ingestion.ingest_documents_v2 --metadata data/documents_metadata.json
```

**Overall Results**:
- **Total Documents**: 38
- **Success**: 38 (100%)
- **Errors**: 0
- **Total Clauses**: 80,986
- **Unique Coverage Names Extracted**: 508

**Coverage Extraction by Carrier**:
| Carrier | Unique Coverages | Status |
|---------|------------------|--------|
| Meritz | 132 | ✅ |
| Lotte | 88 | ✅ |
| Samsung | 87 | ✅ |
| Hanwha | 85 | ✅ |
| DB | 59 | ✅ |
| Hyundai | 46 | ✅ |
| KB | 47 | ✅ (Previously 0) |
| Heungkuk | 32 | ✅ |

**Validation Impact** (Proposal Documents):
| Document | Before | After | Reduction |
|----------|--------|-------|-----------|
| Lotte-proposal-female | 121 | 96 | -21% |
| Lotte-proposal-male | 120 | 96 | -20% |
| Hanwha-proposal | 127 | 99 | -22% |
| KB-proposal | 64 | 47 | **-27%** |
| **Meritz-proposal** | 80 | 39 | **-51%** ✅ |
| Hyundai-proposal | 56 | 50 | -11% |
| Samsung-proposal | 107 | 106 | -1% |
| DB-proposal (40 under) | 59 | 47 | -20% |
| DB-proposal (41 over) | 59 | 47 | -20% |

**Average Reduction**: ~20% of invalid rows filtered

### Known Issues

**⚠️ Validation Not Complete**:
Despite validation, some invalid names remain in extracted data (508 vs target 240-260):
- "담보명" (20 occurrences) - Table header
- "보장내용" (18) - Table header
- "28,403,040원" (12) - Amount with "원" suffix (not caught by number filter)
- "[보험금을 지급하지 않는 사항]" (9) - Section header
- "보통약관의 보험금을 지급하지 않는 사유와 동일" (5) - Description text
- "가입담보" (4) - Table header
- "고객님" (3) - Metadata

**Reason**: Validation rules need strengthening:
1. Korean currency patterns ("원", "만원")
2. Bracket-enclosed headers `[...]`
3. Common table headers ("담보명", "보장내용", "가입담보")
4. Longer description text (currently 150 char limit is too high)

**Action Item**: Phase 0R A.7 - Enhance validation filters (tracked in TODO.md)

### Files Modified Summary

**New Files** (12):
1. `ingestion/parsers/parser_factory.py`
2. `ingestion/parsers/carrier_parsers/base_parser.py`
3-10. 8 carrier parser files
11. `tests/test_carrier_parsers.py`
12. `PHASE_0R_PROGRESS_REPORT.md` (progress tracking)

**Modified Files** (1):
- `ingestion/ingest_documents_v2.py` (line 257)

**Schema Changes** (1):
- `coverage.coverage_name`: VARCHAR(200) → TEXT

### Next Steps

1. **Phase 0R A.7**: Strengthen validation filters (high priority)
2. **Phase 0R D1**: Re-run Phase 2 coverage extraction with validated data
3. **Phase 0R D2-D4**: Complete Phases 2-5 with carrier-specific parsers
4. **Phase 0R Target**: Achieve 85-90% Phase 5 accuracy (currently 54%)

### Testing

**Unit Tests**: 44/44 PASSED ✅
```bash
pytest tests/test_carrier_parsers.py -v
# ============================= 44 passed in 0.03s ==============================
```

**Integration Test**: Phase 1 ingestion completed successfully with 0 errors

### Documentation

- **Progress Report**: `PHASE_0R_PROGRESS_REPORT.md` (live tracking document)
- **Design Plan**: `CARRIER_SPECIFIC_PARSING_PLAN.md` (original implementation plan)
- **Code Comments**: All parsers include docstrings with table structure examples

---

## [2025-12-10] - Phase 1-2 Re-execution: Coverage Extraction Fix

### Problem Identified
- **Phase 5 Evaluation Result**: 72% accuracy (Target: 90%)
- **Root Cause**: Coverage names from DB, 현대, 한화 insurers were extracted as numbers only ("1.", "13.", "29.") instead of actual coverage names
- **Impact**: 14/50 queries failed in Gold QA Set evaluation

### Analysis

**Failed Coverage Names:**
```json
// Before fix (incorrect)
{"coverage_name": "1.", "coverage_amount": 10000000}
{"coverage_name": "13.", "coverage_amount": 30000000}

// After fix (correct)
{"coverage_name": "상해사망·후유장해(20-100%)", "coverage_amount": 10000000}
{"coverage_name": "암 진단비(유사암 제외)", "coverage_amount": 30000000}
```

**Root Cause Analysis:**

DB/현대/한화 insurers use row numbers in the first column of proposal tables:
```
['1.', '', '상해사망·후유장해', '1백만원', ...]
```

`table_parser.py`'s `extract_coverage_name()` only checked first 2 cells:
```python
# Before (incorrect)
for i in range(min(2, len(cells))):  # Only checks cells[0], cells[1]
```

- cells[0] = '1.' → skipped (isdigit check)
- cells[1] = '' → skipped (empty)
- cells[2] = '상해사망·후유장해' → **NOT CHECKED**

### Changes Made

#### 1. Fixed `ingestion/parsers/table_parser.py`

**File**: `ingestion/parsers/table_parser.py:197-235`

**Changed**:
- Extended search range from 2 to 3 cells
- Added explicit row number pattern detection (`"1."`, `"13."`)

```python
# After (correct)
for i in range(min(3, len(cells))):  # Now checks cells[0], cells[1], cells[2]
    if cell.replace('.', '').isdigit():  # Skip row numbers like "1.", "13."
        continue
```

#### 2. Re-executed Phases 1-2

**Phase 1: Document Ingestion**
- Truncated: `document_clause`, `coverage`, `benefit`, `clause_embedding`
- Re-ran: `python3 -m ingestion.ingest_documents_v2`
- Result: 38 documents, 80,521 clauses with corrected `structured_data`

**Phase 2: Entity Extraction**
- Coverage extraction: 357 coverages (7 insurers, KB excluded)
- Clause-coverage linking: 1,014 mappings (Tier 1: 829, Tier 2: 185)
- Benefit extraction: 357 benefits

### Results

**Coverage Extraction by Insurer:**
| Insurer | Unique Coverages | Status |
|---------|------------------|--------|
| 롯데 | 57 | ✅ Fixed |
| 삼성 | 41 | ✅ Normal |
| 한화 | 64 | ✅ Fixed |
| 현대 | 22 | ✅ Fixed |
| 흥국 | 23 | ✅ Normal |
| 메리츠 | 126 | ✅ Normal |
| DB | 22 | ✅ Fixed |
| KB | 0 | ⚠️ Excluded (PDF parsing issue) |

**Phase 1 Results:**
- ✅ 38 documents ingested
- ✅ 80,521 clauses
- ✅ 355 unique coverages extracted (KB excluded)
- ✅ No number-only coverage names ("1.", "13.") remaining

**Phase 2 Results:**
- ✅ 357 coverages inserted
- ✅ 1,014 clause-coverage mappings
- ✅ 357 benefits extracted
  - diagnosis: 118
  - treatment: 74
  - surgery: 67
  - death: 20
  - other: 78

### Known Issues

**KB Insurance - PDF Parsing Error:**
- **Issue**: Coverage name column is completely missing from parsed tables
- **Example**: `['', '1천만원', '700']` (first column empty)
- **Impact**: 4 documents (KB proposal, business_spec, product_summary, terms)
- **Decision**: Excluded from all subsequent phases
- **Workaround**: Requires PDF re-conversion or manual mapping

### Expected Improvements

**Phase 5 Re-evaluation (Pending):**
- Previous accuracy: 72% (36/50)
- Expected accuracy: 85-90% (43-45/50)
- Fixed insurers: DB, 현대, 한화 (previously failed queries should now succeed)

### Progress Update

**Phase 3: Neo4j Sync - ✅ COMPLETE**
- Fixed: Added `load_dotenv()` to `graph_loader.py` for credential loading
- Cleared existing Neo4j data
- Re-synced all entities from PostgreSQL
- Results:
  - 874 nodes (8 companies, 8 products, 4 variants, 357 coverages, 357 benefits, 9 code sets, 131 codes)
  - 857 relationships
- Duration: ~2 seconds

**Phase 4: Vector Embeddings - 🔄 IN PROGRESS**
- Started: 2025-12-10 (background process)
- Backend: OpenAI text-embedding-3-small (1536d)
- Target: 80,521 embeddings
- Batch size: 100
- Estimated duration: ~20 minutes
- Status: Running in background (PID: varies)

### Phase 5 Re-evaluation Results

**Completed**: 2025-12-10 02:10 KST

**Results**: ❌ **54.0% accuracy** (27/50 queries)

**Performance by Category**:
| Category | Success Rate | Status |
|----------|--------------|--------|
| basic | 90.0% (9/10) | ✅ Good |
| gender | 83.3% (5/6) | ✅ Good |
| condition | 75.0% (3/4) | ✅ Good |
| edge_case | 66.7% (4/6) | ⚠️ Medium |
| comparison | 50.0% (3/6) | ❌ Low |
| premium | 50.0% (1/2) | ❌ Low |
| **amount** | **16.7% (2/12)** | ❌ **Critical** |
| **age** | **0.0% (0/4)** | ❌ **Critical** |

**Performance by Difficulty**:
- Easy: 80.0% (12/15)
- Medium: 37.5% (9/24)
- Hard: 54.5% (6/11)

**Latency**:
- Average: 2,724ms
- P95: 5,286ms (Target: <5,000ms) ❌

### Issue Analysis

**Unexpected Result**: Accuracy **decreased** from 72% to 54% (-18%p)

**Root Causes Identified**:

1. **Coverage Name Inconsistency** (롯데 데이터):
   - `document_clause.structured_data`: "일반암진단비Ⅱ" ✅ (Correct)
   - `coverage` table: "암관련" ❌ (Too ambiguous)
   - Impact: Hybrid RAG NL Mapper cannot match "암진단" → "암관련"

2. **Age-based Filtering Failure** (0% accuracy):
   - Queries: "DB 40세 이하", "DB 41세 이상"
   - Issue: Age-based variant detection not working
   - DB proposal has age-specific variants but not properly linked

3. **KB Queries in QA Set**:
   - KB was excluded from ingestion but queries remain in gold_qa_set_50.json
   - 2 KB queries automatically fail

4. **Amount Queries Critical Failure** (16.7%):
   - "삼성화재 암 진단금", "DB손보 뇌출혈" fail
   - NL Mapper or coverage matching issue

**Why Performance Decreased**:
- Phase 1-4 re-execution changed data structure
- Hybrid RAG pipeline (NL Mapper, coverage matching) not adapted to new data
- Some coverages extracted with ambiguous names ("암관련" instead of specific names)

### Next Steps

- [ ] Fix coverage extraction: Ensure specific names (not "암관련")
- [ ] Update NL Mapper to handle new coverage names
- [ ] Fix age-based variant filtering
- [ ] Remove KB queries from QA Set or re-add KB data
- [ ] Re-run Phase 5 evaluation (target: 85-90%)

### Files Modified

- `ingestion/parsers/table_parser.py` - Fixed coverage name extraction logic (lines 197-235)
- `vector_index/openai_embedder.py` - Added `load_dotenv()` for API key loading
- `ingestion/graph_loader.py` - Added `load_dotenv()` for Neo4j credentials loading

### Migration Notes

**Breaking Changes**: None (data truncated and re-ingested)

**Database Impact**:
- Truncated tables: `document_clause`, `coverage`, `benefit`, `clause_embedding`, `clause_coverage`
- Re-populated with corrected data

**Backward Compatibility**: N/A (fresh data load)

---

## [2025-12-09] - Phase 4 Complete: Vector Index with OpenAI Embeddings

### Changed
- Switched from FastEmbed (384d) to OpenAI text-embedding-3-small (1536d)
- Updated schema: `embedding vector(384)` → `embedding vector(1536)`
- Built HNSW index for 80,521 embeddings

### Results
- ✅ 80,521 embeddings generated (~20 minutes)
- ✅ HNSW index created (502 MB)
- ✅ Average search latency: <50ms

---

## [2025-12-09] - Phase 0-3 Complete: Initial Implementation

### Added
- Phase 1: Document ingestion (38 PDFs → 80,521 clauses)
- Phase 2: Entity extraction (240 coverages, 240 benefits)
- Phase 3: Neo4j graph sync (640 nodes, 623 relationships)

### Results
- ✅ 8 insurers, 38 documents
- ✅ Hybrid parsing (Text/Table/Hybrid parsers)
- ✅ Structured data extraction (`structured_data` JSONB)

---

## [Initial] - Project Setup

### Added
- PostgreSQL schema with pgvector extension
- Neo4j graph database
- Qdrant vector store
- PDF → JSON conversion pipeline
- Multi-carrier document metadata
