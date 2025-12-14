#!/usr/bin/env python3
"""
Coverage Metadata Updater
=========================

coverage 테이블에 추가 메타데이터를 설정하는 스크립트

[실행 시점]
  coverage_pipeline.py 실행 후 1회 실행

[하는 일]
  1. group_id     : coverage를 회사별 카테고리 그룹에 연결 (100%)
  2. standard_code: 신정원 표준 담보코드 매핑 (67%)
  3. parent_coverage_id: 담보 간 부모-자식 관계 설정 (13%)
                         예) 유사암진단비 → 암진단비

[사용법]
  python scripts/update_coverage_metadata.py

[데이터 소스]
  - examples/examples/담보명mapping자료.xlsx (신정원 표준코드)
"""

import os
import argparse
import logging
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Parent-child relationships based on standard code patterns
PARENT_CODE_MAP = {
    'A4209': 'A4200_1',    # 고액암 → 암진단비
    'A4210': 'A4200_1',    # 유사암 → 암진단비
    'A4299': 'A4200_1',    # 재진단암 → 암진단비
    'A4102': 'A4101',      # 뇌출혈 → 뇌혈관질환
    'A4103': 'A4101',      # 뇌졸중 → 뇌혈관질환
    'A5104': 'A5100',      # 뇌혈관수술 → 질병수술
    'A5107': 'A5100',      # 허혈성심장수술 → 질병수술
    'A5200': 'A5100',      # 암수술 → 질병수술
    'A5298': 'A5200',      # 유사암수술 → 암수술
}


def get_db_connection():
    """Get database connection from environment variables"""
    return psycopg2.connect(
        host=os.environ.get('POSTGRES_HOST', '127.0.0.1'),
        port=os.environ.get('POSTGRES_PORT', '15432'),
        database=os.environ.get('POSTGRES_DB', 'insurance_ontology_test'),
        user=os.environ.get('POSTGRES_USER', 'postgres'),
        password=os.environ.get('POSTGRES_PASSWORD', 'postgres')
    )


def update_coverage_groups(conn):
    """
    Create coverage_group entries and link coverages to them.
    Groups are created based on (company_id, coverage_category) combinations.
    """
    cur = conn.cursor()

    # 1. Create coverage_group entries
    cur.execute("""
        INSERT INTO coverage_group (company_id, category_id, group_code, group_name_kr)
        SELECT DISTINCT
            p.company_id,
            cat.id as category_id,
            cat.category_code as group_code,
            cat.category_name_kr as group_name_kr
        FROM coverage c
        JOIN product p ON c.product_id = p.id
        JOIN coverage_category cat ON cat.category_code = c.coverage_category
        ON CONFLICT (company_id, group_code, version) DO NOTHING
    """)
    groups_created = cur.rowcount

    # 2. Update coverage.group_id
    cur.execute("""
        UPDATE coverage c
        SET group_id = cg.id
        FROM product p, coverage_group cg
        WHERE c.product_id = p.id
          AND cg.company_id = p.company_id
          AND cg.group_code = c.coverage_category
          AND c.group_id IS NULL
    """)
    coverages_linked = cur.rowcount

    conn.commit()

    # Get stats
    cur.execute("SELECT COUNT(*) FROM coverage_group")
    total_groups = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM coverage WHERE group_id IS NOT NULL")
    with_group = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM coverage")
    total = cur.fetchone()[0]

    cur.close()

    logger.info(f"Coverage groups: {total_groups} total ({groups_created} new)")
    logger.info(f"group_id: {with_group}/{total} ({100*with_group//total}%)")

    return coverages_linked


def update_standard_codes(conn, mapping_file: Path):
    """
    Update coverage.standard_code from mapping Excel file.
    """
    if not mapping_file.exists():
        logger.warning(f"Mapping file not found: {mapping_file}")
        return 0

    # Ensure standard_code column exists
    cur = conn.cursor()
    cur.execute("""
        ALTER TABLE coverage ADD COLUMN IF NOT EXISTS standard_code VARCHAR(20)
    """)
    conn.commit()

    # Load mapping
    df = pd.read_excel(mapping_file)
    logger.info(f"Loaded {len(df)} mappings from {mapping_file.name}")

    # Get coverages from DB
    cur.execute("""
        SELECT c.id, c.coverage_name, comp.company_name
        FROM coverage c
        JOIN product p ON c.product_id = p.id
        JOIN company comp ON p.company_id = comp.id
        WHERE c.standard_code IS NULL
    """)
    db_coverages = cur.fetchall()

    # Build update list
    updates = []
    for cov_id, cov_name, company in db_coverages:
        # Exact match first
        match = df[(df['보험사명'] == company) & (df['담보명(가입설계서)'] == cov_name)]
        if len(match) == 0:
            # Partial match (first 8 chars)
            match = df[(df['보험사명'] == company) & (df['담보명(가입설계서)'].str[:8] == cov_name[:8])]
        if len(match) > 0:
            code = match.iloc[0]['cre_cvr_cd']
            updates.append((code, cov_id))

    # Update standard_code
    execute_batch(cur, "UPDATE coverage SET standard_code = %s WHERE id = %s", updates)
    conn.commit()

    # Get stats
    cur.execute("SELECT COUNT(*) FROM coverage WHERE standard_code IS NOT NULL")
    with_code = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM coverage")
    total = cur.fetchone()[0]

    cur.close()

    logger.info(f"standard_code: {with_code}/{total} ({100*with_code//total}%)")

    return len(updates)


def update_parent_coverage_ids(conn):
    """
    Set parent_coverage_id based on standard code hierarchy.
    """
    cur = conn.cursor()

    updated = 0
    for child_prefix, parent_code in PARENT_CODE_MAP.items():
        cur.execute("""
            UPDATE coverage c
            SET parent_coverage_id = parent.id
            FROM coverage parent
            WHERE c.standard_code LIKE %s
              AND parent.standard_code = %s
              AND c.product_id = parent.product_id
              AND c.id != parent.id
              AND c.parent_coverage_id IS NULL
        """, (child_prefix + '%', parent_code))
        updated += cur.rowcount

    conn.commit()

    # Get stats
    cur.execute("SELECT COUNT(*) FROM coverage WHERE parent_coverage_id IS NOT NULL")
    with_parent = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM coverage")
    total = cur.fetchone()[0]

    cur.close()

    logger.info(f"parent_coverage_id: {with_parent}/{total} ({100*with_parent//total}%)")

    return updated


def main():
    parser = argparse.ArgumentParser(description='Update coverage metadata')
    parser.add_argument('--skip-groups', action='store_true', help='Skip group_id update')
    parser.add_argument('--skip-codes', action='store_true', help='Skip standard_code update')
    parser.add_argument('--skip-parents', action='store_true', help='Skip parent_coverage_id update')
    parser.add_argument('--mapping-file', type=Path,
                        default=Path('examples/examples/담보명mapping자료.xlsx'),
                        help='Path to coverage mapping Excel file')
    args = parser.parse_args()

    logger.info("Starting coverage metadata update...")

    conn = get_db_connection()

    try:
        # 1. Update group_id
        if not args.skip_groups:
            logger.info("\n=== Updating group_id ===")
            update_coverage_groups(conn)

        # 2. Update standard_code
        if not args.skip_codes:
            logger.info("\n=== Updating standard_code ===")
            update_standard_codes(conn, args.mapping_file)

        # 3. Update parent_coverage_id
        if not args.skip_parents:
            logger.info("\n=== Updating parent_coverage_id ===")
            update_parent_coverage_ids(conn)

        logger.info("\n✅ Coverage metadata update complete!")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
