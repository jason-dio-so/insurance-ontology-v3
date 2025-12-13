#!/usr/bin/env python3
"""
Re-ingest documents with structured chunking (Phase 5.5)

This script re-ingests all 38 documents with table parsing enabled.
It reads from data/converted JSON files, applies table parser to structured doc types,
and inserts into PostgreSQL with clause_type and structured_data populated.

Usage:
    python scripts/reingest_with_structured_chunking.py [--dry-run]
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional
import psycopg2
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
load_dotenv(project_root / ".env")

from ingestion.table_parser import TableParser, should_use_structured_parsing


POSTGRES_URL = os.getenv("POSTGRES_URL")
if not POSTGRES_URL:
    raise ValueError("POSTGRES_URL environment variable is required. Check .env file.")


class DocumentReingester:
    """Re-ingest documents with structured table parsing"""

    def __init__(self, pg_conn, dry_run=False):
        self.pg_conn = pg_conn
        self.dry_run = dry_run
        self.table_parser = TableParser()
        self.stats = {
            'documents_processed': 0,
            'clauses_inserted': 0,
            'structured_clauses': 0,
            'text_clauses': 0
        }

    def find_converted_documents(self, data_dir: Path = None) -> List[Path]:
        """Find all converted document directories"""
        if data_dir is None:
            data_dir = project_root / "data" / "converted"

        if not data_dir.exists():
            print(f"Warning: {data_dir} does not exist")
            return []

        # Each subdirectory is a document (contains metadata.json)
        # Structure: data/converted/carrier/document_id/
        doc_dirs = []
        for carrier_dir in data_dir.iterdir():
            if not carrier_dir.is_dir():
                continue

            for doc_dir in carrier_dir.iterdir():
                if doc_dir.is_dir() and (doc_dir / "metadata.json").exists():
                    doc_dirs.append(doc_dir)

        return sorted(doc_dirs)

    def load_document_metadata(self, doc_dir: Path) -> Dict:
        """Load document metadata from JSON"""
        with open(doc_dir / "metadata.json", "r", encoding="utf-8") as f:
            return json.load(f)

    def load_document_text(self, doc_dir: Path) -> Dict:
        """Load document text from JSON"""
        text_file = doc_dir / "text.json"
        if text_file.exists():
            with open(text_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"pages": []}

    def load_document_tables(self, doc_dir: Path) -> List[Dict]:
        """Load document tables from JSON"""
        # Check for tables_index.json (new format)
        tables_index_file = doc_dir / "tables_index.json"
        if tables_index_file.exists():
            with open(tables_index_file, "r", encoding="utf-8") as f:
                return json.load(f)

        # Fallback to tables.json (old format)
        tables_file = doc_dir / "tables.json"
        if tables_file.exists():
            with open(tables_file, "r", encoding="utf-8") as f:
                tables_data = json.load(f)
                return tables_data.get("tables", [])

        return []

    def get_or_create_document_id(self, metadata: Dict) -> int:
        """Get or create PostgreSQL document ID"""
        with self.pg_conn.cursor() as cur:
            # Check if document exists
            cur.execute(
                "SELECT id FROM document WHERE document_id = %s",
                (metadata['document_id'],)
            )
            result = cur.fetchone()
            if result:
                return result[0]

            # Get company_id from company_name
            company_id = None
            if metadata.get('company_name'):
                cur.execute(
                    "SELECT id FROM company WHERE name = %s",
                    (metadata['company_name'],)
                )
                company_result = cur.fetchone()
                if company_result:
                    company_id = company_result[0]

            # Insert new document
            cur.execute("""
                INSERT INTO document (
                    document_id, company_id, doc_type
                )
                VALUES (%s, %s, %s)
                RETURNING id
            """, (
                metadata['document_id'],
                company_id,
                metadata.get('doc_type')
            ))

            doc_id = cur.fetchone()[0]
            self.pg_conn.commit()
            return doc_id

    def ingest_document(self, doc_dir: Path):
        """Ingest a single document with structured chunking"""
        print(f"\n{'='*60}")
        print(f"Processing: {doc_dir.name}")
        print(f"{'='*60}")

        # Load metadata
        metadata = self.load_document_metadata(doc_dir)
        doc_type = metadata.get('doc_type', 'unknown')
        document_id_str = metadata['document_id']

        print(f"  Document ID: {document_id_str}")
        print(f"  Doc Type: {doc_type}")
        print(f"  Company: {metadata.get('company_name')}")
        print(f"  Product: {metadata.get('product_name')}")

        # Check if doc_type should use structured parsing
        use_structured = should_use_structured_parsing(doc_type)
        print(f"  Structured Parsing: {'YES' if use_structured else 'NO'}")

        if self.dry_run:
            print("  [DRY RUN] Skipping actual ingestion")
            return

        # Get or create document in DB
        doc_id = self.get_or_create_document_id(metadata)
        print(f"  PostgreSQL doc_id: {doc_id}")

        # Load document content
        text_data = self.load_document_text(doc_dir)
        tables_data = self.load_document_tables(doc_dir)

        # Create page -> tables mapping
        page_tables = {}
        for table_info in tables_data:
            page_num = table_info['page']
            if page_num not in page_tables:
                page_tables[page_num] = []
            page_tables[page_num].append(table_info['data'])

        # Parse document-level attributes (for gender/age variants)
        doc_attributes = metadata.get('attributes', {})

        # Process pages
        clauses_to_insert = []

        for page_data in text_data.get('pages', []):
            page_num = page_data['page']
            page_text = page_data.get('text', '')
            page_tables_list = page_tables.get(page_num, [])

            # If structured parsing enabled and page has tables
            if use_structured and page_tables_list:
                # Parse tables on this page
                for table in page_tables_list:
                    structured_coverages = self.table_parser.parse_table(table, doc_attributes)

                    if structured_coverages:
                        # Create structured clauses
                        for sc in structured_coverages:
                            clause_text = f"{sc.coverage_name}: {sc.coverage_amount_text or ''}"
                            clauses_to_insert.append({
                                'document_id': doc_id,
                                'page_number': page_num,
                                'section': f"page_{page_num}",
                                'text': clause_text,
                                'clause_type': 'table_row',
                                'structured_data': sc.to_dict()
                            })
                            self.stats['structured_clauses'] += 1
                    else:
                        # Table not recognized as benefit table - fallback to text
                        clauses_to_insert.append({
                            'document_id': doc_id,
                            'page_number': page_num,
                            'section': f"page_{page_num}",
                            'text': page_text,
                            'clause_type': 'text_block',
                            'structured_data': None
                        })
                        self.stats['text_clauses'] += 1
            else:
                # No tables or unstructured doc type - text block
                if page_text.strip():
                    clauses_to_insert.append({
                        'document_id': doc_id,
                        'page_number': page_num,
                        'section': f"page_{page_num}",
                        'text': page_text,
                        'clause_type': 'text_block',
                        'structured_data': None
                    })
                    self.stats['text_clauses'] += 1

        # Insert clauses
        if clauses_to_insert:
            with self.pg_conn.cursor() as cur:
                for clause in clauses_to_insert:
                    # Convert structured_data dict to JSON
                    structured_data_json = json.dumps(clause['structured_data']) if clause['structured_data'] else None

                    cur.execute("""
                        INSERT INTO document_clause (
                            document_id, page_number, section, text, clause_type, structured_data
                        )
                        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    """, (
                        clause['document_id'],
                        clause['page_number'],
                        clause['section'],
                        clause['text'],
                        clause['clause_type'],
                        structured_data_json
                    ))

                self.pg_conn.commit()
                self.stats['clauses_inserted'] += len(clauses_to_insert)

        print(f"  ✓ Inserted {len(clauses_to_insert)} clauses")
        print(f"    - Structured: {sum(1 for c in clauses_to_insert if c['clause_type'] == 'table_row')}")
        print(f"    - Text: {sum(1 for c in clauses_to_insert if c['clause_type'] == 'text_block')}")

        self.stats['documents_processed'] += 1

    def run(self):
        """Run full re-ingestion"""
        print("\n" + "="*60)
        print("Phase 5.5: Re-Ingestion with Structured Chunking")
        print("="*60)

        # Find all converted documents
        doc_dirs = self.find_converted_documents()
        print(f"\nFound {len(doc_dirs)} converted documents")

        if not doc_dirs:
            print("No documents found. Run convert_documents.py first.")
            return

        if self.dry_run:
            print("\n[DRY RUN MODE] - No changes will be made to database\n")

        # Clear existing clauses (if not dry run)
        if not self.dry_run:
            confirm = input("\n⚠️  This will DELETE all existing clauses. Continue? (yes/no): ")
            if confirm.lower() != 'yes':
                print("Aborted.")
                return

            with self.pg_conn.cursor() as cur:
                cur.execute("DELETE FROM document_clause")
                self.pg_conn.commit()
                print("✓ Cleared existing clauses")

        # Process each document
        for doc_dir in doc_dirs:
            try:
                self.ingest_document(doc_dir)
            except Exception as e:
                print(f"  ✗ Error: {e}")
                if not self.dry_run:
                    self.pg_conn.rollback()

        # Print summary
        print("\n" + "="*60)
        print("Re-Ingestion Complete")
        print("="*60)
        print(f"Documents processed: {self.stats['documents_processed']}")
        print(f"Total clauses inserted: {self.stats['clauses_inserted']}")
        print(f"  - Structured (table rows): {self.stats['structured_clauses']}")
        print(f"  - Text blocks: {self.stats['text_clauses']}")


def main():
    parser = argparse.ArgumentParser(description="Re-ingest documents with structured chunking")
    parser.add_argument("--dry-run", action="store_true", help="Dry run - don't modify database")
    args = parser.parse_args()

    # Connect to PostgreSQL
    pg_conn = psycopg2.connect(POSTGRES_URL)

    try:
        reingester = DocumentReingester(pg_conn, dry_run=args.dry_run)
        reingester.run()
    finally:
        pg_conn.close()


if __name__ == "__main__":
    main()
