#!/usr/bin/env python3
"""
PostgreSQL 스키마 검증 스크립트

현재 DB 스키마가 정의된 스키마와 일치하는지 검증합니다.

사용법:
    python verify_schema.py
    python verify_schema.py --verbose
    python verify_schema.py --json
"""

import os
import sys
import json
import argparse
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

import psycopg2
from psycopg2.extras import RealDictCursor


# 기대하는 테이블 목록 (실제 스키마 기준)
EXPECTED_TABLES = {
    "company": ["id", "company_code", "company_name", "business_type", "created_at", "updated_at"],
    "product": ["id", "company_id", "product_code", "product_name", "business_type", "version", "effective_date", "created_at", "updated_at"],
    "product_variant": ["id", "product_id", "variant_name", "variant_code", "target_gender", "target_age_range", "min_age", "max_age", "attributes", "created_at", "updated_at"],
    "coverage_category": ["id", "category_code", "category_name_kr", "category_name_en", "description", "display_order", "created_at", "updated_at"],
    "coverage": ["id", "product_id", "group_id", "coverage_code", "coverage_name", "coverage_category", "renewal_type", "is_basic", "created_at", "updated_at", "parent_coverage_id", "notes"],
    "coverage_group": ["id", "company_id", "category_id", "group_number", "group_code", "group_name_kr", "group_name_en", "is_renewable", "version", "page_number", "description", "created_at", "updated_at"],
    "benefit": ["id", "coverage_id", "benefit_name", "benefit_type", "benefit_amount_text", "benefit_amount", "payment_frequency", "description", "created_at", "updated_at"],
    "document": ["id", "document_id", "company_id", "product_id", "variant_id", "doc_type", "doc_subtype", "version", "file_path", "total_pages", "attributes", "created_at", "updated_at"],
    "document_clause": ["id", "document_id", "clause_number", "clause_title", "clause_text", "clause_type", "structured_data", "section_type", "page_number", "hierarchy_level", "parent_clause_id", "attributes", "created_at", "updated_at"],
    "clause_coverage": ["id", "clause_id", "coverage_id", "relevance_score", "extraction_method", "created_at"],
    "clause_embedding": ["id", "clause_id", "embedding", "model_name", "metadata", "created_at"],
    "disease_code_set": ["id", "set_name", "description", "version", "created_at", "updated_at"],
    "disease_code": ["id", "code_set_id", "code", "code_type", "description_kr", "description_en", "created_at"],
    "condition": ["id", "coverage_id", "condition_type", "condition_text", "min_age", "max_age", "waiting_period_days", "attributes", "created_at", "updated_at"],
    "exclusion": ["id", "coverage_id", "exclusion_type", "exclusion_text", "is_absolute", "attributes", "created_at", "updated_at"],
    "risk_event": ["id", "event_type", "event_name", "severity_level", "icd_code_pattern", "description", "created_at", "updated_at"],
    "benefit_risk_event": ["id", "benefit_id", "risk_event_id", "created_at"],
    "plan": ["id", "document_id", "product_id", "variant_id", "plan_name", "target_gender", "target_age", "insurance_period", "payment_period", "payment_cycle", "total_premium", "attributes", "created_at", "updated_at"],
    "plan_coverage": ["id", "plan_id", "coverage_id", "sum_insured", "sum_insured_text", "premium", "is_basic", "created_at"],
}

# 기대하는 인덱스 (주요 인덱스만)
EXPECTED_INDEXES = [
    "company_pkey",
    "product_pkey",
    "coverage_pkey",
    "benefit_pkey",
    "document_pkey",
    "document_clause_pkey",
    "ix_document_clause_document_id",
    "ix_coverage_product_id",
    "ix_benefit_coverage_id",
]

# 기대하는 확장
EXPECTED_EXTENSIONS = ["vector"]


def get_connection():
    """PostgreSQL 연결 생성"""
    database_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not database_url:
        raise ValueError("DATABASE_URL 또는 POSTGRES_URL 환경변수가 설정되지 않았습니다")
    return psycopg2.connect(database_url)


def get_tables(conn) -> dict:
    """현재 DB의 테이블 목록 조회"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        return {row["table_name"] for row in cur.fetchall()}


def get_columns(conn, table_name: str) -> list:
    """테이블의 컬럼 목록 조회"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        return [row["column_name"] for row in cur.fetchall()]


def get_indexes(conn) -> set:
    """현재 DB의 인덱스 목록 조회"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY indexname
        """)
        return {row["indexname"] for row in cur.fetchall()}


def get_extensions(conn) -> set:
    """설치된 확장 목록 조회"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT extname FROM pg_extension")
        return {row["extname"] for row in cur.fetchall()}


def get_row_counts(conn) -> dict:
    """각 테이블의 행 수 조회"""
    tables = get_tables(conn)
    counts = {}
    with conn.cursor() as cur:
        for table in tables:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            counts[table] = cur.fetchone()[0]
    return counts


def verify_schema(verbose: bool = False) -> dict:
    """스키마 검증 실행"""
    results = {
        "status": "PASS",
        "tables": {"status": "PASS", "expected": len(EXPECTED_TABLES), "actual": 0, "missing": [], "extra": []},
        "columns": {"status": "PASS", "issues": []},
        "indexes": {"status": "PASS", "expected": len(EXPECTED_INDEXES), "actual": 0, "missing": []},
        "extensions": {"status": "PASS", "expected": EXPECTED_EXTENSIONS, "missing": []},
        "row_counts": {},
    }

    try:
        conn = get_connection()
    except Exception as e:
        results["status"] = "FAIL"
        results["error"] = str(e)
        return results

    try:
        # 1. 테이블 검증
        actual_tables = get_tables(conn)
        results["tables"]["actual"] = len(actual_tables)

        expected_table_names = set(EXPECTED_TABLES.keys())
        results["tables"]["missing"] = list(expected_table_names - actual_tables)
        results["tables"]["extra"] = list(actual_tables - expected_table_names)

        if results["tables"]["missing"]:
            results["tables"]["status"] = "FAIL"
            results["status"] = "FAIL"

        # 2. 컬럼 검증
        for table_name, expected_columns in EXPECTED_TABLES.items():
            if table_name in actual_tables:
                actual_columns = get_columns(conn, table_name)
                missing_cols = set(expected_columns) - set(actual_columns)
                if missing_cols:
                    results["columns"]["issues"].append({
                        "table": table_name,
                        "missing_columns": list(missing_cols)
                    })
                    results["columns"]["status"] = "WARN"

        if results["columns"]["status"] == "WARN":
            if results["status"] == "PASS":
                results["status"] = "WARN"

        # 3. 인덱스 검증
        actual_indexes = get_indexes(conn)
        results["indexes"]["actual"] = len(actual_indexes)
        results["indexes"]["missing"] = [idx for idx in EXPECTED_INDEXES if idx not in actual_indexes]

        if results["indexes"]["missing"]:
            results["indexes"]["status"] = "WARN"
            if results["status"] == "PASS":
                results["status"] = "WARN"

        # 4. 확장 검증
        actual_extensions = get_extensions(conn)
        results["extensions"]["missing"] = [ext for ext in EXPECTED_EXTENSIONS if ext not in actual_extensions]

        if results["extensions"]["missing"]:
            results["extensions"]["status"] = "FAIL"
            results["status"] = "FAIL"

        # 5. 행 수 조회
        results["row_counts"] = get_row_counts(conn)

    finally:
        conn.close()

    return results


def print_results(results: dict, verbose: bool = False):
    """결과 출력"""
    status_colors = {
        "PASS": "\033[92m",  # Green
        "WARN": "\033[93m",  # Yellow
        "FAIL": "\033[91m",  # Red
    }
    reset = "\033[0m"

    print("=" * 60)
    print("PostgreSQL 스키마 검증 결과")
    print("=" * 60)
    print()

    # 전체 상태
    status = results["status"]
    color = status_colors.get(status, "")
    print(f"전체 상태: {color}{status}{reset}")
    print()

    # 테이블 검증
    t = results["tables"]
    color = status_colors.get(t["status"], "")
    print(f"[테이블] {color}{t['status']}{reset} - 기대: {t['expected']}, 실제: {t['actual']}")
    if t["missing"]:
        print(f"  - 누락된 테이블: {', '.join(t['missing'])}")
    if t["extra"] and verbose:
        print(f"  - 추가된 테이블: {', '.join(t['extra'])}")

    # 컬럼 검증
    c = results["columns"]
    color = status_colors.get(c["status"], "")
    print(f"[컬럼] {color}{c['status']}{reset}")
    if c["issues"]:
        for issue in c["issues"]:
            print(f"  - {issue['table']}: 누락된 컬럼 {issue['missing_columns']}")

    # 인덱스 검증
    i = results["indexes"]
    color = status_colors.get(i["status"], "")
    print(f"[인덱스] {color}{i['status']}{reset} - 기대: {i['expected']}, 실제: {i['actual']}")
    if i["missing"] and verbose:
        print(f"  - 누락된 인덱스: {', '.join(i['missing'])}")

    # 확장 검증
    e = results["extensions"]
    color = status_colors.get(e["status"], "")
    print(f"[확장] {color}{e['status']}{reset}")
    if e["missing"]:
        print(f"  - 누락된 확장: {', '.join(e['missing'])}")

    # 행 수
    print()
    print("테이블별 행 수:")
    for table, count in sorted(results["row_counts"].items()):
        print(f"  {table}: {count:,}")

    print()
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="PostgreSQL 스키마 검증")
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 출력")
    parser.add_argument("--json", action="store_true", help="JSON 형식 출력")
    args = parser.parse_args()

    results = verify_schema(verbose=args.verbose)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print_results(results, verbose=args.verbose)

    # 종료 코드
    if results["status"] == "FAIL":
        sys.exit(1)
    elif results["status"] == "WARN":
        sys.exit(0)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
