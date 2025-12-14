"""
Hybrid Retriever

온톨로지 매핑 + 벡터 검색을 결합한 하이브리드 검색 시스템입니다.

주요 기능:
- NL Mapper를 통한 엔티티 추출
- 필터링된 벡터 검색 (company_id, product_id, coverage_ids, amount, gender, age)
- 컨텍스트 조립 및 LLM 프롬프팅

Usage:
    from retrieval.hybrid_retriever import HybridRetriever

    retriever = HybridRetriever()
    result = retriever.search("삼성화재 암 진단금 3000만원", top_k=5)
"""

import os
import re
import psycopg2
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from ontology.nl_mapping import NLMapper
from vector_index.factory import get_embedder


# 키워드 부스팅을 위한 담보/보장 관련 핵심 키워드
COVERAGE_BOOST_KEYWORDS = {
    # 담보 유형
    "수술": ["수술", "수술비", "수술담보"],
    "입원": ["입원", "입원비", "입원일당", "입원담보"],
    "진단": ["진단", "진단금", "진단비", "진단담보"],
    "암": ["암", "암진단", "암수술", "암입원", "암치료", "유사암", "재진단암"],
    "뇌": ["뇌", "뇌출혈", "뇌졸중", "뇌경색", "뇌혈관"],
    "심장": ["심장", "심근경색", "급성심근경색", "심혈관"],
    "사망": ["사망", "사망보험금", "사망담보"],
    "후유장해": ["후유장해", "장해", "장해급여"],
    "치료": ["치료", "치료비", "직접치료"],
}

# 금액 관련 키워드 패턴 (실제 금액 값이 있는 문서 감지)
# "보험금" 같은 일반 단어는 제외 (예: "보험금을 지급하지 않는 사유"에서 오탐지)
AMOUNT_PATTERNS = [
    "가입금액:",  # proposal 문서의 금액 패턴
    "가입금액 :",
    "만원,",      # "1,000만원," 패턴
    "천만원",     # "1천만원" 패턴
    "백만원",     # "1백만원" 패턴
]

# Load environment variables from .env file
load_dotenv()


class HybridRetriever:
    """하이브리드 검색 엔진 (온톨로지 + 벡터)"""

    def __init__(
        self,
        postgres_url: str = None,
        embedder_backend: str = None
    ):
        """
        Args:
            postgres_url: PostgreSQL 연결 문자열
            embedder_backend: 임베딩 백엔드 ("fastembed" 또는 "openai", None=환경변수 사용)
        """
        self.postgres_url = postgres_url or os.getenv("POSTGRES_URL")
        if not self.postgres_url:
            raise ValueError("POSTGRES_URL environment variable is required. Check .env file.")
        self.pg_conn = psycopg2.connect(self.postgres_url)
        # 환경변수에서 백엔드 가져오기 (기본값: openai)
        backend = embedder_backend or os.getenv("EMBEDDING_BACKEND", "openai")
        self.embedder = get_embedder(backend)
        self.nl_mapper = NLMapper(self.postgres_url)

    def _extract_boost_keywords(self, query: str) -> List[str]:
        """
        쿼리에서 부스팅할 키워드 추출

        Args:
            query: 사용자 질의

        Returns:
            부스팅할 키워드 리스트
        """
        keywords = []
        query_lower = query.lower()

        # COVERAGE_BOOST_KEYWORDS에서 매칭되는 키워드 확장
        for base_keyword, related_keywords in COVERAGE_BOOST_KEYWORDS.items():
            if base_keyword in query_lower or base_keyword in query:
                keywords.extend(related_keywords)

        # NLMapper에서 추출한 담보/키워드도 추가
        entities = self.nl_mapper.extract_entities(query)
        if entities.get("coverages"):
            keywords.extend(entities["coverages"])
        if entities.get("keywords"):
            keywords.extend(entities["keywords"])

        # 중복 제거
        return list(set(keywords))

    def _calculate_keyword_boost(
        self,
        clause_text: str,
        keywords: List[str],
        boost_weight: float = 0.15,
        require_amount: bool = False
    ) -> float:
        """
        키워드 매칭 기반 부스트 점수 계산

        Args:
            clause_text: 검색된 문서 텍스트
            keywords: 부스팅할 키워드 리스트
            boost_weight: 키워드당 부스트 가중치
            require_amount: True면 금액 정보가 있는 문서에 추가 부스트

        Returns:
            부스트 점수 (0.0 ~ max_boost)
        """
        if not keywords or not clause_text:
            return 0.0

        clause_lower = clause_text.lower()
        matched_count = sum(1 for kw in keywords if kw in clause_lower or kw in clause_text)

        # 기본 부스트 계산
        max_boost = 0.3
        boost = min(matched_count * boost_weight, max_boost)

        # 금액 정보가 필요한 경우 추가 부스트
        if require_amount:
            # 실제 금액 패턴이 있는지 확인 (단순 "보험금" 단어가 아닌 "가입금액:", "1천만원" 등)
            has_amount = any(pattern in clause_text for pattern in AMOUNT_PATTERNS)
            if has_amount:
                # 금액 정보가 있는 문서에 0.25 추가 부스트
                boost += 0.25
            else:
                # 금액 정보가 없으면 부스트 감소
                boost *= 0.3

        return boost

    def _rerank_with_keyword_boost(
        self,
        results: List[Dict[str, Any]],
        keywords: List[str],
        top_k: int,
        require_amount: bool = False
    ) -> List[Dict[str, Any]]:
        """
        키워드 부스팅으로 검색 결과 재순위화

        Args:
            results: 벡터 검색 결과
            keywords: 부스팅할 키워드
            top_k: 반환할 결과 개수
            require_amount: True면 금액 정보가 있는 문서 우선

        Returns:
            재순위화된 결과
        """
        if not keywords or not results:
            return results[:top_k]

        # 각 결과에 final_score 계산
        for result in results:
            keyword_boost = self._calculate_keyword_boost(
                result.get("clause_text", ""),
                keywords,
                require_amount=require_amount
            )
            # Final Score = Vector Similarity + Keyword Boost
            result["keyword_boost"] = keyword_boost
            result["final_score"] = result.get("similarity", 0) + keyword_boost

        # final_score로 재정렬
        reranked = sorted(results, key=lambda x: x.get("final_score", 0), reverse=True)

        return reranked[:top_k]

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        하이브리드 검색 실행

        Args:
            query: 사용자 질의
            top_k: 반환할 결과 개수
            filters: 추가 필터 (선택적)

        Returns:
            검색 결과 리스트 [
                {
                    "clause_id": int,
                    "clause_text": str,
                    "similarity": float,
                    "clause_type": str,
                    "doc_type": str,
                    "product_id": str,
                    "coverage_ids": List[int]
                },
                ...
            ]
        """
        # 1. 엔티티 추출
        entities = self.nl_mapper.extract_entities(query)

        # 1.5. 키워드 부스팅을 위한 키워드 추출
        boost_keywords = self._extract_boost_keywords(query)

        # 2. 필터 구성
        search_filters = filters or {}

        # 엔티티에서 추출한 필터 병합
        if entities["filters"].get("company_id"):
            search_filters.setdefault("company_id", entities["filters"]["company_id"])

        if entities["filters"].get("product_id"):
            search_filters.setdefault("product_id", entities["filters"]["product_id"])

        # NOTE: coverage_ids 필터는 너무 엄격하여 제외
        # NL Mapper의 담보 추출이 부정확할 수 있으므로 벡터 유사도에만 의존
        # if entities["filters"].get("coverage_ids"):
        #     search_filters.setdefault("coverage_ids", entities["filters"]["coverage_ids"])

        # ⭐ Coverage/Amount query detection
        # NOTE: doc_type 필터 제거 - 키워드 부스팅으로 관련 문서 상위 노출
        # 기존: proposal + table_row 필터 → 약관(terms)의 상세 담보 정보 누락
        # 개선: 전체 검색 후 키워드 부스팅으로 재순위화
        coverage_keywords = [
            "진단금", "진단비", "수술비", "입원비", "치료비", "보장금", "보험금", "보장액",
            # 담보 유형 키워드 추가 (이 담보들은 보통 금액 정보가 필요함)
            "암", "암진단", "뇌출혈", "뇌졸중", "심근경색", "골절", "수술", "입원",
            "유사암", "재진단암", "항암", "뇌경색", "뇌혈관", "심장", "후유장해"
        ]
        has_coverage_query = (
            entities.get("coverages") or  # Coverage extracted by NL mapper
            entities["filters"].get("amount") or  # Amount filter present
            any(kw in query for kw in coverage_keywords)  # Coverage keyword in query
        )

        # 금액 정보가 필요한 쿼리인지 판단
        # - 명시적으로 금액을 묻는 쿼리 (예: "얼마", "보장금액", "N만원")
        # - 담보 유형 쿼리 (암진단, 뇌출혈 등) - 대부분 금액 정보 필요
        amount_query_keywords = ["얼마", "금액", "만원", "천원", "보장금", "보험금"]
        is_amount_query = (
            entities["filters"].get("amount") or
            any(kw in query for kw in amount_query_keywords) or
            has_coverage_query  # 담보 관련 쿼리는 금액 정보 우선
        )

        # doc_type/clause_type 필터는 키워드 부스팅이 없을 때만 적용
        # 키워드 부스팅이 있으면 전체 검색 후 재순위화로 관련 문서 상위 노출
        if has_coverage_query and not boost_keywords:
            # Prioritize proposal documents with table_row clauses for accurate benefit info
            search_filters.setdefault("doc_type", "proposal")
            search_filters.setdefault("clause_type", "table_row")

        if entities["filters"].get("amount"):
            search_filters.setdefault("amount", entities["filters"]["amount"])

        if entities["filters"].get("gender"):
            search_filters.setdefault("gender", entities["filters"]["gender"])

        if entities["filters"].get("age"):
            search_filters.setdefault("age", entities["filters"]["age"])

        # 3. 쿼리 임베딩 생성
        query_embedding = self.embedder.embed_query(query)

        # 4. 필터링된 벡터 검색 실행 (with fallback for zero results)
        # 키워드 부스팅을 위해 3배 더 많은 후보 검색 후 re-ranking
        search_top_k = max(top_k * 3, 30)  # 최소 30개 후보

        results = self._filtered_vector_search(
            query_embedding=query_embedding,
            filters=search_filters,
            top_k=search_top_k
        )

        # ⭐ Amount 쿼리일 때 proposal 문서 별도 검색하여 병합
        # proposal 문서는 금액 정보가 있지만 벡터 유사도가 낮을 수 있음
        if is_amount_query and search_filters.get("company_id"):
            proposal_filters = {
                "company_id": search_filters["company_id"],
                "doc_type": "proposal"
            }
            proposal_results = self._filtered_vector_search(
                query_embedding=query_embedding,
                filters=proposal_filters,
                top_k=search_top_k
            )
            # 기존 결과에 proposal 결과 병합 (중복 제거)
            existing_ids = {r["clause_id"] for r in results}
            for pr in proposal_results:
                if pr["clause_id"] not in existing_ids:
                    results.append(pr)

        # ⭐ Fallback search for coverage queries with zero results
        # If proposal + table_row filter is too restrictive, try progressively broader searches
        if has_coverage_query and len(results) == 0:
            # Tier 1: Try proposal without clause_type restriction
            fallback_filters = search_filters.copy()
            if "clause_type" in fallback_filters:
                del fallback_filters["clause_type"]
            results = self._filtered_vector_search(
                query_embedding=query_embedding,
                filters=fallback_filters,
                top_k=search_top_k
            )

            # Tier 2: Try business_spec with table_row (more detailed than summary)
            if len(results) == 0:
                fallback_filters = search_filters.copy()
                fallback_filters["doc_type"] = "business_spec"
                results = self._filtered_vector_search(
                    query_embedding=query_embedding,
                    filters=fallback_filters,
                    top_k=search_top_k
                )

            # Tier 3: Try business_spec without clause_type
            if len(results) == 0:
                fallback_filters = search_filters.copy()
                fallback_filters["doc_type"] = "business_spec"
                if "clause_type" in fallback_filters:
                    del fallback_filters["clause_type"]
                results = self._filtered_vector_search(
                    query_embedding=query_embedding,
                    filters=fallback_filters,
                    top_k=search_top_k
                )

            # Tier 4: Try terms document (most comprehensive coverage info)
            if len(results) == 0:
                fallback_filters = search_filters.copy()
                fallback_filters["doc_type"] = "terms"
                if "clause_type" in fallback_filters:
                    del fallback_filters["clause_type"]
                results = self._filtered_vector_search(
                    query_embedding=query_embedding,
                    filters=fallback_filters,
                    top_k=search_top_k
                )

            # Tier 5: Remove doc_type filter entirely (last resort)
            if len(results) == 0:
                fallback_filters = search_filters.copy()
                if "doc_type" in fallback_filters:
                    del fallback_filters["doc_type"]
                if "clause_type" in fallback_filters:
                    del fallback_filters["clause_type"]
                results = self._filtered_vector_search(
                    query_embedding=query_embedding,
                    filters=fallback_filters,
                    top_k=search_top_k
                )

        # 5. 키워드 부스팅으로 재순위화 (금액 쿼리면 금액 정보 있는 문서 우선)
        results = self._rerank_with_keyword_boost(
            results, boost_keywords, top_k,
            require_amount=is_amount_query
        )

        return results

    def _filtered_vector_search(
        self,
        query_embedding: List[float],
        filters: Dict[str, Any],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        필터링된 벡터 검색

        Args:
            query_embedding: 쿼리 임베딩
            filters: 필터 조건
            top_k: 반환할 결과 개수

        Returns:
            검색 결과 리스트
        """
        with self.pg_conn.cursor() as cur:
            # HNSW 인덱스 ef_search 설정 (필터+벡터검색 시 충분한 후보 탐색)
            # 기본값 40은 필터 적용 시 결과 0 발생 가능 → 200으로 증가
            cur.execute("SET hnsw.ef_search = 200")

            # 기본 SELECT
            query_parts = ["""
                SELECT
                    ce.clause_id,
                    dc.clause_text,
                    (1 - (ce.embedding <=> %s::vector)) as similarity,
                    ce.metadata->>'clause_type' as clause_type,
                    ce.metadata->>'doc_type' as doc_type,
                    ce.metadata->>'product_id' as product_id
                FROM clause_embedding ce
                JOIN document_clause dc ON ce.clause_id = dc.id
                JOIN document d ON dc.document_id = d.id
            """]

            query_params = [query_embedding]
            where_conditions = []

            # Company filter
            if filters.get("company_id"):
                where_conditions.append("d.company_id = %s")
                query_params.append(filters["company_id"])

            # Product filter
            if filters.get("product_id"):
                where_conditions.append("d.product_id = %s")
                query_params.append(filters["product_id"])

            # Document type filter (Phase 6.1 - Proposal 우선 검색)
            if filters.get("doc_type"):
                where_conditions.append("ce.metadata->>'doc_type' = %s")
                query_params.append(filters["doc_type"])

            # Clause type filter (Phase 6.1 - table_row 우선 검색)
            if filters.get("clause_type"):
                where_conditions.append("ce.metadata->>'clause_type' = %s")
                query_params.append(filters["clause_type"])

            # Coverage IDs filter (metadata JSONB) - OPTIONAL, 있으면 적용
            if filters.get("coverage_ids"):
                coverage_ids = filters["coverage_ids"]
                # 담보 필터는 있으면 좋지만, 없어도 검색 가능하도록 유연하게
                or_conditions = []
                for cov_id in coverage_ids:
                    or_conditions.append(
                        f"ce.metadata->'coverage_ids' @> '[{cov_id}]'::jsonb"
                    )
                if or_conditions:
                    where_conditions.append(f"({' OR '.join(or_conditions)})")

            # Amount filter (structured_data JSONB) - Phase 5 v6 Fix
            # Handle Korean amount formats: "3,000만원", "500만원", "1억" etc.
            if filters.get("amount"):
                amount_filter = filters["amount"]
                amount_conditions = []

                # Helper function to parse Korean amounts in SQL
                # Extract number from "N,NNN만원" or "N천만원" format
                parse_korean_amount_sql = """
                    CASE
                        WHEN ce.metadata->'structured_data'->>'coverage_amount' ~ '^[0-9,]+만원$' THEN
                            -- Parse "3,000만원" or "500만원" format
                            (REPLACE(REGEXP_REPLACE(ce.metadata->'structured_data'->>'coverage_amount', '만원$', ''), ',', '')::bigint * 10000)
                        WHEN ce.metadata->'structured_data'->>'coverage_amount' ~ '^[0-9]+억' THEN
                            -- Parse "1억" or "2억5천만원" format (approximate)
                            (REGEXP_REPLACE(ce.metadata->'structured_data'->>'coverage_amount', '억.*', '')::bigint * 100000000)
                        WHEN ce.metadata->'structured_data'->>'coverage_amount' ~ '^[0-9]+천만원$' THEN
                            -- Parse "3천만원" format
                            (REGEXP_REPLACE(ce.metadata->'structured_data'->>'coverage_amount', '천만원$', '')::bigint * 10000000)
                        WHEN ce.metadata->'structured_data'->>'coverage_amount' ~ '^[0-9]+원$' THEN
                            -- Pure "NNN원" format
                            REGEXP_REPLACE(ce.metadata->'structured_data'->>'coverage_amount', '원$', '')::bigint
                        ELSE NULL
                    END
                """

                if amount_filter.get("min"):
                    amount_conditions.append(
                        f"({parse_korean_amount_sql}) >= {amount_filter['min']}"
                    )
                if amount_filter.get("max"):
                    amount_conditions.append(
                        f"({parse_korean_amount_sql}) <= {amount_filter['max']}"
                    )

                if amount_conditions:
                    where_conditions.append(f"({' AND '.join(amount_conditions)})")

            # Gender filter (product_variant)
            if filters.get("gender"):
                query_parts.insert(1, "JOIN product_variant pv ON d.variant_id = pv.id")
                where_conditions.append("pv.target_gender = %s")
                query_params.append(filters["gender"])

            # Age filter (product_variant, target_age_range)
            if filters.get("age"):
                age_filter = filters["age"]
                if "variant_id" not in " ".join(query_parts):
                    query_parts.insert(1, "JOIN product_variant pv ON d.variant_id = pv.id")

                # age_filter: {"min": int, "max": int}
                # pv.target_age_range: "≤40", "≥41", "20~40" 등
                # 간단한 문자열 매칭으로 처리 (실전에서는 더 정교한 파싱 필요)
                if age_filter.get("max") and not age_filter.get("min"):
                    # "≤N" 범위 찾기
                    where_conditions.append("pv.target_age_range LIKE %s")
                    query_params.append(f"≤%")
                elif age_filter.get("min") and not age_filter.get("max"):
                    # "≥N" 범위 찾기
                    where_conditions.append("pv.target_age_range LIKE %s")
                    query_params.append(f"≥%")

            # WHERE 절 구성
            if where_conditions:
                query_parts.append("WHERE " + " AND ".join(where_conditions))

            # ORDER BY 및 LIMIT
            query_parts.append("ORDER BY ce.embedding <=> %s::vector")
            query_parts.append(f"LIMIT %s")

            query_params.append(query_embedding)  # ORDER BY용
            query_params.append(top_k)

            # 최종 쿼리 실행
            final_query = "\n".join(query_parts)
            cur.execute(final_query, query_params)

            results = []
            for row in cur.fetchall():
                results.append({
                    "clause_id": row[0],
                    "clause_text": row[1],
                    "similarity": row[2],
                    "clause_type": row[3],
                    "doc_type": row[4],
                    "product_id": row[5]
                })

            return results

    def search_multi_company(
        self,
        query: str,
        company_names: List[str],
        coverage_name: str,
        top_k: int = 5,
        search_top_k: int = 50
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        여러 보험사에 대해 동일 쿼리로 검색 (상품 비교용)

        Args:
            query: 기본 쿼리 (예: "암진단")
            company_names: 비교할 보험사 이름 리스트 (예: ["삼성화재", "DB손보"])
            coverage_name: 담보 이름
            top_k: 각 회사당 반환할 결과 개수

        Returns:
            회사별 검색 결과 딕셔너리
            {
                "samsung": [results],
                "db": [results],
                ...
            }
        """
        results_by_company = {}

        for company_name in company_names:
            # 회사별 개별 검색 실행
            company_query = f"{company_name} {coverage_name}"

            try:
                # NL Mapper로 company_id 추출
                entities = self.nl_mapper.extract_entities(company_query)
                company_id = entities["filters"].get("company_id")

                if not company_id:
                    # company_id를 못 찾으면 DB에서 직접 조회
                    company_id = self._get_company_id_by_name(company_name)

                if company_id:
                    # 검색 실행 (Terms 문서 우선 - 가장 상세하고 정확)
                    # search_top_k로 많이 가져온 후 re-ranking으로 top_k 선택
                    # 1차: terms 문서 검색 (가장 정확한 정보)
                    search_results = self.search(
                        query=company_query,
                        top_k=search_top_k,  # 많이 가져오기
                        filters={
                            "company_id": company_id,
                            "doc_type": "terms"
                        }
                    )

                    # 2차: 결과가 없으면 business_spec 시도 (두 번째로 상세)
                    if not search_results:
                        search_results = self.search(
                            query=company_query,
                            top_k=search_top_k,
                            filters={
                                "company_id": company_id,
                                "doc_type": "business_spec"
                            }
                        )

                    # 3차: 결과가 없으면 product_summary (요약 정보)
                    if not search_results:
                        search_results = self.search(
                            query=company_query,
                            top_k=search_top_k,
                            filters={
                                "company_id": company_id,
                                "doc_type": "product_summary"
                            }
                        )

                    # 4차: 여전히 없으면 proposal (짧은 정보지만 어쩔 수 없음)
                    if not search_results:
                        search_results = self.search(
                            query=company_query,
                            top_k=search_top_k,
                            filters={
                                "company_id": company_id,
                                "doc_type": "proposal"
                            }
                        )

                    # 5차: 여전히 없으면 모든 문서 검색
                    if not search_results:
                        search_results = self.search(
                            query=company_query,
                            top_k=search_top_k,
                            filters={"company_id": company_id}
                        )

                    results_by_company[company_name] = search_results
                else:
                    # 회사를 찾지 못한 경우
                    results_by_company[company_name] = []

            except Exception as e:
                print(f"Error searching for company {company_name}: {e}")
                results_by_company[company_name] = []

        return results_by_company

    def _get_company_id_by_name(self, company_name: str) -> Optional[int]:
        """
        회사명으로 company_id 조회 (부분 매칭)

        Args:
            company_name: 회사명 (예: "삼성", "삼성화재")

        Returns:
            company_id 또는 None
        """
        with self.pg_conn.cursor() as cur:
            # 부분 매칭 (예: "삼성" → "삼성화재")
            cur.execute("""
                SELECT id
                FROM company
                WHERE company_name LIKE %s OR company_code LIKE %s
                LIMIT 1
            """, (f"%{company_name}%", f"%{company_name}%"))

            row = cur.fetchone()
            return row[0] if row else None

    def close(self):
        """리소스 정리"""
        if self.pg_conn:
            self.pg_conn.close()
        if self.nl_mapper:
            self.nl_mapper.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# 편의 함수
def hybrid_search(
    query: str,
    top_k: int = 10,
    postgres_url: str = None
) -> List[Dict[str, Any]]:
    """
    하이브리드 검색 (원샷 함수)

    Args:
        query: 사용자 질의
        top_k: 반환할 결과 개수
        postgres_url: PostgreSQL 연결 문자열

    Returns:
        검색 결과 리스트
    """
    with HybridRetriever(postgres_url) as retriever:
        return retriever.search(query, top_k=top_k)
