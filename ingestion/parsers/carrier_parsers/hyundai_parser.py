"""
Hyundai Marine Insurance Proposal Parser

Table Structure (Multi-structure support):
    Type 1 (5 columns): [number, coverage_name, amount, premium, period]
    Type 2 (8 columns): [number, "", coverage_name, "", "", period, amount, premium]

Example Rows:
    Type 1: ['1.', '기본계약(상해사망)', '1천만원', '448', '20년납100세만기']
    Type 2: ['1', '', '상해사망', '', '', '20년/100세', '1백만원', '500']

Special Cases:
    - Row number at cells[0]: "1.", "2.", "13." (with period in 5-col), "1", "2" (no period in 8-col)
    - Coverage name at cells[1] (5-col) or cells[2] (8-col)
    - Section headers: ["●", "위험보장 및 보험금 지급내용"] → skip
"""

from .base_parser import BaseCarrierParser
from typing import List, Dict, Optional


class HyundaiParser(BaseCarrierParser):
    """Hyundai Marine Insurance proposal parser with multi-structure support"""

    def parse_coverage_row(self, cells: List[str]) -> Optional[Dict]:
        """
        Parse Hyundai proposal table row (supports 5-col and 8-col structures)

        Args:
            cells: Either [number, coverage_name, amount, premium, period]
                   or [number, "", coverage_name, "", "", period, amount, premium]

        Returns:
            Parsed coverage data or None if row should be skipped
        """
        if len(cells) < 5:
            return None

        # Detect table structure by column count
        if len(cells) >= 8:
            # 8-column structure: cells[2] is coverage name
            coverage_name = cells[2]
            coverage_amount = cells[6] if len(cells) > 6 else ""
            premium = cells[7] if len(cells) > 7 else ""
            period = cells[5] if len(cells) > 5 else ""
        else:
            # 5-column structure: cells[1] is coverage name
            coverage_name = cells[1]
            coverage_amount = cells[2]
            premium = cells[3]
            period = cells[4]

        # Skip empty coverage names
        if self.is_empty_or_whitespace(coverage_name):
            return None

        # Validate coverage name
        if not self.is_valid_coverage_name(coverage_name):
            return None

        return {
            'coverage_name': self.clean_coverage_name(coverage_name),
            'coverage_amount': coverage_amount,
            'premium': premium,
            'period': period
        }
