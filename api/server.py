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
from api.info_extractor import InfoExtractor

load_dotenv()

# ========== Company Name Mapping ==========
# DB 회사명 → 표시명 매핑
COMPANY_DISPLAY_NAMES = {
    "삼성": "삼성화재",
    "현대": "현대해상",
    "DB": "DB손해보험",
    "KB": "KB손해보험",
    "한화": "한화손해보험",
    "롯데": "롯데손해보험",
    "메리츠": "메리츠화재",
    "흥국": "흥국화재",
}

# 별칭 → DB 회사명 매핑 (NL Mapper와 동일)
COMPANY_ALIASES = {
    # 삼성
    "삼성화재": "삼성", "삼성생명": "삼성", "삼성손보": "삼성", "삼성손해보험": "삼성",
    # DB
    "동부": "DB", "동부화재": "DB", "동부손보": "DB", "동부손해보험": "DB",
    "DB손보": "DB", "DB손해보험": "DB", "DB화재": "DB",
    # 현대
    "현대해상": "현대", "현대생명": "현대", "현대손보": "현대", "현대손해보험": "현대",
    # 한화
    "한화손보": "한화", "한화손해보험": "한화", "한화생명": "한화", "한화화재": "한화",
    # 롯데
    "롯데손보": "롯데", "롯데손해보험": "롯데", "롯데화재": "롯데",
    # KB
    "KB손보": "KB", "KB손해보험": "KB", "KB생명": "KB", "KB화재": "KB",
    # 메리츠
    "메리츠화재": "메리츠", "메리츠손보": "메리츠", "메리츠손해보험": "메리츠",
    # 흥국
    "흥국화재": "흥국", "흥국생명": "흥국", "흥국손보": "흥국",
}


def resolve_company_name(name: str) -> str:
    """별칭을 DB 회사명으로 변환"""
    return COMPANY_ALIASES.get(name, name)


def get_display_name(db_name: str) -> str:
    """DB 회사명을 표시명으로 변환"""
    return COMPANY_DISPLAY_NAMES.get(db_name, db_name)


def normalize_coverage_name(name: str) -> str:
    """
    담보명 정규화 (중복 제거용)

    Examples:
        "뇌출혈진단비" -> "뇌출혈진단"
        "뇌출혈 진단비" -> "뇌출혈진단"
        "뇌출혈진단담보" -> "뇌출혈진단"
    """
    if not name:
        return ""
    # 공백 제거
    normalized = name.replace(" ", "")
    # 접미사 제거 (순서 중요: 긴 것부터)
    suffixes = ["진단담보", "담보", "진단비", "비"]
    for suffix in suffixes:
        if normalized.endswith(suffix) and len(normalized) > len(suffix):
            normalized = normalized[:-len(suffix)]
            break
    return normalized


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


class SearchParams(BaseModel):
    """템플릿 기반 검색 파라미터"""
    coverageKeyword: Optional[str] = None
    exactMatch: Optional[bool] = False
    excludeKeywords: Optional[List[str]] = None
    docTypes: Optional[List[str]] = None


class HybridSearchRequest(BaseModel):
    """하이브리드 검색 요청"""
    query: str = Field(..., description="사용자 질문")
    userProfile: Optional[UserProfile] = None
    selectedCategories: Optional[List[str]] = None
    selectedCoverageTags: Optional[List[str]] = None
    lastCoverage: Optional[str] = Field(None, description="이전 대화에서 언급된 담보명 (컨텍스트 유지용)")
    templateId: Optional[str] = Field(None, description="선택된 템플릿 ID")
    searchParams: Optional[SearchParams] = Field(None, description="템플릿 기반 구조화된 검색 파라미터")


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
info_extractor: Optional[InfoExtractor] = None


@app.on_event("startup")
async def startup_event():
    """서버 시작 시 초기화"""
    global retriever, assembler, prompt_builder, nl_mapper, llm_client, info_extractor

    postgres_url = os.getenv("POSTGRES_URL")
    if not postgres_url:
        raise RuntimeError("POSTGRES_URL environment variable is required. Check .env file.")

    retriever = HybridRetriever(postgres_url=postgres_url)
    assembler = ContextAssembler(postgres_url=postgres_url)
    prompt_builder = PromptBuilder()
    nl_mapper = NLMapper(postgres_url=postgres_url)
    info_extractor = InfoExtractor(postgres_url=postgres_url)
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
        # 항상 쿼리에서 엔티티 추출 먼저 수행
        nl_entities = nl_mapper.extract_entities(request.query)
        print(f"[DEBUG] NL entities from query: {nl_entities}")

        # 템플릿 기반 검색이면 템플릿 파라미터를 폴백으로 사용
        if request.templateId and request.searchParams:
            print(f"[DEBUG] Template-based search: {request.templateId}")

            # 쿼리에서 담보 추출 실패 시 keywords에서 담보 키워드 추출 시도
            query_coverages = nl_entities.get("coverages", [])
            if not query_coverages:
                # keywords에서 담보 관련 키워드 추출
                coverage_keyword_list = ["암진단", "수술", "입원", "통원", "치료비", "유사암", "제자리암", "경계성종양", "뇌졸중", "급성심근경색", "다빈치"]
                query_keywords = nl_entities.get("keywords", [])
                extracted_coverages = [kw for kw in query_keywords if kw in coverage_keyword_list]

                if extracted_coverages:
                    print(f"[DEBUG] Extracted coverages from keywords: {extracted_coverages}")
                    nl_entities["coverages"] = extracted_coverages
                elif request.searchParams.coverageKeyword:
                    print(f"[DEBUG] No coverages in query/keywords, falling back to template keyword: {request.searchParams.coverageKeyword}")
                    nl_entities["coverages"] = [request.searchParams.coverageKeyword]
            else:
                print(f"[DEBUG] Using coverages from query: {query_coverages}")

        # 3. Enhance entities with user context
        if age:
            nl_entities["user_age"] = age
        if gender:
            nl_entities["user_gender"] = gender
        if request.selectedCoverageTags:
            nl_entities["coverage_tags"] = request.selectedCoverageTags

        # 4. Check if it's a multi-company comparison query
        # 템플릿 기반 검색과 일반 검색 모두 지원
        company_names_in_query = nl_entities.get("companies", [])
        print(f"[DEBUG] NL entities: {nl_entities}")
        print(f"[DEBUG] Extracted companies: {company_names_in_query}")

        # "전체 보험사" 또는 "전체"가 쿼리에 있으면 모든 회사로 확장
        ALL_COMPANIES = list(COMPANY_DISPLAY_NAMES.keys())  # ['삼성', '현대', 'DB', 'KB', '한화', '롯데', '메리츠', '흥국']
        if "전체 보험사" in request.query or "전체보험사" in request.query or (
            "전체" in request.query and ("비교" in request.query or "암" in request.query)
        ):
            company_names_in_query = ALL_COMPANIES
            print(f"[DEBUG] Expanded '전체 보험사' to all companies: {company_names_in_query}")

        # Extract coverage names from NL mapper first
        coverages_from_nl = nl_entities.get("coverages", [])
        print(f"[DEBUG] Extracted coverages: {coverages_from_nl}")

        # Clean and filter coverages: remove leading "- " or numbers, and deduplicate
        valid_coverages = []
        seen_normalized = set()  # 정규화된 이름으로 중복 체크
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
            # Deduplicate using normalized name
            # 예: "뇌출혈진단비", "뇌출혈 진단비", "뇌출혈진단담보" -> 모두 "뇌출혈진단"으로 정규화
            normalized = normalize_coverage_name(cleaned)
            if normalized and normalized not in seen_normalized:
                valid_coverages.append(cleaned)  # 원본 담보명 저장
                seen_normalized.add(normalized)

        # Fallback: Extract coverage name from query (simple heuristic)
        if not valid_coverages:
            coverage_keywords = ["암진단", "수술", "입원", "통원", "치료비", "유사암", "제자리암", "경계성종양", "뇌졸중", "급성심근경색", "다빈치"]
            for keyword in coverage_keywords:
                if keyword in request.query and keyword not in valid_coverages:
                    valid_coverages.append(keyword)
            if valid_coverages:
                print(f"[DEBUG] Fallback extracted coverages: {valid_coverages}")

        # If still not found, use lastCoverage from previous conversation
        if not valid_coverages and request.lastCoverage:
            valid_coverages = [request.lastCoverage]
            print(f"[DEBUG] Using lastCoverage from context: {request.lastCoverage}")

        # Check if it's a single-company information extraction query
        info_templates = {
            "coverage-start-date": "coverage-start-date",
            "coverage-limit": "coverage-limit",
            "enrollment-age": "enrollment-age",
            "exclusions": "exclusions",
            "renewal-info": "renewal-info"
        }

        if (len(company_names_in_query) == 1 and
            request.templateId in info_templates and
            valid_coverages):
            # Single-company information extraction
            company = company_names_in_query[0]
            coverage_keyword = valid_coverages[0]
            info_type = info_templates[request.templateId]

            print(f"[DEBUG] InfoExtractor: {company}, coverage: {coverage_keyword}, info_type: {info_type}")

            query_keywords = nl_entities.get("keywords", [])
            print(f"[DEBUG] Query keywords from NL: {query_keywords}")

            try:
                info_result = info_extractor.extract_info(
                    company=company,
                    coverage_keyword=coverage_keyword,
                    info_type=info_type,
                    query_keywords=query_keywords if query_keywords else None
                )

                # Initialize variables
                coverage_name = coverage_keyword  # Default to query coverage

                # Format response
                if info_result["status"] == "no_data":
                    answer = f"**{company}**\n\n{info_result['message']}"
                    sources = []
                elif info_result["status"] == "error":
                    answer = f"**오류**\n\n{info_result['message']}"
                    sources = []
                else:
                    # Success - Use LLM to generate clear answer
                    product_name = info_result.get("product", "N/A")
                    coverage_name = info_result.get("coverage", coverage_keyword)

                    # Get benefit amount from info_result
                    benefit_amount_raw = info_result.get("benefit_amount")
                    benefit_amount = f"{int(benefit_amount_raw):,}원" if benefit_amount_raw else None

                    # Build LLM prompt with coverage info and clauses
                    clause_texts = info_result.get("sources", [])

                    prompt = prompt_builder.build_info_extraction_prompt(
                        query=request.query,
                        company=company,
                        product_name=product_name,
                        coverage_name=coverage_name,
                        benefit_amount=benefit_amount,
                        info_type=info_type,
                        clause_texts=clause_texts
                    )

                    # Generate LLM answer
                    print(f"[DEBUG] Generating LLM answer for info extraction")
                    llm_answer = llm_client.generate(prompt)

                    # Build final answer with header
                    answer_parts = [
                        f"# {company} - {coverage_name}",
                        f"**상품명**: {product_name}",
                    ]
                    if benefit_amount:
                        answer_parts.append(f"**보장금액**: {benefit_amount}")

                    answer_parts.extend([
                        "",
                        "## 정보",
                        llm_answer
                    ])

                    answer = "\n".join(answer_parts)

                    # Format sources - 중복 제거
                    sources = []
                    seen_clauses = set()
                    for src in clause_texts:
                        # clause_text를 기준으로 중복 체크
                        clause_key = f"{src.get('clause_number', '')}:{src.get('clause_title', '')}:{src.get('clause_text', '')[:100]}"
                        if clause_key not in seen_clauses:
                            seen_clauses.add(clause_key)
                            sources.append({
                                "company": company,
                                "product": product_name,
                                "clause": f"[{src.get('clause_number', 'N/A')}] {src.get('clause_title', '')}: {src.get('clause_text', '')[:150]}...",
                                "docType": "terms"
                            })
                            if len(sources) >= 3:  # 최대 3개까지만
                                break

                return HybridSearchResponse(
                    answer=answer,
                    comparisonTable=None,
                    sources=sources if sources else None,
                    coverage=coverage_name
                )

            except Exception as e:
                print(f"[ERROR] InfoExtractor failed: {e}")
                import traceback
                traceback.print_exc()
                # Fall through to general search

        # If multiple companies mentioned or comparison intent detected, use ProductComparer
        if len(company_names_in_query) >= 2 and valid_coverages:
            # Multi-company comparison using ProductComparer (Phase 6.1)
            print(f"[DEBUG] ProductComparer: {company_names_in_query}, coverages: {valid_coverages}")

            # 템플릿 기반 검색이면 제외 키워드 적용
            exclude_keywords = []
            if request.templateId and request.searchParams and request.searchParams.excludeKeywords:
                exclude_keywords = request.searchParams.excludeKeywords
                print(f"[DEBUG] Exclude keywords: {exclude_keywords}")

            # NL entities에서 추출한 키워드 전달
            query_keywords = nl_entities.get("keywords", [])
            print(f"[DEBUG] Query keywords from NL: {query_keywords}")

            from api.compare import ProductComparer
            comparer = ProductComparer(hybrid_retriever=retriever)

            try:
                comparison_result = comparer.compare_products(
                    companies=company_names_in_query,
                    coverage=valid_coverages,  # Pass list of coverages
                    include_sources=True,
                    include_recommendation=True,
                    exclude_keywords=exclude_keywords if exclude_keywords else None,
                    query_keywords=query_keywords if query_keywords else None
                )

                # Convert ProductComparer result to HybridSearchResponse format
                coverages_list = comparison_result["coverages"]
                answer_parts = []
                comparison_table_data = []

                # Improve section title using query keywords when coverage is generic
                def get_display_title(cov: str, keywords: list, query: str = "") -> str:
                    """쿼리 키워드를 활용해 더 구체적인 제목 생성"""
                    generic_terms = ["암수술담보", "암진단담보", "진단담보", "수술담보"]
                    if cov in generic_terms:
                        # 쿼리에서 직접 특정 키워드 추출
                        query_specific_terms = ["유사암", "다빈치", "로봇", "뇌졸중", "급성심근경색", "제자리암", "경계성종양"]
                        for term in query_specific_terms:
                            if term in query:
                                # 담보에서 "암" 제거하고 타입만 추출 (수술/진단)
                                base = cov.replace("담보", "").replace("암", "")  # "수술" or "진단"
                                return f"{term} {base}비"  # "유사암 수술비"
                        # keywords에서도 확인
                        if keywords:
                            specific_keywords = [k for k in keywords if k in query_specific_terms]
                            if specific_keywords:
                                base = cov.replace("담보", "").replace("암", "")
                                return f"{specific_keywords[0]} {base}비"
                    return cov

                # Group by coverage and build sections
                for cov in coverages_list:
                    display_title = get_display_title(cov, query_keywords, request.query)
                    answer_parts.append(f"\n# {display_title} 비교\n")

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
                        age_range = data.get("ageRange")

                        # 보장금액이 없으면 명시적 메시지 표시
                        if not amount and coverage_name_full == cov:
                            # 담보명이 검색어 그대로면 DB에서 찾지 못한 것
                            answer_parts.append(f"\n**{company}**: 해당 담보 정보를 찾을 수 없습니다.")
                            continue

                        answer_parts.append(f"\n**{company}** ({product_name})")
                        answer_parts.append(f"- 담보: {coverage_name_full}")
                        answer_parts.append(f"- 보장금액: {amount_str}")
                        if age_range:
                            answer_parts.append(f"- 가입나이: {age_range}")

                        # Build comparison table row
                        notes = f"가입나이: {age_range}" if age_range else None
                        comparison_table_data.append({
                            "company": company,
                            "product": product_name,
                            "coverage": coverage_name_full,
                            "benefit": amount_str,
                            "notes": notes
                        })

                # 주요 차이점 분석
                answer_parts.append("\n\n## 주요 차이점")

                # Analyze differences per coverage
                has_valid_comparison = False
                for cov in coverages_list:
                    valid_data = {}
                    for company in company_names_in_query:
                        key = f"{company}_{cov}"
                        data = comparison_result["comparison"].get(key, {})
                        # 실제 보장금액이 있는 데이터만 유효로 처리
                        if data.get("status") != "no_data" and data.get("amount"):
                            valid_data[company] = data

                    if len(valid_data) >= 2:
                        has_valid_comparison = True
                        display_title = get_display_title(cov, query_keywords, request.query)
                        answer_parts.append(f"\n### {display_title}")
                        # 보장금액 비교
                        amounts = [(k, v.get("amount") or 0) for k, v in valid_data.items()]
                        amounts.sort(key=lambda x: x[1], reverse=True)

                        if amounts[0][1] != amounts[1][1]:
                            diff = amounts[0][1] - amounts[1][1]
                            answer_parts.append(f"- **보장금액**: {amounts[0][0]}이(가) {amounts[1][0]}보다 {int(diff):,}원 더 높습니다.")
                        else:
                            answer_parts.append(f"- **보장금액**: 모든 상품이 동일한 보장금액을 제공합니다 ({int(amounts[0][1]):,}원)")

                if not has_valid_comparison:
                    # 유효한 비교 데이터가 없으면 메시지 표시
                    answer_parts.append("\n비교 가능한 담보 데이터가 없습니다.")

                # 종합 판단
                if comparison_result.get("recommendation"):
                    answer_parts.append(f"\n\n## 종합 판단\n{comparison_result['recommendation']}")

                llm_answer = "\n".join(answer_parts)

                # Format sources from ProductComparer - 중복 제거
                sources = []
                seen_sources = set()
                for key, data in comparison_result["comparison"].items():
                    if "sources" in data:
                        company = data.get("company", "")
                        for src in data["sources"]:
                            # clause를 기준으로 중복 체크
                            clause_key = f"{src.get('company', company)}:{src.get('clause', '')[:100]}"
                            if clause_key not in seen_sources:
                                seen_sources.add(clause_key)
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
        # 중복 제거 후 sources 생성
        sources = []
        seen_clauses = set()
        for c in enriched_clauses:
            clause_key = f"{c.get('clause_number', '')}:{c.get('clause_title', '')}:{c.get('clause_text', '')[:100]}"
            if clause_key not in seen_clauses:
                seen_clauses.add(clause_key)
                sources.append({
                    "company": c.get("company_name", "N/A"),
                    "product": c.get("product_name", "N/A"),
                    "clause": f"[{c.get('clause_number', 'N/A')}] {c.get('clause_title', '')}: {c.get('clause_text', '')[:150]}..."
                })
                if len(sources) >= 5:  # 최대 5개까지만
                    break

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


@app.get("/api/companies")
async def get_companies():
    """
    보험사 리스트 조회

    Returns:
        List of companies with name (DB명) and displayName (표시명)
    """
    if not retriever:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        import psycopg2
        conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT DISTINCT company_name
                FROM company
                ORDER BY company_name
            """)

            companies = []
            for row in cur.fetchall():
                db_name = row[0]
                companies.append({
                    "name": db_name,
                    "displayName": get_display_name(db_name)
                })
            cur.close()

            return {"companies": companies}
        finally:
            conn.close()

    except Exception as e:
        print(f"Error in get_companies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/companies/{company_name}/products")
async def get_company_products(company_name: str):
    """
    특정 보험사의 상품 리스트 조회

    Args:
        company_name: 보험사명 (별칭 지원: 삼성화재, 현대해상 등)

    Returns:
        List of products
    """
    if not retriever:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        import psycopg2
        from urllib.parse import unquote

        # URL 디코딩 및 별칭 해석
        company_name = unquote(company_name)
        company_name = resolve_company_name(company_name)

        conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT DISTINCT p.product_name
                FROM product p
                JOIN company c ON p.company_id = c.id
                WHERE c.company_name = %s
                ORDER BY p.product_name
            """, (company_name,))

            products = []
            for row in cur.fetchall():
                product_name = row[0]
                if product_name:
                    products.append(product_name)

            return {"products": products}

        finally:
            conn.close()

    except Exception as e:
        print(f"Error fetching products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/companies/{company_name}/products/{product_name}/coverages")
async def get_product_coverages(company_name: str, product_name: str):
    """
    특정 보험사의 특정 상품의 담보 리스트 조회

    Args:
        company_name: 보험사명 (별칭 지원: 삼성화재, 현대해상 등)
        product_name: 상품명

    Returns:
        List of coverages with benefit amounts
    """
    if not retriever:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        import psycopg2
        from urllib.parse import unquote

        # URL 디코딩 및 별칭 해석
        company_name = unquote(company_name)
        company_name = resolve_company_name(company_name)
        product_name = unquote(product_name)

        conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT DISTINCT
                    cov.coverage_name,
                    b.benefit_amount,
                    p.product_name
                FROM coverage cov
                JOIN product p ON cov.product_id = p.id
                JOIN company c ON p.company_id = c.id
                LEFT JOIN benefit b ON cov.id = b.coverage_id
                WHERE c.company_name = %s
                  AND p.product_name = %s
                ORDER BY cov.coverage_name
            """, (company_name, product_name))

            coverages = []
            seen = set()
            for row in cur.fetchall():
                coverage_name, benefit_amount, product_name = row

                # 잘못된 데이터 필터링
                if not coverage_name or len(coverage_name.strip()) < 3:
                    continue

                coverage_stripped = coverage_name.strip()

                # 숫자로 시작하는 경우 (조항 번호 등)
                if coverage_stripped[0].isdigit():
                    # "10년형" 같은 기간 데이터 제외
                    if "년" in coverage_stripped and len(coverage_stripped) <= 4:
                        continue
                    # "119", "121" 같은 순수 숫자 제외
                    if coverage_stripped.split()[0].isdigit():
                        continue

                # 중복 제거 (담보명 기준)
                if coverage_name in seen:
                    continue
                seen.add(coverage_name)

                coverages.append({
                    "coverage_name": coverage_name,
                    "benefit_amount": benefit_amount,
                    "product_name": product_name
                })

            return {"coverages": coverages}

        finally:
            conn.close()

    except Exception as e:
        print(f"Error fetching coverages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/companies/{company_name}/coverages")
async def get_company_coverages(company_name: str):
    """
    특정 보험사의 담보 리스트 조회

    Args:
        company_name: 보험사명 (별칭 지원: 삼성화재, 현대해상 등)

    Returns:
        List of coverages with benefit amounts
    """
    if not retriever:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        import psycopg2
        from urllib.parse import unquote

        # URL 디코딩 및 별칭 해석
        company_name = unquote(company_name)
        company_name = resolve_company_name(company_name)

        conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT DISTINCT
                    cov.coverage_name,
                    b.benefit_amount,
                    p.product_name
                FROM coverage cov
                JOIN product p ON cov.product_id = p.id
                JOIN company comp ON p.company_id = comp.id
                LEFT JOIN benefit b ON cov.id = b.coverage_id
                WHERE comp.company_name = %s
                ORDER BY
                    b.benefit_amount DESC NULLS LAST,
                    cov.coverage_name
                LIMIT 100
            """, (company_name,))

            coverages = []
            seen = set()

            for row in cur.fetchall():
                coverage_name, benefit_amount, product_name = row

                # 잘못된 데이터 필터링
                # 1. 숫자로만 구성된 담보명 제외
                # 2. "10년", "15년" 같은 기간 데이터 제외
                # 3. 너무 짧은 담보명 제외 (3자 미만)
                if not coverage_name or len(coverage_name.strip()) < 3:
                    continue

                coverage_stripped = coverage_name.strip()

                # 숫자로 시작하는 경우 (조항 번호 등)
                if coverage_stripped[0].isdigit():
                    # "10년형" 같은 기간 데이터 제외
                    if "년" in coverage_stripped and len(coverage_stripped) <= 4:
                        continue
                    # "119", "121" 같은 순수 숫자 제외
                    if coverage_stripped.split()[0].isdigit():
                        continue

                # 중복 제거 (담보명 기준)
                if coverage_name in seen:
                    continue
                seen.add(coverage_name)

                coverages.append({
                    "coverage_name": coverage_name,
                    "benefit_amount": int(benefit_amount) if benefit_amount else None,
                    "product_name": product_name
                })

            cur.close()

            return {"coverages": coverages}
        finally:
            conn.close()

    except Exception as e:
        print(f"Error in get_company_coverages: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/coverages")
async def get_all_coverages():
    """
    전체 담보 목록 조회 (비교 쿼리용)

    Returns:
        List of unique coverage names across all companies
    """
    if not retriever:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        import psycopg2

        conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT DISTINCT cov.coverage_name
                FROM coverage cov
                JOIN product p ON cov.product_id = p.id
                ORDER BY cov.coverage_name
            """)

            coverages = [row[0] for row in cur.fetchall() if row[0] and len(row[0].strip()) >= 3]
            cur.close()

            return {"coverages": coverages}
        finally:
            conn.close()

    except Exception as e:
        print(f"Error in get_all_coverages: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


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
