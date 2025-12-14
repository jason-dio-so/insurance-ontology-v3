"""
Risk Event Extractor

Purpose: Extract RiskEvent data from terms (약관) documents
Strategy:
  1. Parse document_clause for clauses with "정의" in title
  2. Extract risk event types (cancer, cerebrovascular, cardiovascular, etc.)
  3. Extract ICD codes from clause text
  4. Insert into risk_event table

Usage:
    python -m ingestion.risk_event_extractor [--carrier CARRIER] [--dry-run]
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


# Risk event type mappings
RISK_EVENT_PATTERNS = {
    'cancer': {
        'patterns': [
            r'암[,\s]',
            r'일반암',
            r'갑상선암',
            r'기타피부암',
            r'유사암',
            r'소액암',
            r'고액치료비암',
            r'재진단암',
            r'남성생식기암',
            r'악성\s*신생물',
        ],
        'title_patterns': [
            r'암.*정의',
            r'일반암.*정의',
            r'갑상선암.*정의',
            r'재진단암.*정의',
            r'고액치료비암.*정의',
        ],
        'severity_default': 'high',
    },
    'cerebrovascular': {
        'patterns': [
            r'뇌출혈',
            r'뇌졸중',
            r'뇌혈관질환',
            r'뇌경색',
            r'일과성뇌허혈발작',
            r'뇌동맥질환',
            r'외상성뇌손상',
            r'외상성뇌출혈',
        ],
        'title_patterns': [
            r'뇌.*정의',
        ],
        'severity_default': 'high',
    },
    'cardiovascular': {
        'patterns': [
            r'급성심근경색',
            r'심혈관질환',
            r'심뇌혈관질환',
            r'심근병증',
            r'허혈성심장질환',
        ],
        'title_patterns': [
            r'심근.*정의',
            r'심혈관.*정의',
        ],
        'severity_default': 'high',
    },
    'injury': {
        'patterns': [
            r'중증화상',
            r'부식진단',
            r'골절',
            r'상해',
        ],
        'title_patterns': [
            r'화상.*정의',
            r'골절.*정의',
        ],
        'severity_default': 'medium',
    },
    'treatment': {
        'patterns': [
            r'항암방사선치료',
            r'항암약물치료',
            r'항암화학치료',
            r'표적항암',
            r'면역항암',
            r'호르몬치료',
            r'양성자방사선',
            r'중입자방사선',
            r'다빈치로봇',
        ],
        'title_patterns': [
            r'항암.*치료.*정의',
            r'표적항암.*정의',
            r'면역항암.*정의',
        ],
        'severity_default': 'medium',
    },
    'hospitalization': {
        'patterns': [
            r'입원',
            r'종합병원',
        ],
        'title_patterns': [
            r'입원.*정의',
        ],
        'severity_default': 'low',
    },
}

# ICD code patterns
ICD_PATTERNS = [
    (r'C\d{2}(?:-C\d{2})?', 'cancer'),  # C00-C97 malignant neoplasms
    (r'I6\d(?:-I\d{2})?', 'cerebrovascular'),  # I60-I69 cerebrovascular diseases
    (r'I2[0-5](?:-I\d{2})?', 'cardiovascular'),  # I20-I25 ischemic heart diseases
    (r'S\d{2}(?:-S\d{2})?', 'injury'),  # S00-S99 injuries
    (r'T\d{2}(?:-T\d{2})?', 'injury'),  # T00-T98 injuries, poisoning
]


class RiskEventExtractor:
    """Extract RiskEvent data from terms documents"""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.conn = psycopg2.connect(db_url)

    def extract_all(self, carrier: Optional[str] = None, dry_run: bool = False) -> Dict:
        """
        Extract risk events from all terms documents

        Args:
            carrier: Optional carrier filter (e.g., 'lotte', 'samsung')
            dry_run: If True, show what would be extracted without inserting

        Returns:
            Summary dict with counts
        """
        # Get definition clauses from terms documents
        clauses = self._get_definition_clauses(carrier)
        logger.info(f"Found {len(clauses)} definition clauses")

        stats = {'processed': 0, 'events_created': 0, 'duplicates_skipped': 0, 'errors': []}
        extracted_events = []

        for clause in clauses:
            try:
                events = self._extract_risk_events(clause)
                for event in events:
                    if dry_run:
                        extracted_events.append(event)
                    else:
                        result = self._insert_risk_event(event)
                        if result == 'created':
                            stats['events_created'] += 1
                        elif result == 'duplicate':
                            stats['duplicates_skipped'] += 1
                stats['processed'] += 1
            except Exception as e:
                logger.error(f"Error processing clause {clause['id']}: {e}")
                stats['errors'].append({'clause_id': clause['id'], 'error': str(e)})

        if not dry_run:
            self.conn.commit()

        if dry_run:
            stats['preview'] = extracted_events

        return stats

    def _get_definition_clauses(self, carrier: Optional[str] = None) -> List[Dict]:
        """Get clauses with definitions from terms documents"""
        cur = self.conn.cursor(cursor_factory=RealDictCursor)

        query = """
            SELECT dc.id, dc.clause_title, dc.clause_text, d.document_id,
                   c.company_code, p.product_code
            FROM document_clause dc
            JOIN document d ON dc.document_id = d.id
            JOIN product p ON d.product_id = p.id
            JOIN company c ON p.company_id = c.id
            WHERE d.doc_type = 'terms'
              AND dc.clause_title LIKE '%정의%'
              AND (
                  dc.clause_title ~ '(암|뇌|심근|화상|골절|입원|치료)'
                  OR dc.clause_text ~ '(암|뇌출혈|뇌졸중|심근경색)'
              )
        """
        params = []

        if carrier:
            query += " AND c.company_code = %s"
            params.append(carrier)

        query += " ORDER BY dc.id"
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)

        return [dict(row) for row in cur.fetchall()]

    def _extract_risk_events(self, clause: Dict) -> List[Dict]:
        """Extract risk events from a single clause"""
        events = []
        title = clause['clause_title'] or ''
        text = clause['clause_text'] or ''
        combined = f"{title} {text}"

        # Determine event type from patterns
        detected_types = set()
        for event_type, config in RISK_EVENT_PATTERNS.items():
            # Check title patterns first
            for pattern in config.get('title_patterns', []):
                if re.search(pattern, title, re.IGNORECASE):
                    detected_types.add(event_type)
                    break

            # Check text patterns
            if event_type not in detected_types:
                for pattern in config['patterns']:
                    if re.search(pattern, combined):
                        detected_types.add(event_type)
                        break

        if not detected_types:
            return []

        # Extract ICD codes
        icd_codes = []
        for pattern, code_type in ICD_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                icd_codes.append(match)

        # Generate event name from title
        event_name = self._extract_event_name(title, text)
        if not event_name:
            return []

        # Create event for each detected type
        for event_type in detected_types:
            severity = RISK_EVENT_PATTERNS[event_type]['severity_default']
            icd_pattern = ', '.join(icd_codes[:5]) if icd_codes else None

            # Extract description (first 500 chars of definition)
            description = self._extract_description(text)

            event = {
                'event_type': event_type,
                'event_name': event_name,
                'severity_level': severity,
                'icd_code_pattern': icd_pattern,
                'description': description,
                'source_clause_id': clause['id'],
            }
            events.append(event)

        return events

    def _extract_event_name(self, title: str, text: str) -> Optional[str]:
        """Extract a clean event name from title"""
        if not title:
            return None

        # Remove common suffixes
        name = re.sub(r'의\s*정의.*$', '', title)
        name = re.sub(r'\s*정의.*$', '', name)
        name = re.sub(r'\(.*\)', '', name)
        name = name.strip()

        # Limit length
        if len(name) > 100:
            name = name[:100]

        return name if name else None

    def _extract_description(self, text: str) -> Optional[str]:
        """Extract description from clause text"""
        if not text:
            return None

        # Clean up text
        description = re.sub(r'\s+', ' ', text).strip()

        # Extract first meaningful paragraph
        # Look for definition pattern like "'xxx'이라 함은" or "xxx란"
        def_match = re.search(r"['「']([^'」']+)['」']\s*(이라\s*함은|란)\s*([^.]+\.)", description)
        if def_match:
            return f"'{def_match.group(1)}': {def_match.group(3)}"[:500]

        # Fallback: first 500 chars
        return description[:500] if len(description) > 500 else description

    def _insert_risk_event(self, event: Dict) -> str:
        """Insert risk event into database"""
        cur = self.conn.cursor()

        # Check for duplicate
        cur.execute("""
            SELECT id FROM risk_event
            WHERE event_type = %s AND event_name = %s
        """, (event['event_type'], event['event_name']))

        if cur.fetchone():
            return 'duplicate'

        # Insert
        cur.execute("""
            INSERT INTO risk_event (
                event_type, event_name, severity_level, icd_code_pattern, description
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            event['event_type'],
            event['event_name'],
            event['severity_level'],
            event['icd_code_pattern'],
            event['description']
        ))

        event_id = cur.fetchone()[0]
        logger.info(f"Created risk_event {event_id}: {event['event_name']}")
        return 'created'

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='Extract RiskEvent from terms documents')
    parser.add_argument('--carrier', type=str, help='Filter by carrier (e.g., lotte, samsung)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be extracted without inserting')

    args = parser.parse_args()

    db_url = os.getenv('POSTGRES_URL')
    if not db_url:
        print("Error: POSTGRES_URL environment variable not set")
        return

    extractor = RiskEventExtractor(db_url)

    try:
        result = extractor.extract_all(args.carrier, args.dry_run)

        if args.dry_run:
            print(f"\nDry run - would extract {len(result.get('preview', []))} risk events:\n")
            seen = set()
            for event in result.get('preview', []):
                key = (event['event_type'], event['event_name'])
                if key not in seen:
                    seen.add(key)
                    print(f"  [{event['event_type']}] {event['event_name']}")
                    if event.get('icd_code_pattern'):
                        print(f"    ICD: {event['icd_code_pattern']}")
            print(f"\nUnique events: {len(seen)}")
        else:
            print(f"\nExtraction complete:")
            print(f"  Processed: {result['processed']} clauses")
            print(f"  Events created: {result['events_created']}")
            print(f"  Duplicates skipped: {result['duplicates_skipped']}")
            if result['errors']:
                print(f"  Errors: {len(result['errors'])}")
    finally:
        extractor.close()


if __name__ == '__main__':
    main()
