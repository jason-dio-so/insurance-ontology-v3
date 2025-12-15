"""
Document Parsers for Insurance Ontology V2 (Clean)

Parser types for different document structures:
- TextParser: Terms (약관) → Article chunks
- TableParser: Proposal (가입설계서) → Benefit table row chunks
- FormParser: Proposal (가입설계서) → Form-style key-value extraction
- HybridParserV2: Business Spec, Product Summary, Easy Summary → Section + Table chunks (with validation)

Design: docs/phase0/PHASE0.2_ONTOLOGY_REDESIGN_v2.md
"""

from .text_parser import TextParser
from .table_parser import TableParser
from .form_parser import FormParser, is_form_table, parse_form_table

__all__ = ['TextParser', 'TableParser', 'FormParser', 'is_form_table', 'parse_form_table']
