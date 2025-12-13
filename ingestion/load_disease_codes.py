"""
Disease Code Loader

Purpose: Extract and load disease code sets from insurance terms documents
Strategy:
  1. Extract ICD/KCD code references from document_clause
  2. Parse code ranges (e.g., C00-C97)
  3. Create disease_code_set and disease_code entries
  4. Support major disease categories:
     - 악성신생물 (Malignant neoplasms): C00-C97
     - 제자리신생물 (In situ neoplasms): D00-D09
     - 뇌혈관질환 (Cerebrovascular): I60-I69
     - 심장질환 (Heart disease): I20-I25

Design: Phase 2.2 of TODO.md
"""

import os
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Tuple
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DiseaseCodeLoader:
    """Extract and load disease codes from terms documents"""

    # Predefined disease code sets based on standard insurance categories
    DISEASE_CODE_SETS = {
        '악성신생물': {
            'description': '암(악성신생물) 분류표',
            'code_ranges': [('C00', 'C97')],
            'code_type': 'KCD',
        },
        '제자리신생물': {
            'description': '제자리신생물 및 양성신생물',
            'code_ranges': [('D00', 'D09')],
            'code_type': 'KCD',
        },
        '기타피부암': {
            'description': '기타피부암',
            'code_ranges': [('C44',)],
            'code_type': 'KCD',
        },
        '갑상선암': {
            'description': '갑상선의 악성신생물',
            'code_ranges': [('C73',)],
            'code_type': 'KCD',
        },
        '뇌출혈': {
            'description': '뇌출혈 (뇌내출혈, 거미막하출혈 등)',
            'code_ranges': [('I60', 'I62')],
            'code_type': 'KCD',
        },
        '뇌경색': {
            'description': '뇌경색',
            'code_ranges': [('I63',)],
            'code_type': 'KCD',
        },
        '뇌졸중': {
            'description': '뇌졸중 (뇌혈관질환)',
            'code_ranges': [('I60', 'I69')],
            'code_type': 'KCD',
        },
        '급성심근경색': {
            'description': '급성심근경색증',
            'code_ranges': [('I21',)],
            'code_type': 'KCD',
        },
        '허혈성심장질환': {
            'description': '허혈성 심장질환',
            'code_ranges': [('I20', 'I25')],
            'code_type': 'KCD',
        },
    }

    def __init__(self, db_url: str):
        self.db_url = db_url

    def expand_code_range(self, start: str, end: str = None) -> List[str]:
        """
        Expand ICD/KCD code range into individual codes

        Args:
            start: Start code (e.g., 'C00')
            end: End code (e.g., 'C97'), or None for single code

        Returns:
            List of codes
        """
        if end is None:
            return [start]

        # Extract prefix and numeric parts
        prefix = re.match(r'([A-Z]+)', start).group(1)
        start_num = int(re.search(r'(\d+)', start).group(1))
        end_num = int(re.search(r'(\d+)', end).group(1))

        codes = []
        for num in range(start_num, end_num + 1):
            codes.append(f"{prefix}{num:02d}")

        return codes

    def create_disease_code_set(self, set_name: str, description: str, version: str = 'KCD-8') -> int:
        """
        Create a disease code set

        Args:
            set_name: Name of the code set
            description: Description
            version: Version (default: KCD-8)

        Returns:
            code_set_id
        """
        conn = psycopg2.connect(self.db_url)
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO disease_code_set (set_name, description, version)
            VALUES (%s, %s, %s)
            ON CONFLICT (set_name) DO UPDATE SET description = EXCLUDED.description
            RETURNING id
        """, (set_name, description, version))

        code_set_id = cur.fetchone()[0]

        conn.commit()
        cur.close()
        conn.close()

        return code_set_id

    def load_disease_codes(self, code_set_id: int, codes: List[str], code_type: str = 'KCD'):
        """
        Load disease codes into database

        Args:
            code_set_id: ID of the code set
            codes: List of codes to load
            code_type: 'KCD' or 'ICD'
        """
        conn = psycopg2.connect(self.db_url)
        cur = conn.cursor()

        inserted = 0
        for code in codes:
            try:
                cur.execute("""
                    INSERT INTO disease_code (code_set_id, code, code_type, description_kr)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (code_set_id, code) DO NOTHING
                """, (code_set_id, code, code_type, None))

                if cur.rowcount > 0:
                    inserted += 1

            except Exception as e:
                logger.error(f"Failed to insert code {code}: {e}")
                continue

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"Loaded {inserted}/{len(codes)} codes for code_set_id={code_set_id}")
        return inserted

    def load_all_disease_code_sets(self) -> Dict:
        """
        Load all predefined disease code sets

        Returns:
            Summary dictionary
        """
        summary = {
            'total_sets': 0,
            'total_codes': 0,
            'sets': []
        }

        for set_name, config in self.DISEASE_CODE_SETS.items():
            logger.info(f"Loading disease code set: {set_name}")

            # Create code set
            code_set_id = self.create_disease_code_set(
                set_name=set_name,
                description=config['description']
            )

            # Expand code ranges
            all_codes = []
            for code_range in config['code_ranges']:
                if len(code_range) == 1:
                    all_codes.extend(self.expand_code_range(code_range[0]))
                else:
                    all_codes.extend(self.expand_code_range(code_range[0], code_range[1]))

            # Load codes
            inserted = self.load_disease_codes(
                code_set_id=code_set_id,
                codes=all_codes,
                code_type=config['code_type']
            )

            summary['total_sets'] += 1
            summary['total_codes'] += inserted
            summary['sets'].append({
                'name': set_name,
                'code_set_id': code_set_id,
                'code_count': inserted
            })

        return summary


def main():
    """Main function"""
    db_url = os.getenv('POSTGRES_URL')
    if not db_url:
        raise ValueError("POSTGRES_URL environment variable is required. Check .env file.")

    loader = DiseaseCodeLoader(db_url)
    summary = loader.load_all_disease_code_sets()

    print(f"\n✅ Disease Code Loading Complete")
    print(f"   Total Sets: {summary['total_sets']}")
    print(f"   Total Codes: {summary['total_codes']}\n")

    print("📋 Code Sets:")
    for s in summary['sets']:
        print(f"   - {s['name']}: {s['code_count']} codes (id={s['code_set_id']})")


if __name__ == '__main__':
    main()
