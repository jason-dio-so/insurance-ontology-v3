"""
Hanwha Life Insurance Proposal Parser

Table Structure:
    [number, coverage_name, amount, premium, period]

Example Row:
    ['1', '보통약관(상해사망)', '1,000만원', '590원', '100세만기 / 20년납']

Special Cases:
    - Row number at cells[0]: "1", "2", "13" (no period)
    - Coverage name at cells[1]
    - Standard column order (amount before premium)
"""

from .base_parser import BaseCarrierParser
from typing import List, Dict, Optional


class HanwhaParser(BaseCarrierParser):
    """Hanwha Life Insurance proposal parser"""

    def parse_coverage_row(self, cells: List[str]) -> Optional[Dict]:
        """
        Parse Hanwha proposal table row

        Args:
            cells: [number, coverage_name, amount, premium, period]

        Returns:
            Parsed coverage data or None if row should be skipped
        """
        if len(cells) < 5:
            return None

        # cells[0] is row number (skip)
        # cells[1] is coverage name
        coverage_name = cells[1]

        # Skip empty coverage names
        if self.is_empty_or_whitespace(coverage_name):
            return None

        # Validate coverage name
        if not self.is_valid_coverage_name(coverage_name):
            return None

        return {
            'coverage_name': self.clean_coverage_name(coverage_name),
            'coverage_amount': cells[2],
            'premium': cells[3],
            'period': cells[4]
        }
