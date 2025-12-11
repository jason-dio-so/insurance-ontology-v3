"""
FastAPI Server for Insurance Ontology Hybrid RAG

Provides REST API endpoints for:
- Hybrid search with user profile
- Product comparison
- Chat interface

Usage:
    uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import os
from dotenv import load_dotenv

# Import existing retrieval modules
from retrieval.hybrid_retriever import HybridRetriever
from retrieval.context_assembly import ContextAssembler
from retrieval.prompts import PromptBuilder
from ontology.nl_mapping import NLMapper
from retrieval.llm_client import LLMClient

load_dotenv()

app = FastAPI(
    title="Insurance Ontology API",
    description="Hybrid RAG system for Korean insurance documents",
    version="1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative frontend port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== Request/Response Models ==========

class UserProfile(BaseModel):
    """사용자 프로필"""
    birthDate: str = Field(..., description="생년월일 (YYYY-MM-DD)")
    gender: str = Field(..., description="성별 (male/female)")
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    occupation: Optional[str] = None
    isSmoker: Optional[bool] = None
    hasPreexistingConditions: Optional[bool] = None


class ComparisonResult(BaseModel):
    """상품 비교 결과"""
    company: str
    product: str
    coverage: str
    benefit: str
    premium: Optional[str] = None
    notes: Optional[str] = None


class HybridSearchRequest(BaseModel):
    """하이브리드 검색 요청"""
    query: str = Field(..., description="사용자 질문")
    userProfile: Optional[UserProfile] = None
    selectedCategories: Optional[List[str]] = None
    selectedCoverageTags: Optional[List[str]] = None
    lastCoverage: Optional[str] = Field(None, description="이전 대화에서 언급된 담보명 (컨텍스트 유지용)")


class HybridSearchResponse(BaseModel):
    """하이브리드 검색 응답"""
    answer: str
    comparisonTable: Optional[List[ComparisonResult]] = None
    sources: Optional[List[Dict[str, Any]]] = None
    coverage: Optional[str] = Field(None, description="이번 응답에서 사용된 담보명 (다음 요청 시 컨텍스트로 전달)")


class CompareRequest(BaseModel):
    """상품 비교 요청"""
    productIds: List[str]
    userProfile: Optional[UserProfile] = None


# ========== Helper Functions ==========

def calculate_age(birth_date_str: str) -> int:
    """생년월일로부터 나이 계산"""
    try:
        birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
        today = date.today()
        age = today.year - birth_date.year
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1
        return age
    except Exception:
        return None


def format_comparison_table(clauses: List[Dict], nl_entities: Dict) -> List[ComparisonResult]:
    """검색 결과를 비교 테이블로 변환"""
    comparison_results = []
    seen_coverages = set()

    for clause in clauses[:10]:  # Top 10 results
        # Use enriched metadata from context_assembly
        company = clause.get("company_name", "N/A")
        product = clause.get("product_name", "N/A")

        # Get coverage info from clause_title or clause_number
        coverage_name = clause.get("clause_title", clause.get("clause_number", ""))

        # Avoid duplicates
        key = f"{company}_{product}_{coverage_name}"
        if key in seen_coverages:
            continue
        seen_coverages.add(key)

        # Extract benefit amount from clause text
        clause_text = clause.get("clause_text", "")
        benefit = extract_benefit_amount(clause_text)

        comparison_results.append(ComparisonResult(
            company=company,
            product=product,
            coverage=coverage_name or "일반보장",
            benefit=benefit,
            premium=None,  # Premium calculation would require more data
            notes=f"조항 [{clause.get('clause_number', 'N/A')}]"
        ))

    return comparison_results


def extract_benefit_amount(text: str) -> str:
    """조항 텍스트에서 보장 금액 추출 (간단한 패턴 매칭)"""
    import re

    # Pattern: "3,000만원", "5천만원", "100만원" etc.
    patterns = [
        r'(\d{1,3}(?:,\d{3})*)\s*만원',
        r'(\d+)\s*천만원',
        r'(\d+)\s*억원?',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)

    return "보장금액 확인 필요"


# ========== Global Instances ==========

retriever: Optional[HybridRetriever] = None
assembler: Optional[ContextAssembler] = None
prompt_builder: Optional[PromptBuilder] = None
nl_mapper: Optional[NLMapper] = None
llm_client: Optional[LLMClient] = None


@app.on_event("startup")
async def startup_event():
    """서버 시작 시 초기화"""
    global retriever, assembler, prompt_builder, nl_mapper, llm_client

    postgres_url = os.getenv(
        "POSTGRES_URL",
        "postgresql://postgres:postgres@localhost:5432/insurance_ontology"
    )

    retriever = HybridRetriever(postgres_url=postgres_url)
    assembler = ContextAssembler(postgres_url=postgres_url)
    prompt_builder = PromptBuilder()
    nl_mapper = NLMapper(postgres_url=postgres_url)
    # LLM client initialization - model selection based on backend
    backend = os.getenv("LLM_BACKEND", "ollama")
    if backend == "openai":
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    else:
        model = os.getenv("OLLAMA_MODEL", "qwen3:8b")

    llm_client = LLMClient(backend=backend, model=model)

    print("✅ Insurance Ontology API initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 정리"""
    print("🔴 Insurance Ontology API shutting down")


# ========== API Endpoints ==========

@app.get("/")
async def root():
    """헬스 체크 엔드포인트"""
    return {
        "service": "Insurance Ontology API",
        "version": "1.0.0",
        "status": "healthy"
    }


@app.get("/health")
async def health_check():
    """상세 헬스 체크"""
    return {
        "status": "healthy",
        "postgres": "connected" if retriever else "disconnected",
        "llm": os.getenv("LLM_BACKEND", "ollama"),
        "vector_backend": os.getenv("VECTOR_BACKEND", "pgvector")
    }


@app.post("/api/test-search")
async def test_search(query: str = "삼성 암진단비"):
    """디버깅용 간단한 검색 테스트"""
    if not retriever:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # Simple search without filters
        results = retriever.search(query=query, top_k=5, filters={})

        return {
            "query": query,
            "result_count": len(results),
            "results": results[:3]  # First 3 results
        }
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.post("/api/hybrid-search", response_model=HybridSearchResponse)
async def hybrid_search(request: HybridSearchRequest):
    """
    하이브리드 검색 (온톨로지 매핑 + 벡터 검색 + LLM 응답)

    1. NL 매퍼로 엔티티 추출 (회사명, 보장 타입, 금액 등)
    2. 온톨로지 필터 + 벡터 검색으로 관련 조항 검색
    3. LLM으로 자연어 응답 생성
    4. 비교 테이블 생성 (상품/보장 비교)
    """
    if not all([retriever, nl_mapper, llm_client]):
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # 1. Extract age from user profile
        age = None
        gender = None
        if request.userProfile:
            age = calculate_age(request.userProfile.birthDate)
            gender = request.userProfile.gender

        # 2. NL Mapping: Extract entities from query
        nl_entities = nl_mapper.extract_entities(request.query)

        # 3. Enhance entities with user context
        if age:
            nl_entities["user_age"] = age
        if gender:
            nl_entities["user_gender"] = gender
        if request.selectedCoverageTags:
            nl_entities["coverage_tags"] = request.selectedCoverageTags

        # 4. Check if it's a multi-company comparison query
        company_names_in_query = nl_entities.get("entities", {}).get("companies", [])
        print(f"[DEBUG] NL entities: {nl_entities}")
        print(f"[DEBUG] Extracted companies: {company_names_in_query}")

        # Extract coverage names from NL mapper first
        coverages_from_nl = nl_entities.get("coverages", [])
        print(f"[DEBUG] Extracted coverages: {coverages_from_nl}")

        # Clean and filter coverages: remove leading "- " or numbers, and deduplicate
        valid_coverages = []
        seen = set()
        for c in coverages_from_nl:
            if not c:
                continue
            # Remove leading "- " prefix
            cleaned = c.strip()
            if cleaned.startswith("- "):
                cleaned = cleaned[2:].strip()
            # Skip if starts with number (likely ID)
            if cleaned and cleaned[0].isdigit():
                continue
            # Deduplicate
            if cleaned not in seen:
                valid_coverages.append(cleaned)
                seen.add(cleaned)

        # Fallback: Extract coverage name from query (simple heuristic)
        if not valid_coverages:
            coverage_keywords = ["암진단", "수술", "입원", "통원", "치료비", "유사암", "제자리암", "경계성종양"]
            for keyword in coverage_keywords:
                if keyword in request.query:
                    valid_coverages = [keyword]
                    break

        # If still not found, use lastCoverage from previous conversation
        if not valid_coverages and request.lastCoverage:
            valid_coverages = [request.lastCoverage]
            print(f"[DEBUG] Using lastCoverage from context: {request.lastCoverage}")

        # If multiple companies mentioned or comparison intent detected, use ProductComparer
        if len(company_names_in_query) >= 2 and valid_coverages:
            # Multi-company comparison using ProductComparer (Phase 6.1)
            print(f"[DEBUG] ProductComparer: {company_names_in_query}, coverages: {valid_coverages}")

            from api.compare import ProductComparer
            comparer = ProductComparer(hybrid_retriever=retriever)

            try:
                comparison_result = comparer.compare_products(
                    companies=company_names_in_query,
                    coverage=valid_coverages,  # Pass list of coverages
                    include_sources=True,
                    include_recommendation=True
                )

                # Convert ProductComparer result to HybridSearchResponse format
                coverages_list = comparison_result["coverages"]
                answer_parts = []
                comparison_table_data = []

                # Group by coverage and build sections
                for cov in coverages_list:
                    answer_parts.append(f"\n# {cov} 비교\n")

                    # Collect data for this coverage across companies
                    for company in company_names_in_query:
                        key = f"{company}_{cov}"
                        data = comparison_result["comparison"].get(key, {})

                        if data.get("status") == "no_data":
                            answer_parts.append(f"\n**{company}**: {data.get('message', '데이터 없음')}")
                            continue

                        # Build answer text
                        product_name = data.get("productName", "N/A")
                        coverage_name_full = data.get("coverageName", cov)
                        amount = data.get("amount", 0)
                        amount_str = f"{int(amount):,}원" if amount else "N/A"

                        answer_parts.append(f"\n**{company}** ({product_name})")
                        answer_parts.append(f"- 담보: {coverage_name_full}")
                        answer_parts.append(f"- 보장금액: {amount_str}")

                        # Build comparison table row
                        comparison_table_data.append({
                            "company": company,
                            "product": product_name,
                            "coverage": coverage_name_full,
                            "benefit": amount_str
                        })

                # 주요 차이점 분석
                answer_parts.append("\n\n## 주요 차이점")

                # Analyze differences per coverage
                for cov in coverages_list:
                    valid_data = {}
                    for company in company_names_in_query:
                        key = f"{company}_{cov}"
                        data = comparison_result["comparison"].get(key, {})
                        if data.get("status") != "no_data":
                            valid_data[company] = data

                    if len(valid_data) >= 2:
                        answer_parts.append(f"\n### {cov}")
                        # 보장금액 비교 (None을 0으로 처리)
                        amounts = [(k, v.get("amount") or 0) for k, v in valid_data.items()]
                        amounts.sort(key=lambda x: x[1], reverse=True)

                        if amounts[0][1] != amounts[1][1]:
                            diff = amounts[0][1] - amounts[1][1]
                            answer_parts.append(f"- **보장금액**: {amounts[0][0]}이(가) {amounts[1][0]}보다 {int(diff):,}원 더 높습니다.")
                        else:
                            answer_parts.append(f"- **보장금액**: 모든 상품이 동일한 보장금액을 제공합니다 ({int(amounts[0][1]):,}원)")

                # 종합 판단
                if comparison_result.get("recommendation"):
                    answer_parts.append(f"\n\n## 종합 판단\n{comparison_result['recommendation']}")

                llm_answer = "\n".join(answer_parts)

                # Format sources from ProductComparer
                sources = []
                for key, data in comparison_result["comparison"].items():
                    if "sources" in data:
                        company = data.get("company", "")
                        for src in data["sources"]:
                            sources.append({
                                "company": src.get("company", company),
                                "product": src.get("product", data.get("productName", "")),
                                "clause": src.get("clause", "")[:150],
                                "docType": src.get("docType", "")
                            })

                return HybridSearchResponse(
                    answer=llm_answer,
                    comparisonTable=comparison_table_data if comparison_table_data else None,
                    sources=sources[:5] if sources else None,
                    coverage=", ".join(coverages_list)  # Join multiple coverages
                )

            except Exception as e:
                print(f"[ERROR] ProductComparer failed: {e}")
                import traceback
                traceback.print_exc()
                # Fallback to original multi-company search
                results_by_company = retriever.search_multi_company(
                    query=request.query,
                    company_names=company_names_in_query,
                    coverage_name=valid_coverages[0] if valid_coverages else None,
                    top_k=5,
                    search_top_k=20
                )

                # Flatten results
                retrieved_clauses = []
                for company, company_results in results_by_company.items():
                    print(f"[DEBUG] {company}: {len(company_results)} results")
                    retrieved_clauses.extend(company_results)

                print(f"[DEBUG] Total retrieved_clauses: {len(retrieved_clauses)}")
        else:
            # 4. Hybrid retrieval (single company or general search)
            # Build filters from NL entities
            filters = nl_entities.get("filters", {}).copy()  # Use filters from NL mapper
            if age:
                filters["age"] = {"exact": age}  # Age filter needs dict format
            if gender:
                filters["gender"] = gender

            print(f"[DEBUG] Single company search, filters: {filters}")

            # NOTE: clause_embedding metadata doesn't have company_id, only product_id
            # So company_id filter won't work. We need to use product_id instead.
            # For now, just do general vector search without company filter
            # TODO: Add company_id to clause_embedding metadata OR convert company_id to product_ids

            print(f"[DEBUG] Using general search (coverage_ids ignored due to NL mapper inaccuracy)")
            retrieved_clauses = retriever.search(
                query=request.query,
                top_k=20,
                filters={}  # Empty filters for now - metadata doesn't support company_id
            )

            print(f"[DEBUG] Retrieved {len(retrieved_clauses)} clauses")

        # 5. Fallback: Query coverage/benefit data directly
        fallback_context = ""
        if nl_entities.get("coverage_keywords"):
            coverage_kw = nl_entities["coverage_keywords"][0] if nl_entities["coverage_keywords"] else ""
            company_names = nl_entities.get("company_names", [])

            if coverage_kw and company_names:
                import psycopg2
                conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
                try:
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT
                            comp.company_name,
                            p.product_name,
                            cov.coverage_name,
                            b.benefit_amount
                        FROM coverage cov
                        JOIN product p ON cov.product_id = p.id
                        JOIN company comp ON p.company_id = comp.id
                        LEFT JOIN benefit b ON cov.id = b.coverage_id
                        WHERE comp.company_name = ANY(%s)
                          AND cov.coverage_name LIKE %s
                        ORDER BY comp.company_name, cov.coverage_name
                        LIMIT 20
                    """, (company_names, f'%{coverage_kw}%'))

                    rows = cur.fetchall()
                    if rows:
                        fallback_context = "\n\n## 담보 정보 (Coverage Information)\n\n"
                        for row in rows:
                            comp, prod, cov, amt = row
                            amt_str = f"{int(amt):,}원" if amt else "N/A"
                            fallback_context += f"- **{comp}** | {prod}\n  - 담보: {cov}\n  - 보장금액: {amt_str}\n\n"

                    cur.close()
                finally:
                    conn.close()

        # 5b. Assemble context
        context = assembler.assemble(
            vector_results=retrieved_clauses,
            query=request.query,
            max_context_length=4000
        )

        # 6. Build prompt
        # Add user context to query if available
        enriched_query = request.query
        if age and gender:
            enriched_query = f"{request.query} (나이: 만 {age}세, 성별: {gender})"
        elif age:
            enriched_query = f"{request.query} (나이: 만 {age}세)"
        elif gender:
            enriched_query = f"{request.query} (성별: {gender})"

        # Context is a dict with 'context_text' key
        context_str = context.get("context_text", "") if isinstance(context, dict) else str(context)

        # Prepend fallback context if available
        if fallback_context:
            context_str = fallback_context + "\n\n" + context_str

        # Debug: Log context preview
        print(f"[DEBUG] Context length: {len(context_str)} chars")
        print(f"[DEBUG] Fallback context: {len(fallback_context)} chars")
        print(f"[DEBUG] Context preview (first 500 chars): {context_str[:500]}")
        print(f"[DEBUG] Enriched clauses count: {len(context.get('clauses', []))}")

        prompt = prompt_builder.build_qa_prompt(
            query=enriched_query,
            context=context_str
        )

        # 7. Generate LLM answer
        print(f"[DEBUG] Starting LLM generation with prompt length: {len(prompt)}")
        import time
        start_time = time.time()
        llm_answer = llm_client.generate(prompt)
        elapsed = time.time() - start_time
        print(f"[DEBUG] LLM generation completed in {elapsed:.2f}s")

        # 8. Format comparison table (use enriched clauses from context)
        enriched_clauses = context.get('clauses', []) if isinstance(context, dict) else []
        comparison_table = format_comparison_table(enriched_clauses, nl_entities)

        # 9. Format sources (use enriched clauses)
        sources = [
            {
                "company": c.get("company_name", "N/A"),
                "product": c.get("product_name", "N/A"),
                "clause": f"[{c.get('clause_number', 'N/A')}] {c.get('clause_title', '')}: {c.get('clause_text', '')[:150]}..."
            }
            for c in enriched_clauses[:5]
        ]

        return HybridSearchResponse(
            answer=llm_answer,
            comparisonTable=comparison_table if comparison_table else None,
            sources=sources
        )

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error in hybrid_search: {e}")
        print(error_trace)

        # Return detailed error for debugging
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "type": type(e).__name__,
                "traceback": error_trace.split('\n')[-5:]  # Last 5 lines
            }
        )


@app.post("/api/compare", response_model=List[ComparisonResult])
async def compare_products(request: CompareRequest):
    """
    상품 비교 API

    주어진 product IDs에 대해 보장 내용, 가입 금액, 보험료 등을 비교
    """
    if not retriever:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # TODO: Implement product comparison logic
        # For now, return empty list
        return []

    except Exception as e:
        print(f"Error in compare_products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
