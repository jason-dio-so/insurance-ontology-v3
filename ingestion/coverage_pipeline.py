"""
Coverage Extraction Pipeline

Purpose: Extract coverage entities from document_clause table
Strategy:
  1. Extract coverage names from proposal documents (structured_data)
  2. Extract coverage constraints from business_spec tables
  3. Populate coverage table with metadata

Design: Phase 2.1 of TODO.md
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Optional
import logging
import argparse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CoveragePipeline:
    """Extract coverage entities from ingested documents"""

    def __init__(self, db_url: str):
        self.db_url = db_url

    def extract_coverages_from_proposals(self, carrier: Optional[str] = None) -> List[Dict]:
        """
        Extract unique coverage names from proposal, product_summary, and business_spec documents

        Per carrier_analysis_report.md:
        - Proposals have 26.3% of coverage data
        - Product summaries have 15.8%
        - Business specs have 5.3%
        - Easy summaries have 2.6%

        Args:
            carrier: Filter by carrier (e.g., 'samsung', 'db', 'lotte')

        Returns:
            List of coverage dictionaries with metadata
        """
        conn = psycopg2.connect(self.db_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Build query with optional carrier filter
        # Extract from ALL document types that contain coverage data
        query = """
            SELECT DISTINCT
                c.company_code,
                p.product_code,
                p.id as product_id,
                d.doc_type,
                dc.structured_data->>'coverage_name' as coverage_name,
                dc.structured_data->>'coverage_amount_text' as coverage_amount_text,
                dc.structured_data->>'premium' as premium,
                dc.structured_data->>'premium_frequency' as premium_frequency
            FROM document_clause dc
            JOIN document d ON dc.document_id = d.id
            JOIN product p ON d.product_id = p.id
            JOIN company c ON p.company_id = c.id
            WHERE d.doc_type IN ('proposal', 'product_summary', 'business_spec', 'easy_summary')
              AND dc.clause_type = 'table_row'
              AND dc.structured_data IS NOT NULL
              AND dc.structured_data->>'coverage_name' IS NOT NULL
        """

        params = []
        if carrier:
            query += " AND c.company_code = %s"
            params.append(carrier)

        query += " ORDER BY c.company_code, p.product_code, coverage_name"

        cur.execute(query, params)
        results = cur.fetchall()

        cur.close()
        conn.close()

        # Log extraction stats by doc_type
        doc_type_counts = {}
        for row in results:
            doc_type = row['doc_type']
            doc_type_counts[doc_type] = doc_type_counts.get(doc_type, 0) + 1

        logger.info(f"Extracted {len(results)} coverage entries from all document types:")
        for doc_type, count in sorted(doc_type_counts.items()):
            logger.info(f"  {doc_type}: {count} coverages")

        return [dict(row) for row in results]

    def save_coverages(self, coverages: List[Dict]) -> int:
        """
        Save unique coverages to coverage table

        Args:
            coverages: List of coverage dictionaries

        Returns:
            Number of coverages inserted
        """
        conn = psycopg2.connect(self.db_url)
        cur = conn.cursor()

        inserted = 0
        skipped_invalid = 0

        for cov in coverages:
            try:
                # Clean coverage name and extract metadata (problem.md fix)
                cleaned = self._clean_coverage_name(cov['coverage_name'])

                # Skip invalid coverage names (period-only, too short, etc.)
                if not cleaned['is_valid']:
                    skipped_invalid += 1
                    logger.debug(f"Skipped invalid coverage: {cov['coverage_name']}")
                    continue

                # Use cleaned coverage_name
                coverage_name = cleaned['coverage_name']
                clause_number = cleaned['clause_number']
                coverage_period = cleaned['coverage_period']

                # Determine renewal_type (cleaned value takes precedence)
                renewal_type = cleaned['renewal_type'] or self._extract_renewal_type(coverage_name)

                # Insert coverage with new columns
                cur.execute("""
                    INSERT INTO coverage (
                        product_id,
                        coverage_code,
                        coverage_name,
                        coverage_category,
                        renewal_type,
                        is_basic,
                        clause_number,
                        coverage_period
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (product_id, coverage_code) DO NOTHING
                    RETURNING id
                """, (
                    cov['product_id'],
                    self._generate_coverage_code(coverage_name),
                    coverage_name,
                    self._infer_coverage_category(coverage_name),
                    renewal_type,
                    '기본계약' in coverage_name,
                    clause_number,
                    coverage_period
                ))

                result = cur.fetchone()
                if result:
                    inserted += 1
                    logger.debug(f"Inserted coverage: {coverage_name} (id={result[0]})")

            except Exception as e:
                logger.error(f"Failed to insert coverage {cov['coverage_name']}: {e}")
                continue

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"Inserted {inserted} new coverages (skipped {skipped_invalid} invalid)")
        return inserted

    def _generate_coverage_code(self, coverage_name: str) -> str:
        """
        Generate coverage_code from coverage_name

        Examples:
            "일반암진단비Ⅱ" → "일반암진단비2"
            "상해사망" → "상해사망"
            "갑상선암·기타피부암·유사암진단비" → "갑상선암기타피부암유사암진단비"
        """
        import unicodedata
        import re

        # Normalize to NFC
        normalized = unicodedata.normalize('NFC', coverage_name)

        # Remove special characters but keep Korean, English, numbers
        # Replace · with empty string
        cleaned = normalized.replace('·', '').replace('(', '').replace(')', '')

        # Convert Roman numerals to Arabic
        cleaned = cleaned.replace('Ⅰ', '1').replace('Ⅱ', '2').replace('Ⅲ', '3').replace('Ⅳ', '4')

        # Remove any remaining special characters except Korean/English/numbers
        cleaned = re.sub(r'[^\w가-힣]', '', cleaned)

        return cleaned

    def _infer_coverage_category(self, coverage_name: str) -> str:
        """
        Infer coverage category from coverage name

        Returns:
            Category string matching coverage_category table
        """
        # Cancer-related
        if '암' in coverage_name and '진단' in coverage_name:
            return 'cancer_diagnosis'
        # Major diseases (stroke, heart)
        elif ('뇌' in coverage_name or '심근경색' in coverage_name or '허혈' in coverage_name) and '진단' in coverage_name:
            return 'major_disease_diagnosis'
        # Death/Disability
        elif '사망' in coverage_name or '장해' in coverage_name or '장애' in coverage_name:
            return 'death_disability'
        # Hospitalization
        elif '입원' in coverage_name:
            return 'hospitalization'
        # Surgery
        elif '수술' in coverage_name:
            return 'surgery'
        # Outpatient
        elif '통원' in coverage_name:
            return 'outpatient'
        # Specific disease diagnosis
        elif '진단' in coverage_name:
            return 'specific_disease_diagnosis'
        else:
            return 'other_benefits'

    def _extract_renewal_type(self, coverage_name: str) -> Optional[str]:
        """
        Extract renewal type from coverage name

        Returns:
            '갱신형', '비갱신형', or None
        """
        if '갱신형' in coverage_name:
            return '갱신형'
        elif '비갱신형' in coverage_name:
            return '비갱신형'
        return None

    def _clean_coverage_name(self, raw_name: str) -> Dict:
        """
        Clean coverage name and extract clause_number, coverage_period, renewal_type

        Handles data pollution patterns from problem.md:
        - "119 뇌졸중진단비" → clause_number: "119", coverage_name: "뇌졸중진단비"
        - "10년", "15년" → skip (period-only data)
        - "[갱신형]담보명" → renewal_type: "갱신형", coverage_name: "담보명"

        Args:
            raw_name: Original coverage name from structured_data

        Returns:
            Dict with keys: coverage_name, clause_number, coverage_period, renewal_type, is_valid
        """
        import re

        result = {
            'coverage_name': raw_name,
            'clause_number': None,
            'coverage_period': None,
            'renewal_type': None,
            'is_valid': True
        }

        if not raw_name or not raw_name.strip():
            result['is_valid'] = False
            return result

        name = raw_name.strip()

        # Pattern 1: Period-only data ("10년", "15년", "20년")
        if re.match(r'^(5|10|15|20|30)년$', name):
            result['is_valid'] = False
            result['coverage_period'] = name
            return result

        # Pattern 2: Clause number prefix ("119 뇌졸중진단비", "121 뇌출혈진단비")
        clause_match = re.match(r'^(\d+)\s+(.+)$', name)
        if clause_match:
            result['clause_number'] = clause_match.group(1)
            name = clause_match.group(2).strip()

        # Pattern 3: Renewal type prefix ("[갱신형]담보명", "[비갱신형]담보명")
        if name.startswith('[갱신형]'):
            result['renewal_type'] = '갱신형'
            name = name.replace('[갱신형]', '').strip()
        elif name.startswith('[비갱신형]'):
            result['renewal_type'] = '비갱신형'
            name = name.replace('[비갱신형]', '').strip()

        # Pattern 4: Period prefix ("10년형 암진단비")
        period_match = re.match(r'^(\d+년형?)\s+(.+)$', name)
        if period_match:
            result['coverage_period'] = period_match.group(1)
            name = period_match.group(2).strip()

        # Validation: Too short name (< 3 characters)
        if len(name) < 3:
            result['is_valid'] = False

        # Validation: Pure number
        if name.isdigit():
            result['is_valid'] = False

        result['coverage_name'] = name
        return result

    def run(self, carrier: Optional[str] = None) -> Dict:
        """
        Run coverage extraction pipeline

        Args:
            carrier: Optional carrier filter

        Returns:
            Summary dictionary
        """
        logger.info(f"Starting coverage extraction pipeline{' for ' + carrier if carrier else ''}...")

        # 1. Extract coverages from proposals
        coverages = self.extract_coverages_from_proposals(carrier)

        # 2. Save to coverage table
        inserted = self.save_coverages(coverages)

        summary = {
            'total_extracted': len(coverages),
            'inserted': inserted,
            'carrier': carrier or 'all'
        }

        logger.info(f"✅ Coverage extraction complete: {inserted}/{len(coverages)} inserted")
        return summary


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Extract coverages from proposal documents')
    parser.add_argument('--carrier', help='Filter by carrier (e.g., samsung, db, lotte)')
    parser.add_argument('--mode', default='extract_toc',
                        help='Mode: extract_toc (default) or extract_constraints')

    args = parser.parse_args()

    db_url = os.getenv('POSTGRES_URL')
    if not db_url:
        raise ValueError("POSTGRES_URL environment variable is required. Check .env file.")

    pipeline = CoveragePipeline(db_url)

    # Handle "all" carrier as None (no filter)
    carrier_filter = None if args.carrier == 'all' else args.carrier

    if args.mode == 'extract_toc':
        summary = pipeline.run(carrier=carrier_filter)
        print(f"\n📊 Summary:")
        print(f"  Carrier: {summary['carrier']}")
        print(f"  Total extracted: {summary['total_extracted']}")
        print(f"  Inserted: {summary['inserted']}")
    else:
        logger.warning(f"Mode '{args.mode}' not yet implemented")


if __name__ == '__main__':
    main()
