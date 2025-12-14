"""
Proposal Plan Extractor

Purpose: Extract Plan metadata from proposal (가입설계서) documents
Strategy:
  1. Parse converted JSON tables for plan-level metadata
  2. Extract: target_gender, target_age, insurance_period, payment_period, total_premium
  3. Insert into plan table
  4. Link to coverages via plan_coverage table

Usage:
    python -m ingestion.proposal_plan_extractor [--carrier CARRIER]
"""

import os
import re
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
import argparse
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProposalPlanExtractor:
    """Extract Plan metadata from proposal documents"""

    # Company code to directory name mapping
    COMPANY_DIR_MAP = {
        'samsung': '삼성',
        'db': 'db',
        'lotte': '롯데',
        'kb': 'kb',
        'hyundai': '현대',
        'hanwha': '한화',
        'heungkuk': '흥국',
        'meritz': '메리츠',
    }

    @staticmethod
    def _parse_sum_insured(text: str) -> tuple:
        """
        가입금액 텍스트를 숫자와 텍스트로 분리

        Args:
            text: 가입금액 텍스트 (예: "1,000만원", "3천만원", "1억원")

        Returns:
            (numeric_value, original_text) 튜플

        Examples:
            "1,000만원" → (10000000.0, "1,000만원")
            "3천만원" → (30000000.0, "3천만원")
            "1억원" → (100000000.0, "1억원")
            "10만원" → (100000.0, "10만원")
            "1,000" → (1000.0, "1,000")  # 단위 없는 경우 (단위: 만원 가정)
        """
        if not text:
            return None, None

        original = str(text).strip()
        cleaned = original.replace(',', '').replace(' ', '')

        try:
            # 패턴 1: "N억M천만원" (복합)
            match = re.search(r'(\d+)억(\d*)천?만?원?', cleaned)
            if match:
                eok = int(match.group(1))
                rest = int(match.group(2)) if match.group(2) else 0
                if '천만' in cleaned:
                    return float(eok * 100000000 + rest * 10000000), original
                elif '만' in cleaned:
                    return float(eok * 100000000 + rest * 10000), original
                else:
                    return float(eok * 100000000), original

            # 패턴 2: "N억원"
            match = re.search(r'(\d+\.?\d*)억', cleaned)
            if match:
                return float(match.group(1)) * 100000000, original

            # 패턴 3: "N천만원"
            match = re.search(r'(\d+\.?\d*)천만', cleaned)
            if match:
                return float(match.group(1)) * 10000000, original

            # 패턴 4: "N만원" 또는 "N만"
            match = re.search(r'(\d+\.?\d*)만', cleaned)
            if match:
                return float(match.group(1)) * 10000, original

            # 패턴 5: 숫자만 있는 경우 (테이블에서 단위가 만원인 경우)
            # 예: "1,000" (표 헤더가 "가입금액(만원)"인 경우)
            match = re.search(r'^(\d+\.?\d*)$', cleaned)
            if match:
                value = float(match.group(1))
                # 1000 이하는 만원 단위로 가정 (1,000만원 = 10,000,000원)
                if value <= 10000:
                    return value * 10000, original
                else:
                    return value, original

        except (ValueError, AttributeError):
            pass

        return None, original

    @staticmethod
    def _parse_premium(text: str) -> float:
        """
        보험료 텍스트를 숫자로 변환

        Args:
            text: 보험료 텍스트 (예: "590원", "8,050원", "590")

        Returns:
            numeric_value (float) 또는 None

        Examples:
            "590원" → 590.0
            "8,050원" → 8050.0
            "34,230" → 34230.0
        """
        if not text:
            return None

        cleaned = str(text).strip().replace(',', '').replace(' ', '')

        # "원" 제거
        cleaned = cleaned.replace('원', '')

        # "-" 또는 빈값 처리
        if cleaned in ['-', '', '해당없음']:
            return None

        try:
            return float(cleaned)
        except ValueError:
            return None

    def __init__(self, db_url: str, converted_dir: str = 'data/converted_v2'):
        self.db_url = db_url
        self.converted_dir = Path(converted_dir)
        self.conn = psycopg2.connect(db_url)

    def extract_all(self, carrier: Optional[str] = None) -> Dict:
        """
        Extract plans from all proposal documents

        Args:
            carrier: Optional carrier filter (e.g., 'lotte', 'samsung')

        Returns:
            Summary dict with counts
        """
        # Get proposal documents from DB
        proposals = self._get_proposal_documents(carrier)
        logger.info(f"Found {len(proposals)} proposal documents")

        stats = {'processed': 0, 'plans_created': 0, 'plan_coverages_created': 0, 'errors': []}

        for doc in proposals:
            try:
                result = self._process_proposal(doc)
                if result:
                    stats['plans_created'] += result['plans']
                    stats['plan_coverages_created'] += result['plan_coverages']
                stats['processed'] += 1
            except Exception as e:
                logger.error(f"Error processing {doc['document_id']}: {e}")
                stats['errors'].append({'document_id': doc['document_id'], 'error': str(e)})

        self.conn.commit()
        return stats

    def _get_proposal_documents(self, carrier: Optional[str] = None) -> List[Dict]:
        """Get proposal documents from database"""
        cur = self.conn.cursor(cursor_factory=RealDictCursor)

        query = """
            SELECT d.id, d.document_id, d.product_id, d.variant_id, d.attributes,
                   c.company_code, p.product_code
            FROM document d
            JOIN product p ON d.product_id = p.id
            JOIN company c ON p.company_id = c.id
            WHERE d.doc_type = 'proposal'
        """
        params = []

        if carrier:
            query += " AND c.company_code = %s"
            params.append(carrier)

        query += " ORDER BY d.document_id"
        cur.execute(query, params)

        return [dict(row) for row in cur.fetchall()]

    def _process_proposal(self, doc: Dict) -> Optional[Dict]:
        """
        Process a single proposal document

        Args:
            doc: Document dict from database

        Returns:
            Result dict with counts or None
        """
        document_id = doc['document_id']
        company_code = doc['company_code']

        # Find converted directory (use mapping for Korean directory names)
        company_dir = self.COMPANY_DIR_MAP.get(company_code, company_code)
        converted_path = self.converted_dir / company_dir / document_id

        if not converted_path.exists():
            logger.warning(f"Converted path not found: {converted_path}")
            return None

        # Load tables
        tables = self._load_tables(converted_path)
        if not tables:
            logger.warning(f"No tables found for {document_id}")
            return None

        # Extract plan metadata
        plan_data = self._extract_plan_metadata(tables, doc)

        if not plan_data:
            logger.warning(f"Could not extract plan metadata from {document_id}")
            return None

        # Check if plan already exists
        existing_plan = self._get_existing_plan(doc['id'])
        if existing_plan:
            logger.info(f"Plan already exists for document {document_id}, skipping")
            return {'plans': 0, 'plan_coverages': 0}

        # Insert plan
        plan_id = self._insert_plan(doc, plan_data)

        # Link to coverages
        coverage_count = self._link_plan_coverages(plan_id, doc['id'], tables)

        logger.info(f"Created plan {plan_id} with {coverage_count} coverages for {document_id}")

        return {'plans': 1, 'plan_coverages': coverage_count}

    def _load_tables(self, converted_path: Path) -> List[Dict]:
        """Load all tables from converted directory"""
        tables_index_path = converted_path / 'tables_index.json'

        if not tables_index_path.exists():
            return []

        with open(tables_index_path, 'r', encoding='utf-8') as f:
            tables_index = json.load(f)

        tables = []
        for table_info in tables_index.get('tables', []):
            table_path = converted_path / table_info['file']
            if table_path.exists():
                with open(table_path, 'r', encoding='utf-8') as f:
                    table_data = json.load(f)
                    tables.append({
                        'table_id': table_info['table_id'],
                        'page': table_info['page'],
                        'rows': table_data
                    })

        return tables

    def _extract_plan_metadata(self, tables: List[Dict], doc: Dict) -> Optional[Dict]:
        """
        Extract plan metadata from tables

        Returns:
            Dict with target_gender, target_age, insurance_period, payment_period, total_premium
        """
        plan_data = {
            'target_gender': None,
            'target_age': None,
            'insurance_period': None,
            'payment_period': None,
            'total_premium': None,
            'plan_name': None
        }

        # Try to get from document attributes first
        if doc.get('attributes'):
            attrs = doc['attributes']
            if 'target_gender' in attrs:
                plan_data['target_gender'] = attrs['target_gender']
            if 'target_age_range' in attrs:
                # Parse age range like "≤40" or "≥41"
                age_range = attrs['target_age_range']
                if '≤' in age_range:
                    plan_data['target_age'] = int(re.search(r'\d+', age_range).group())
                elif '≥' in age_range:
                    plan_data['target_age'] = int(re.search(r'\d+', age_range).group())

        # Extract from tables
        for table in tables:
            rows = table['rows']

            for row in rows:
                row_text = ' '.join([str(cell) for cell in row if cell])

                # Extract gender and age from 피보험자 row
                # Pattern: "고객(650407-1******) 60세" or "피보험자 ... 남 40세"
                if '피보험자' in row_text or '고객' in row_text:
                    # Try to extract age
                    age_match = re.search(r'(\d+)\s*세', row_text)
                    if age_match and not plan_data['target_age']:
                        plan_data['target_age'] = int(age_match.group(1))

                    # Try to extract gender from resident number (1,3=male, 2,4=female)
                    resident_match = re.search(r'\d{6}-([1-4])', row_text)
                    if resident_match and not plan_data['target_gender']:
                        digit = resident_match.group(1)
                        plan_data['target_gender'] = 'male' if digit in ['1', '3'] else 'female'

                    # Try explicit gender
                    if '남' in row_text and not plan_data['target_gender']:
                        plan_data['target_gender'] = 'male'
                    elif '여' in row_text and not plan_data['target_gender']:
                        plan_data['target_gender'] = 'female'

                # Extract insurance/payment period
                # Pattern 1: "20년/100세" or "20년납/80세만기"
                period_match = re.search(r'(\d+)\s*년[납]?\s*/\s*(\d+)\s*세', row_text)
                if period_match:
                    if not plan_data['payment_period']:
                        plan_data['payment_period'] = f"{period_match.group(1)}년납"
                    if not plan_data['insurance_period']:
                        plan_data['insurance_period'] = f"{period_match.group(2)}세만기"

                # Pattern 2: "100세만기/20년납" (reversed order)
                if not plan_data['insurance_period'] or not plan_data['payment_period']:
                    period_match2 = re.search(r'(\d+)\s*세만기\s*/\s*(\d+)\s*년납', row_text)
                    if period_match2:
                        if not plan_data['insurance_period']:
                            plan_data['insurance_period'] = f"{period_match2.group(1)}세만기"
                        if not plan_data['payment_period']:
                            plan_data['payment_period'] = f"{period_match2.group(2)}년납"

                # Pattern 2b: "20년납 100세만기" (space separated, KB/Samsung style)
                if not plan_data['insurance_period'] or not plan_data['payment_period']:
                    period_match2b = re.search(r'(\d+)\s*년납\s+(\d+)\s*세만기', row_text)
                    if period_match2b:
                        if not plan_data['payment_period']:
                            plan_data['payment_period'] = f"{period_match2b.group(1)}년납"
                        if not plan_data['insurance_period']:
                            plan_data['insurance_period'] = f"{period_match2b.group(2)}세만기"

                # Pattern 2c: "20년납100세만기" (no separator, Hyundai style)
                if not plan_data['insurance_period'] or not plan_data['payment_period']:
                    period_match2c = re.search(r'(\d+)년납(\d+)세만기', row_text)
                    if period_match2c:
                        if not plan_data['payment_period']:
                            plan_data['payment_period'] = f"{period_match2c.group(1)}년납"
                        if not plan_data['insurance_period']:
                            plan_data['insurance_period'] = f"{period_match2c.group(2)}세만기"

                # Pattern 3: "보험기간" row with "100세만기/20년납"
                if '보험기간' in row_text:
                    for cell in row:
                        cell_str = str(cell) if cell else ''
                        # Try "100세만기/20년납" pattern
                        pm = re.search(r'(\d+)\s*세만기\s*/\s*(\d+)\s*년납', cell_str)
                        if pm:
                            plan_data['insurance_period'] = f"{pm.group(1)}세만기"
                            plan_data['payment_period'] = f"{pm.group(2)}년납"
                            break
                        # Try "20년납/100세만기" pattern
                        pm2 = re.search(r'(\d+)\s*년납\s*/\s*(\d+)\s*세', cell_str)
                        if pm2:
                            plan_data['payment_period'] = f"{pm2.group(1)}년납"
                            plan_data['insurance_period'] = f"{pm2.group(2)}세만기"
                            break

                # Also try "납기/만기" header format
                if '납기' in row_text and '만기' in row_text:
                    for cell in row:
                        if cell and '년' in str(cell) and '세' in str(cell):
                            pm = re.search(r'(\d+)\s*년\s*/\s*(\d+)\s*세', str(cell))
                            if pm:
                                plan_data['payment_period'] = f"{pm.group(1)}년납"
                                plan_data['insurance_period'] = f"{pm.group(2)}세만기"
                                break

                # Extract total premium
                # Pattern: "보장보험료 합계 : 255,110 원" or "합계: 50,000원"
                if '합계' in row_text:
                    premium_match = re.search(r'([0-9,]+)\s*원', row_text)
                    if premium_match:
                        premium_str = premium_match.group(1).replace(',', '')
                        plan_data['total_premium'] = float(premium_str)

        # Generate plan name
        parts = []
        if plan_data['target_gender']:
            parts.append('남성' if plan_data['target_gender'] == 'male' else '여성')
        if plan_data['target_age']:
            parts.append(f"{plan_data['target_age']}세")
        if plan_data['payment_period']:
            parts.append(plan_data['payment_period'])

        plan_data['plan_name'] = ' '.join(parts) if parts else doc['document_id']

        return plan_data if any(v for k, v in plan_data.items() if k != 'plan_name') else None

    def _get_existing_plan(self, document_id: int) -> Optional[int]:
        """Check if plan already exists for document"""
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM plan WHERE document_id = %s", (document_id,))
        row = cur.fetchone()
        return row[0] if row else None

    def _insert_plan(self, doc: Dict, plan_data: Dict) -> int:
        """Insert plan into database"""
        cur = self.conn.cursor()

        cur.execute("""
            INSERT INTO plan (
                document_id, product_id, variant_id, plan_name,
                target_gender, target_age, insurance_period, payment_period, total_premium
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            doc['id'],
            doc['product_id'],
            doc.get('variant_id'),
            plan_data['plan_name'],
            plan_data['target_gender'],
            plan_data['target_age'],
            plan_data['insurance_period'],
            plan_data['payment_period'],
            plan_data['total_premium']
        ))

        return cur.fetchone()[0]

    def _link_plan_coverages(self, plan_id: int, document_id: int, tables: List[Dict]) -> int:
        """
        Link plan to coverages via plan_coverage table

        Uses existing document_clause structured_data to find coverage amounts
        """
        cur = self.conn.cursor(cursor_factory=RealDictCursor)

        # Get coverages from document_clause structured_data
        cur.execute("""
            SELECT dc.id as clause_id,
                   dc.structured_data->>'coverage_name' as coverage_name,
                   dc.structured_data->>'coverage_amount' as coverage_amount,
                   dc.structured_data->>'coverage_amount_text' as coverage_amount_text,
                   dc.structured_data->>'premium' as premium,
                   c.id as coverage_id
            FROM document_clause dc
            LEFT JOIN coverage c ON c.coverage_name = dc.structured_data->>'coverage_name'
            WHERE dc.document_id = %s
              AND dc.clause_type = 'table_row'
              AND dc.structured_data IS NOT NULL
              AND dc.structured_data->>'coverage_name' IS NOT NULL
        """, (document_id,))

        clauses = cur.fetchall()
        count = 0

        for clause in clauses:
            if not clause['coverage_id']:
                continue  # Skip if no matching coverage in coverage table

            # Parse sum_insured (가입금액)
            sum_insured = None
            sum_insured_text = None

            # Try coverage_amount_text first (original text), then coverage_amount
            amount_text = clause.get('coverage_amount_text') or clause.get('coverage_amount')
            if amount_text:
                sum_insured, sum_insured_text = self._parse_sum_insured(amount_text)

            # Parse premium (보험료)
            premium = self._parse_premium(clause.get('premium'))

            # Insert plan_coverage
            try:
                cur.execute("""
                    INSERT INTO plan_coverage (plan_id, coverage_id, sum_insured, sum_insured_text, premium)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (plan_id, coverage_id) DO UPDATE SET
                        sum_insured = EXCLUDED.sum_insured,
                        sum_insured_text = EXCLUDED.sum_insured_text,
                        premium = EXCLUDED.premium
                """, (plan_id, clause['coverage_id'], sum_insured, sum_insured_text, premium))
                count += 1
            except Exception as e:
                logger.warning(f"Could not link coverage {clause['coverage_id']}: {e}")

        return count

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='Extract Plan metadata from proposals')
    parser.add_argument('--carrier', type=str, help='Filter by carrier (e.g., lotte, samsung)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be extracted without inserting')

    args = parser.parse_args()

    db_url = os.getenv('POSTGRES_URL')
    if not db_url:
        print("Error: POSTGRES_URL environment variable not set")
        return

    extractor = ProposalPlanExtractor(db_url)

    try:
        if args.dry_run:
            print("Dry run mode - showing extraction preview...")
            proposals = extractor._get_proposal_documents(args.carrier)
            for doc in proposals:
                company_dir = extractor.COMPANY_DIR_MAP.get(doc['company_code'], doc['company_code'])
                converted_path = extractor.converted_dir / company_dir / doc['document_id']
                if converted_path.exists():
                    tables = extractor._load_tables(converted_path)
                    plan_data = extractor._extract_plan_metadata(tables, doc)
                    print(f"\n{doc['document_id']}:")
                    print(f"  {plan_data}")
        else:
            result = extractor.extract_all(args.carrier)
            print(f"\nExtraction complete:")
            print(f"  Processed: {result['processed']}")
            print(f"  Plans created: {result['plans_created']}")
            print(f"  Plan-Coverage links: {result['plan_coverages_created']}")
            if result['errors']:
                print(f"  Errors: {len(result['errors'])}")
                for err in result['errors']:
                    print(f"    - {err['document_id']}: {err['error']}")
    finally:
        extractor.close()


if __name__ == '__main__':
    main()
