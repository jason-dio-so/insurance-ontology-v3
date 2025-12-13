#!/usr/bin/env python3
"""
PostgreSQL 스키마에서 문서 자동 생성 스크립트

생성 문서:
- DATA_DICTIONARY.md: 테이블별 컬럼 정의
- RELATIONSHIP_MAP.md: 외래키 관계 맵

사용법:
    python generate_docs.py [--db-url DATABASE_URL] [--output-dir OUTPUT_DIR]
"""

import os
import argparse
from datetime import datetime
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor


def get_connection(db_url: str):
    """DB 연결 생성"""
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)


def get_tables(conn) -> list:
    """모든 테이블 목록 조회"""
    query = """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_type = 'BASE TABLE'
    ORDER BY table_name
    """
    with conn.cursor() as cur:
        cur.execute(query)
        return [row['table_name'] for row in cur.fetchall()]


def get_table_comment(conn, table_name: str) -> Optional[str]:
    """테이블 코멘트 조회"""
    query = """
    SELECT obj_description(c.oid) as comment
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relname = %s AND n.nspname = 'public'
    """
    with conn.cursor() as cur:
        cur.execute(query, (table_name,))
        row = cur.fetchone()
        return row['comment'] if row else None


def get_columns(conn, table_name: str) -> list:
    """테이블 컬럼 정보 조회"""
    query = """
    SELECT
        c.column_name,
        c.data_type,
        c.character_maximum_length,
        c.numeric_precision,
        c.numeric_scale,
        c.is_nullable,
        c.column_default,
        pgd.description as comment
    FROM information_schema.columns c
    LEFT JOIN pg_catalog.pg_statio_all_tables st
        ON c.table_schema = st.schemaname AND c.table_name = st.relname
    LEFT JOIN pg_catalog.pg_description pgd
        ON pgd.objoid = st.relid AND pgd.objsubid = c.ordinal_position
    WHERE c.table_schema = 'public' AND c.table_name = %s
    ORDER BY c.ordinal_position
    """
    with conn.cursor() as cur:
        cur.execute(query, (table_name,))
        return cur.fetchall()


def get_primary_keys(conn, table_name: str) -> list:
    """기본키 컬럼 조회"""
    query = """
    SELECT a.attname as column_name
    FROM pg_index i
    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
    JOIN pg_class c ON c.oid = i.indrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE i.indisprimary AND c.relname = %s AND n.nspname = 'public'
    """
    with conn.cursor() as cur:
        cur.execute(query, (table_name,))
        return [row['column_name'] for row in cur.fetchall()]


def get_foreign_keys(conn) -> list:
    """모든 외래키 관계 조회"""
    query = """
    SELECT
        tc.table_name as from_table,
        kcu.column_name as from_column,
        ccu.table_name as to_table,
        ccu.column_name as to_column,
        tc.constraint_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage ccu
        ON ccu.constraint_name = tc.constraint_name
        AND ccu.table_schema = tc.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_schema = 'public'
    ORDER BY tc.table_name, kcu.column_name
    """
    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


def get_indexes(conn, table_name: str) -> list:
    """테이블 인덱스 조회"""
    query = """
    SELECT
        i.relname as index_name,
        am.amname as index_type,
        array_agg(a.attname ORDER BY x.n) as columns,
        ix.indisunique as is_unique,
        ix.indisprimary as is_primary
    FROM pg_index ix
    JOIN pg_class i ON i.oid = ix.indexrelid
    JOIN pg_class t ON t.oid = ix.indrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    JOIN pg_am am ON am.oid = i.relam
    CROSS JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS x(attnum, n)
    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = x.attnum
    WHERE t.relname = %s AND n.nspname = 'public'
    GROUP BY i.relname, am.amname, ix.indisunique, ix.indisprimary
    ORDER BY i.relname
    """
    with conn.cursor() as cur:
        cur.execute(query, (table_name,))
        return cur.fetchall()


def format_data_type(col: dict) -> str:
    """데이터 타입 포맷팅"""
    dtype = col['data_type']

    if dtype == 'character varying':
        return f"varchar({col['character_maximum_length']})"
    elif dtype == 'numeric':
        return f"numeric({col['numeric_precision']},{col['numeric_scale']})"
    elif dtype == 'USER-DEFINED':
        return 'vector'
    else:
        return dtype


def generate_data_dictionary(conn, output_dir: str):
    """DATA_DICTIONARY.md 생성"""
    tables = get_tables(conn)

    lines = [
        "# 데이터 사전 (Data Dictionary)",
        "",
        f"> 자동 생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 목차",
        "",
    ]

    # 목차 생성
    for table in tables:
        comment = get_table_comment(conn, table) or ''
        lines.append(f"- [{table}](#{table}) - {comment}")

    lines.append("")
    lines.append("---")
    lines.append("")

    # 각 테이블 상세
    for table in tables:
        comment = get_table_comment(conn, table)
        pks = get_primary_keys(conn, table)
        columns = get_columns(conn, table)
        indexes = get_indexes(conn, table)

        lines.append(f"## {table}")
        lines.append("")
        if comment:
            lines.append(f"**설명**: {comment}")
            lines.append("")

        # 컬럼 테이블
        lines.append("### 컬럼")
        lines.append("")
        lines.append("| 컬럼명 | 타입 | NULL | 기본값 | 설명 |")
        lines.append("|--------|------|------|--------|------|")

        for col in columns:
            pk_mark = " 🔑" if col['column_name'] in pks else ""
            nullable = "N" if col['is_nullable'] == 'NO' else "Y"
            default = col['column_default'] or '-'
            if len(default) > 30:
                default = default[:27] + '...'
            col_comment = col['comment'] or '-'
            dtype = format_data_type(col)

            lines.append(f"| {col['column_name']}{pk_mark} | {dtype} | {nullable} | {default} | {col_comment} |")

        lines.append("")

        # 인덱스
        if indexes:
            lines.append("### 인덱스")
            lines.append("")
            lines.append("| 인덱스명 | 타입 | 컬럼 | 유니크 |")
            lines.append("|----------|------|------|--------|")
            for idx in indexes:
                if idx['is_primary']:
                    continue
                unique = "Y" if idx['is_unique'] else "N"
                cols = ', '.join(idx['columns'])
                lines.append(f"| {idx['index_name']} | {idx['index_type']} | {cols} | {unique} |")
            lines.append("")

        lines.append("---")
        lines.append("")

    # 파일 저장
    output_path = os.path.join(output_dir, "DATA_DICTIONARY.md")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"✅ 생성됨: {output_path}")
    return output_path


def generate_relationship_map(conn, output_dir: str):
    """RELATIONSHIP_MAP.md 생성"""
    fks = get_foreign_keys(conn)
    tables = get_tables(conn)

    lines = [
        "# 테이블 관계 맵 (Relationship Map)",
        "",
        f"> 자동 생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 외래키 관계 목록",
        "",
        "| From 테이블 | From 컬럼 | → | To 테이블 | To 컬럼 |",
        "|-------------|-----------|---|-----------|---------|",
    ]

    for fk in fks:
        lines.append(f"| {fk['from_table']} | {fk['from_column']} | → | {fk['to_table']} | {fk['to_column']} |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # 테이블별 관계 요약
    lines.append("## 테이블별 관계 요약")
    lines.append("")

    for table in tables:
        # 이 테이블이 참조하는 테이블
        refs_to = [fk for fk in fks if fk['from_table'] == table]
        # 이 테이블을 참조하는 테이블
        refs_from = [fk for fk in fks if fk['to_table'] == table]

        if refs_to or refs_from:
            comment = get_table_comment(conn, table) or ''
            lines.append(f"### {table}")
            if comment:
                lines.append(f"_{comment}_")
            lines.append("")

            if refs_to:
                lines.append("**참조하는 테이블:**")
                for fk in refs_to:
                    lines.append(f"- `{fk['from_column']}` → `{fk['to_table']}.{fk['to_column']}`")
                lines.append("")

            if refs_from:
                lines.append("**참조되는 테이블:**")
                for fk in refs_from:
                    lines.append(f"- `{fk['from_table']}.{fk['from_column']}` → `{fk['to_column']}`")
                lines.append("")

    # Mermaid 다이어그램
    lines.append("---")
    lines.append("")
    lines.append("## ER 다이어그램 (Mermaid)")
    lines.append("")
    lines.append("```mermaid")
    lines.append("erDiagram")

    for fk in fks:
        lines.append(f"    {fk['to_table']} ||--o{{ {fk['from_table']} : \"{fk['from_column']}\"")

    lines.append("```")
    lines.append("")

    # 파일 저장
    output_path = os.path.join(output_dir, "RELATIONSHIP_MAP.md")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"✅ 생성됨: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description='PostgreSQL 스키마 문서 자동 생성')
    parser.add_argument('--db-url',
                        default=os.environ.get('DATABASE_URL',
                                               'postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology'),
                        help='PostgreSQL 연결 URL')
    parser.add_argument('--output-dir',
                        default=os.path.join(os.path.dirname(__file__), '..', 'docs'),
                        help='출력 디렉토리')

    args = parser.parse_args()

    # 출력 디렉토리 생성
    os.makedirs(args.output_dir, exist_ok=True)

    print(f"📊 DB 연결: {args.db_url.split('@')[1] if '@' in args.db_url else args.db_url}")
    print(f"📁 출력 경로: {args.output_dir}")
    print()

    try:
        conn = get_connection(args.db_url)

        generate_data_dictionary(conn, args.output_dir)
        generate_relationship_map(conn, args.output_dir)

        conn.close()
        print()
        print("✅ 문서 생성 완료!")

    except Exception as e:
        print(f"❌ 오류: {e}")
        raise


if __name__ == '__main__':
    main()
