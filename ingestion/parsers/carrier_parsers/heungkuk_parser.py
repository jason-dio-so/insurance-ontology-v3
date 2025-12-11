"""
Heungkuk Life Insurance Proposal Parser

Table Structure:
    [blank, coverage_name, period, amount, premium]

Example Row:
    ['', '일반상해후유장해(80%이상)', '20년납 100세만기', '1,000만원', '130']

Special Cases:
    - cells[0] is typically empty (no row number or category)
    - Coverage name at cells[1]
    - **Different column order**: period BEFORE amount (cells[2], cells[3])
    - Premium at cells[4]
"""

from .base_parser import BaseCarrierParser
from typing import List, Dict, Optional


class HeungkukParser(BaseCarrierParser):
    """Heungkuk Life Insurance proposal parser"""

    def parse_coverage_row(self, cells: List[str]) -> Optional[Dict]:
        """
        Parse Heungkuk proposal table row

        Args:
            cells: [blank, coverage_name, period, amount, premium]

        Returns:
            Parsed coverage data or None if row should be skipped

        Note:
            Heungkuk has different column order: period comes BEFORE amount
        """
        if len(cells) < 5:
            return None

        # cells[0] is typically empty
        # cells[1] is coverage name
        coverage_name = cells[1]

        # Skip empty coverage names
        if self.is_empty_or_whitespace(coverage_name):
            return None

        # Validate coverage name
        if not self.is_valid_coverage_name(coverage_name):
            return None

        # Note: Different column order
        # cells[2] = period (not amount!)
        # cells[3] = amount (not premium!)
        # cells[4] = premium
        return {
            'coverage_name': self.clean_coverage_name(coverage_name),
            'period': cells[2],
            'coverage_amount': cells[3],
            'premium': cells[4]
        }
