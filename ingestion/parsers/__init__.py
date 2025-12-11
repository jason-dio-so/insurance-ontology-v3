"""
Document Parsers for Insurance Ontology V2 (Clean)

Three parser types for different document structures:
- TextParser: Terms (약관) → Article chunks
- TableParser: Proposal (가입설계서) → Table row chunks
- HybridParserV2: Business Spec, Product Summary, Easy Summary → Section + Table chunks (with validation)

Design: docs/phase0/PHASE0.2_ONTOLOGY_REDESIGN_v2.md
"""

from .text_parser import TextParser
from .table_parser import TableParser

__all__ = ['TextParser', 'TableParser']
