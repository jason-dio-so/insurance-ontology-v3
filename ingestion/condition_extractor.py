"""
Condition Extractor

Purpose: Extract Condition data from terms (약관) documents
Strategy:
  1. Find condition clauses ("보장개시", "면책기간", "가입조건")
  2. Link to coverage via clause_coverage table
  3. Extract waiting_period_days, min_age, max_age
  4. Insert into condition table

Usage:
    python -m ingestion.condition_extractor [--carrier CARRIER] [--dry-run]
"""

import os
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, List, Optional, Tuple
import logging
import argparse
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Condition type patterns
CONDITION_PATTERNS = {
    'waiting_period': {
        'title_patterns': [r'보장개시', r'면책기간'],
        'text_patterns': [
            (r'(\d+)일이\s*지난\s*날', 'days'),
            (r'(\d+)일\s*(?:이\s*)?(?:경과|지난)', 'days'),
            (r'면책기간\s*(\d+)일', 'days'),
        ],
    },
    'age_limit': {
        'title_patterns': [r'가입나이', r'피보험자의\s*범위', r'가입연령'],
        'text_patterns': [
            (r'(\d+)세\s*~\s*(\d+)세', 'age_range'),
            (r'(\d+)세\s*이상\s*(\d+)세\s*이하', 'age_range'),
            (r'만\s*(\d+)세.*만\s*(\d+)세', 'age_range'),
        ],
    },
    'renewal': {
        'title_patterns': [r'갱신', r'자동갱신'],
        'text_patterns': [],
    },
}


class ConditionExtractor:
    """Extract Condition data from terms documents"""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.conn = psycopg2.connect(db_url)

    def extract_all(self, carrier: Optional[str] = None, dry_run: bool = False) -> Dict:
        """
        Extract conditions from all terms documents

        Args:
            carrier: Optional carrier filter
            dry_run: If True, show what would be extracted without inserting

        Returns:
            Summary dict with counts
        """
        # Get condition clauses linked to coverages
        clauses = self._get_condition_clauses(carrier)
        logger.info(f"Found {len(clauses)} condition clauses linked to coverages")

        stats = {'processed': 0, 'conditions_created': 0, 'duplicates_skipped': 0, 'errors': []}
        extracted = []

        for clause in clauses:
            try:
                condition = self._extract_condition(clause)
                if condition:
                    if dry_run:
                        extracted.append(condition)
                    else:
                        result = self._insert_condition(condition)
                        if result == 'created':
                            stats['conditions_created'] += 1
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

    def _get_condition_clauses(self, carrier: Optional[str] = None) -> List[Dict]:
        """Get condition clauses linked to coverages"""
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
                  dc.clause_title LIKE '%보장개시%'
                  OR dc.clause_title LIKE '%면책기간%'
                  OR dc.clause_title LIKE '%가입나이%'
                  OR dc.clause_title LIKE '%가입연령%'
                  OR dc.clause_text LIKE '%일이 지난 날%'
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

    def _extract_condition(self, clause: Dict) -> Optional[Dict]:
        """Extract condition from a single clause"""
        title = clause['clause_title'] or ''
        text = clause['clause_text'] or ''

        if not text or len(text) < 10:
            return None

        # Determine condition type
        condition_type = self._classify_condition_type(title, text)

        # Extract waiting period
        waiting_period = self._extract_waiting_period(text)

        # Extract age limits
        min_age, max_age = self._extract_age_limits(text)

        return {
            'coverage_id': clause['coverage_id'],
            'condition_type': condition_type,
            'condition_text': text[:2000],  # Limit text length
            'min_age': min_age,
            'max_age': max_age,
            'waiting_period_days': waiting_period,
            'attributes': {
                'source_clause_id': clause['clause_id'],
                'coverage_name': clause['coverage_name'],
                'document_id': clause['document_id'],
            }
        }

    def _classify_condition_type(self, title: str, text: str) -> str:
        """Classify the type of condition"""
        for cond_type, config in CONDITION_PATTERNS.items():
            for pattern in config.get('title_patterns', []):
                if re.search(pattern, title):
                    return cond_type
        return 'general'

    def _extract_waiting_period(self, text: str) -> Optional[int]:
        """Extract waiting period in days from text"""
        patterns = [
            r'(\d+)일이\s*지난\s*날',
            r'(\d+)일\s*(?:이\s*)?(?:경과|지난)',
            r'면책기간\s*(\d+)일',
            r'(\d+)일\s*간',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                days = int(match.group(1))
                if 1 <= days <= 365:  # Reasonable range
                    return days
        return None

    def _extract_age_limits(self, text: str) -> Tuple[Optional[int], Optional[int]]:
        """Extract min and max age from text"""
        patterns = [
            (r'(\d+)세\s*~\s*(\d+)세', (1, 2)),
            (r'(\d+)세\s*이상\s*(\d+)세\s*이하', (1, 2)),
            (r'만\s*(\d+)세.*만\s*(\d+)세', (1, 2)),
        ]

        for pattern, groups in patterns:
            match = re.search(pattern, text)
            if match:
                min_age = int(match.group(groups[0]))
                max_age = int(match.group(groups[1]))
                if 0 <= min_age <= 100 and 0 <= max_age <= 100:
                    return min_age, max_age

        return None, None

    def _insert_condition(self, condition: Dict) -> str:
        """Insert condition into database"""
        cur = self.conn.cursor()

        # Check for duplicate (same coverage and similar text)
        cur.execute("""
            SELECT id FROM condition
            WHERE coverage_id = %s
              AND LEFT(condition_text, 200) = LEFT(%s, 200)
        """, (condition['coverage_id'], condition['condition_text']))

        if cur.fetchone():
            return 'duplicate'

        # Insert
        cur.execute("""
            INSERT INTO condition (
                coverage_id, condition_type, condition_text,
                min_age, max_age, waiting_period_days, attributes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            condition['coverage_id'],
            condition['condition_type'],
            condition['condition_text'],
            condition['min_age'],
            condition['max_age'],
            condition['waiting_period_days'],
            psycopg2.extras.Json(condition['attributes'])
        ))

        cond_id = cur.fetchone()[0]
        logger.info(f"Created condition {cond_id} for coverage {condition['attributes']['coverage_name']}")
        return 'created'

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='Extract Condition from terms documents')
    parser.add_argument('--carrier', type=str, help='Filter by carrier (e.g., lotte, samsung)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be extracted without inserting')

    args = parser.parse_args()

    db_url = os.getenv('POSTGRES_URL')
    if not db_url:
        print("Error: POSTGRES_URL environment variable not set")
        return

    extractor = ConditionExtractor(db_url)

    try:
        result = extractor.extract_all(args.carrier, args.dry_run)

        if args.dry_run:
            print(f"\nDry run - would extract {len(result.get('preview', []))} conditions:\n")
            by_type = {}
            for cond in result.get('preview', []):
                t = cond['condition_type']
                by_type[t] = by_type.get(t, 0) + 1

            print("By type:")
            for t, cnt in sorted(by_type.items(), key=lambda x: -x[1]):
                print(f"  {t}: {cnt}")

            print("\nSamples:")
            for cond in result.get('preview', [])[:10]:
                print(f"  [{cond['condition_type']}] {cond['attributes']['coverage_name']}")
                if cond['waiting_period_days']:
                    print(f"    Waiting: {cond['waiting_period_days']} days")
                if cond['min_age'] or cond['max_age']:
                    print(f"    Age: {cond['min_age']}-{cond['max_age']}")
        else:
            print(f"\nExtraction complete:")
            print(f"  Processed: {result['processed']} clauses")
            print(f"  Conditions created: {result['conditions_created']}")
            print(f"  Duplicates skipped: {result['duplicates_skipped']}")
            if result['errors']:
                print(f"  Errors: {len(result['errors'])}")
    finally:
        extractor.close()


if __name__ == '__main__':
    main()
