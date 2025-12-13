"""
Context Assembly

벡터 검색 결과와 DB 구조화 데이터를 병합하여 LLM에 전달할 컨텍스트를 생성합니다.

주요 기능:
- 벡터 검색 결과 + DB 구조화 데이터 병합
- 중복 제거 및 랭킹
- Citation 매핑 (clause_id, document_id, page)
- LLM 프롬프트용 포맷팅

Usage:
    from retrieval.context_assembly import ContextAssembler

    assembler = ContextAssembler()
    context = assembler.assemble(
        vector_results=retriever_results,
        query="암 진단시 보장금액은?"
    )
"""

import os
import psycopg2
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ContextAssembler:
    """컨텍스트 조립 클래스"""

    def __init__(self, postgres_url: str = None):
        """
        Args:
            postgres_url: PostgreSQL 연결 문자열
        """
        self.postgres_url = postgres_url or os.getenv("POSTGRES_URL")
        if not self.postgres_url:
            raise ValueError("POSTGRES_URL environment variable is required. Check .env file.")
        self.pg_conn = psycopg2.connect(self.postgres_url)

    def assemble(
        self,
        vector_results: List[Dict[str, Any]],
        query: str,
        max_context_length: int = 4000,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        벡터 검색 결과를 LLM용 컨텍스트로 조립합니다.

        Args:
            vector_results: 벡터 검색 결과 리스트
            query: 사용자 질의
            max_context_length: 최대 컨텍스트 길이 (토큰 수)
            include_metadata: 메타데이터 포함 여부

        Returns:
            조립된 컨텍스트 딕셔너리
            {
                "query": str,
                "context_text": str,  # LLM에 전달할 텍스트
                "clauses": List[Dict],  # 조항 정보
                "citations": List[Dict],  # 인용 정보
                "metadata": Dict  # 추가 메타데이터
            }
        """
        # 1. 중복 제거
        unique_results = self._deduplicate(vector_results)

        # 2. 랭킹 (이미 유사도순으로 정렬되어 있음)
        ranked_results = self._rank(unique_results)

        # 3. DB에서 추가 메타데이터 가져오기
        enriched_results = self._enrich_with_metadata(ranked_results)

        # 4. Citation 매핑
        citations = self._build_citations(enriched_results)

        # 5. 컨텍스트 텍스트 생성
        context_text = self._build_context_text(
            enriched_results,
            max_length=max_context_length
        )

        # 6. 메타데이터 수집
        metadata = self._collect_metadata(enriched_results) if include_metadata else {}

        return {
            "query": query,
            "context_text": context_text,
            "clauses": enriched_results,
            "citations": citations,
            "metadata": metadata
        }

    def _deduplicate(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        중복 조항 제거

        Args:
            results: 검색 결과

        Returns:
            중복 제거된 결과
        """
        seen_clause_ids = set()
        unique_results = []

        for result in results:
            clause_id = result.get('clause_id')
            if clause_id not in seen_clause_ids:
                seen_clause_ids.add(clause_id)
                unique_results.append(result)

        return unique_results

    def _rank(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        결과 랭킹 (유사도 + 문서 타입 가중치)

        Args:
            results: 검색 결과

        Returns:
            랭킹된 결과
        """
        # 문서 타입별 가중치 (가입설계서 > 상품요약서 > 사업방법서 > 약관)
        doc_type_weights = {
            '가입설계서': 1.2,    # 구체적인 보장금액, 보험료 정보
            'proposal': 1.2,
            '상품요약서': 1.15,   # 요약된 보장 정보
            'product_summary': 1.15,
            '사업방법서': 1.1,    # 가입 조건, 제약사항
            'business_spec': 1.1,
            '약관': 1.0,          # 일반 조항
            'terms': 1.0
        }

        # 재스코어링 및 정렬
        for result in results:
            original_similarity = result.get('similarity', 0)
            doc_type = result.get('doc_type', '약관')
            weight = doc_type_weights.get(doc_type, 1.0)

            # 가중치 적용한 스코어 계산
            result['weighted_score'] = original_similarity * weight
            result['doc_type_weight'] = weight

        # weighted_score 기준으로 재정렬
        ranked = sorted(results, key=lambda x: x.get('weighted_score', 0), reverse=True)

        return ranked

    def _enrich_with_metadata(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        DB에서 추가 메타데이터를 가져와서 결과를 풍부하게 만듭니다.

        Args:
            results: 검색 결과

        Returns:
            메타데이터가 추가된 결과
        """
        if not results:
            return results

        clause_ids = [r['clause_id'] for r in results]

        with self.pg_conn.cursor() as cur:
            # 조항 상세 정보 + 문서 정보 조회
            cur.execute("""
                SELECT
                    dc.id as clause_id,
                    dc.clause_number,
                    dc.clause_title,
                    dc.section_type,
                    dc.page_number,
                    doc.document_id,
                    doc.doc_type,
                    doc.doc_subtype,
                    c.company_name as company_name,
                    c.company_code as company_code,
                    p.product_name as product_name,
                    p.business_type
                FROM document_clause dc
                JOIN document doc ON dc.document_id = doc.id
                LEFT JOIN company c ON doc.company_id = c.id
                LEFT JOIN product p ON doc.product_id = p.id
                WHERE dc.id = ANY(%s)
            """, (clause_ids,))

            metadata_map = {}
            for row in cur.fetchall():
                metadata_map[row[0]] = {
                    'clause_number': row[1],
                    'clause_title': row[2],
                    'section_type': row[3],
                    'page_number': row[4],
                    'document_id': row[5],
                    'doc_type': row[6],
                    'doc_subtype': row[7],
                    'company_name': row[8],
                    'company_code': row[9],
                    'product_name': row[10],
                    'product_type': row[11]
                }

            # ✨ Context Enrichment: Add coverage/benefit information
            cur.execute("""
                SELECT
                    dc.id as clause_id,
                    c.coverage_name,
                    c.id as coverage_id,
                    b.benefit_amount,
                    b.benefit_type,
                    b.payment_frequency
                FROM document_clause dc
                LEFT JOIN clause_coverage cc ON dc.id = cc.clause_id
                LEFT JOIN coverage c ON cc.coverage_id = c.id
                LEFT JOIN benefit b ON c.id = b.coverage_id
                WHERE dc.id = ANY(%s)
                  AND c.coverage_name IS NOT NULL
            """, (clause_ids,))

            # Store coverage/benefit info (can have multiple per clause)
            coverage_map = {}
            for row in cur.fetchall():
                clause_id = row[0]
                if clause_id not in coverage_map:
                    coverage_map[clause_id] = []

                coverage_info = {
                    'coverage_name': row[1],
                    'coverage_id': row[2],
                    'benefit_amount': row[3],
                    'benefit_type': row[4],
                    'payment_frequency': row[5]
                }
                coverage_map[clause_id].append(coverage_info)

        # 결과에 메타데이터 병합
        enriched = []
        for result in results:
            clause_id = result['clause_id']
            if clause_id in metadata_map:
                enriched_result = {**result, **metadata_map[clause_id]}

                # Add coverage/benefit info if available
                if clause_id in coverage_map:
                    enriched_result['coverages'] = coverage_map[clause_id]

                enriched.append(enriched_result)
            else:
                # Even if no metadata, add coverage info if available
                enriched_result = {**result}
                if clause_id in coverage_map:
                    enriched_result['coverages'] = coverage_map[clause_id]
                enriched.append(enriched_result)

        return enriched

    def _build_citations(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """
        Citation 정보 생성

        Args:
            results: 검색 결과

        Returns:
            Citation 리스트
        """
        citations = []
        for i, result in enumerate(results, 1):
            citation = {
                'index': i,
                'clause_id': result.get('clause_id'),
                'clause_number': result.get('clause_number', 'N/A'),
                'clause_title': result.get('clause_title', ''),
                'document_id': result.get('document_id', 'N/A'),
                'doc_type': result.get('doc_type', 'N/A'),
                'page_number': result.get('page_number'),
                'company_name': result.get('company_name', 'N/A'),
                'product_name': result.get('product_name', 'N/A')
            }
            citations.append(citation)

        return citations

    def _build_context_text(
        self,
        results: List[Dict[str, Any]],
        max_length: int = 4000
    ) -> str:
        """
        LLM에 전달할 컨텍스트 텍스트 생성

        Args:
            results: 검색 결과
            max_length: 최대 길이 (대략적인 문자 수)

        Returns:
            컨텍스트 텍스트
        """
        context_parts = []
        current_length = 0

        for i, result in enumerate(results, 1):
            # Citation 헤더
            citation_header = f"[{i}] {result.get('clause_number', 'N/A')}"
            if result.get('clause_title'):
                citation_header += f" {result['clause_title']}"
            citation_header += f"\n출처: {result.get('doc_type', 'N/A')}"
            if result.get('company_name'):
                citation_header += f" ({result['company_name']})"
            if result.get('page_number'):
                citation_header += f" - 페이지 {result['page_number']}"

            # 조항 내용
            clause_text = result.get('clause_text', '')

            # ✨ Coverage/Benefit 정보 추가 (Phase 5 v5: Enhanced amount formatting)
            coverage_text = ""
            if 'coverages' in result and result['coverages']:
                coverage_text = "\n📋 보장 정보:\n"
                for cov in result['coverages']:
                    coverage_text += f"  - 담보명: {cov.get('coverage_name', 'N/A')}\n"
                    if cov.get('benefit_amount'):
                        # Format amount in both numeric and Korean formats
                        # Phase 5 v5: Prioritize numeric format for better LLM extraction
                        amount = float(cov['benefit_amount'])

                        # Numeric format with commas (e.g., "1,000만원", "5,000만원")
                        if amount >= 100000000:  # 1억 이상
                            man_units = int(amount / 10000)  # Convert to 만원
                            amount_numeric = f"{man_units:,}만원"  # With commas
                            amount_kr = f"{amount/100000000:.0f}억원"
                        elif amount >= 10000:  # 1만 이상
                            man_units = int(amount / 10000)
                            amount_numeric = f"{man_units:,}만원"  # e.g., "1,000만원"
                            amount_kr = f"{amount/10000:.0f}만원"  # e.g., "1000만원"
                        else:
                            amount_numeric = f"{amount:,.0f}원"
                            amount_kr = f"{amount:.0f}원"

                        # Highlight numeric format, show Korean format in parentheses
                        coverage_text += f"    💰 보장금액: **{amount_numeric}** ({amount_kr})\n"
                    if cov.get('benefit_type'):
                        type_kr = {
                            'diagnosis': '진단',
                            'surgery': '수술',
                            'hospitalization': '입원',
                            'treatment': '치료',
                            'death': '사망',
                            'other': '기타'
                        }.get(cov['benefit_type'], cov['benefit_type'])
                        coverage_text += f"    보장유형: {type_kr}\n"

            # 전체 항목
            item = f"{citation_header}\n{clause_text}{coverage_text}\n\n"

            # 길이 체크
            if current_length + len(item) > max_length:
                break

            context_parts.append(item)
            current_length += len(item)

        return "".join(context_parts)

    def _collect_metadata(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        추가 메타데이터 수집

        Args:
            results: 검색 결과

        Returns:
            메타데이터 딕셔너리
        """
        if not results:
            return {}

        # 회사 및 상품 정보 수집
        companies = set()
        products = set()
        doc_types = set()

        for result in results:
            if result.get('company_name'):
                companies.add(result['company_name'])
            if result.get('product_name'):
                products.add(result['product_name'])
            if result.get('doc_type'):
                doc_types.add(result['doc_type'])

        return {
            'num_clauses': len(results),
            'companies': list(companies),
            'products': list(products),
            'doc_types': list(doc_types),
            'avg_similarity': sum(r.get('similarity', 0) for r in results) / len(results) if results else 0
        }

    def close(self):
        """PostgreSQL 연결 종료"""
        if self.pg_conn:
            self.pg_conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
