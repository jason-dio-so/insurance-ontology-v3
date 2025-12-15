"""
Form Parser for Insurance Documents

Purpose: Extract structured key-value data from form-style tables
         in proposals (가입설계서) where merged cells create sparse tables.

Examples:
- 가입조건 테이블: 피보험자, 상해급수, 직업, 보험료 등
- 계약자 정보: 계약자명, 주민번호, 관계 등

Strategy:
1. Detect form tables by empty cell ratio (60%+) and column count (5+)
2. Distinguish header-data patterns vs parallel key-value structures
3. Extract key-value pairs based on column position heuristics

Part of: Structured Chunking Architecture
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass


@dataclass
class FormField:
    """Extracted form field"""
    key: str
    value: str
    section: Optional[str] = None
    row_index: int = -1

    def to_dict(self) -> Dict:
        return {k: v for k, v in self.__dict__.items() if v is not None and v != -1}


class FormParser:
    """Parser for form-style tables with merged cells"""

    # Known key patterns in insurance forms
    KEY_PATTERNS = [
        "계약자", "계 약 자", "피보험자", "피 보 험 자",
        "만기", "납기", "보험료", "플랜", "방법",
        "관계", "주민번호", "상해급수", "직업", "운행차량",
        "환급금", "차량용도", "구분", "가입금액", "담보",
        "보장", "합계", "성별", "나이", "기간", "수익자"
    ]

    # Patterns that indicate terms/clause tables (not forms)
    TERMS_PATTERNS = [
        "최초의 계약", "갱신된 계약", "보험계약일부터",
        "보험가입금액 50%", "보험가입금액 100%",
        "보험수익자에게 지급", "연간 1회에 한하여"
    ]

    def __init__(self, empty_threshold: float = 0.6, min_rows: int = 5, min_cols: int = 5):
        self.empty_threshold = empty_threshold
        self.min_rows = min_rows
        self.min_cols = min_cols

    def is_form_table(self, table: List[List[str]]) -> bool:
        """
        Determine if table is a form-style table

        Criteria:
        1. 60%+ empty cells (due to merged cells)
        2. 5+ columns
        3. 5+ rows
        4. 3+ potential key-value pairs
        5. Not a terms clause table
        """
        if not table or not table[0]:
            return False

        # Criterion 1: Minimum rows
        if len(table) < self.min_rows:
            return False

        # Criterion 2: Empty cell ratio
        total_cells = sum(len(row) for row in table)
        empty_cells = sum(1 for row in table for cell in row if cell == "")
        empty_ratio = empty_cells / total_cells if total_cells > 0 else 0

        if empty_ratio < self.empty_threshold:
            return False

        # Criterion 3: Column count
        num_cols = len(table[0])
        if num_cols < self.min_cols:
            return False

        # Criterion 4: Potential key-value pairs
        kv_count = self._count_potential_key_values(table)
        if kv_count < 3:
            return False

        # Criterion 5: Quick parse check
        try:
            result = self.parse(table)
            if len(result.get('fields', {})) < 2:
                return False
        except:
            return False

        # Criterion 6: Not a terms clause table
        if self._is_terms_clause_table(table):
            return False

        return True

    def _is_terms_clause_table(self, table: List[List[str]]) -> bool:
        """Check if table is a terms/clause explanation table (not a form)"""
        all_text = " ".join(
            cell for row in table for cell in row if cell.strip()
        )
        match_count = sum(1 for p in self.TERMS_PATTERNS if p in all_text)
        return match_count >= 2

    def _count_potential_key_values(self, table: List[List[str]]) -> int:
        """Estimate number of extractable key-value pairs"""
        kv_count = 0

        for row in table:
            non_empty = [(i, cell.strip()) for i, cell in enumerate(row) if cell.strip()]

            if 2 <= len(non_empty) <= 6:
                for idx, cell in non_empty:
                    if any(pattern in cell for pattern in self.KEY_PATTERNS):
                        right_cells = [(i, c) for i, c in non_empty if i > idx]
                        if right_cells:
                            kv_count += 1
                            break

        return kv_count

    def parse(self, table: List[List[str]]) -> Dict[str, Any]:
        """
        Parse form table into structured key-value pairs

        Returns:
            {
                "type": "form",
                "sections": [{"name": str, "row": int}, ...],
                "fields": {"key": "value", ...}
            }
        """
        result = {
            "type": "form",
            "sections": [],
            "fields": {}
        }

        current_section = None
        row_idx = 0

        while row_idx < len(table):
            row = table[row_idx]
            non_empty = [(i, cell) for i, cell in enumerate(row) if cell.strip()]

            if not non_empty:
                row_idx += 1
                continue

            # Single cell row = potential section header
            if len(non_empty) == 1:
                cell_text = non_empty[0][1]
                if len(cell_text) < 50 and not any(c in cell_text for c in ['※', '1.', '2.', '◎']):
                    current_section = cell_text
                    result["sections"].append({
                        "name": current_section,
                        "row": row_idx
                    })
                    row_idx += 1
                    continue

            # Check for header-data pattern with next row
            if row_idx + 1 < len(table):
                next_row = table[row_idx + 1]
                if self._is_header_data_pattern(row, next_row):
                    pairs = self._match_header_data_rows(row, next_row)
                    for key, value in pairs:
                        if key and value:
                            field_key = f"{current_section}_{key}" if current_section else key
                            result["fields"][field_key] = value
                    row_idx += 2
                    continue

            # Single row key-value extraction
            pairs = self._extract_key_value_pairs_single_row(non_empty)
            for key, value in pairs:
                if key and value:
                    field_key = f"{current_section}_{key}" if current_section else key
                    result["fields"][field_key] = value

            row_idx += 1

        return result

    def _is_header_data_pattern(self, header_row: List[str], data_row: List[str]) -> bool:
        """
        Check if two rows form a header-data pattern

        Returns False if header row already contains values (parallel structure)
        """
        header_cells = [(i, c) for i, c in enumerate(header_row) if c.strip()]
        data_cells = [(i, c) for i, c in enumerate(data_row) if c.strip()]

        if len(header_cells) < 2 or len(data_cells) < 2:
            return False

        header_texts = [c for _, c in header_cells]

        # If header has values, it's parallel structure, not header-data
        if any(self._is_value_like(t) for t in header_texts):
            return False

        # If header has 2+ keys and 4+ cells, likely parallel structure
        key_count = sum(1 for t in header_texts if len(t) < 15 and not self._is_value_like(t))
        if key_count >= 2 and len(header_cells) >= 4:
            return False

        # Header cells should mostly be short (labels)
        short_header_ratio = sum(1 for t in header_texts if len(t) < 20) / len(header_texts)
        if short_header_ratio < 0.7:
            return False

        # Data row must have values
        data_texts = [c for _, c in data_cells]
        if not any(self._is_value_like(t) for t in data_texts):
            return False

        # Check position overlap
        header_positions = set(i for i, _ in header_cells)
        data_positions = set(i for i, _ in data_cells)

        overlap = 0
        for dp in data_positions:
            for hp in header_positions:
                if abs(dp - hp) <= 2:
                    overlap += 1
                    break

        overlap_ratio = overlap / len(data_positions) if data_positions else 0
        return overlap_ratio >= 0.5

    def _is_value_like(self, text: str) -> bool:
        """Check if text looks like a value (amount, date, number)"""
        text = text.strip()

        # Amount pattern
        if '원' in text and any(c.isdigit() for c in text):
            return True
        # Date pattern
        if re.match(r'^\d{4}\.\d{2}\.\d{2}', text):
            return True
        # "N급", "N세", "N명" pattern
        if re.match(r'^\d+[급세명]$', text):
            return True
        # Gender/age pattern
        if re.match(r'^[남여]\s*/\s*\d+세', text):
            return True
        # ID number pattern
        if re.match(r'.*\d{6}-', text):
            return True
        # Pure number
        clean = text.replace(',', '').replace('.', '').replace('-', '').replace(' ', '')
        if clean.isdigit() and len(clean) >= 2:
            return True
        # Year pattern
        if '년' in text and any(c.isdigit() for c in text):
            return True
        # "N명" pattern
        if re.match(r'^\d+명$', text):
            return True

        return False

    def _is_key_like(self, text: str) -> bool:
        """Check if text looks like a key/label"""
        # Check value patterns first
        if '세만기' in text or '년납' in text or '년/100세' in text:
            return False
        if '종_' in text or '플랜' in text.lower():
            return False
        if text in ['월납', '연납', '일시납', '-']:
            return False
        if re.match(r'^\d{4}\.\d{2}\.\d{2}', text):
            return False
        if re.match(r'.*\d{6}-', text):
            return False
        if '원' in text and any(c.isdigit() for c in text):
            return False
        if re.match(r'^\d+[급세명]$', text):
            return False
        if re.match(r'^[남여]\s*/\s*\d+세', text):
            return False

        # Explicit key patterns
        if any(pattern in text for pattern in self.KEY_PATTERNS):
            return True

        # Short text without digits/units
        if len(text) < 15:
            clean = text.replace(',', '').replace('.', '').replace('-', '').replace(' ', '')
            if not clean.isdigit() and '원' not in text:
                return True

        return False

    def _match_header_data_rows(self, header_row: List[str], data_row: List[str]) -> List[Tuple[str, str]]:
        """Match header cells with data cells by position"""
        pairs = []

        header_cells = [(i, c.strip()) for i, c in enumerate(header_row) if c.strip()]
        data_cells = [(i, c.strip()) for i, c in enumerate(data_row) if c.strip()]

        used_headers = set()

        for data_idx, data_val in data_cells:
            best_header = None
            best_distance = float('inf')

            for header_idx, header_text in header_cells:
                if header_idx in used_headers:
                    continue

                distance = abs(data_idx - header_idx)
                if distance < best_distance:
                    best_distance = distance
                    best_header = (header_idx, header_text)

            if best_header and best_distance <= 3:
                used_headers.add(best_header[0])
                pairs.append((best_header[1], data_val))

        return pairs

    def _extract_key_value_pairs_single_row(self, non_empty: List[Tuple[int, str]]) -> List[Tuple[str, str]]:
        """Extract key-value pairs from a single row"""
        pairs = []

        keys = [(i, c) for i, c in non_empty if self._is_key_like(c)]
        vals = [(i, c) for i, c in non_empty if not self._is_key_like(c)]

        if not keys or not vals:
            return pairs

        used_vals = set()

        for key_idx, key_text in sorted(keys, key=lambda x: x[0]):
            best_val = None
            best_dist = float('inf')

            for val_idx, val_text in vals:
                if val_idx in used_vals:
                    continue
                if val_idx > key_idx:  # Value should be to the right of key
                    dist = val_idx - key_idx
                    if dist < best_dist:
                        best_dist = dist
                        best_val = (val_idx, val_text)

            if best_val:
                used_vals.add(best_val[0])
                pairs.append((key_text.strip(), best_val[1].strip()))

        return pairs


# Singleton instance
_parser = FormParser()


def is_form_table(table: List[List[str]]) -> bool:
    """Convenience function: Check if table is a form table"""
    return _parser.is_form_table(table)


def parse_form_table(table: List[List[str]]) -> Dict[str, Any]:
    """Convenience function: Parse form table"""
    return _parser.parse(table)
