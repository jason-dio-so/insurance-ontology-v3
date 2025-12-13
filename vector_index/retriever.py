"""
Hybrid Retriever

벡터 검색 + 메타데이터 필터링을 결합한 검색 시스템입니다.

Usage:
    from vector_index.retriever import HybridRetriever

    retriever = HybridRetriever()
    results = retriever.search(
        query="암 진단 시 보장금액은?",
        top_k=10,
        company_id=1
    )
"""

import os
import psycopg2
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from .factory import get_embedder

# Load environment variables from .env file
load_dotenv()


class HybridRetriever:
    """Hybrid Retrieval 시스템"""

    def __init__(
        self,
        postgres_url: str = None,
        backend: str = None
    ):
        """
        Args:
            postgres_url: PostgreSQL 연결 문자열
            backend: 임베딩 백엔드 (jina 또는 openai)
        """
        self.postgres_url = postgres_url or os.getenv("POSTGRES_URL")
        if not self.postgres_url:
            raise ValueError("POSTGRES_URL environment variable is required. Check .env file.")

        self.backend = backend or os.getenv("EMBEDDING_BACKEND", "fastembed")
        self.embedder = get_embedder(self.backend)

        self.pg_conn = psycopg2.connect(self.postgres_url)

    def search(
        self,
        query: str,
        top_k: int = 10,
        company_id: Optional[int] = None,
        product_id: Optional[int] = None,
        doc_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Hybrid 검색을 수행합니다.

        Args:
            query: 검색 쿼리
            top_k: 반환할 최대 결과 개수
            company_id: 회사 필터 (None이면 전체)
            product_id: 상품 필터 (None이면 전체)
            doc_type: 문서 타입 필터 (None이면 전체)

        Returns:
            검색 결과 리스트 (각 결과는 딕셔너리)

        Example:
            >>> retriever = HybridRetriever()
            >>> results = retriever.search("암 진단비", top_k=5, company_id=1)
            >>> for result in results:
            ...     print(result['clause_text'])
            ...     print(f"Similarity: {result['similarity']:.3f}")
        """
        # 1. 쿼리 임베딩
        query_embedding = self.embedder.embed_query(query)

        # 2. 벡터 검색 (메타데이터 필터링 포함)
        with self.pg_conn.cursor() as cur:
            # search_similar_clauses 함수 호출
            cur.execute("""
                SELECT
                    clause_id,
                    similarity,
                    clause_text,
                    company_name,
                    product_name,
                    doc_type
                FROM search_similar_clauses(
                    %s::vector(384),
                    %s,
                    %s,
                    %s,
                    %s
                )
            """, (
                query_embedding,
                top_k,
                company_id,
                product_id,
                doc_type
            ))

            results = []
            for row in cur.fetchall():
                results.append({
                    'clause_id': row[0],
                    'similarity': row[1],
                    'clause_text': row[2],
                    'company_name': row[3],
                    'product_name': row[4],
                    'doc_type': row[5]
                })

        return results

    def search_by_coverage(
        self,
        query: str,
        coverage_id: int,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        특정 담보와 관련된 조항만 검색합니다.

        Args:
            query: 검색 쿼리
            coverage_id: 담보 ID
            top_k: 반환할 최대 결과 개수

        Returns:
            검색 결과 리스트
        """
        # 1. 쿼리 임베딩
        query_embedding = self.embedder.embed_query(query)

        # 2. 담보 관련 조항만 검색
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT
                    dc.id AS clause_id,
                    1 - (ce.embedding <=> %s::vector(384)) AS similarity,
                    dc.clause_text,
                    c.name AS company_name,
                    p.name AS product_name,
                    doc.doc_type
                FROM clause_coverage cc
                JOIN document_clause dc ON cc.clause_id = dc.id
                JOIN clause_embedding ce ON dc.id = ce.clause_id
                JOIN document doc ON dc.document_id = doc.id
                LEFT JOIN company c ON doc.company_id = c.company_id
                LEFT JOIN product p ON doc.product_id = p.product_id
                WHERE cc.coverage_id = %s
                ORDER BY ce.embedding <=> %s::vector(384)
                LIMIT %s
            """, (query_embedding, coverage_id, query_embedding, top_k))

            results = []
            for row in cur.fetchall():
                results.append({
                    'clause_id': row[0],
                    'similarity': row[1],
                    'clause_text': row[2],
                    'company_name': row[3],
                    'product_name': row[4],
                    'doc_type': row[5]
                })

        return results

    def close(self):
        """PostgreSQL 연결 종료"""
        if self.pg_conn:
            self.pg_conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
