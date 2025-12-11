"""
Samsung Fire Insurance Proposal Parser

Table Structure:
    [category/blank, coverage_name, amount, premium, period]

Example Rows:
    ['진단', '보험료 납입면제대상Ⅱ', '10만원', '189', '20년납 100세만기']
    ['', '암 진단비(유사암 제외)', '3,000만원', '40,620', '20년납 100세만기']

Special Cases:
    - Time period rows must be skipped: "3개월", "6개월", "10년"
    - Category column (cells[0]) may be empty or contain category name
    - Coverage name is always at cells[1]
"""

from .base_parser import BaseCarrierParser
from typing import List, Dict, Optional
import re


class SamsungParser(BaseCarrierParser):
    """Samsung Fire Insurance proposal parser"""

    def parse_coverage_row(self, cells: List[str]) -> Optional[Dict]:
        """
        Parse Samsung proposal table row

        Args:
            cells: [category/blank, coverage_name, amount, premium, period]

        Returns:
            Parsed coverage data or None if row should be skipped
        """
        if len(cells) < 5:
            return None

        coverage_name = cells[1]

        # Skip time-period-only rows ("3개월", "6개월", "10년")
        if self._is_time_period_only(coverage_name):
            return None

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

    def _is_time_period_only(self, name: str) -> bool:
        """
        Detect time-period-only names (Samsung special case)

        Examples:
            "3개월" → True
            "6개월" → True
            "10년" → True
            "암 진단비" → False
        """
        if not name:
            return False

        # Pattern: digits followed by "개월" or "년"
        return bool(re.match(r'^\d+(개월|년)$', name.strip()))
