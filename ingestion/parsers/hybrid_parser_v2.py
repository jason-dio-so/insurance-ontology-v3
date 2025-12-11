"""
HybridParser V2 for Mixed Text/Table Documents (with Validation)

Changes from V1:
- Added coverage name validation using validation functions
- Invalid coverage names are filtered out
- Reduces invalid entries from hybrid-parsed documents (business_spec, product_summary)

Purpose: Parse documents with both text sections and tables
Strategy: Combine section-level text chunks + table row chunks
Document Types: business_spec, product_summary, easy_summary

Design: docs/phase0/PHASE0.2_ONTOLOGY_REDESIGN_v2.md
"""

from typing import Dict, List, Optional
from .table_parser import TableParser, StructuredCoverage
from .carrier_parsers.base_parser import BaseCarrierParser


class HybridParserV2:
    """Parser for mixed text/table documents with validation"""

    def __init__(self):
        """Initialize hybrid parser"""
        self.table_parser = TableParser()
        # Create a temporary validator instance for validation methods
        # We use an anonymous subclass to satisfy abstract method requirement
        class _Validator(BaseCarrierParser):
            def parse_coverage_row(self, cells):
                # Not used in hybrid parser
                return None
        self.validator = _Validator()

    def parse(self, sections: List[Dict], tables: List[Dict], doc_metadata: Dict) -> List[Dict]:
        """
        Parse document with both text sections and tables

        Args:
            sections: List of section dictionaries
                [{'text': '...', 'page': 1}, ...]
            tables: List of table dictionaries
                [{'rows': [[cell, ...], ...], 'page': 1}, ...]
            doc_metadata: Document metadata

        Returns:
            List of clause dictionaries (mix of text and table_row types)
        """
        chunks = []

        # Get document-level attributes for table parsing
        doc_attributes = doc_metadata.get('attributes', {})

        # 1. Parse text sections
        section_chunks = self._parse_sections(sections, doc_metadata)
        chunks.extend(section_chunks)

        # 2. Parse tables (only benefit tables, with validation)
        table_chunks = self._parse_tables(tables, doc_attributes)
        chunks.extend(table_chunks)

        return chunks

    def _parse_sections(self, sections: List[Dict], doc_metadata: Dict) -> List[Dict]:
        """
        Parse text sections into text_block chunks

        Args:
            sections: List of section dictionaries
            doc_metadata: Document metadata

        Returns:
            List of text chunk dictionaries
        """
        chunks = []

        for section in sections:
            text = section.get('text', '').strip()
            page = section.get('page')

            # Skip empty sections
            if not text or len(text) < 20:
                continue

            # Create text block chunk
            chunk = {
                'clause_number': None,
                'clause_title': self._extract_section_title(text),
                'clause_text': text,
                'clause_type': 'text_block',
                'structured_data': None,
                'section_type': None,
                'page_number': page,
                'hierarchy_level': 0,
                'parent_clause_id': None,
                'attributes': None,
            }

            chunks.append(chunk)

        return chunks

    def _parse_tables(self, tables: List[Dict], doc_attributes: Optional[Dict]) -> List[Dict]:
        """
        Parse tables into table_row chunks with validation

        Args:
            tables: List of table dictionaries
            doc_attributes: Document-level attributes

        Returns:
            List of table row chunk dictionaries
        """
        chunks = []

        for table in tables:
            rows = table.get('rows', [])
            page = table.get('page')

            # Skip non-benefit tables
            if not self.table_parser.is_benefit_table(rows):
                continue

            # Parse each row
            structured_coverages = self.table_parser.parse_table(rows, doc_attributes)

            for structured in structured_coverages:
                # ✨ NEW: Validate and clean coverage name before creating chunk
                if not self.validator.is_valid_coverage_name(structured.coverage_name):
                    # Skip invalid coverage name
                    continue

                # Clean the coverage name (remove newlines, normalize whitespace)
                cleaned_name = self.validator.clean_coverage_name(structured.coverage_name)

                # Update structured coverage with cleaned name
                structured.coverage_name = cleaned_name

                # Create table_row chunk
                chunk = {
                    'clause_number': None,
                    'clause_title': cleaned_name,
                    'clause_text': self._format_table_row_text(structured),
                    'clause_type': 'table_row',
                    'structured_data': structured.to_dict(),
                    'section_type': None,
                    'page_number': page,
                    'hierarchy_level': 0,
                    'parent_clause_id': None,
                    'attributes': None,
                }

                chunks.append(chunk)

        return chunks

    def _extract_section_title(self, text: str) -> Optional[str]:
        """
        Extract section title from first line

        Args:
            text: Section text

        Returns:
            Section title or None
        """
        lines = text.split('\n')
        if lines:
            first_line = lines[0].strip()
            # If first line is short (<100 chars), use as title
            if len(first_line) < 100:
                return first_line

        return None

    def _format_table_row_text(self, structured: StructuredCoverage) -> str:
        """
        Format structured coverage as human-readable text

        Args:
            structured: StructuredCoverage object

        Returns:
            Formatted text representation
        """
        parts = [structured.coverage_name]

        if structured.coverage_amount_text:
            parts.append(f"가입금액: {structured.coverage_amount_text}")

        if structured.premium and structured.premium_frequency:
            parts.append(f"{structured.premium_frequency}보험료: {structured.premium:,}원")

        if structured.conditions:
            parts.append(f"조건: {structured.conditions}")

        if structured.target_gender:
            parts.append(f"성별: {structured.target_gender}")

        if structured.target_age_range:
            parts.append(f"연령: {structured.target_age_range}")

        return ', '.join(parts)
