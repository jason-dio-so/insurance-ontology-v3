"""
Carrier-Specific Parsers for Insurance Proposal Documents

This package contains table parsers for 8 insurance carriers, each with
different table structures and formatting.

Available Parsers:
- SamsungParser: Samsung Fire Insurance (삼성화재)
- DBParser: DB Insurance (DB손해보험)
- LotteParser: Lotte Insurance (롯데손해보험)
- MeritzParser: Meritz Fire Insurance (메리츠화재)
- KBParser: KB Insurance (KB손해보험)
- HanwhaParser: Hanwha Life Insurance (한화생명)
- HyundaiParser: Hyundai Marine Insurance (현대해상)
- HeungkukParser: Heungkuk Life Insurance (흥국생명)

Usage:
    from ingestion.parsers.carrier_parsers import SamsungParser

    parser = SamsungParser()
    result = parser.parse_coverage_row(cells)
"""

from .base_parser import BaseCarrierParser

# Import carrier parsers
from .samsung_parser import SamsungParser
from .db_parser import DBParser
from .lotte_parser import LotteParser
from .meritz_parser import MeritzParser
from .kb_parser import KBParser
from .hanwha_parser import HanwhaParser
from .hyundai_parser import HyundaiParser
from .heungkuk_parser import HeungkukParser

__all__ = [
    'BaseCarrierParser',
    'SamsungParser',
    'DBParser',
    'LotteParser',
    'MeritzParser',
    'KBParser',
    'HanwhaParser',
    'HyundaiParser',
    'HeungkukParser',
]
