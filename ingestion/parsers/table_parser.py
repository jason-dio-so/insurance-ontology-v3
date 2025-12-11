"""
Table Parser for Insurance Documents

Purpose: Extract structured data from table-formatted coverage information
         in proposals (가입설계서), product summaries (상품요약서), and easy summaries (쉬운요약서)

Strategy:
- Detect benefit tables using keyword heuristics
- Parse table rows into structured JSON
- Normalize Korean amount text to integers
- Handle carrier-specific variations (gender, age, premium frequency)

Part of: Phase 5.5 Structured Chunking Architecture (ARCH-2025-001)
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import unicodedata


@dataclass
class StructuredCoverage:
    """Structured coverage data extracted from table row"""
    coverage_name: str
    coverage_amount: Optional[int] = None
    coverage_amount_text: Optional[str] = None
    premium: Optional[int] = None
    premium_frequency: Optional[str] = None
    conditions: Optional[str] = None
    target_gender: Optional[str] = None
    target_age_range: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSONB storage"""
        return {k: v for k, v in self.__dict__.items() if v is not None}


class TableParser:
    """Parser for table-formatted coverage information"""

    # Keywords for benefit table detection
    BENEFIT_TABLE_KEYWORDS = [
        "담보", "보장", "보험금", "가입금액", "보험료",
        "지급사유", "지급금액", "보장내용", "보장금액"
    ]

    # Keywords indicating table headers (not data rows)
    HEADER_KEYWORDS = [
        "담보명", "보장명", "가입금액", "보험료", "지급사유",
        "구분", "항목", "내용", "보장내용"
    ]

    # Amount patterns for Korean text
    # Order matters: match more specific patterns first, then general patterns
    AMOUNT_PATTERNS = [
        # "5억 3천만원" → 530000000 (must come before simpler patterns)
        (r'(\d+)\s*억\s*(\d+)\s*천\s*만\s*원', lambda m: int(m.group(1)) * 100000000 + int(m.group(2)) * 10000000),
        # "5억 3,000만원" → 530000000
        (r'(\d+)\s*억\s*(\d{1,3}(?:,\d{3})+)\s*만\s*원', lambda m: int(m.group(1)) * 100000000 + int(m.group(2).replace(',', '')) * 10000),
        # "5억 3000만원" → 530000000 (no comma, 4+ digits)
        (r'(\d+)\s*억\s*(\d{4,})\s*만\s*원', lambda m: int(m.group(1)) * 100000000 + int(m.group(2)) * 10000),
        # "5억 300만원" → 503000000 (3 digits)
        (r'(\d+)\s*억\s*(\d{1,3})\s*만\s*원', lambda m: int(m.group(1)) * 100000000 + int(m.group(2)) * 10000),
        # "5억" → 500000000
        (r'(\d+)\s*억', lambda m: int(m.group(1)) * 100000000),
        # "3천만원" → 30000000
        (r'(\d+)\s*천\s*만\s*원', lambda m: int(m.group(1)) * 10000000),
        # "3,000만원" → 30000000 (with comma)
        (r'(\d{1,3}(?:,\d{3})+)\s*만\s*원', lambda m: int(m.group(1).replace(',', '')) * 10000),
        # "3000만원" → 30000000 (no comma)
        (r'(\d+)\s*만\s*원', lambda m: int(m.group(1)) * 10000),
        # "3,000원" → 3000 (with comma)
        (r'(\d{1,3}(?:,\d{3})+)\s*원', lambda m: int(m.group(1).replace(',', ''))),
        # "3000원" → 3000 (no comma)
        (r'(\d+)\s*원', lambda m: int(m.group(1))),
    ]

    # Premium frequency patterns
    PREMIUM_FREQUENCY_PATTERNS = [
        (r'월\s*납', '월'),
        (r'월\s*보험료', '월'),
        (r'연\s*납', '연'),
        (r'일시납', '일시'),
    ]

    def __init__(self):
        """Initialize table parser"""
        pass

    def is_benefit_table(self, table: List[List[str]]) -> bool:
        """
        Detect if a table contains benefit/coverage information

        Args:
            table: List of rows, each row is a list of cell texts

        Returns:
            True if table appears to contain benefit data
        """
        if not table or len(table) < 2:  # Need at least header + 1 row
            return False

        # Check first 2 rows for benefit keywords
        # Handle None values in cells
        header_text = ' '.join([
            ' '.join([str(cell) if cell is not None else '' for cell in row])
            for row in table[:2]
        ])

        keyword_count = sum(1 for keyword in self.BENEFIT_TABLE_KEYWORDS if keyword in header_text)

        return keyword_count >= 2  # At least 2 benefit keywords

    def is_header_row(self, row: List[str]) -> bool:
        """
        Check if a row is a header row (not data)

        Args:
            row: List of cell texts

        Returns:
            True if row appears to be a header
        """
        # Handle None values in row
        row_text = ' '.join([str(cell) if cell is not None else '' for cell in row])

        # Check for header keywords
        for keyword in self.HEADER_KEYWORDS:
            if keyword in row_text:
                return True

        # If row contains amounts, it's likely a data row, not header
        for cell in row:
            if cell is None:
                continue
            cell_str = str(cell)
            if any(keyword in cell_str for keyword in ['만원', '억', '원']) and any(char.isdigit() for char in cell_str):
                return False

        # If row has mostly very short cells (<5 chars), likely header
        if len(row) >= 2:
            very_short_cells = sum(1 for cell in row if cell is not None and len(str(cell).strip()) < 5)
            if very_short_cells / len(row) > 0.7:
                return True

        return False

    def parse_amount(self, text: str) -> Tuple[Optional[int], Optional[str]]:
        """
        Parse Korean amount text to integer

        Args:
            text: Korean amount text (e.g., "3,000만원", "5억")

        Returns:
            (amount_int, amount_text) tuple
            - amount_int: Integer value or None
            - amount_text: Original text or None
        """
        if not text or not isinstance(text, str):
            return None, None

        text = text.strip()

        # Try each pattern
        for pattern, converter in self.AMOUNT_PATTERNS:
            match = re.search(pattern, text)
            if match:
                try:
                    amount_int = converter(match)
                    return amount_int, text
                except (ValueError, AttributeError):
                    continue

        return None, None

    def parse_premium_frequency(self, text: str) -> Optional[str]:
        """
        Extract premium payment frequency from text

        Args:
            text: Text containing frequency info

        Returns:
            Frequency: '월', '연', '일시', or None
        """
        if not text or not isinstance(text, str):
            return None

        for pattern, frequency in self.PREMIUM_FREQUENCY_PATTERNS:
            if re.search(pattern, text):
                return frequency

        return None

    def extract_coverage_name(self, cells: List[str]) -> Optional[str]:
        """
        Extract coverage name from table row cells

        Strategy: Coverage name is typically in first 3 cells
        Some carriers (e.g., DB) use first column for row numbers ("1.", "2.", etc.)

        Args:
            cells: List of cell texts (may contain None)

        Returns:
            Coverage name or None
        """
        if not cells:
            return None

        # Try first 3 cells (extended from 2 to handle DB's numbered rows)
        for i in range(min(3, len(cells))):
            if cells[i] is None:
                continue
            cell = str(cells[i]).strip()

            # Skip empty cells
            if not cell:
                continue

            # Skip row number patterns (e.g., "1.", "2.", "13.")
            if cell.replace('.', '').isdigit():
                continue

            # Skip cells that look like amounts
            if any(keyword in cell for keyword in ['만원', '억', '원']):
                continue

            # Valid coverage name
            if len(cell) > 2:
                return cell

        return None

    def parse_table_row(self, row: List[str], doc_attributes: Optional[Dict] = None) -> Optional[StructuredCoverage]:
        """
        Parse a single table row into structured coverage data

        Args:
            row: List of cell texts
            doc_attributes: Document-level attributes (gender, age_range from metadata)

        Returns:
            StructuredCoverage object or None if row is not parseable
        """
        if not row or len(row) < 2:
            return None

        # Skip header rows
        if self.is_header_row(row):
            return None

        # Extract coverage name
        coverage_name = self.extract_coverage_name(row)
        if not coverage_name:
            return None

        # Parse amounts from remaining cells
        coverage_amount = None
        coverage_amount_text = None
        premium = None

        # Collect all amounts first
        amounts = []
        for cell in row:
            if cell is None or not cell or cell == coverage_name:
                continue

            amount_int, amount_text = self.parse_amount(str(cell))
            if amount_int is not None:
                amounts.append((amount_int, amount_text))

        # Heuristic: largest amount is coverage, smallest is premium
        if amounts:
            amounts.sort(key=lambda x: x[0], reverse=True)

            # First (largest) is coverage amount
            coverage_amount, coverage_amount_text = amounts[0]

            # Last (smallest) is premium, if there are multiple amounts
            if len(amounts) > 1:
                premium, _ = amounts[-1]

        # Infer premium frequency from context (default: 월)
        premium_frequency = '월' if premium else None

        # Inherit document-level attributes
        target_gender = None
        target_age_range = None

        if doc_attributes:
            target_gender = doc_attributes.get('target_gender')
            target_age_range = doc_attributes.get('target_age_range')

        # Create structured coverage
        structured = StructuredCoverage(
            coverage_name=coverage_name,
            coverage_amount=coverage_amount,
            coverage_amount_text=coverage_amount_text,
            premium=premium,
            premium_frequency=premium_frequency,
            target_gender=target_gender,
            target_age_range=target_age_range
        )

        # Only return if we extracted at least coverage_amount or premium
        if coverage_amount or premium:
            return structured

        return None

    def parse_table(self, table: List[List[str]], doc_attributes: Optional[Dict] = None) -> List[StructuredCoverage]:
        """
        Parse entire table into list of structured coverages

        Args:
            table: List of rows (each row is list of cell texts)
            doc_attributes: Document-level attributes

        Returns:
            List of StructuredCoverage objects
        """
        if not self.is_benefit_table(table):
            return []

        results = []

        for row in table:
            structured = self.parse_table_row(row, doc_attributes)
            if structured:
                results.append(structured)

        return results

    def should_use_structured_parsing(self, doc_type: str) -> bool:
        """
        Determine if document type should use structured table parsing

        Args:
            doc_type: Document type (terms, business_spec, product_summary, proposal, easy_summary)

        Returns:
            True if document should be parsed for tables
        """
        # Based on 8-carrier analysis: 19/38 documents have tables
        structured_doc_types = [
            'proposal',         # 가입설계서 (10 docs)
            'product_summary',  # 상품요약서 (6 docs)
            'easy_summary',     # 쉬운요약서 (1 doc - Samsung)
            'business_spec',    # 사업방법서 (2 docs - DB, 흥국)
        ]

        return doc_type in structured_doc_types


# Singleton instance
_parser = TableParser()


def parse_amount(text: str) -> Tuple[Optional[int], Optional[str]]:
    """Convenience function for parsing amounts"""
    return _parser.parse_amount(text)


def parse_table(table: List[List[str]], doc_attributes: Optional[Dict] = None) -> List[Dict]:
    """Convenience function for parsing tables"""
    structured_coverages = _parser.parse_table(table, doc_attributes)
    return [sc.to_dict() for sc in structured_coverages]


def is_benefit_table(table: List[List[str]]) -> bool:
    """Convenience function for table detection"""
    return _parser.is_benefit_table(table)


def should_use_structured_parsing(doc_type: str) -> bool:
    """Convenience function for doc type check"""
    return _parser.should_use_structured_parsing(doc_type)
