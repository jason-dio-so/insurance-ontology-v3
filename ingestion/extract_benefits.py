"""
Benefit Extraction Pipeline

Purpose: Extract benefit information from table_row clauses
Strategy:
  1. Get table_row clauses with structured_data (coverage_name, coverage_amount)
  2. Match to existing coverage via clause_coverage mapping
  3. Create benefit entries with amount and type

Design: Phase 2.4 of TODO.md
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict
import logging
import argparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BenefitExtractor:
    """Extract benefits from proposal table_row clauses"""

    def __init__(self, db_url: str):
        self.db_url = db_url

    def parse_korean_amount(self, text: str) -> float:
        """
        Parse Korean amount format to numeric value

        Examples:
            '3,000만원' → 30000000
            '1천만원' → 10000000
            '5백만원' → 5000000
            '10만원' → 100000
            '2만원' → 20000

        Returns:
            Numeric amount or None if unparseable
        """
        if not text or not isinstance(text, str):
            return None

        # Remove commas, spaces, and '원'
        text = text.replace(',', '').replace(' ', '').replace('원', '')

        # Skip non-amount strings
        skip_keywords = ['이율', '적용', '회한', '납', '만기', '형', '급', '등급', '직', '년', '전화', ':']
        if any(kw in text for kw in skip_keywords):
            return None

        try:
            # Pattern 1: Pure numbers (already numeric)
            # '30000000' → 30000000
            if text.isdigit():
                return float(text)

            # Pattern 2: Numbers with Korean units
            # '3000만' → 3000 * 10000
            # '1천만' → 1000 * 10000
            # '5백만' → 500 * 10000

            # Replace Korean digit words
            text = text.replace('천만', '*10000000')  # 천만 = 10,000,000
            text = text.replace('백만', '*1000000')   # 백만 = 1,000,000
            text = text.replace('만', '*10000')       # 만 = 10,000
            text = text.replace('천', '*1000')        # 천 = 1,000
            text = text.replace('백', '*100')         # 백 = 100

            # Evaluate the expression
            # '3000*10000' → 30000000
            result = eval(text)
            return float(result)

        except:
            # If all parsing fails, return None
            return None

    def infer_benefit_type(self, coverage_name: str) -> str:
        """
        Infer benefit type from coverage name

        Returns:
            benefit_type: 'diagnosis', 'surgery', 'hospitalization', 'treatment', 'death', 'other'
        """
        coverage_lower = coverage_name.lower()

        if '진단' in coverage_lower or '확정' in coverage_lower:
            return 'diagnosis'
        elif '수술' in coverage_lower:
            return 'surgery'
        elif '입원' in coverage_lower:
            return 'hospitalization'
        elif '치료' in coverage_lower or '요양' in coverage_lower:
            return 'treatment'
        elif '사망' in coverage_lower or '유족' in coverage_lower:
            return 'death'
        else:
            return 'other'

    def extract_benefits(self) -> Dict:
        """
        Extract benefits from table_row clauses

        Returns:
            Summary dictionary
        """
        conn = psycopg2.connect(self.db_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get table_row clauses with structured_data and coverage mapping
        cur.execute("""
            SELECT DISTINCT
                dc.id as clause_id,
                dc.structured_data->>'coverage_name' as coverage_name,
                dc.structured_data->>'coverage_amount' as coverage_amount,
                dc.structured_data->>'coverage_amount_text' as coverage_amount_text,
                cc.coverage_id
            FROM document_clause dc
            JOIN clause_coverage cc ON dc.id = cc.clause_id
            WHERE dc.clause_type = 'table_row'
              AND dc.structured_data IS NOT NULL
              AND dc.structured_data->>'coverage_name' IS NOT NULL
              AND dc.structured_data->>'coverage_amount' IS NOT NULL
              AND cc.coverage_id IS NOT NULL
        """)

        clauses = cur.fetchall()
        logger.info(f"Found {len(clauses)} table_row clauses with coverage mapping")

        inserted = 0
        skipped = 0

        for clause in clauses:
            coverage_id = clause['coverage_id']
            coverage_name = clause['coverage_name']
            coverage_amount = clause['coverage_amount']
            coverage_amount_text = clause['coverage_amount_text']

            # Infer benefit type
            benefit_type = self.infer_benefit_type(coverage_name)

            # Create benefit name (use coverage name as benefit name)
            benefit_name = coverage_name

            try:
                # Convert amount using Korean amount parser
                if coverage_amount:
                    benefit_amount = self.parse_korean_amount(coverage_amount)
                    # Convert to integer if successfully parsed
                    if benefit_amount is not None:
                        benefit_amount = int(benefit_amount)
                else:
                    benefit_amount = None

                # Check if benefit already exists
                cur.execute("""
                    SELECT id FROM benefit
                    WHERE coverage_id = %s AND benefit_name = %s
                """, (coverage_id, benefit_name))

                if cur.fetchone():
                    skipped += 1
                    continue

                # Insert benefit
                cur.execute("""
                    INSERT INTO benefit (
                        coverage_id,
                        benefit_name,
                        benefit_type,
                        benefit_amount,
                        benefit_amount_text,
                        payment_frequency
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    coverage_id,
                    benefit_name,
                    benefit_type,
                    benefit_amount,
                    coverage_amount_text,
                    'once'  # Default: 1회 지급
                ))

                if cur.rowcount > 0:
                    inserted += 1
                    conn.commit()  # Commit immediately after each successful insert
                else:
                    skipped += 1

            except Exception as e:
                logger.error(f"Failed to insert benefit for coverage {coverage_name}: {e}")
                # Rollback this failed transaction and continue with next item
                conn.rollback()
                skipped += 1
                continue
        cur.close()
        conn.close()

        summary = {
            'total_clauses': len(clauses),
            'inserted': inserted,
            'skipped': skipped
        }

        logger.info(f"Benefit extraction: {inserted} inserted, {skipped} skipped")
        return summary

    def get_benefit_stats(self) -> Dict:
        """Get benefit statistics"""
        conn = psycopg2.connect(self.db_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Total benefits
        cur.execute("SELECT COUNT(*) as total FROM benefit")
        total = cur.fetchone()['total']

        # By type
        cur.execute("""
            SELECT benefit_type, COUNT(*) as count
            FROM benefit
            GROUP BY benefit_type
            ORDER BY count DESC
        """)
        by_type = cur.fetchall()

        # By coverage
        cur.execute("""
            SELECT c.coverage_name, COUNT(b.id) as benefit_count
            FROM coverage c
            LEFT JOIN benefit b ON c.id = b.coverage_id
            GROUP BY c.coverage_name
            HAVING COUNT(b.id) > 0
            ORDER BY benefit_count DESC
            LIMIT 10
        """)
        top_coverages = cur.fetchall()

        cur.close()
        conn.close()

        return {
            'total': total,
            'by_type': [dict(row) for row in by_type],
            'top_coverages': [dict(row) for row in top_coverages]
        }


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Extract benefits from table_row clauses')
    args = parser.parse_args()

    db_url = os.getenv('POSTGRES_URL', 'postgresql://postgres:postgres@localhost:5432/insurance_ontology')

    extractor = BenefitExtractor(db_url)

    logger.info("Extracting benefits...")
    summary = extractor.extract_benefits()

    print(f"\n✅ Benefit Extraction Complete")
    print(f"   Total Clauses: {summary['total_clauses']}")
    print(f"   Inserted: {summary['inserted']}")
    print(f"   Skipped: {summary['skipped']}")

    # Show stats
    stats = extractor.get_benefit_stats()
    print(f"\n📊 Benefit Statistics:")
    print(f"   Total Benefits: {stats['total']}")

    print(f"\n   By Type:")
    for row in stats['by_type']:
        print(f"     - {row['benefit_type']}: {row['count']}")

    print(f"\n   Top 10 Coverages by Benefit Count:")
    for row in stats['top_coverages'][:10]:
        print(f"     - {row['coverage_name'][:50]:50s}: {row['benefit_count']} benefits")


if __name__ == '__main__':
    main()
