"""
KB Insurance Proposal Parser

Table Structure (before filtering):
    [number, coverage_name, EMPTY*9, amount, EMPTY*5, premium, EMPTY*4]

Table Structure (after filtering):
    [number, coverage_name, amount, premium]

Example Row (raw):
    ['1', '일반상해사망(기본)', '', '1천만원', '', '', '', '700', '', '', '', '', '']

Example Row (filtered):
    ['1', '일반상해사망(기본)', '1천만원', '700']

Special Cases:
    - pdfplumber creates 13 columns (9 empty) - must filter empty columns
    - Row number at filtered[0]
    - Coverage name at filtered[1]
    - Amount at filtered[2]
    - Premium at filtered[3]
"""

from .base_parser import BaseCarrierParser
from typing import List, Dict, Optional


class KBParser(BaseCarrierParser):
    """KB Insurance proposal parser with empty column filtering"""

    def parse_coverage_row(self, cells: List[str]) -> Optional[Dict]:
        """
        Parse KB proposal table row

        Args:
            cells: Raw cells with empty columns

        Returns:
            Parsed coverage data or None if row should be skipped
        """
        # Remove empty columns first (KB special case)
        filtered = self.filter_empty_cells(cells)

        if len(filtered) < 4:
            return None

        # After filtering:
        # filtered[0] = row number (skip)
        # filtered[1] = coverage name
        # filtered[2] = amount
        # filtered[3] = premium

        coverage_name = filtered[1]

        # Skip empty coverage names
        if self.is_empty_or_whitespace(coverage_name):
            return None

        # Validate coverage name
        if not self.is_valid_coverage_name(coverage_name):
            return None

        return {
            'coverage_name': self.clean_coverage_name(coverage_name),
            'coverage_amount': filtered[2],
            'premium': filtered[3]
        }
