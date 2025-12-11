"""
Meritz Fire Insurance Proposal Parser

Table Structure:
    [category, number, coverage_name, amount, premium, period]

Example Row:
    ['기본계약', '1', '일반상해80%이상후유장해[기본계약]', '1백만원', '8', '20년 / 100세']

Special Cases:
    - Row number at cells[1] (not cells[0])
    - Coverage names may contain newline characters: "지급\\n보험금"
    - Category column (cells[0]) contains category like "기본계약"
    - Coverage name is at cells[2]
"""

from .base_parser import BaseCarrierParser
from typing import List, Dict, Optional


class MeritzParser(BaseCarrierParser):
    """Meritz Fire Insurance proposal parser"""

    def parse_coverage_row(self, cells: List[str]) -> Optional[Dict]:
        """
        Parse Meritz proposal table row

        Args:
            cells: [category, number, coverage_name, amount, premium, period]

        Returns:
            Parsed coverage data or None if row should be skipped
        """
        if len(cells) < 6:
            return None

        # cells[0] is category
        # cells[1] is row number (skip)
        # cells[2] is coverage name
        coverage_name = cells[2]

        # Skip empty coverage names
        if self.is_empty_or_whitespace(coverage_name):
            return None

        # Validate coverage name
        if not self.is_valid_coverage_name(coverage_name):
            return None

        # Clean newlines (Meritz special case)
        # Example: "지급\n보험금" → "지급 보험금"
        coverage_name = self.clean_coverage_name(coverage_name)

        return {
            'coverage_name': coverage_name,
            'coverage_amount': cells[3],
            'premium': cells[4],
            'period': cells[5]
        }
