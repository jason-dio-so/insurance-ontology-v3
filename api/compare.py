"""
Product Comparison API

여러 보험사의 동일 담보를 비교하는 기능을 제공합니다.

Usage:
    from api.compare import ProductComparer

    comparer = ProductComparer()
    result = comparer.compare_products(
        companies=["삼성화재", "DB손보"],
        coverage="암진단"
    )
"""

import os
import psycopg2
from typing import Dict, List, Any, Optional
from retrieval.hybrid_retriever import HybridRetriever


class ProductComparer:
    """
    상품 비교기

    여러 보험사의 동일 담보를 비교하여 표 형식으로 제공
    """

    def __init__(
        self,
        postgres_url: str = None,
        hybrid_retriever: HybridRetriever = None
    ):
        """
        Args:
            postgres_url: PostgreSQL 연결 문자열
            hybrid_retriever: 하이브리드 검색기 (선택)
        """
        self.postgres_url = postgres_url or os.getenv(
            "POSTGRES_URL",
            "postgresql://postgres:postgres@localhost:5432/insurance_ontology"
        )
        self.pg_conn = psycopg2.connect(self.postgres_url)

        if hybrid_retriever:
            self.retriever = hybrid_retriever
        else:
            self.retriever = HybridRetriever(self.postgres_url)

    def compare_products(
        self,
        companies: List[str],
        coverage: str | List[str],
        include_sources: bool = True,
        include_recommendation: bool = True
    ) -> Dict[str, Any]:
        """
        상품 비교 실행

        Args:
            companies: 비교할 보험사 리스트 (예: ["삼성화재", "DB손보"])
            coverage: 담보 이름 또는 담보 리스트 (예: "암진단" 또는 ["제자리암", "경계성종양"])
            include_sources: 출처 포함 여부
            include_recommendation: 추천 메시지 포함 여부

        Returns:
            {
                "companies": ["삼성화재", "DB손보"],
                "coverage": "암진단" or ["제자리암", "경계성종양"],
                "comparison": {
                    "삼성화재": {
                        "productName": "마이헬스파트너",
                        "coverageName": "암진단비",
                        "amount": 30000000,
                        "premium": 40620,
                        "exemptionPeriod": "90일",
                        "reductionPeriod": "1년 (50%)",
                        "specialNotes": ["유사암 별도 담보"],
                        "sources": [...]
                    },
                    "DB손보": { ... }
                },
                "recommendation": "..."
            }
        """
        # Coverage를 리스트로 정규화
        coverages = coverage if isinstance(coverage, list) else [coverage]

        # 각 coverage별로 비교 데이터 수집
        all_comparison_data = {}

        for cov in coverages:
            # 1. Multi-company search 실행
            search_results = self.retriever.search_multi_company(
                query=cov,
                company_names=companies,
                coverage_name=cov,
                top_k=5
            )

            # 2. 각 회사별 비교 데이터 추출
            for company in companies:
                results = search_results.get(company, [])

                # Company+Coverage 키 생성
                key = f"{company}_{cov}"

                if not results:
                    all_comparison_data[key] = {
                        "company": company,
                        "coverage": cov,
                        "status": "no_data",
                        "message": "해당 회사의 데이터를 찾을 수 없습니다."
                    }
                    continue

                # 상위 결과에서 데이터 추출
                extracted_data = self._extract_comparison_data(
                    company=company,
                    coverage=cov,
                    search_results=results
                )

                # 추가 정보 조회 (DB에서)
                additional_info = self._get_additional_info(
                    company=company,
                    coverage=cov
                )

                # 병합
                extracted_data.update(additional_info)
                extracted_data["company"] = company
                extracted_data["coverage"] = cov

                # 출처 추가 (DB에서 실제 사용된 문서 기반)
                if include_sources:
                    extracted_data["sources"] = self._get_db_sources(
                        company=company,
                        product_name=additional_info.get("productName", ""),
                        coverage_name=additional_info.get("coverageName", cov)
                    )

                all_comparison_data[key] = extracted_data

        # 3. 추천 메시지 생성 (간소화된 데이터로)
        recommendation = None
        if include_recommendation:
            # 단일 coverage 비교의 경우 기존 로직 사용
            if len(coverages) == 1:
                simple_comparison = {data["company"]: data for data in all_comparison_data.values()}
                recommendation = self._generate_recommendation(simple_comparison)

        return {
            "companies": companies,
            "coverages": coverages,
            "comparison": all_comparison_data,
            "recommendation": recommendation
        }

    def _extract_comparison_data(
        self,
        company: str,
        coverage: str,
        search_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        검색 결과에서 비교 데이터 추출

        Args:
            company: 회사명
            coverage: 담보명
            search_results: 검색 결과 리스트

        Returns:
            추출된 비교 데이터
        """
        if not search_results:
            return {"status": "no_data"}

        # 상위 table_row 결과 우선
        table_rows = [r for r in search_results if r.get('clause_type') == 'table_row']

        if not table_rows:
            # table_row가 없으면 일반 clause 사용
            table_rows = search_results

        # Re-ranking: 키워드 매칭으로 정확도 향상
        table_rows = self._rerank_by_keywords(table_rows, coverage)

        top_result = table_rows[0]

        # structured_data 파싱 (metadata에서)
        # NOTE: structured_data는 metadata JSONB에 저장되어 있지 않음
        # clause_text에서 직접 파싱하거나, DB에서 조회 필요
        # 여기서는 clause_text 파싱으로 처리

        clause_text = top_result.get('clause_text', '')

        # 간단한 파싱 (실제로는 더 정교한 파싱 필요)
        amount = self._parse_amount(clause_text)
        premium = self._parse_premium(clause_text)

        return {
            "productName": self._get_product_name(top_result.get('product_id')),
            "coverageName": self._parse_coverage_name(clause_text),
            "amount": amount,
            "premium": premium,
            "clause_text": clause_text,
            "similarity": top_result.get('similarity', 0.0)
        }

    def _rerank_by_keywords(
        self,
        results: List[Dict[str, Any]],
        coverage: str
    ) -> List[Dict[str, Any]]:
        """
        키워드 매칭으로 검색 결과 재순위화

        Args:
            results: 검색 결과 리스트
            coverage: 담보명 (예: "암진단")

        Returns:
            재순위화된 검색 결과
        """
        # 담보명을 키워드로 분해
        keywords = []
        bonus_keywords = []  # 강한 매칭 키워드

        if "암" in coverage:
            keywords.append("암")
        if "진단" in coverage:
            keywords.append("진단")
            bonus_keywords.append("진단비")  # "진단비" 정확 매칭 시 추가 보너스
        if "수술" in coverage:
            keywords.append("수술")
        if "입원" in coverage:
            keywords.append("입원")

        # 각 결과에 키워드 매칭 점수 부여
        def keyword_score(result):
            clause_text = result.get('clause_text', '')
            score = 0

            # 기본 키워드 매칭
            for keyword in keywords:
                if keyword in clause_text:
                    score += 1

            # 보너스 키워드 매칭 (더 강한 가중치)
            for bonus_keyword in bonus_keywords:
                if bonus_keyword in clause_text:
                    score += 1.5

            # 잘못된 매칭 패널티
            if "화상" in clause_text and "암" in coverage:
                score -= 2  # 화상은 암이 아님
            if "골절" in clause_text and "암" in coverage:
                score -= 2  # 골절은 암이 아님

            # 원래 유사도와 결합 (유사도 60% + 키워드 40%)
            original_similarity = result.get('similarity', 0.0)
            keyword_bonus = (score / max(len(keywords) + len(bonus_keywords), 1)) * 0.4
            return original_similarity * 0.6 + keyword_bonus

        # 점수 기준으로 정렬
        results_with_score = sorted(results, key=keyword_score, reverse=True)
        return results_with_score

    def _parse_amount(self, clause_text: str) -> Optional[int]:
        """
        clause_text에서 보장금액 파싱

        Examples:
            "암 진단비, 가입금액: 3,000만원" -> 30000000
            "보장금액 2000만원" -> 20000000
            "가입금액: 3천만원" -> 30000000
            "가입금액: 1천만원" -> 10000000
        """
        import re

        # 한글 숫자 변환
        korean_nums = {
            '일': 1, '이': 2, '삼': 3, '사': 4, '오': 5,
            '육': 6, '칠': 7, '팔': 8, '구': 9,
            '천': 1000, '백': 100, '십': 10
        }

        # 패턴: "N천만원" 형식 우선 처리
        match = re.search(r'(\d+)천만원', clause_text)
        if match:
            num = int(match.group(1))
            return num * 10000000  # N천만원 = N * 1000만원 = N * 10,000,000원

        # 패턴: "N,NNN만원" 또는 "NNNN만원"
        patterns = [
            r'(\d{1,3}(?:,\d{3})+)만원',  # 3,000만원
            r'(\d+)만원',  # 3000만원
            r'(\d{1,3}(?:,\d{3})+)원',  # 30,000,000원
        ]

        for pattern in patterns:
            match = re.search(pattern, clause_text)
            if match:
                amount_str = match.group(1).replace(',', '')
                amount = int(amount_str)

                # 단위 변환
                if '만원' in clause_text:
                    return amount * 10000
                else:
                    return amount

        return None

    def _parse_premium(self, clause_text: str) -> Optional[int]:
        """
        clause_text에서 월 보험료 파싱

        Examples:
            "월보험료: 40,620원" -> 40620
            "보험료 28450원" -> 28450
        """
        import re

        # 패턴: "보험료" 키워드 후 숫자
        patterns = [
            r'보험료[:\s]*(\d{1,3}(?:,\d{3})+)원',  # 40,620원
            r'보험료[:\s]*(\d+)원',  # 40620원
        ]

        for pattern in patterns:
            match = re.search(pattern, clause_text)
            if match:
                premium_str = match.group(1).replace(',', '')
                return int(premium_str)

        return None

    def _parse_coverage_name(self, clause_text: str) -> str:
        """
        clause_text에서 담보명 파싱

        Examples:
            "암 진단비(유사암 제외), 가입금액: ..." -> "암 진단비"
        """
        # 첫 번째 콤마 또는 괄호 앞까지
        import re

        match = re.match(r'([^,(]+)', clause_text)
        if match:
            return match.group(1).strip()

        return clause_text[:30] + "..."  # fallback

    def _get_product_name(self, product_id: str) -> Optional[str]:
        """
        product_id로 상품명 조회

        Args:
            product_id: 상품 ID (문자열)

        Returns:
            상품명 또는 None
        """
        if not product_id:
            return None

        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT product_name
                FROM product
                WHERE id = %s
            """, (int(product_id),))

            row = cur.fetchone()
            return row[0] if row else None

    def _get_additional_info(
        self,
        company: str,
        coverage: str
    ) -> Dict[str, Any]:
        """
        DB에서 추가 정보 조회 (담보명, 보장금액, 면책기간 등)

        Args:
            company: 회사명
            coverage: 담보명

        Returns:
            추가 정보 딕셔너리
        """
        print(f"[DEBUG] _get_additional_info: company={company}, coverage={coverage}")

        # 키워드 분해 (구체적인 키워드 우선)
        keywords = []

        # 구체적 키워드 먼저 추출 (우선순위 높음)
        if "제자리암" in coverage:
            keywords.append("제자리암")
        elif "경계성종양" in coverage:
            keywords.append("경계성종양")
        elif "유사암" in coverage or "4대유사암" in coverage:
            keywords.append("유사암")
        elif "암" in coverage:
            keywords.append("암")

        if "진단" in coverage:
            keywords.append("진단")
        if "수술" in coverage:
            keywords.append("수술")

        print(f"[DEBUG] Keywords: {keywords}")

        # DB에서 coverage/benefit 데이터 직접 조회
        # 모든 키워드가 포함된 담보 찾기
        with self.pg_conn.cursor() as cur:
            # 동적으로 LIKE 조건 생성
            like_conditions = " AND ".join([f"cov.coverage_name LIKE %s" for _ in keywords])
            like_params = [f'%{kw}%' for kw in keywords]

            query = f"""
                SELECT
                    comp.company_name,
                    p.product_name,
                    cov.coverage_name,
                    b.benefit_amount
                FROM coverage cov
                JOIN product p ON cov.product_id = p.id
                JOIN company comp ON p.company_id = comp.id
                LEFT JOIN benefit b ON cov.id = b.coverage_id
                WHERE comp.company_name = %s
                  AND ({like_conditions})
                ORDER BY b.benefit_amount DESC NULLS LAST
                LIMIT 1
            """

            cur.execute(query, (company, *like_params))

            row = cur.fetchone()
            if row:
                company_name, product_name, coverage_name, benefit_amount = row
                print(f"[DEBUG] Found coverage: {coverage_name}, amount: {benefit_amount}")

                # 담보명 정리: 앞의 숫자 제거 (예: "36 재진단암진단비" -> "재진단암진단비")
                import re
                cleaned_coverage_name = re.sub(r'^\d+\s+', '', coverage_name)

                return {
                    "productName": product_name,
                    "coverageName": cleaned_coverage_name,
                    "amount": int(benefit_amount) if benefit_amount else 0,
                    "exemptionPeriod": None,
                    "reductionPeriod": None,
                    "specialNotes": []
                }
            else:
                print(f"[DEBUG] No coverage found in DB, searching document clauses...")

                # Fallback: Search in document_clause table
                like_conditions_clause = " AND ".join([f"dc.clause_text LIKE %s" for _ in keywords])
                like_params_clause = [f'%{kw}%' for kw in keywords]

                fallback_query = """
                    SELECT
                        comp.company_name,
                        p.product_name,
                        dc.clause_text
                    FROM document_clause dc
                    JOIN document d ON dc.document_id = d.id
                    JOIN company comp ON d.company_id = comp.id
                    LEFT JOIN product p ON d.product_id = p.id
                    WHERE comp.company_name = %s
                      AND ({})
                    LIMIT 1
                """.format(like_conditions_clause)

                cur.execute(fallback_query, (company, *like_params_clause))
                fallback_row = cur.fetchone()

                if fallback_row:
                    _, product_name, clause_text = fallback_row
                    print(f"[DEBUG] Found in document clauses for product: {product_name}")

                    # Return with indication that data exists in documents
                    return {
                        "productName": product_name,
                        "coverageName": coverage,  # Use original coverage name
                        "amount": None,  # Cannot extract amount from unstructured text
                        "exemptionPeriod": None,
                        "reductionPeriod": None,
                        "specialNotes": ["문서에서 관련 내용을 확인했으나 구조화된 보장금액 정보가 없습니다."]
                    }
                else:
                    print(f"[DEBUG] No coverage found in DB or documents")
                    return {
                        "exemptionPeriod": None,
                        "reductionPeriod": None,
                        "specialNotes": []
                    }

    def _get_db_sources(
        self,
        company: str,
        product_name: str,
        coverage_name: str
    ) -> List[Dict[str, Any]]:
        """
        DB에서 실제 coverage와 관련된 문서 조회

        Args:
            company: 회사명
            product_name: 상품명
            coverage_name: 담보명

        Returns:
            관련 문서 리스트
        """
        sources = []

        with self.pg_conn.cursor() as cur:
            # Coverage와 관련된 document_clause 조회 (회사당 1개만)
            query = """
                SELECT DISTINCT
                    comp.company_name,
                    p.product_name,
                    d.doc_type,
                    dc.clause_text,
                    dc.clause_number
                FROM coverage cov
                JOIN product p ON cov.product_id = p.id
                JOIN company comp ON p.company_id = comp.id
                JOIN document d ON d.product_id = p.id
                JOIN document_clause dc ON dc.document_id = d.id
                WHERE comp.company_name = %s
                  AND cov.coverage_name LIKE %s
                ORDER BY d.doc_type
                LIMIT 1
            """

            cur.execute(query, (company, f'%{coverage_name}%'))
            rows = cur.fetchall()

            for row in rows:
                comp_name, prod_name, doc_type, clause_text, clause_number = row
                sources.append({
                    "company": comp_name,
                    "product": prod_name,
                    "docType": doc_type,
                    "clause": clause_text[:200] if clause_text else "",
                    "clauseNumber": clause_number
                })

        return sources

    def _format_sources(
        self,
        search_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        출처 정보 포맷팅 (레거시, 사용 안 함)

        Args:
            search_results: 검색 결과 리스트

        Returns:
            포맷팅된 출처 리스트
        """
        sources = []
        for result in search_results:
            sources.append({
                "docType": result.get('doc_type'),
                "clauseId": result.get('clause_id'),
                "description": result.get('clause_text', '')[:100] + "..."
            })

        return sources

    def _generate_recommendation(
        self,
        comparison_data: Dict[str, Dict[str, Any]]
    ) -> Optional[str]:
        """
        비교 데이터 기반 추천 메시지 생성

        Args:
            comparison_data: 비교 데이터 딕셔너리

        Returns:
            추천 메시지 또는 None
        """
        # 간단한 휴리스틱 기반 추천
        valid_companies = {
            company: data
            for company, data in comparison_data.items()
            if data.get("status") != "no_data" and data.get("amount")
        }

        if len(valid_companies) < 2:
            return None

        # 보장금액 최고
        max_amount_company = max(
            valid_companies.items(),
            key=lambda x: x[1].get("amount", 0)
        )

        # 보험료 최저 (있는 경우)
        companies_with_premium = {
            c: d for c, d in valid_companies.items()
            if d.get("premium")
        }

        min_premium_company = None
        if companies_with_premium:
            min_premium_company = min(
                companies_with_premium.items(),
                key=lambda x: x[1].get("premium", float('inf'))
            )

        # 추천 메시지 구성
        recommendation = []

        recommendation.append(
            f"{max_amount_company[0]}의 보장금액이 "
            f"{max_amount_company[1]['amount']:,}원으로 가장 높습니다."
        )

        if min_premium_company:
            recommendation.append(
                f"{min_premium_company[0]}의 보험료가 "
                f"{min_premium_company[1]['premium']:,}원으로 가장 저렴합니다."
            )

        return " ".join(recommendation)

    def close(self):
        """리소스 정리"""
        if self.pg_conn:
            self.pg_conn.close()
        if self.retriever:
            self.retriever.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
