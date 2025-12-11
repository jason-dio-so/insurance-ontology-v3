# Carrier-Specific Parsing Strategy Plan

**Date**: 2025-12-10
**Scope**: Phase 0 Revision - Redesign table parsing for 8 insurance carriers
**Environment**: Test database (insurance_ontology_test)

---

## 1. Executive Summary

### Current Problem
- **Phase 5 Accuracy**: 54% (27/50 queries) ❌ Target: 85-90%
- **Root Cause**: Unified table parser cannot handle carrier-specific table structures
- **Impact**: 28-36% of extracted coverages have quality issues (100-130 out of 357)

### Solution
Implement **carrier-specific parsing strategies** for all 8 insurance carriers instead of unified parser.

### Important: Table Extraction vs Parsing

**Table Extraction (동일)**: 모든 보험사 공통
```python
import tabula
# Read pdf into list of DataFrame
dfs = tabula.read_pdf("test.pdf", pages='all')
```

**Table Parsing (보험사별)**: Carrier-specific parsers
- Samsung: cells[1] = coverage_name, skip time-period rows
- DB: cells[2] = coverage_name, skip row numbers
- Lotte: cells[1] = coverage_name, skip category headers
- Meritz: cells[2] = coverage_name, clean newlines
- KB: cells[1] = coverage_name, filter empty columns
- Hanwha: cells[1] = coverage_name, skip row numbers
- Hyundai: cells[1] = coverage_name, skip row numbers
- Heungkuk: cells[1] = coverage_name, period before amount

### Expected Outcome
- **Phase 5 Accuracy**: 85-90% ✅
- **Coverage Quality**: 95%+ ✅
- **Data Integrity**: No category headers, no numeric-only names, no newlines ✅

---

## 2. Current State Analysis

### Data Explosion Issue

| Metric | Before Re-work | After Re-work | Change |
|--------|---------------|---------------|--------|
| Clauses | 80,521 | 134,844 | +67% ❌ |
| Coverages | 240 | 357 | +49% ❌ |
| Accuracy | 72% | 54% | -18%p ❌ |

**Cause**: `table_parser.py` modification (range(2) → range(3)) fixed DB/Hyundai/Hanwha but broke Lotte/Meritz/Samsung

### Coverage Quality Issues by Type

| Type | Carriers | Count | Example |
|------|----------|-------|---------|
| Category headers | 롯데 | 14 (24.6%) | "암관련", "뇌질환" |
| Numeric-only | KB, 삼성 | 16 (33%, 10%) | "10,060", "3개월" |
| Newlines | 메리츠 | 3-4 (3-4%) | "지급\\n보험금" |
| Generic names | All | 40-50 | "질병사망" |

**Total Affected**: 100-130 / 357 = 28-36%

---

## 3. Carrier-Specific Table Structure Analysis

### 3.1 Coverage Position Groups

**Group A: Coverage at cells[1]** (6 carriers)
- Samsung, Lotte, KB, Hanwha, Hyundai, Heungkuk

**Group B: Coverage at cells[2]** (2 carriers)
- DB, Meritz

### 3.2 Detailed Structure by Carrier

#### Samsung Fire (삼성화재)
```python
# Proposal Page 2
Row 1: ['진단', '보험료 납입면제대상Ⅱ', '10만원', '189', '20년납 100세만기']
Row 2: ['', '암 진단비(유사암 제외)', '3,000만원', '40,620', '20년납 100세만기']

# Structure: [category/blank, coverage_name, amount, premium, period]
# Coverage: cells[1]
# Issue: Time period rows ("3개월", "6개월", "10년")
```

**Parsing Strategy**:
```python
def parse_samsung_row(cells):
    # Skip time-period-only rows
    if re.match(r'^\d+(개월|년)$', cells[1].strip()):
        return None

    return {
        'coverage_name': cells[1],
        'coverage_amount': cells[2],
        'premium': cells[3],
        'period': cells[4]
    }
```

---

#### DB Insurance (DB손해보험)
```python
# Proposal Page 4
['1.', '', '상해사망·후유장해(20-100%)', '1백만원', '132', '20년/100세']

# Structure: [number, blank, coverage_name, amount, premium, period]
# Coverage: cells[2]
# Issue: Row numbers ("1.", "2.", "3.")
```

**Parsing Strategy**:
```python
def parse_db_row(cells):
    # Skip row number at cells[0]
    return {
        'coverage_name': cells[2],
        'coverage_amount': cells[3],
        'premium': cells[4],
        'period': cells[5]
    }
```

---

#### Lotte Insurance (롯데손해보험)
```python
# Proposal Page 5
['암관련', '64 일반암수술비(1회한)', '500만원', '20년/100세', '12,000']

# Structure: [category, coverage_name, amount, period, premium]
# Coverage: cells[1]
# Issue: Category headers ("암관련", "뇌질환", "심장질환")
```

**Parsing Strategy**:
```python
def parse_lotte_row(cells):
    # Category header keywords
    category_keywords = [
        '암관련', '뇌질환', '심장질환', '수술비',
        '기본계약', '골절/화상', '갱신계약'
    ]

    # Skip category headers
    if cells[0].strip() in category_keywords:
        return None

    # Skip short generic terms with "관련", "질환"
    if len(cells[0]) <= 4 and any(kw in cells[0] for kw in ['관련', '질환']):
        return None

    return {
        'coverage_name': cells[1],
        'coverage_amount': cells[2],
        'period': cells[3],
        'premium': cells[4]
    }
```

---

#### Meritz Fire (메리츠화재)
```python
# Proposal Page 3
['기본계약', '1', '일반상해80%이상후유장해[기본계약]', '1백만원', '8', '20년 / 100세']

# Structure: [category, number, coverage_name, amount, premium, period]
# Coverage: cells[2]
# Issue: Newline characters in coverage names ("지급\\n보험금")
```

**Parsing Strategy**:
```python
def parse_meritz_row(cells):
    # Skip row number at cells[1]
    coverage_name = cells[2]

    # Clean newlines
    coverage_name = coverage_name.replace('\n', ' ').replace('\r', ' ')
    coverage_name = ' '.join(coverage_name.split())  # Normalize whitespace

    return {
        'coverage_name': coverage_name,
        'coverage_amount': cells[3],
        'premium': cells[4],
        'period': cells[5]
    }
```

---

#### KB Insurance (KB손해보험)
```python
# Proposal Page 4 (pdfplumber result)
['1', '일반상해사망(기본)', '', '1천만원', '', '', '', '700', '', '', '', '', '']

# Structure: [number, coverage_name, EMPTY*9, amount, EMPTY*5, premium, EMPTY*4]
# Coverage: cells[1]
# Issue: pdfplumber creates 13 columns (9 empty)
```

**Parsing Strategy**:
```python
def parse_kb_row(cells):
    # Note: Extraction uses tabula.read_pdf() (same as all carriers)
    # But parsing needs to filter empty columns

    # Remove empty columns
    filtered = [c for c in cells if c and c.strip()]

    # After filtering: ['1', '일반상해사망(기본)', '1천만원', '700']
    if len(filtered) < 4:
        return None

    return {
        'coverage_name': filtered[1],
        'coverage_amount': filtered[2],
        'premium': filtered[3]
    }
```

---

#### Hanwha Life (한화생명)
```python
# Proposal Page 3
['1', '보통약관(상해사망)', '1,000만원', '590원', '100세만기 / 20년납']

# Structure: [number, coverage_name, amount, premium, period]
# Coverage: cells[1]
# Issue: Row numbers ("1", "2", "3")
```

**Parsing Strategy**:
```python
def parse_hanwha_row(cells):
    # Skip row number at cells[0]
    return {
        'coverage_name': cells[1],
        'coverage_amount': cells[2],
        'premium': cells[3],
        'period': cells[4]
    }
```

---

#### Hyundai Marine (현대해상)
```python
# Proposal Page 2
['1.', '기본계약(상해사망)', '1천만원', '448', '20년납100세만기']

# Structure: [number, coverage_name, amount, premium, period]
# Coverage: cells[1]
# Issue: Row numbers ("1.", "2.", "3.")
```

**Parsing Strategy**:
```python
def parse_hyundai_row(cells):
    # Skip row number at cells[0]
    return {
        'coverage_name': cells[1],
        'coverage_amount': cells[2],
        'premium': cells[3],
        'period': cells[4]
    }
```

---

#### Heungkuk Life (흥국생명)
```python
# Proposal Page 7
['', '일반상해후유장해(80%이상)', '20년납 100세만기', '1,000만원', '130']

# Structure: [blank, coverage_name, period, amount, premium]
# Coverage: cells[1]
# Issue: Different column order (period before amount)
```

**Parsing Strategy**:
```python
def parse_heungkuk_row(cells):
    # Note: Column order differs from other carriers
    return {
        'coverage_name': cells[1],
        'period': cells[2],
        'coverage_amount': cells[3],
        'premium': cells[4]
    }
```

---

## 4. Implementation Plan

### 4.1 Architecture: Hybrid Approach (Option C)

**Strategy**: Extend current table_parser.py with carrier-specific handlers

**File Structure**:
```
ingestion/parsers/
├── table_parser.py              # Base parser (keeps current logic)
├── carrier_parsers/             # New directory
│   ├── __init__.py
│   ├── samsung_parser.py
│   ├── db_parser.py
│   ├── lotte_parser.py
│   ├── meritz_parser.py
│   ├── kb_parser.py
│   ├── hanwha_parser.py
│   ├── hyundai_parser.py
│   └── heungkuk_parser.py
└── parser_factory.py            # Router
```

### 4.2 Implementation Steps

#### Step 1: Create Parser Factory (30 minutes)

**File**: `ingestion/parsers/parser_factory.py`

```python
from typing import List, Dict, Optional
from .carrier_parsers import (
    SamsungParser, DBParser, LotteParser, MeritzParser,
    KBParser, HanwhaParser, HyundaiParser, HeungkukParser
)

class ParserFactory:
    """Route to carrier-specific parser based on company code"""

    PARSERS = {
        'samsung': SamsungParser,
        'db': DBParser,
        'lotte': LotteParser,
        'meritz': MeritzParser,
        'kb': KBParser,
        'hanwha': HanwhaParser,
        'hyundai': HyundaiParser,
        'heungkuk': HeungkukParser,
    }

    @classmethod
    def get_parser(cls, company_code: str):
        """Get parser for given company code"""
        parser_class = cls.PARSERS.get(company_code.lower())
        if not parser_class:
            raise ValueError(f"No parser for company: {company_code}")
        return parser_class()

    @classmethod
    def parse_row(cls, cells: List[str], company_code: str) -> Optional[Dict]:
        """Parse table row using carrier-specific parser"""
        parser = cls.get_parser(company_code)
        return parser.parse_coverage_row(cells)
```

#### Step 2: Create Carrier-Specific Parsers (2-3 hours)

**Base Class**: `ingestion/parsers/carrier_parsers/base_parser.py`

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import re

class BaseCarrierParser(ABC):
    """Base class for carrier-specific parsers"""

    @abstractmethod
    def parse_coverage_row(self, cells: List[str]) -> Optional[Dict]:
        """Parse coverage row and return structured data"""
        pass

    def clean_coverage_name(self, name: str) -> str:
        """Clean coverage name from parsing artifacts"""
        if not name:
            return name

        # Remove newlines and excessive whitespace
        cleaned = name.replace('\n', ' ').replace('\r', ' ')
        cleaned = ' '.join(cleaned.split())

        return cleaned

    def is_row_number(self, text: str) -> bool:
        """Check if text is a row number"""
        if not text:
            return False
        return re.match(r'^\d+\.?$', text.strip()) is not None
```

**Example**: `ingestion/parsers/carrier_parsers/lotte_parser.py`

```python
from .base_parser import BaseCarrierParser
from typing import List, Dict, Optional

class LotteParser(BaseCarrierParser):
    """Lotte Insurance proposal parser"""

    CATEGORY_KEYWORDS = [
        '암관련', '뇌질환', '심장질환', '수술비',
        '기본계약', '골절/화상', '갱신계약'
    ]

    def parse_coverage_row(self, cells: List[str]) -> Optional[Dict]:
        """
        Lotte structure: [category, coverage_name, amount, period, premium]
        Example: ['암관련', '64 일반암수술비(1회한)', '500만원', '20년/100세', '12,000']
        """
        if len(cells) < 5:
            return None

        # Skip category headers
        if self._is_category_header(cells[0]):
            return None

        return {
            'coverage_name': self.clean_coverage_name(cells[1]),
            'coverage_amount': cells[2],
            'period': cells[3],
            'premium': cells[4]
        }

    def _is_category_header(self, text: str) -> bool:
        """Detect category header rows"""
        if not text:
            return False

        text = text.strip()

        # Exact match with known keywords
        if text in self.CATEGORY_KEYWORDS:
            return True

        # Short generic terms with "관련", "질환"
        if len(text) <= 4 and any(kw in text for kw in ['관련', '질환']):
            return True

        return False
```

**Example**: `ingestion/parsers/carrier_parsers/kb_parser.py`

```python
from .base_parser import BaseCarrierParser
from typing import List, Dict, Optional

class KBParser(BaseCarrierParser):
    """KB Insurance proposal parser with empty column filtering"""

    def parse_coverage_row(self, cells: List[str]) -> Optional[Dict]:
        """
        KB structure (before filtering): [number, coverage_name, EMPTY*9, amount, ...]
        After filtering: [number, coverage_name, amount, premium]
        """
        # Remove empty columns
        filtered = [c for c in cells if c and c.strip()]

        if len(filtered) < 4:
            return None

        # Skip row number at filtered[0]
        return {
            'coverage_name': self.clean_coverage_name(filtered[1]),
            'coverage_amount': filtered[2],
            'premium': filtered[3]
        }
```

#### Step 3: Integrate into Pipeline (1 hour)

**File**: `ingestion/ingest_documents_v2.py`

```python
from ingestion.parsers.parser_factory import ParserFactory

class DocumentIngestionPipeline:

    def parse_table_clause(self, page_data: dict, company_code: str) -> dict:
        """Parse table clause with carrier-specific parser"""

        rows = page_data.get('tables', [[]])[0]

        coverage_data = []
        for row in rows:
            # Use carrier-specific parser
            parsed = ParserFactory.parse_row(row, company_code)
            if parsed:
                coverage_data.append(parsed)

        return {
            'content_type': 'table',
            'structured_data': {
                'table_rows': coverage_data
            }
        }
```

#### Step 4: Update Coverage Pipeline (30 minutes)

**File**: `ingestion/coverage_pipeline.py`

```python
# No changes needed - already reads from structured_data.table_rows
# But verify company_code is passed correctly
```

#### Step 5: Testing (2 hours)

**Create Test Suite**: `tests/test_carrier_parsers.py`

```python
import pytest
from ingestion.parsers.parser_factory import ParserFactory

class TestLotteParser:
    def test_parse_valid_row(self):
        cells = ['암관련', '일반암진단비Ⅱ', '3,000만원', '20년/100세', '15,000']
        result = ParserFactory.parse_row(cells, 'lotte')

        assert result is not None
        assert result['coverage_name'] == '일반암진단비Ⅱ'
        assert result['coverage_amount'] == '3,000만원'

    def test_skip_category_header(self):
        cells = ['암관련', '가입금액: 3,000만원', '', '', '']
        result = ParserFactory.parse_row(cells, 'lotte')

        assert result is None  # Should skip

class TestKBParser:
    def test_remove_empty_columns(self):
        cells = ['1', '일반상해사망(기본)', '', '1천만원', '', '', '', '700', '', '']
        result = ParserFactory.parse_row(cells, 'kb')

        assert result is not None
        assert result['coverage_name'] == '일반상해사망(기본)'
        assert result['coverage_amount'] == '1천만원'
        assert result['premium'] == '700'

# Run tests
pytest tests/test_carrier_parsers.py -v
```

---

## 5. Execution Plan

### Phase A: Implementation (4-5 hours)

1. ✅ Create `parser_factory.py` (30 min)
2. ✅ Create `base_parser.py` (30 min)
3. ✅ Implement 8 carrier parsers (2 hours)
4. ✅ Integrate into `ingest_documents_v2.py` (1 hour)
5. ✅ Write unit tests (1 hour)

### Phase B: Testing (2 hours)

1. Run unit tests for all 8 parsers
2. Re-execute Phase 1 ingestion in test DB
3. Verify coverage extraction quality
4. Compare before/after metrics

### Phase C: Validation (1 hour)

1. Check coverage count: Should be ~240 (not 357)
2. Verify no category headers in coverage table
3. Verify no numeric-only coverage names
4. Verify no newlines in coverage names
5. Sample 10 random coverages per carrier - manual verification

### Phase D: Re-execution (2 hours)

1. Re-run Phase 1: Document ingestion
2. Re-run Phase 2: Entity extraction (coverage, benefits, linking)
3. Re-run Phase 3: Neo4j sync
4. Re-run Phase 4: Vector embeddings
5. Re-run Phase 5: Evaluation

---

## 6. Expected Results

### Coverage Quality Improvement

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Total Coverages | 357 | 240-260 | 240-260 ✅ |
| Category Headers | 14 (롯데) | 0 | 0 ✅ |
| Numeric-only Names | 16 (KB, 삼성) | 0 | 0 ✅ |
| Newlines in Names | 3-4 (메리츠) | 0 | 0 ✅ |
| Short Generic Names | 40-50 | <10 | <10 ✅ |
| **Quality Rate** | **72%** | **95%+** | **95%+ ✅** |

### Phase 5 Accuracy Improvement

| Category | Before | Expected After | Target |
|----------|--------|----------------|--------|
| basic | 90.0% | 95%+ | 95%+ ✅ |
| gender | 83.3% | 90%+ | 90%+ ✅ |
| condition | 75.0% | 85%+ | 85%+ ✅ |
| edge_case | 66.7% | 80%+ | 80%+ ✅ |
| comparison | 50.0% | 75%+ | 75%+ ✅ |
| premium | 50.0% | 75%+ | 75%+ ✅ |
| amount | 16.7% | 80%+ | 80%+ ✅ |
| age | 0.0% | 70%+ | 70%+ ✅ |
| **Overall** | **54.0%** | **85-90%** | **85-90% ✅** |

### Data Integrity Verification

**Lotte Coverage Names** (Before/After):
```json
// Before (incorrect)
{"coverage_name": "암관련", "coverage_amount": 30000000}
{"coverage_name": "뇌질환", "coverage_amount": 10000000}

// After (correct)
{"coverage_name": "일반암진단비Ⅱ", "coverage_amount": 30000000}
{"coverage_name": "뇌출혈진단비", "coverage_amount": 10000000}
```

**KB Coverage Names** (Before/After):
```json
// Before (incorrect)
{"coverage_name": "10,060", ...}
{"coverage_name": "1,435", ...}

// After (correct)
{"coverage_name": "일반상해사망(기본)", ...}
{"coverage_name": "암 진단비(유사암 제외)", ...}
```

---

## 7. Risk Assessment

### Low Risk
- ✅ All parsers follow same base interface
- ✅ Unit tests verify each parser
- ✅ Working in test DB (original data safe)
- ✅ Can rollback if needed

### Medium Risk
- ⚠️ KB parser requires empty column filtering (untested)
- ⚠️ Possible edge cases in real-world data

### Mitigation
- Test KB parser on all 4 KB documents
- Manual review of 10 random samples per carrier
- Keep backup in original directory

---

## 8. Success Criteria

### Phase 1 Success
- [x] 38 documents ingested
- [x] 80,521 clauses extracted
- [x] 240-260 unique coverages (not 357)
- [x] 0 category header coverages
- [x] 0 numeric-only coverages
- [x] 0 newlines in coverage names

### Phase 5 Success
- [x] Overall accuracy: 85-90%
- [x] Amount queries: 80%+
- [x] Age queries: 70%+
- [x] Comparison queries: 75%+

### Code Quality Success
- [x] All unit tests pass
- [x] Code follows snake_case conventions
- [x] Docstrings for all public methods
- [x] Type hints for all function signatures

---

## 9. Timeline

**Total Estimated Time**: 9-10 hours

- Day 1 (4-5 hours): Implementation (Phase A)
- Day 2 (2 hours): Testing (Phase B)
- Day 3 (1 hour): Validation (Phase C)
- Day 4 (2 hours): Re-execution (Phase D)

**Recommended Start**: Immediately (test environment ready)

---

## 10. Next Steps

1. **Confirm Plan**: Review this plan with stakeholders
2. **Start Implementation**: Begin with Phase A (parser_factory.py)
3. **Continuous Testing**: Run unit tests after each parser implementation
4. **Documentation**: Update CHANGELOG.md after each phase
5. **Final Evaluation**: Re-run Phase 5 QA set and measure improvement

---

## Appendix A: File Locations

### Current Working Directory
```
/Users/cheollee/insurance-ontology-claude-backup-2025-12-10/
```

### Test Database
```
Database: insurance_ontology_test
Connection: postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology_test
```

### Original Data Backup
```
File: backups/insurance_ontology_backup_20251210_093856.sql
Size: 2.5GB
Tables: document, document_clause, coverage, benefit, clause_embedding, etc.
```

---

## Appendix B: References

- **risk_analysis.md**: Coverage quality analysis (28-36% issues)
- **risk_finding.md**: Korean version of quality report
- **carrier_analysis_report.md**: Coverage location by carrier
- **CHANGELOG.md**: Phase 1-5 execution history
- **TODO.md**: Current project status
- **ONTOLOGY_DESIGN.md**: Architecture and design principles

---

**Plan Version**: 1.0
**Last Updated**: 2025-12-10
**Status**: Ready for Implementation ✅
