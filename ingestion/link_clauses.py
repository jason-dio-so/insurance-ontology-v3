"""
Clause-Coverage Linking Pipeline

Purpose: Map document clauses to coverage entities
Strategy:
  Tier 1 (Exact Match): Match table_row clauses with structured_data.coverage_name
  Tier 2 (Fuzzy Match): Use string similarity for article/text_block
  Tier 3 (LLM): Use LLM for ambiguous cases

Design: Phase 2.3 of TODO.md
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Tuple, Optional
import logging
import argparse
from fuzzywuzzy import fuzz
import unicodedata
import requests
import json
import re
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClauseCoverageLinker:
    """Link document clauses to coverage entities"""

    def __init__(self, db_url: str, ollama_url: str = "http://localhost:11434", llm_provider: str = "ollama"):
        self.db_url = db_url
        self.ollama_url = ollama_url
        self.llm_provider = llm_provider  # "ollama" or "openai"

    def normalize_text(self, text: str) -> str:
        """Normalize text for comparison (NFC + strip)"""
        if not text:
            return ""
        return unicodedata.normalize('NFC', text).strip()

    def tier1_exact_match(self) -> Dict:
        """
        Tier 1: Exact match for table_row clauses with structured_data.coverage_name

        Returns:
            Summary dictionary
        """
        conn = psycopg2.connect(self.db_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get table_row clauses with coverage_name
        cur.execute("""
            SELECT
                dc.id as clause_id,
                dc.structured_data->>'coverage_name' as coverage_name,
                d.product_id
            FROM document_clause dc
            JOIN document d ON dc.document_id = d.id
            WHERE dc.clause_type = 'table_row'
              AND dc.structured_data IS NOT NULL
              AND dc.structured_data->>'coverage_name' IS NOT NULL
        """)

        clauses = cur.fetchall()
        logger.info(f"Found {len(clauses)} table_row clauses with coverage_name")

        matched = 0
        skipped = 0

        for clause in clauses:
            clause_id = clause['clause_id']
            coverage_name = self.normalize_text(clause['coverage_name'])
            product_id = clause['product_id']

            # Find matching coverage
            cur.execute("""
                SELECT id
                FROM coverage
                WHERE product_id = %s
                  AND coverage_name = %s
                LIMIT 1
            """, (product_id, coverage_name))

            coverage_row = cur.fetchone()

            if coverage_row:
                coverage_id = coverage_row['id']

                # Insert into clause_coverage
                try:
                    cur.execute("""
                        INSERT INTO clause_coverage (clause_id, coverage_id, relevance_score, extraction_method)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (clause_id, coverage_id) DO NOTHING
                    """, (clause_id, coverage_id, 1.0, 'exact_match'))

                    if cur.rowcount > 0:
                        matched += 1
                except Exception as e:
                    logger.error(f"Failed to insert mapping for clause {clause_id}: {e}")
                    continue
            else:
                skipped += 1
                logger.debug(f"No coverage found for: {coverage_name} (product_id={product_id})")

        conn.commit()
        cur.close()
        conn.close()

        summary = {
            'total_clauses': len(clauses),
            'matched': matched,
            'skipped': skipped,
        }

        logger.info(f"Tier 1 Exact Match: {matched}/{len(clauses)} matched ({skipped} skipped)")
        return summary

    def tier2_fuzzy_match(self, threshold: int = 80) -> Dict:
        """
        Tier 2: Fuzzy match for unmapped clauses

        Args:
            threshold: Minimum similarity score (0-100)

        Returns:
            Summary dictionary
        """
        conn = psycopg2.connect(self.db_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get unmapped article/text_block clauses
        cur.execute("""
            SELECT
                dc.id as clause_id,
                dc.clause_title,
                dc.clause_text,
                d.product_id
            FROM document_clause dc
            JOIN document d ON dc.document_id = d.id
            LEFT JOIN clause_coverage cc ON dc.id = cc.clause_id
            WHERE dc.clause_type IN ('article', 'text_block')
              AND cc.id IS NULL
              AND (dc.clause_title IS NOT NULL OR dc.clause_text IS NOT NULL)
            LIMIT 1000
        """)

        clauses = cur.fetchall()
        logger.info(f"Found {len(clauses)} unmapped article/text_block clauses")

        matched = 0

        for clause in clauses:
            clause_id = clause['clause_id']
            clause_title = self.normalize_text(clause['clause_title'] or '')
            clause_text = self.normalize_text(clause['clause_text'] or '')
            product_id = clause['product_id']

            # Search text: title + first 200 chars of text
            search_text = (clause_title + ' ' + clause_text[:200]).strip()

            if not search_text:
                continue

            # Get all coverages for this product
            cur.execute("""
                SELECT id, coverage_name
                FROM coverage
                WHERE product_id = %s
            """, (product_id,))

            coverages = cur.fetchall()

            best_match = None
            best_score = 0

            for cov in coverages:
                coverage_name = self.normalize_text(cov['coverage_name'])

                # Calculate fuzzy similarity
                score = fuzz.partial_ratio(search_text, coverage_name)

                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = cov['id']

            if best_match:
                try:
                    cur.execute("""
                        INSERT INTO clause_coverage (clause_id, coverage_id, relevance_score, extraction_method)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (clause_id, coverage_id) DO NOTHING
                    """, (clause_id, best_match, best_score / 100.0, 'fuzzy_match'))

                    if cur.rowcount > 0:
                        matched += 1
                except Exception as e:
                    logger.error(f"Failed to insert fuzzy mapping for clause {clause_id}: {e}")
                    continue

        conn.commit()
        cur.close()
        conn.close()

        summary = {
            'total_clauses': len(clauses),
            'matched': matched,
        }

        logger.info(f"Tier 2 Fuzzy Match: {matched}/{len(clauses)} matched")
        return summary

    def call_llm(self, prompt: str, model: str = "gpt-4o-mini") -> Optional[str]:
        """
        Call LLM API (Ollama or OpenAI)

        Args:
            prompt: Prompt text
            model: Model name

        Returns:
            Response text or None
        """
        if self.llm_provider == "openai":
            try:
                import openai

                client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "당신은 보험 약관 분석 전문가입니다."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=500
                )

                return response.choices[0].message.content.strip()

            except Exception as e:
                logger.error(f"Failed to call OpenAI: {e}")
                return None

        else:  # ollama
            try:
                response = requests.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "top_p": 0.9,
                        }
                    },
                    timeout=300
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get('response', '').strip()
                else:
                    logger.error(f"Ollama API error: {response.status_code}")
                    return None

            except Exception as e:
                logger.error(f"Failed to call Ollama: {e}")
                return None

    def tier3_llm_match(self, limit: int = 100, min_confidence: float = 0.6) -> Dict:
        """
        Tier 3: LLM-based matching for unmapped clauses

        Args:
            limit: Maximum number of clauses to process
            min_confidence: Minimum confidence score (0.0-1.0)

        Returns:
            Summary dictionary
        """
        conn = psycopg2.connect(self.db_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get unmapped clauses with coverage-related keywords
        cur.execute("""
            SELECT
                dc.id as clause_id,
                dc.clause_title,
                dc.clause_text,
                d.product_id
            FROM document_clause dc
            JOIN document d ON dc.document_id = d.id
            LEFT JOIN clause_coverage cc ON dc.id = cc.clause_id
            WHERE dc.clause_type IN ('article', 'text_block')
              AND cc.id IS NULL
              AND (
                  dc.clause_text LIKE '%%보험금%%'
                  OR dc.clause_text LIKE '%%담보%%'
                  OR dc.clause_text LIKE '%%보장%%'
                  OR dc.clause_text LIKE '%%진단%%'
                  OR dc.clause_text LIKE '%%수술%%'
                  OR dc.clause_text LIKE '%%입원%%'
                  OR dc.clause_text LIKE '%%치료%%'
                  OR dc.clause_title LIKE '%%보험금%%'
                  OR dc.clause_title LIKE '%%담보%%'
              )
            LIMIT %s
        """, (limit,))

        clauses = cur.fetchall()
        logger.info(f"Found {len(clauses)} unmapped coverage-related clauses for LLM processing")

        matched = 0
        skipped = 0

        for idx, clause in enumerate(clauses):
            if (idx + 1) % 10 == 0:
                logger.info(f"Processing {idx + 1}/{len(clauses)}...")

            clause_id = clause['clause_id']
            clause_title = self.normalize_text(clause['clause_title'] or '')
            clause_text = self.normalize_text(clause['clause_text'] or '')
            product_id = clause['product_id']

            # Get all coverages for this product
            cur.execute("""
                SELECT id, coverage_name
                FROM coverage
                WHERE product_id = %s
            """, (product_id,))

            coverages = cur.fetchall()

            if not coverages:
                skipped += 1
                continue

            # Prepare coverage options
            coverage_list = "\n".join([f"{i+1}. {cov['coverage_name']}" for i, cov in enumerate(coverages)])

            # Prepare prompt
            prompt = f"""다음 보험 약관 조항이 어떤 담보(coverage)와 관련이 있는지 판단해주세요.

조항 제목: {clause_title}
조항 내용: {clause_text[:500]}

가능한 담보 목록:
{coverage_list}

지시사항:
1. 위 조항이 가장 관련 있는 담보의 번호를 선택하세요.
2. 관련 없으면 "NONE"을 반환하세요.
3. 신뢰도를 0.0~1.0 사이로 평가하세요.

응답 형식 (반드시 이 형식을 따르세요):
ANSWER: <번호 또는 NONE>
CONFIDENCE: <0.0-1.0>
"""

            # Call LLM
            llm_response = self.call_llm(prompt)

            if not llm_response:
                skipped += 1
                continue

            # Parse response
            answer_match = re.search(r'ANSWER:\s*(\d+|NONE)', llm_response, re.IGNORECASE)
            confidence_match = re.search(r'CONFIDENCE:\s*(0?\.\d+|1\.0?)', llm_response)

            if not answer_match or not confidence_match:
                logger.warning(f"Failed to parse LLM response: {llm_response[:200]}")
                skipped += 1
                continue

            answer = answer_match.group(1)
            confidence = float(confidence_match.group(1))

            if answer.upper() == 'NONE' or confidence < min_confidence:
                skipped += 1
                continue

            try:
                coverage_idx = int(answer) - 1
                if 0 <= coverage_idx < len(coverages):
                    coverage_id = coverages[coverage_idx]['id']

                    # Insert mapping
                    cur.execute("""
                        INSERT INTO clause_coverage (clause_id, coverage_id, relevance_score, extraction_method)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (clause_id, coverage_id) DO NOTHING
                    """, (clause_id, coverage_id, confidence, 'llm'))

                    if cur.rowcount > 0:
                        matched += 1
                        logger.debug(f"LLM matched clause {clause_id} to coverage {coverages[coverage_idx]['coverage_name']} (confidence: {confidence:.2f})")
                else:
                    skipped += 1

            except (ValueError, IndexError) as e:
                logger.error(f"Invalid answer from LLM: {answer}")
                skipped += 1
                continue

        conn.commit()
        cur.close()
        conn.close()

        summary = {
            'total_clauses': len(clauses),
            'matched': matched,
            'skipped': skipped,
        }

        logger.info(f"Tier 3 LLM Match: {matched}/{len(clauses)} matched ({skipped} skipped)")
        return summary

    def get_mapping_stats(self) -> Dict:
        """Get mapping statistics"""
        conn = psycopg2.connect(self.db_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT
                extraction_method,
                COUNT(*) as count,
                AVG(relevance_score) as avg_score
            FROM clause_coverage
            GROUP BY extraction_method
            ORDER BY extraction_method
        """)

        stats = cur.fetchall()

        cur.execute("SELECT COUNT(*) as total FROM clause_coverage")
        total = cur.fetchone()['total']

        cur.close()
        conn.close()

        return {
            'total': total,
            'by_method': [dict(s) for s in stats]
        }


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Link document clauses to coverages')
    parser.add_argument('--method', default='exact',
                        help='Matching method: exact, fuzzy, llm, all')
    parser.add_argument('--threshold', type=int, default=80,
                        help='Fuzzy match threshold (0-100)')
    parser.add_argument('--limit', type=int, default=100,
                        help='LLM processing limit (default: 100)')
    parser.add_argument('--min-confidence', type=float, default=0.6,
                        help='Minimum LLM confidence (0.0-1.0, default: 0.6)')
    parser.add_argument('--llm-provider', default='ollama',
                        help='LLM provider: ollama or openai (default: ollama)')

    args = parser.parse_args()

    db_url = os.getenv('POSTGRES_URL')
    if not db_url:
        raise ValueError("POSTGRES_URL environment variable is required. Check .env file.")

    linker = ClauseCoverageLinker(db_url, llm_provider=args.llm_provider)

    if args.method == 'exact' or args.method == 'all':
        logger.info("Running Tier 1: Exact Match...")
        summary = linker.tier1_exact_match()
        print(f"\n✅ Tier 1 Exact Match Complete:")
        print(f"   Total clauses: {summary['total_clauses']}")
        print(f"   Matched: {summary['matched']}")
        print(f"   Skipped: {summary['skipped']}")

    if args.method == 'fuzzy' or args.method == 'all':
        logger.info("Running Tier 2: Fuzzy Match...")
        summary = linker.tier2_fuzzy_match(threshold=args.threshold)
        print(f"\n✅ Tier 2 Fuzzy Match Complete:")
        print(f"   Total clauses: {summary['total_clauses']}")
        print(f"   Matched: {summary['matched']}")

    if args.method == 'llm' or args.method == 'all':
        logger.info("Running Tier 3: LLM Match...")
        summary = linker.tier3_llm_match(limit=args.limit, min_confidence=args.min_confidence)
        print(f"\n✅ Tier 3 LLM Match Complete:")
        print(f"   Total clauses: {summary['total_clauses']}")
        print(f"   Matched: {summary['matched']}")
        print(f"   Skipped: {summary['skipped']}")

    # Show final stats
    stats = linker.get_mapping_stats()
    print(f"\n📊 Mapping Statistics:")
    print(f"   Total mappings: {stats['total']}")
    print(f"\n   By method:")
    for method_stat in stats['by_method']:
        print(f"     - {method_stat['extraction_method']}: {method_stat['count']} "
              f"(avg score: {method_stat['avg_score']:.2f})")


if __name__ == '__main__':
    main()
