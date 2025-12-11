"""
Parser Factory for Carrier-Specific Table Parsing

Routes table parsing to carrier-specific parsers based on company code.

Usage:
    from ingestion.parsers.parser_factory import ParserFactory

    # Parse a table row
    cells = ['1.', '', '상해사망·후유장해(20-100%)', '1백만원', '132', '20년/100세']
    result = ParserFactory.parse_row(cells, company_code='db')

    # Get parser instance
    parser = ParserFactory.get_parser('db')
    result = parser.parse_coverage_row(cells)
"""

from typing import List, Dict, Optional
from ingestion.parsers.carrier_parsers import (
    SamsungParser,
    DBParser,
    LotteParser,
    MeritzParser,
    KBParser,
    HanwhaParser,
    HyundaiParser,
    HeungkukParser,
)


class ParserFactory:
    """Factory class for routing to carrier-specific parsers"""

    PARSERS = {
        'samsung': SamsungParser,
        'db': DBParser,
        'lotte': LotteParser,
        'meritz': MeritzParser,
        'kb': KBParser,
        'hanwha': HanwhaParser,
        'hyundai': HyundaiParser,
        'heungkuk': HeungkukParser,
    }

    @classmethod
    def get_parser(cls, company_code: str):
        """
        Get parser instance for given company code

        Args:
            company_code: Company code (e.g., 'samsung', 'db', 'lotte')

        Returns:
            Parser instance for the company

        Raises:
            ValueError: If no parser found for company code
        """
        if not company_code:
            raise ValueError("company_code is required")

        company_code = company_code.lower().strip()

        parser_class = cls.PARSERS.get(company_code)
        if not parser_class:
            available = ', '.join(cls.PARSERS.keys())
            raise ValueError(
                f"No parser found for company: {company_code}. "
                f"Available parsers: {available}"
            )

        return parser_class()

    @classmethod
    def parse_row(cls, cells: List[str], company_code: str) -> Optional[Dict]:
        """
        Parse table row using carrier-specific parser

        Args:
            cells: List of cell values from table row
            company_code: Company code (e.g., 'samsung', 'db', 'lotte')

        Returns:
            Parsed coverage data dict or None if row should be skipped

            Example return value:
            {
                'coverage_name': '상해사망·후유장해(20-100%)',
                'coverage_amount': '1백만원',
                'premium': '132',
                'period': '20년/100세'
            }

        Raises:
            ValueError: If no parser found for company code
        """
        if not cells:
            return None

        parser = cls.get_parser(company_code)

        # Skip header rows before parsing
        if parser.is_header_row(cells):
            return None

        return parser.parse_coverage_row(cells)

    @classmethod
    def register_parser(cls, company_code: str, parser_class):
        """
        Register a parser for a company code (for testing/extensions)

        Args:
            company_code: Company code
            parser_class: Parser class (must implement BaseCarrierParser)
        """
        cls.PARSERS[company_code.lower().strip()] = parser_class

    @classmethod
    def list_parsers(cls) -> List[str]:
        """List all registered parser company codes"""
        return sorted(cls.PARSERS.keys())
