"""
CLI Interface for Insurance Ontology Hybrid RAG

Provides command-line interface for:
- Hybrid RAG queries (NL mapping → vector search → LLM)
- Vector search only
- Plan validation
- Document listing

Usage:
    python -m api.cli hybrid "암 진단시 보장금액은?"
    python -m api.cli search "암 진단" --limit 5
    python -m api.cli docs --limit 10
    python -m api.cli plan-report --company 삼성화재 --product "..." --format text
"""

import argparse
import json
import sys
import os
from typing import Dict, Any, Optional, List
import psycopg2
from dotenv import load_dotenv

# Import our modules
from retrieval.hybrid_retriever import HybridRetriever
from retrieval.context_assembly import ContextAssembler
from retrieval.prompts import PromptBuilder
from ontology.nl_mapping import NLMapper
from retrieval.llm_client import LLMClient

# Load environment variables
load_dotenv()


class InsuranceCLI:
    """CLI 인터페이스 클래스"""

    def __init__(self):
        """Initialize CLI with database connections"""
        self.postgres_url = os.getenv("POSTGRES_URL")
        if not self.postgres_url:
            raise ValueError("POSTGRES_URL environment variable is required. Check .env file.")
        self.retriever = HybridRetriever(postgres_url=self.postgres_url)
        self.assembler = ContextAssembler(postgres_url=self.postgres_url)
        self.prompt_builder = PromptBuilder()
        self.nl_mapper = NLMapper(postgres_url=self.postgres_url)
        backend = os.getenv("LLM_BACKEND", "ollama")
        # Backend에 따라 적절한 model 환경변수 선택
        if backend == "openai":
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        else:
            model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
        self.llm_client = LLMClient(backend=backend, model=model)
        self.pg_conn = psycopg2.connect(self.postgres_url)

    def hybrid_query(
        self,
        query: str,
        limit: int = 5,
        response_format: str = "text",
        use_llm: bool = True
    ) -> Dict[str, Any]:
        """
        Hybrid RAG 파이프라인 실행

        Args:
            query: 자연어 질의
            limit: 반환할 조항 개수
            response_format: 응답 포맷 ("text" or "json")
            use_llm: LLM 사용 여부

        Returns:
            결과 딕셔너리
        """
        print(f"🔍 Query: {query}\n")

        # 0. NL Mapping (extract entities)
        print("🧠 Step 0/3: Entity extraction...")
        entities = self.nl_mapper.extract_entities(query)
        if entities.get("companies"):
            print(f"   Companies: {', '.join(entities['companies'])}")
        if entities.get("products"):
            print(f"   Products: {', '.join(entities['products'])}")
        if entities.get("coverages"):
            print(f"   Coverages: {', '.join(entities['coverages'])}")
        print()

        # 1. Vector search (with entity filters)
        print("📊 Step 1/3: Vector search...")

        # 비교 쿼리 감지: 회사가 2개 이상이고 비교 키워드가 있는 경우
        comparison_keywords = ["비교", "차이", "vs", "VS", "와", "과"]
        companies = entities.get("companies", [])
        is_comparison_query = (
            len(companies) >= 2 and
            any(kw in query for kw in comparison_keywords)
        )

        if is_comparison_query:
            # 비교 쿼리: 각 회사별로 개별 검색 후 병합
            print(f"   🔄 Comparison mode: searching {len(companies)} companies...")
            coverage_keywords = entities.get("coverages", [])
            coverage_name = coverage_keywords[0] if coverage_keywords else ""

            # 키워드 추출 (담보/보장 관련)
            for kw in ["입원", "수술", "진단", "암", "뇌출혈", "뇌졸중", "심근경색", "골절"]:
                if kw in query and kw not in coverage_name:
                    coverage_name = kw if not coverage_name else f"{coverage_name} {kw}"

            results_by_company = self.retriever.search_multi_company(
                query=query,
                company_names=companies,
                coverage_name=coverage_name,
                top_k=limit,
                search_top_k=30
            )

            # 결과 병합 (각 회사별 top 결과를 교차 배치)
            vector_results = []
            max_results = max(len(v) for v in results_by_company.values()) if results_by_company else 0
            for i in range(min(max_results, limit)):
                for company_name, results in results_by_company.items():
                    if i < len(results) and len(vector_results) < limit:
                        vector_results.append(results[i])

            print(f"   Found results from: {', '.join(k for k, v in results_by_company.items() if v)}")
        else:
            # 일반 쿼리: 기존 검색 방식
            vector_results = self.retriever.search(
                query=query,
                top_k=limit
            )

        print(f"   Found {len(vector_results)} relevant clauses\n")

        # 2. Context assembly
        print("🔧 Step 2/3: Assembling context...")
        context = self.assembler.assemble(
            vector_results=vector_results,
            query=query,
            max_context_length=4000,
            include_metadata=True
        )
        print(f"   Context: {len(context['context_text'])} chars")
        print(f"   Products: {', '.join(context['metadata'].get('products', []))}\n")

        if not use_llm:
            return {
                "query": query,
                "context": context,
                "answer": None,
                "metadata": context['metadata']
            }

        # 3. LLM generation
        print("🤖 Step 3/3: Generating answer with LLM...")
        prompt = self.prompt_builder.build_qa_prompt(
            query=query,
            context=context['context_text'],
            response_format=response_format
        )

        # For now, return the prompt (LLM integration pending)
        # TODO: Integrate with OpenAI API or local LLM
        answer = self._call_llm(prompt, response_format)

        return {
            "query": query,
            "answer": answer,
            "context": context,
            "metadata": context['metadata']
        }

    def _call_llm(self, prompt: str, response_format: str = "text") -> str:
        """
        Call LLM API (Ollama or OpenAI)

        Args:
            prompt: LLM 프롬프트
            response_format: 응답 포맷

        Returns:
            LLM 응답
        """
        # LLM 가용성 확인
        if not self.llm_client.is_available():
            backend = self.llm_client.backend
            if backend == "ollama":
                return f"⚠️ Ollama 서버에 연결할 수 없습니다.\n\n다음 명령으로 Ollama를 시작하세요:\n  ollama serve\n\n그리고 qwen3:8b 모델을 다운로드하세요:\n  ollama pull qwen3:8b"
            else:
                return f"⚠️ {backend} LLM을 사용할 수 없습니다."

        try:
            print(f"   Using LLM: {self.llm_client.backend}/{self.llm_client.model}")

            # 스트리밍 여부 설정
            stream = os.getenv("LLM_STREAM", "false").lower() == "true"

            response = self.llm_client.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=1000,  # 2000 → 1000 for faster response
                stream=stream
            )

            return response

        except Exception as e:
            return f"⚠️ LLM 호출 중 오류 발생: {e}\n\nPrompt preview:\n{prompt[:500]}..."

    def vector_search(self, query: str, limit: int = 5) -> list:
        """
        벡터 검색만 수행

        Args:
            query: 검색 질의
            limit: 결과 개수

        Returns:
            검색 결과 리스트
        """
        print(f"🔍 Vector search: {query}\n")
        results = self.retriever.search(query, top_k=limit)

        print(f"Found {len(results)} results:\n")
        for i, result in enumerate(results, 1):
            print(f"[{i}] {result.get('clause_number', 'N/A')} - {result.get('clause_title', '')}")
            print(f"    Similarity: {result.get('similarity', 0):.4f}")
            print(f"    Product: {result.get('product_name', 'N/A')}")
            print(f"    Text: {result.get('clause_text', '')[:100]}...")
            print()

        return results

    def list_documents(self, limit: int = 10, doc_type: str = None) -> list:
        """
        문서 목록 조회

        Args:
            limit: 결과 개수
            doc_type: 문서 타입 필터

        Returns:
            문서 리스트
        """
        with self.pg_conn.cursor() as cur:
            if doc_type:
                cur.execute("""
                    SELECT
                        doc.document_id,
                        doc.doc_type,
                        doc.doc_subtype,
                        c.name as company_name,
                        p.name as product_name,
                        doc.version,
                        doc.created_at,
                        COUNT(dc.id) as clause_count
                    FROM document doc
                    LEFT JOIN company c ON doc.company_id = c.id
                    LEFT JOIN product p ON doc.product_id = p.id
                    LEFT JOIN document_clause dc ON doc.id = dc.document_id
                    WHERE doc.doc_type = %s
                    GROUP BY doc.id, c.name, p.name
                    ORDER BY doc.created_at DESC
                    LIMIT %s
                """, (doc_type, limit))
            else:
                cur.execute("""
                    SELECT
                        doc.document_id,
                        doc.doc_type,
                        doc.doc_subtype,
                        c.name as company_name,
                        p.name as product_name,
                        doc.version,
                        doc.created_at,
                        COUNT(dc.id) as clause_count
                    FROM document doc
                    LEFT JOIN company c ON doc.company_id = c.id
                    LEFT JOIN product p ON doc.product_id = p.id
                    LEFT JOIN document_clause dc ON doc.id = dc.document_id
                    GROUP BY doc.id, c.name, p.name
                    ORDER BY doc.created_at DESC
                    LIMIT %s
                """, (limit,))

            results = cur.fetchall()

        print(f"📄 Found {len(results)} documents:\n")
        for row in results:
            doc_id, doc_type, doc_subtype, company, product, version, date, clause_count = row
            print(f"• {doc_id}")
            print(f"  Type: {doc_type}" + (f" ({doc_subtype})" if doc_subtype else ""))
            print(f"  Company: {company or 'N/A'}, Product: {product or 'N/A'}")
            print(f"  Version: {version}, Date: {date}")
            print(f"  Clauses: {clause_count}")
            print()

        return results

    def plan_validation_report(
        self,
        company: str,
        product: str,
        plan_data: Dict[str, Any] = None,
        output_format: str = "text"
    ) -> str:
        """
        가입설계서 검증 리포트 생성

        Args:
            company: 회사명
            product: 상품명
            plan_data: 설계서 데이터 (미제공시 샘플 사용)
            output_format: 출력 포맷 ("text" or "json")

        Returns:
            검증 리포트
        """
        print(f"📋 Generating plan validation report...")
        print(f"   Company: {company}")
        print(f"   Product: {product}\n")

        # Fetch business spec constraints
        constraints = self._fetch_business_spec_constraints(company, product)

        if not constraints:
            return f"⚠️ No business spec found for {company} - {product}"

        # Use sample plan data if not provided
        if not plan_data:
            plan_data = {
                "age": 35,
                "gender": "M",
                "insurance_period": 20,
                "payment_period": 10,
                "coverages": [
                    {"name": "암진단금", "amount": 50000000},
                    {"name": "뇌출혈진단금", "amount": 30000000}
                ]
            }

        # Build validation prompt
        prompt = self.prompt_builder.build_validation_prompt(
            plan_data=plan_data,
            constraints=constraints
        )

        # Call LLM for validation
        validation_result = self._call_llm(prompt, response_format=output_format)

        print("✅ Validation complete\n")
        return validation_result

    def _fetch_business_spec_constraints(
        self,
        company: str,
        product: str
    ) -> str:
        """
        사업방법서 제약 조건 조회

        Args:
            company: 회사명
            product: 상품명

        Returns:
            제약 조건 텍스트
        """
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT dc.clause_text
                FROM document_clause dc
                JOIN document doc ON dc.document_id = doc.id
                JOIN company c ON doc.company_id = c.id
                JOIN product p ON doc.product_id = p.id
                WHERE doc.doc_type = 'business_spec'
                  AND c.name = %s
                  AND p.name = %s
                  AND dc.section_type IN ('가입조건', '담보내용', '보험금지급')
                ORDER BY dc.page_number, dc.clause_number
            """, (company, product))

            results = cur.fetchall()

        if not results:
            return ""

        constraints = "\n\n".join([row[0] for row in results])
        return constraints

    def compare_products(
        self,
        companies: List[str],
        coverage: str,
        output_format: str = "text"
    ) -> Dict[str, Any]:
        """
        상품 비교 실행

        Args:
            companies: 비교할 보험사 리스트
            coverage: 담보명
            output_format: 출력 포맷 ("text" or "json")

        Returns:
            비교 결과 딕셔너리
        """
        from api.compare import ProductComparer

        print(f"🔍 상품 비교: {', '.join(companies)} - {coverage}\n")

        # ProductComparer 초기화
        comparer = ProductComparer(
            postgres_url=self.postgres_url,
            hybrid_retriever=self.retriever
        )

        # 비교 실행
        result = comparer.compare_products(
            companies=companies,
            coverage=coverage,
            include_sources=True,
            include_recommendation=True
        )

        # 출력 포맷팅
        if output_format == "json":
            return result

        # Text 포맷 출력
        print("=" * 80)
        print(f"상품 비교 결과: {coverage}")
        print("=" * 80)
        print()

        # 비교 테이블 출력
        comparison = result.get("comparison", {})

        # 헤더
        header = f"{'항목':<20} | " + " | ".join([f"{c:<25}" for c in companies])
        print(header)
        print("-" * len(header))

        # 상품명
        product_names = [
            comparison.get(c, {}).get("productName", "N/A")
            for c in companies
        ]
        print(f"{'상품명':<20} | " + " | ".join([f"{p:<25}" for p in product_names]))

        # 담보명
        coverage_names = [
            comparison.get(c, {}).get("coverageName", "N/A")
            for c in companies
        ]
        print(f"{'담보명':<20} | " + " | ".join([f"{c:<25}" for c in coverage_names]))

        # 보장금액
        amounts = []
        for c in companies:
            amount = comparison.get(c, {}).get("amount")
            if amount:
                amounts.append(f"{amount:,}원")
            else:
                amounts.append("N/A")
        print(f"{'보장금액':<20} | " + " | ".join([f"{a:<25}" for a in amounts]))

        # 보험료
        premiums = []
        for c in companies:
            premium = comparison.get(c, {}).get("premium")
            if premium:
                premiums.append(f"{premium:,}원")
            else:
                premiums.append("N/A")
        print(f"{'월보험료':<20} | " + " | ".join([f"{p:<25}" for p in premiums]))

        # 유사도 (참고)
        similarities = [
            f"{comparison.get(c, {}).get('similarity', 0):.4f}"
            for c in companies
        ]
        print(f"{'유사도':<20} | " + " | ".join([f"{s:<25}" for s in similarities]))

        print()

        # 추천
        recommendation = result.get("recommendation")
        if recommendation:
            print("💡 추천:")
            print(f"   {recommendation}")
            print()

        # 출처
        print("📄 출처:")
        for company in companies:
            sources = comparison.get(company, {}).get("sources", [])
            if sources:
                print(f"\n   {company}:")
                for source in sources[:3]:
                    doc_type = source.get("docType", "unknown")
                    clause_id = source.get("clauseId", "N/A")
                    print(f"   • {doc_type} (clause_id: {clause_id})")

        print()
        print("=" * 80)

        return result

    def close(self):
        """리소스 정리"""
        if self.pg_conn:
            self.pg_conn.close()
        if self.assembler:
            self.assembler.close()
        if self.nl_mapper:
            self.nl_mapper.close()


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Insurance Ontology Hybrid RAG CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Hybrid RAG query
  python -m api.cli hybrid "암 진단시 보장금액은?"

  # Hybrid query with JSON output
  python -m api.cli hybrid "뇌출혈 보장 조건" --format json

  # Vector search only
  python -m api.cli search "암 진단" --limit 5

  # List all documents
  python -m api.cli docs --limit 10

  # List only terms documents
  python -m api.cli docs --type terms --limit 5

  # Generate plan validation report
  python -m api.cli plan-report --company 삼성화재 --product "마이헬스 1종" --format text
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Hybrid command
    hybrid_parser = subparsers.add_parser("hybrid", help="Hybrid RAG query")
    hybrid_parser.add_argument("query", type=str, help="Natural language query")
    hybrid_parser.add_argument("--limit", type=int, default=5, help="Number of results")
    hybrid_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Response format"
    )
    hybrid_parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM generation (context only)"
    )

    # Search command
    search_parser = subparsers.add_parser("search", help="Vector search only")
    search_parser.add_argument("query", type=str, help="Search query")
    search_parser.add_argument("--limit", type=int, default=5, help="Number of results")

    # Docs command
    docs_parser = subparsers.add_parser("docs", help="List documents")
    docs_parser.add_argument("--limit", type=int, default=10, help="Number of documents")
    docs_parser.add_argument(
        "--type",
        choices=["terms", "business_spec", "product_summary", "proposal"],
        help="Filter by document type"
    )

    # Plan report command
    plan_parser = subparsers.add_parser("plan-report", help="Generate plan validation report")
    plan_parser.add_argument("--company", type=str, required=True, help="Company name")
    plan_parser.add_argument("--product", type=str, required=True, help="Product name")
    plan_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format"
    )

    # Compare command (NEW - Phase 6.1)
    compare_parser = subparsers.add_parser("compare", help="Compare products across companies")
    compare_parser.add_argument(
        "--companies",
        type=str,
        required=True,
        help="Comma-separated company names (e.g., '삼성화재,DB손보')"
    )
    compare_parser.add_argument(
        "--coverage",
        type=str,
        required=True,
        help="Coverage name to compare (e.g., '암진단')"
    )
    compare_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Initialize CLI
    cli = InsuranceCLI()

    try:
        if args.command == "hybrid":
            result = cli.hybrid_query(
                query=args.query,
                limit=args.limit,
                response_format=args.format,
                use_llm=not args.no_llm
            )

            if args.format == "json":
                print("\n📄 Result (JSON):")
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print("\n📄 Answer:")
                print(result.get("answer", "No answer generated"))
                print("\n📊 Metadata:")
                print(f"   Products: {', '.join(result['metadata'].get('products', []))}")
                print(f"   Clauses: {result['metadata'].get('num_clauses', 0)}")
                print(f"   Avg Similarity: {result['metadata'].get('avg_similarity', 0):.4f}")

        elif args.command == "search":
            cli.vector_search(query=args.query, limit=args.limit)

        elif args.command == "docs":
            cli.list_documents(limit=args.limit, doc_type=args.type)

        elif args.command == "plan-report":
            report = cli.plan_validation_report(
                company=args.company,
                product=args.product,
                output_format=args.format
            )
            print(report)

        elif args.command == "compare":
            # Parse companies (comma-separated)
            companies = [c.strip() for c in args.companies.split(',')]

            result = cli.compare_products(
                companies=companies,
                coverage=args.coverage,
                output_format=args.format
            )

            if args.format == "json":
                print(json.dumps(result, ensure_ascii=False, indent=2))

    finally:
        cli.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
