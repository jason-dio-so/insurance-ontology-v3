"""
Exclusion Extractor

Purpose: Extract Exclusion data from terms (약관) documents
Strategy:
  1. Find exclusion clauses ("보험금을 지급하지 않는 사유", "면책")
  2. Link to coverage via clause_coverage table
  3. Classify exclusion type (absolute, conditional, etc.)
  4. Insert into exclusion table

Usage:
    python -m ingestion.exclusion_extractor [--carrier CARRIER] [--dry-run]
"""

import os
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, List, Optional
import logging
import argparse
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Exclusion type patterns
EXCLUSION_TYPE_PATTERNS = {
    'absolute': [
        r'고의로',
        r'전쟁.*폭동',
        r'자살',
        r'범죄행위',
        r'음주.*운전',
        r'무면허',
    ],
    'conditional': [
        r'다만.*경우에는',
        r'제외.*경우',
        r'단,',
    ],
    'temporal': [
        r'보장개시일.*이전',
        r'계약일.*이전',
        r'면책기간',
    ],
    'pre_existing': [
        r'계약전.*알릴의무',
        r'기왕증',
        r'과거병력',
    ],
}


class ExclusionExtractor:
    """Extract Exclusion data from terms documents"""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.conn = psycopg2.connect(db_url)

    def extract_all(self, carrier: Optional[str] = None, dry_run: bool = False) -> Dict:
        """
        Extract exclusions from all terms documents

        Args:
            carrier: Optional carrier filter
            dry_run: If True, show what would be extracted without inserting

        Returns:
            Summary dict with counts
        """
        # Get exclusion clauses linked to coverages
        clauses = self._get_exclusion_clauses(carrier)
        logger.info(f"Found {len(clauses)} exclusion clauses linked to coverages")

        stats = {'processed': 0, 'exclusions_created': 0, 'duplicates_skipped': 0, 'errors': []}
        extracted = []

        for clause in clauses:
            try:
                exclusion = self._extract_exclusion(clause)
                if exclusion:
                    if dry_run:
                        extracted.append(exclusion)
                    else:
                        result = self._insert_exclusion(exclusion)
                        if result == 'created':
                            stats['exclusions_created'] += 1
                        elif result == 'duplicate':
                            stats['duplicates_skipped'] += 1
                    stats['processed'] += 1
            except Exception as e:
                logger.error(f"Error processing clause {clause['clause_id']}: {e}")
                stats['errors'].append({'clause_id': clause['clause_id'], 'error': str(e)})

        if not dry_run:
            self.conn.commit()

        if dry_run:
            stats['preview'] = extracted

        return stats

    def _get_exclusion_clauses(self, carrier: Optional[str] = None) -> List[Dict]:
        """Get exclusion clauses linked to coverages"""
        cur = self.conn.cursor(cursor_factory=RealDictCursor)

        query = """
            SELECT
                dc.id as clause_id,
                dc.clause_title,
                dc.clause_text,
                cc.coverage_id,
                c.coverage_name,
                d.document_id,
                comp.company_code
            FROM document_clause dc
            JOIN clause_coverage cc ON dc.id = cc.clause_id
            JOIN coverage c ON cc.coverage_id = c.id
            JOIN document d ON dc.document_id = d.id
            JOIN product p ON d.product_id = p.id
            JOIN company comp ON p.company_id = comp.id
            WHERE d.doc_type = 'terms'
              AND (
                  dc.clause_title LIKE '%지급하지 않%'
                  OR dc.clause_title LIKE '%면책%'
                  OR dc.clause_text LIKE '%보험금을 지급하지 않습니다%'
              )
        """
        params = []

        if carrier:
            query += " AND comp.company_code = %s"
            params.append(carrier)

        query += " ORDER BY dc.id"

        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)

        return [dict(row) for row in cur.fetchall()]

    def _extract_exclusion(self, clause: Dict) -> Optional[Dict]:
        """Extract exclusion from a single clause"""
        text = clause['clause_text'] or ''

        if not text or len(text) < 10:
            return None

        # Determine exclusion type
        exclusion_type = self._classify_exclusion_type(text)

        # Determine if absolute (no exceptions) or conditional
        is_absolute = not bool(re.search(r'다만|단,|제외하고|예외', text))

        return {
            'coverage_id': clause['coverage_id'],
            'exclusion_type': exclusion_type,
            'exclusion_text': text[:2000],  # Limit text length
            'is_absolute': is_absolute,
            'attributes': {
                'source_clause_id': clause['clause_id'],
                'coverage_name': clause['coverage_name'],
                'document_id': clause['document_id'],
            }
        }

    def _classify_exclusion_type(self, text: str) -> str:
        """Classify the type of exclusion"""
        for exc_type, patterns in EXCLUSION_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return exc_type
        return 'general'

    def _insert_exclusion(self, exclusion: Dict) -> str:
        """Insert exclusion into database"""
        cur = self.conn.cursor()

        # Check for duplicate (same coverage and similar text)
        cur.execute("""
            SELECT id FROM exclusion
            WHERE coverage_id = %s
              AND LEFT(exclusion_text, 200) = LEFT(%s, 200)
        """, (exclusion['coverage_id'], exclusion['exclusion_text']))

        if cur.fetchone():
            return 'duplicate'

        # Insert
        cur.execute("""
            INSERT INTO exclusion (
                coverage_id, exclusion_type, exclusion_text, is_absolute, attributes
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            exclusion['coverage_id'],
            exclusion['exclusion_type'],
            exclusion['exclusion_text'],
            exclusion['is_absolute'],
            psycopg2.extras.Json(exclusion['attributes'])
        ))

        excl_id = cur.fetchone()[0]
        logger.info(f"Created exclusion {excl_id} for coverage {exclusion['attributes']['coverage_name']}")
        return 'created'

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='Extract Exclusion from terms documents')
    parser.add_argument('--carrier', type=str, help='Filter by carrier (e.g., lotte, samsung)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be extracted without inserting')

    args = parser.parse_args()

    db_url = os.getenv('POSTGRES_URL')
    if not db_url:
        print("Error: POSTGRES_URL environment variable not set")
        return

    extractor = ExclusionExtractor(db_url)

    try:
        result = extractor.extract_all(args.carrier, args.dry_run)

        if args.dry_run:
            print(f"\nDry run - would extract {len(result.get('preview', []))} exclusions:\n")
            for excl in result.get('preview', [])[:20]:
                print(f"  [{excl['exclusion_type']}] {excl['attributes']['coverage_name']}")
                print(f"    Text: {excl['exclusion_text'][:80]}...")
            if len(result.get('preview', [])) > 20:
                print(f"  ... and {len(result['preview']) - 20} more")
        else:
            print(f"\nExtraction complete:")
            print(f"  Processed: {result['processed']} clauses")
            print(f"  Exclusions created: {result['exclusions_created']}")
            print(f"  Duplicates skipped: {result['duplicates_skipped']}")
            if result['errors']:
                print(f"  Errors: {len(result['errors'])}")
    finally:
        extractor.close()


if __name__ == '__main__':
    main()
