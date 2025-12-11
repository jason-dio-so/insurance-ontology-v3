"""
Document Ingestion Pipeline v3 (Optimized)

Changes from v2:
- Removed CoverageMapper (moved to Phase 2.3)
- Use HybridParserV2 with validation
- ~60% faster ingestion (no coverage mapping overhead)

Purpose: Ingest 38 documents with structured chunking
Strategy:
  1. Route documents to appropriate parser (Text/Table/Hybrid V2)
  2. Parse into chunks (article/text_block/table_row) with validation
  3. Save to document + document_clause tables
  4. Coverage mapping deferred to Phase 2.3 (link_clauses.py)

Design: docs/phase0/PHASE0.2_ONTOLOGY_REDESIGN_v2.md
"""

import os
import json
import re
import psycopg2
from pathlib import Path
from typing import Dict, List, Optional
import logging

from ingestion.parsers import TextParser, TableParser
from ingestion.parsers.hybrid_parser_v2 import HybridParserV2
from ingestion.parsers.parser_factory import ParserFactory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DocumentIngestionPipeline:
    """v3 ingestion pipeline (optimized, no coverage mapping)"""

    # Document type → Parser mapping
    PARSER_MAPPING = {
        'terms': 'text',           # TextParser
        'proposal': 'table',       # TableParser (table_row only)
        'business_spec': 'hybrid', # HybridParserV2
        'product_summary': 'hybrid',
        'easy_summary': 'hybrid',
    }

    def __init__(self, db_url: str):
        """
        Initialize ingestion pipeline

        Args:
            db_url: PostgreSQL connection URL
        """
        self.db_url = db_url
        self.text_parser = TextParser()
        self.table_parser = TableParser()
        self.hybrid_parser = HybridParserV2()  # V2 with validation
        # CoverageMapper removed - moved to Phase 2.3

    def route_parser(self, doc_type: str) -> str:
        """
        Route document type to parser type

        Args:
            doc_type: Document type

        Returns:
            Parser type: 'text', 'table', 'hybrid'
        """
        return self.PARSER_MAPPING.get(doc_type, 'hybrid')

    def load_converted_document(self, document_id: str, converted_dir: str = 'data/converted') -> Optional[Dict]:
        """
        Load converted document JSON

        Args:
            document_id: Document ID
            converted_dir: Base directory for converted docs

        Returns:
            Document data dictionary (pages list) or None
        """
        # Find JSON file matching document_id
        converted_path = Path(converted_dir)

        for carrier_dir in converted_path.iterdir():
            if not carrier_dir.is_dir():
                continue

            doc_dir = carrier_dir / document_id
            if doc_dir.exists():
                # Load text.json which contains pages data
                text_file = doc_dir / 'text.json'
                if text_file.exists():
                    with open(text_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # Return pages array
                        return data.get('pages', [])

        logger.warning(f"Converted document not found: {document_id}")
        return None

    def save_document(self, metadata: Dict) -> int:
        """
        Save document metadata to database

        Args:
            metadata: Document metadata

        Returns:
            document.id (database ID)
        """
        conn = psycopg2.connect(self.db_url)
        cur = conn.cursor()

        # Get or create company
        company_code = metadata.get('company_code')
        cur.execute("""
            INSERT INTO company (company_code, company_name, business_type)
            VALUES (%s, %s, %s)
            ON CONFLICT (company_code) DO UPDATE SET company_name = EXCLUDED.company_name
            RETURNING id
        """, (company_code, metadata.get('company_name', company_code), None))

        company_id = cur.fetchone()[0]

        # Get or create product
        product_code = metadata.get('product_code')
        product_name = metadata.get('product_name', product_code)
        version = metadata.get('version')

        cur.execute("""
            INSERT INTO product (company_id, product_code, product_name, version)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (company_id, product_code, version) DO UPDATE SET product_name = EXCLUDED.product_name
            RETURNING id
        """, (company_id, product_code, product_name, version))

        product_id = cur.fetchone()[0]

        # Get or create product_variant (if gender/age specific)
        variant_id = None
        doc_subtype = metadata.get('doc_subtype')
        attributes = metadata.get('attributes', {})

        if doc_subtype in ['male', 'female', 'age_40_under', 'age_41_over']:
            variant_code = doc_subtype
            target_gender = attributes.get('target_gender') or ('male' if 'male' in doc_subtype else ('female' if 'female' in doc_subtype else None))
            target_age_range = attributes.get('target_age_range')

            cur.execute("""
                INSERT INTO product_variant (product_id, variant_name, variant_code, target_gender, target_age_range, attributes)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (product_id, variant_code) DO UPDATE SET variant_name = EXCLUDED.variant_name
                RETURNING id
            """, (product_id, doc_subtype, variant_code, target_gender, target_age_range, json.dumps(attributes)))

            variant_id = cur.fetchone()[0]

        # Insert document
        document_id_str = metadata.get('document_id')
        doc_type = metadata.get('doc_type')
        file_path = metadata.get('file_path')
        total_pages = metadata.get('total_pages')

        cur.execute("""
            INSERT INTO document (document_id, company_id, product_id, variant_id, doc_type, doc_subtype, version, file_path, total_pages, attributes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (document_id) DO UPDATE
            SET doc_type = EXCLUDED.doc_type,
                doc_subtype = EXCLUDED.doc_subtype,
                total_pages = EXCLUDED.total_pages
            RETURNING id
        """, (document_id_str, company_id, product_id, variant_id, doc_type, doc_subtype, version, file_path, total_pages, json.dumps(attributes)))

        doc_db_id = cur.fetchone()[0]

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"Saved document: {document_id_str} (id={doc_db_id}, product_id={product_id})")
        return doc_db_id, product_id

    def parse_document(self, doc_data: List[Dict], metadata: Dict) -> List[Dict]:
        """
        Parse document using appropriate parser

        Args:
            doc_data: Converted document data (list of pages)
            metadata: Document metadata

        Returns:
            List of clause dictionaries
        """
        doc_type = metadata.get('doc_type')
        parser_type = self.route_parser(doc_type)

        logger.info(f"Parsing {doc_type} with {parser_type} parser")

        # Extract sections and tables from pages
        sections = []
        tables = []

        for page in doc_data:
            page_num = page.get('page')

            # Collect text as sections
            page_text = page.get('text', '')
            if page_text:
                sections.append({
                    'text': page_text,
                    'page': page_num,
                    'section_type': None,
                })

            # Collect tables
            for table in page.get('tables', []):
                tables.append({
                    'rows': table,  # table is already list of rows
                    'page': page_num,
                })

        # Route to appropriate parser
        if parser_type == 'text':
            chunks = self.text_parser.parse(sections, metadata)
        elif parser_type == 'table':
            # For proposals, use carrier-specific parsers
            chunks = []
            company_code = metadata.get('company_code')

            if not company_code:
                logger.warning(f"No company_code in metadata for {metadata.get('document_id')}, falling back to standard parser")
                # Fallback to standard parser
                doc_attributes = metadata.get('attributes', {})
                for table in tables:
                    rows = table['rows']
                    page = table['page']
                    structured_coverages = self.table_parser.parse_table(rows, doc_attributes)
                    for structured in structured_coverages:
                        chunk = {
                            'clause_number': None,
                            'clause_title': structured.coverage_name,
                            'clause_text': self._format_table_row_text_from_structured(structured),
                            'clause_type': 'table_row',
                            'structured_data': structured.to_dict(),
                            'section_type': None,
                            'page_number': page,
                            'hierarchy_level': 0,
                            'parent_clause_id': None,
                            'attributes': None,
                        }
                        chunks.append(chunk)
            else:
                # Use carrier-specific parser
                for table in tables:
                    rows = table['rows']
                    page = table['page']

                    for row in rows:
                        try:
                            parsed_data = ParserFactory.parse_row(row, company_code)
                            if parsed_data:
                                # parsed_data is a dict with keys: coverage_name, coverage_amount, premium, period
                                chunk = {
                                    'clause_number': None,
                                    'clause_title': parsed_data.get('coverage_name'),
                                    'clause_text': self._format_table_row_text(parsed_data),
                                    'clause_type': 'table_row',
                                    'structured_data': parsed_data,
                                    'section_type': None,
                                    'page_number': page,
                                    'hierarchy_level': 0,
                                    'parent_clause_id': None,
                                    'attributes': None,
                                }
                                chunks.append(chunk)
                        except Exception as e:
                            logger.error(f"Error parsing row with {company_code} parser: {e}")
                            logger.error(f"Row: {row}")
                            continue

        else:  # hybrid
            chunks = self.hybrid_parser.parse(sections, tables, metadata)

        logger.info(f"Parsed {len(chunks)} chunks")
        return chunks

    def save_clauses(self, doc_db_id: int, chunks: List[Dict]) -> List[int]:
        """
        Save clauses to database

        Args:
            doc_db_id: Document database ID
            chunks: List of clause dictionaries

        Returns:
            List of clause IDs
        """
        conn = psycopg2.connect(self.db_url)
        cur = conn.cursor()

        clause_ids = []

        for chunk in chunks:
            # Convert structured_data to JSON if present
            if chunk['structured_data']:
                # Clean NULL characters from structured_data values
                cleaned_data = {}
                for k, v in chunk['structured_data'].items():
                    if isinstance(v, str):
                        cleaned_data[k] = v.replace('\x00', '')
                    else:
                        cleaned_data[k] = v
                structured_data_json = json.dumps(cleaned_data)
            else:
                structured_data_json = None

            # Clean NULL characters from text fields (PostgreSQL doesn't allow 0x00)
            clause_text = chunk['clause_text'].replace('\x00', '') if chunk['clause_text'] else None
            clause_title = chunk['clause_title'].replace('\x00', '') if chunk['clause_title'] else None

            cur.execute("""
                INSERT INTO document_clause (
                    document_id, clause_number, clause_title, clause_text,
                    clause_type, structured_data, section_type, page_number,
                    hierarchy_level, parent_clause_id, attributes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                doc_db_id,
                chunk['clause_number'],
                clause_title,
                clause_text,
                chunk['clause_type'],
                structured_data_json,
                chunk['section_type'],
                chunk['page_number'],
                chunk['hierarchy_level'],
                chunk['parent_clause_id'],
                json.dumps(chunk['attributes']) if chunk['attributes'] else None
            ))

            clause_id = cur.fetchone()[0]
            clause_ids.append(clause_id)

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"Saved {len(clause_ids)} clauses")
        return clause_ids

    def ingest_document(self, metadata: Dict, converted_dir: str = 'data/converted') -> Dict:
        """
        Ingest a single document

        Args:
            metadata: Document metadata dictionary
            converted_dir: Base directory for converted docs

        Returns:
            Ingestion result dictionary
        """
        document_id = metadata['document_id']
        logger.info(f"Ingesting document: {document_id}")

        # 1. Load converted document
        doc_data = self.load_converted_document(document_id, converted_dir)
        if not doc_data:
            logger.error(f"Failed to load converted document: {document_id}")
            return {'status': 'error', 'message': 'Document not found'}

        # 2. Save document metadata
        doc_db_id, product_id = self.save_document(metadata)

        # 3. Parse document into chunks
        chunks = self.parse_document(doc_data, metadata)

        # 4. Save clauses
        clause_ids = self.save_clauses(doc_db_id, chunks)

        # Coverage mapping moved to Phase 2.3 (link_clauses.py)
        logger.info(f"✅ {document_id}: {len(clause_ids)} clauses")

        return {
            'status': 'success',
            'document_id': document_id,
            'doc_db_id': doc_db_id,
            'product_id': product_id,
            'clause_count': len(clause_ids),
        }

    def ingest_all_documents(self, metadata_json: str = 'data/documents_metadata.json') -> Dict:
        """
        Ingest all documents from metadata JSON

        Args:
            metadata_json: Path to metadata JSON file

        Returns:
            Summary dictionary
        """
        results = []
        errors = []

        # Load JSON metadata
        with open(metadata_json, 'r', encoding='utf-8') as f:
            documents = json.load(f)

        for doc_metadata in documents:
            try:
                result = self.ingest_document(doc_metadata)
                results.append(result)

                if result['status'] == 'success':
                    logger.info(f"✅ {doc_metadata['document_id']}: {result['clause_count']} clauses")
                else:
                    logger.error(f"❌ {doc_metadata['document_id']}: {result.get('message')}")
                    errors.append(doc_metadata['document_id'])

            except Exception as e:
                logger.error(f"❌ {doc_metadata['document_id']}: {str(e)}")
                errors.append(doc_metadata['document_id'])

        summary = {
            'total': len(results),
            'success': len([r for r in results if r.get('status') == 'success']),
            'errors': errors,
        }

        logger.info(f"\n📊 Ingestion Summary:")
        logger.info(f"  Total: {summary['total']}")
        logger.info(f"  Success: {summary['success']}")
        logger.info(f"  Errors: {len(summary['errors'])}")

        return summary

    def _format_table_row_text(self, data: Dict) -> str:
        """
        Format parsed coverage data (Dict) as text

        Args:
            data: Parsed coverage data from carrier-specific parser
                  Keys: coverage_name, coverage_amount, premium, period

        Returns:
            Formatted text string
        """
        parts = []

        coverage_name = data.get('coverage_name')
        if coverage_name:
            parts.append(coverage_name)

        coverage_amount = data.get('coverage_amount')
        if coverage_amount:
            parts.append(f"가입금액: {coverage_amount}")

        premium = data.get('premium')
        if premium:
            parts.append(f"보험료: {premium}원")

        period = data.get('period')
        if period:
            parts.append(f"기간: {period}")

        return ', '.join(parts) if parts else ''

    def _format_table_row_text_from_structured(self, structured) -> str:
        """
        Format structured coverage object as text (fallback for standard parser)

        Args:
            structured: StructuredCoverage object from standard TableParser

        Returns:
            Formatted text string
        """
        parts = [structured.coverage_name]
        if structured.coverage_amount_text:
            parts.append(f"가입금액: {structured.coverage_amount_text}")
        if structured.premium:
            parts.append(f"{structured.premium_frequency}보험료: {structured.premium:,}원")
        return ', '.join(parts)


def main():
    """Main ingestion function"""
    import argparse

    parser = argparse.ArgumentParser(description='Ingest insurance documents into PostgreSQL')
    parser.add_argument('metadata_json', nargs='?', default='data/documents_metadata.json',
                        help='Path to documents metadata JSON file')
    parser.add_argument('--metadata', dest='metadata_json_flag',
                        help='Path to documents metadata JSON file (alternative flag)')

    args = parser.parse_args()

    # Use --metadata flag if provided, otherwise use positional argument
    metadata_json = args.metadata_json_flag if args.metadata_json_flag else args.metadata_json

    db_url = os.getenv('POSTGRES_URL', 'postgresql://postgres:postgres@localhost:5432/insurance_ontology')

    pipeline = DocumentIngestionPipeline(db_url)
    pipeline.ingest_all_documents(metadata_json)


if __name__ == '__main__':
    main()
