"""
Lotte Insurance Proposal Parser

Table Structure:
    [category, coverage_name, amount, period, premium]

Example Row:
    ['암관련', '64 일반암수술비(1회한)', '500만원', '20년/100세', '12,000']

Special Cases:
    - Category headers must be filtered: "암관련", "뇌질환", "심장질환", etc.
    - Category column (cells[0]) contains category or blank
    - Coverage name is at cells[1]
    - Column order differs: period before premium (cells[3], cells[4])
"""

from .base_parser import BaseCarrierParser
from typing import List, Dict, Optional


class LotteParser(BaseCarrierParser):
    """Lotte Insurance proposal parser"""

    # Known category header keywords (Lotte-specific)
    CATEGORY_KEYWORDS = [
        '암관련', '뇌질환', '심장질환', '수술비',
        '기본계약', '골절/화상', '갱신계약'
    ]

    def parse_coverage_row(self, cells: List[str]) -> Optional[Dict]:
        """
        Parse Lotte proposal table row

        Args:
            cells: [category, coverage_name, amount, period, premium]

        Returns:
            Parsed coverage data or None if row should be skipped
        """
        if len(cells) < 5:
            return None

        # Skip category headers
        if self._is_category_header(cells[0]):
            return None

        coverage_name = cells[1]

        # Skip empty coverage names
        if self.is_empty_or_whitespace(coverage_name):
            return None

        # Validate coverage name
        if not self.is_valid_coverage_name(coverage_name):
            return None

        # Note: Column order differs from other carriers
        # cells[3] = period, cells[4] = premium
        return {
            'coverage_name': self.clean_coverage_name(coverage_name),
            'coverage_amount': cells[2],
            'period': cells[3],
            'premium': cells[4]
        }

    def _is_category_header(self, text: str) -> bool:
        """
        Detect category header rows (Lotte special case)

        Category headers have characteristics:
        1. Exact match with known keywords
        2. Short generic terms (≤4 chars) containing "관련" or "질환"

        Examples:
            "암관련" → True (exact match)
            "뇌질환" → True (exact match)
            "심질환" → True (short term with "질환")
            "일반암진단비Ⅱ" → False (actual coverage)
        """
        if not text:
            return False

        text = text.strip()

        # Pattern 1: Exact match with known category keywords
        if text in self.CATEGORY_KEYWORDS:
            return True

        # Pattern 2: Short generic terms with "관련" or "질환"
        if len(text) <= 4 and any(kw in text for kw in ['관련', '질환']):
            return True

        return False
