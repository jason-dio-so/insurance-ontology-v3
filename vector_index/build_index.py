#!/usr/bin/env python3
"""
벡터 인덱스 빌드 스크립트

PostgreSQL의 document_clause 테이블에서 조항을 읽어
임베딩을 생성하고 clause_embedding 테이블에 저장합니다.

Usage:
    python vector_index/build_index.py [--backend jina|openai] [--batch-size 100]
"""

import os
import sys
import argparse
import psycopg2
from typing import List, Tuple
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 상대 import가 실패할 경우 절대 import 시도
try:
    from .factory import get_embedder
except ImportError:
    from vector_index.factory import get_embedder


def fetch_clauses(pg_conn, limit: int = None) -> List[Tuple[int, str, dict]]:
    """
    PostgreSQL에서 조항을 조회합니다.

    Args:
        pg_conn: PostgreSQL 연결
        limit: 최대 조회 개수 (None이면 전체)

    Returns:
        (clause_id, clause_text, metadata) 튜플 리스트
    """
    with pg_conn.cursor() as cur:
        query = """
            SELECT
                dc.id,
                dc.clause_text,
                dc.clause_type,
                dc.structured_data,
                d.doc_type,
                d.product_id,
                ARRAY_AGG(cc.coverage_id) FILTER (WHERE cc.coverage_id IS NOT NULL) as coverage_ids
            FROM document_clause dc
            JOIN document d ON dc.document_id = d.id
            LEFT JOIN clause_coverage cc ON dc.id = cc.clause_id
            GROUP BY dc.id, dc.clause_text, dc.clause_type, dc.structured_data, d.doc_type, d.product_id
            ORDER BY dc.id
        """

        if limit:
            query += f" LIMIT {limit}"

        cur.execute(query)
        results = []
        for row in cur.fetchall():
            clause_id = row[0]
            clause_text = row[1]
            clause_type = row[2]
            structured_data = row[3]
            doc_type = row[4]
            product_id = row[5]
            coverage_ids = row[6] if row[6] else []

            metadata = {
                'clause_type': clause_type,
                'doc_type': doc_type,
                'product_id': product_id,
                'coverage_ids': coverage_ids
            }

            if structured_data:
                metadata['structured_data'] = structured_data

            results.append((clause_id, clause_text, metadata))

        return results


def build_embeddings(
    pg_conn,
    backend: str = "jina",
    batch_size: int = 100,
    limit: int = None
):
    """
    조항 임베딩을 생성하고 저장합니다.

    Args:
        pg_conn: PostgreSQL 연결
        backend: 임베딩 백엔드 (jina 또는 openai)
        batch_size: 배치 크기
        limit: 최대 처리 개수 (None이면 전체)
    """
    print(f"🔧 Using embedding backend: {backend}")

    # Embedder 생성
    embedder = get_embedder(backend)
    model_name = embedder.get_model_name()
    dimension = embedder.get_dimension()

    print(f"   Model: {model_name}")
    print(f"   Dimension: {dimension}")
    print()

    # 기존 임베딩 확인 (삭제하지 않음)
    print("🔍 Checking existing embeddings...")
    with pg_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM clause_embedding")
        existing_count = cur.fetchone()[0]

        # 이미 임베딩된 clause_id 조회
        cur.execute("SELECT clause_id FROM clause_embedding")
        existing_ids = set(row[0] for row in cur.fetchall())

    print(f"   Found {existing_count} existing embeddings")
    print(f"   Will skip {len(existing_ids)} clauses")
    print()

    # 조항 조회
    print("📦 Fetching clauses from PostgreSQL...")
    clauses = fetch_clauses(pg_conn, limit=limit)

    # 이미 임베딩된 clause 필터링
    clauses_to_process = [(cid, text, meta) for cid, text, meta in clauses if cid not in existing_ids]

    total_clauses = len(clauses)
    total_to_process = len(clauses_to_process)

    print(f"   Found {total_clauses} total clauses")
    print(f"   Need to process: {total_to_process} clauses")
    print(f"   Already embedded: {total_clauses - total_to_process} clauses")
    print()

    if total_to_process == 0:
        print("✅ All clauses already embedded. Nothing to do.")
        return

    clauses = clauses_to_process
    total = total_to_process

    # 배치 처리
    print(f"🔄 Generating embeddings (batch size: {batch_size})...")
    processed = 0

    with pg_conn.cursor() as cur:
        for i in range(0, total, batch_size):
            batch_clauses = clauses[i:i + batch_size]
            clause_ids = [c[0] for c in batch_clauses]
            texts = [c[1] for c in batch_clauses]
            metadatas = [c[2] for c in batch_clauses]

            # 임베딩 생성
            try:
                embeddings = embedder.embed_documents(texts)
            except Exception as e:
                print(f"   ❌ Error generating embeddings: {e}")
                continue

            # DB에 저장
            for clause_id, embedding, metadata in zip(clause_ids, embeddings, metadatas):
                # pgvector는 리스트를 자동으로 변환
                # metadata를 JSON으로 저장
                import json
                cur.execute("""
                    INSERT INTO clause_embedding (clause_id, embedding, model_name, metadata)
                    VALUES (%s, %s, %s, %s)
                """, (clause_id, embedding, model_name, json.dumps(metadata)))

            pg_conn.commit()

            processed += len(batch_clauses)
            print(f"   [{processed}/{total}] {processed * 100 // total}% completed")

    print()
    print("=" * 60)
    print("✅ Index build completed!")
    print("=" * 60)
    print(f"   Total clauses: {total}")
    print(f"   Model: {model_name}")
    print(f"   Dimension: {dimension}")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="벡터 인덱스 빌드")
    parser.add_argument(
        "--backend",
        choices=["fastembed", "bge", "jina", "openai"],
        default=os.getenv("EMBEDDING_BACKEND", "fastembed"),
        help="임베딩 백엔드 (기본: fastembed)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="배치 크기 (기본: 100)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="최대 처리 개수 (테스트용, 기본: 전체)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("벡터 인덱스 빌드")
    print("=" * 60)
    print()

    # PostgreSQL 연결
    postgres_url = os.getenv(
        "POSTGRES_URL",
        "postgresql://postgres:postgres@localhost:5432/insurance_ontology"
    )

    try:
        pg_conn = psycopg2.connect(postgres_url)
        print("✅ Connected to PostgreSQL")
        print()

        build_embeddings(
            pg_conn,
            backend=args.backend,
            batch_size=args.batch_size,
            limit=args.limit
        )

        pg_conn.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
