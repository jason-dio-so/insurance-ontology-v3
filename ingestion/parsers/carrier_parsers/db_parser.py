"""
DB Insurance Proposal Parser

Table Structure:
    [number, blank, coverage_name, amount, premium, period]

Example Row:
    ['1.', '', '상해사망·후유장해(20-100%)', '1백만원', '132', '20년/100세']

Special Cases:
    - Row number at cells[0] must be skipped: "1.", "2.", "13."
    - cells[1] is typically empty
    - Coverage name is at cells[2]
"""

from .base_parser import BaseCarrierParser
from typing import List, Dict, Optional


class DBParser(BaseCarrierParser):
    """DB Insurance proposal parser"""

    def parse_coverage_row(self, cells: List[str]) -> Optional[Dict]:
        """
        Parse DB proposal table row

        Args:
            cells: [number, blank, coverage_name, amount, premium, period]

        Returns:
            Parsed coverage data or None if row should be skipped
        """
        if len(cells) < 6:
            return None

        # cells[0] is row number (skip)
        # cells[1] is typically empty
        # cells[2] is coverage name
        coverage_name = cells[2]

        # Skip empty coverage names
        if self.is_empty_or_whitespace(coverage_name):
            return None

        # Validate coverage name
        if not self.is_valid_coverage_name(coverage_name):
            return None

        return {
            'coverage_name': self.clean_coverage_name(coverage_name),
            'coverage_amount': cells[3],
            'premium': cells[4],
            'period': cells[5]
        }
