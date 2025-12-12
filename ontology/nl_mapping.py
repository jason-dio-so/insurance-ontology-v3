"""
Natural Language to Ontology Mapping

Maps natural language queries to structured ontology entities (Coverage, Product, Company, etc.)
Uses pattern matching and database lookups for entity extraction.

주요 기능:
- 질의에서 엔티티 추출 (담보명, 상품명, 회사명, 질병명 등)
- DB 조회를 통한 정확한 매칭
- 매핑된 엔티티를 필터로 변환하여 벡터 검색에 활용

Usage:
    from ontology.nl_mapping import NLMapper

    mapper = NLMapper()
    entities = mapper.extract_entities("삼성화재 마이헬스 암진단금은?")
    # Returns: {
    #   "companies": ["삼성화재"],
    #   "products": ["마이헬스"],
    #   "coverages": ["암진단금"],
    #   "filters": {"company_id": 1, "product_id": 5}
    # }
"""

import re
import psycopg2
from typing import Dict, List, Any, Optional
import os


class NLMapper:
    """자연어 → 온톨로지 엔티티 매핑 클래스"""

    # 회사명 별칭 매핑 (alias → DB company_name)
    COMPANY_ALIASES = {
        # 삼성
        '삼성화재': '삼성',
        '삼성생명': '삼성',
        '삼성손보': '삼성',
        '삼성손해보험': '삼성',
        # DB (구 동부)
        '동부': 'DB',
        '동부화재': 'DB',
        '동부손보': 'DB',
        '동부손해보험': 'DB',
        'DB손보': 'DB',
        'DB손해보험': 'DB',
        'DB화재': 'DB',
        # 현대
        '현대해상': '현대',
        '현대생명': '현대',
        '현대손보': '현대',
        '현대손해보험': '현대',
        # 한화
        '한화손보': '한화',
        '한화손해보험': '한화',
        '한화생명': '한화',
        '한화화재': '한화',
        # 롯데
        '롯데손보': '롯데',
        '롯데손해보험': '롯데',
        '롯데화재': '롯데',
        # KB
        'KB손보': 'KB',
        'KB손해보험': 'KB',
        'KB생명': 'KB',
        # 메리츠
        '메리츠화재': '메리츠',
        '메리츠손보': '메리츠',
        '메리츠손해보험': '메리츠',
        # 흥국
        '흥국화재': '흥국',
        '흥국생명': '흥국',
        '흥국손보': '흥국',
    }

    def __init__(self, postgres_url: str = None):
        """
        Args:
            postgres_url: PostgreSQL 연결 문자열
        """
        self.postgres_url = postgres_url or os.getenv(
            "POSTGRES_URL",
            "postgresql://postgres:postgres@localhost:5432/insurance_ontology"
        )
        self.pg_conn = psycopg2.connect(self.postgres_url)

        # 엔티티 캐시 (성능 최적화)
        self._company_cache = None
        self._product_cache = None
        self._coverage_cache = None
        self._disease_cache = None

    def extract_entities(self, query: str) -> Dict[str, Any]:
        """
        질의에서 엔티티 추출

        Args:
            query: 자연어 질의

        Returns:
            추출된 엔티티와 필터 딕셔너리
        """
        entities = {
            "entities": {  # Add nested structure for compatibility
                "companies": [],
                "products": [],
                "coverages": [],
                "diseases": [],
            },
            "companies": [],
            "products": [],
            "coverages": [],
            "diseases": [],
            "keywords": [],
            "amount_filter": None,
            "gender_filter": None,
            "age_filter": None,
            "filters": {}
        }

        # 1. 회사명 추출
        companies = self._extract_companies(query)
        if companies:
            entities["companies"] = companies
            entities["entities"]["companies"] = companies  # Also populate nested structure
            entities["filters"]["company_id"] = self._get_company_id(companies[0])

        # 2. 상품명 추출
        products = self._extract_products(query)
        if products:
            entities["products"] = products
            entities["filters"]["product_id"] = self._get_product_id(products[0])

        # 3. 담보명 추출
        coverages = self._extract_coverages(query)
        if coverages:
            entities["coverages"] = coverages
            # Note: coverage_id는 벡터 검색 메타데이터 필터로 사용 가능
            coverage_ids = [self._get_coverage_id(c) for c in coverages]
            entities["filters"]["coverage_ids"] = [cid for cid in coverage_ids if cid]

        # 4. 질병명 추출
        diseases = self._extract_diseases(query)
        if diseases:
            entities["diseases"] = diseases

        # 5. 금액 필터 추출
        amount_filter = self._extract_amount(query)
        if amount_filter:
            entities["amount_filter"] = amount_filter
            entities["filters"]["amount"] = amount_filter

        # 6. 성별 필터 추출
        gender_filter = self._extract_gender(query)
        if gender_filter:
            entities["gender_filter"] = gender_filter
            entities["filters"]["gender"] = gender_filter

        # 7. 나이 필터 추출
        age_filter = self._extract_age(query)
        if age_filter:
            entities["age_filter"] = age_filter
            entities["filters"]["age"] = age_filter

        # 8. 핵심 키워드 추출
        keywords = self._extract_keywords(query)
        entities["keywords"] = keywords

        return entities

    def _extract_companies(self, query: str) -> List[str]:
        """회사명 추출 (별칭 매핑 + 부분 매칭 지원)"""
        if not self._company_cache:
            self._load_company_cache()

        found = []
        found_set = set()  # 중복 방지

        # 1. 별칭 매핑 우선 처리 (긴 별칭부터 매칭하여 정확도 향상)
        sorted_aliases = sorted(self.COMPANY_ALIASES.keys(), key=len, reverse=True)
        for alias in sorted_aliases:
            if alias in query:
                company_name = self.COMPANY_ALIASES[alias]
                if company_name not in found_set:
                    found.append(company_name)
                    found_set.add(company_name)

        # 2. DB의 회사명/코드 직접 매칭
        for company in self._company_cache:
            company_name = company['company_name']
            company_code = company['company_code']

            if company_name in found_set:
                continue

            # 전체 이름 정확 매칭
            if company_name in query:
                found.append(company_name)
                found_set.add(company_name)
                continue

            # 코드 매칭 (대소문자 무시)
            if company_code and company_code.lower() in query.lower():
                found.append(company_name)
                found_set.add(company_name)
                continue

        # 3. 핵심 키워드 부분 매칭 (예: "삼성" → "삼성")
        core_keywords = {
            '삼성': '삼성',
            '동부': 'DB',  # 동부 → DB
            'DB': 'DB',
            '롯데': '롯데',
            '메리츠': '메리츠',
            '한화': '한화',
            '현대': '현대',
            'KB': 'KB',
            '흥국': '흥국',
        }
        for keyword, company_name in core_keywords.items():
            if keyword in query and company_name not in found_set:
                found.append(company_name)
                found_set.add(company_name)

        return found

    def _extract_products(self, query: str) -> List[str]:
        """상품명 추출"""
        if not self._product_cache:
            self._load_product_cache()

        found = []
        for product in self._product_cache:
            # 상품명 부분 매칭 (예: "마이헬스", "리얼속속" 등)
            if product['name'] in query:
                found.append(product['name'])

        return found

    def _extract_coverages(self, query: str) -> List[str]:
        """담보명 추출 (키워드 기반)"""
        if not self._coverage_cache:
            self._load_coverage_cache()

        query_normalized = query.replace(' ', '')
        found = []

        for coverage in self._coverage_cache:
            name = coverage['name']

            # 정확한 매칭
            if name in query:
                found.append(name)
                continue

            # 부분 매칭 (예: "암 진단" → "암진단비")
            name_without_suffix = name.replace('금', '').replace('비', '').replace('담보', '')
            if name_without_suffix in query_normalized:
                found.append(name)
                continue

        # 키워드 기반 매핑 (일반 용어 → 표준 담보명)
        # 정확한 매칭이 없을 때만 키워드 기반 검색
        # if not found:  # 제거 - 항상 키워드 검색 스킵하여 중복 방지

        return list(set(found))  # 중복 제거

    def _extract_diseases(self, query: str) -> List[str]:
        """질병명 추출"""
        if not self._disease_cache:
            self._load_disease_cache()

        found = []
        for disease in self._disease_cache:
            if disease['name'] in query or disease['code'] in query:
                found.append(disease['name'])

        return found

    def _extract_keywords(self, query: str) -> List[str]:
        """핵심 키워드 추출 (보험 도메인 용어)"""
        # 보험 관련 키워드 패턴 (구체적 키워드를 먼저 배치하여 우선 매칭)
        # 순서: 구체적 → 일반적 (제자리암 > 유사암 > 암)
        insurance_keywords = [
            # 구체적 암 종류 (우선순위 높음)
            '제자리암', '경계성종양', '유사암', '4대유사암',
            '갑상선암', '기타피부암', '재진단암',
            '일반암', '소액암', '고액암',
            # 일반 보장 타입
            '보장', '진단', '수술', '입원', '통원',
            # 일반 암/질병 (구체적 암 키워드 이후에 매칭)
            '암', '뇌출혈', '급성심근경색', '질병', '상해',
            # 조건 관련
            '면책', '감액', '지급', '한도', '제한',
            '가입', '나이', '기간', '금액', '조건',
            # 특수 담보
            '다빈치', '로봇'
        ]

        found = []
        for keyword in insurance_keywords:
            if keyword in query:
                found.append(keyword)

        return found

    def _extract_amount(self, query: str) -> Optional[Dict[str, int]]:
        """
        금액 필터 추출

        Examples:
            "3000만원" → {"min": 30000000, "max": 30000000}
            "2천만원 이상" → {"min": 20000000, "max": None}
            "5000만원 이하" → {"min": None, "max": 50000000}
            "1억~2억" → {"min": 100000000, "max": 200000000}

        Returns:
            {"min": int, "max": int} 또는 None
        """
        import re

        # 패턴 1: "N천만원", "N억원", "N만원"
        patterns = [
            # "1억", "2억5천만원" (먼저 처리)
            (r'(\d+)억(?:(\d+)천)?(?:(\d+)백)?만?원?', lambda m: (
                int(m.group(1)) * 100000000 +
                (int(m.group(2)) * 10000000 if m.group(2) else 0) +
                (int(m.group(3)) * 1000000 if m.group(3) else 0)
            )),
            # "3천만원", "2천5백만원"
            (r'(\d+)천(?:(\d+)백)?만원', lambda m: (int(m.group(1)) * 1000 + (int(m.group(2)) * 100 if m.group(2) else 0)) * 10000),
            # "3000만원", "3,000만원" (순수 숫자+만원)
            (r'(\d{1,4}),?(\d{3})만원', lambda m: int(m.group(1) + m.group(2)) * 10000),
        ]

        amounts = []
        for pattern, converter in patterns:
            for match in re.finditer(pattern, query):
                try:
                    amount = converter(match)
                    amounts.append(amount)
                except:
                    pass

        if not amounts:
            return None

        # 범위 키워드 확인
        if '이상' in query:
            return {"min": min(amounts), "max": None}
        elif '이하' in query or '미만' in query:
            return {"min": None, "max": max(amounts)}
        elif '~' in query or '-' in query or '에서' in query:
            if len(amounts) >= 2:
                return {"min": min(amounts), "max": max(amounts)}
            else:
                return {"min": amounts[0], "max": amounts[0]}
        else:
            # 정확한 금액
            return {"min": amounts[0], "max": amounts[0]}

    def _extract_gender(self, query: str) -> Optional[str]:
        """
        성별 필터 추출

        Returns:
            "male", "female", 또는 None
        """
        if any(keyword in query for keyword in ['남성', '남자', '남']):
            return 'male'
        elif any(keyword in query for keyword in ['여성', '여자', '여']):
            return 'female'
        return None

    def _extract_age(self, query: str) -> Optional[Dict[str, int]]:
        """
        나이 필터 추출

        Examples:
            "40세" → {"min": 40, "max": 40}
            "30세 이상" → {"min": 30, "max": None}
            "50세 이하" → {"min": None, "max": 50}
            "20~30세" → {"min": 20, "max": 30}

        Returns:
            {"min": int, "max": int} 또는 None
        """
        import re

        # 금액 단위가 있으면 나이 추출 건너뛰기
        if any(keyword in query for keyword in ['만원', '억', '천만', '백만']):
            # 명확한 나이 표현만 추출
            age_pattern = r'(\d{1,2})(?:세|살)'
        else:
            # 일반 패턴
            age_pattern = r'(\d{1,2})(?:세|살)?'

        matches = list(re.finditer(age_pattern, query))
        if not matches:
            return None

        ages = [int(m.group(1)) for m in matches if 1 <= int(m.group(1)) <= 120]  # 현실적인 나이 범위

        if not ages:
            return None

        # 범위 키워드 확인
        if '이상' in query and '가입' in query:
            return {"min": min(ages), "max": None}
        elif ('이하' in query or '미만' in query) and '가입' in query:
            return {"min": None, "max": max(ages)}
        elif '~' in query or '-' in query:
            if len(ages) >= 2:
                return {"min": min(ages), "max": max(ages)}
        elif '세' in query or '살' in query or '가입' in query:
            # 명확한 나이 컨텍스트
            return {"min": ages[0], "max": ages[0]}

        return None

    def _get_company_id(self, company_name: str) -> Optional[int]:
        """회사명으로 company_id 조회"""
        if not self._company_cache:
            self._load_company_cache()

        for company in self._company_cache:
            if company['company_name'] == company_name:  # Fixed: was 'name'
                return company['id']
        return None

    def _get_product_id(self, product_name: str) -> Optional[int]:
        """상품명으로 product_id 조회"""
        if not self._product_cache:
            self._load_product_cache()

        for product in self._product_cache:
            if product['name'] == product_name:
                return product['id']
        return None

    def _get_coverage_id(self, coverage_name: str) -> Optional[int]:
        """담보명으로 coverage_id 조회"""
        if not self._coverage_cache:
            self._load_coverage_cache()

        for coverage in self._coverage_cache:
            if coverage['name'] == coverage_name:
                return coverage['id']
        return None

    def _load_company_cache(self):
        """회사 정보 캐시 로드"""
        with self.pg_conn.cursor() as cur:
            cur.execute("SELECT id, company_name, company_code FROM company")
            self._company_cache = [
                {"id": row[0], "company_name": row[1], "company_code": row[2]}  # Fixed: match dict keys to usage
                for row in cur.fetchall()
            ]

    def _load_product_cache(self):
        """상품 정보 캐시 로드"""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT p.id, p.product_name, p.business_type, c.company_name
                FROM product p
                JOIN company c ON p.company_id = c.id
            """)
            self._product_cache = [
                {
                    "id": row[0],
                    "name": row[1],
                    "product_type": row[2],
                    "company_name": row[3]
                }
                for row in cur.fetchall()
            ]

    def _load_coverage_cache(self):
        """담보 정보 캐시 로드 (coverage 테이블 + structured_data)"""
        with self.pg_conn.cursor() as cur:
            # 1. coverage 테이블에서 기본 담보 로드
            cur.execute("""
                SELECT DISTINCT c.id, c.coverage_name, c.coverage_category
                FROM coverage c
                ORDER BY c.coverage_name
            """)
            self._coverage_cache = [
                {"id": row[0], "name": row[1], "coverage_group": row[2]}
                for row in cur.fetchall()
            ]

            # 2. clause_embedding.metadata->structured_data에서 추가 담보명 로드
            cur.execute("""
                SELECT DISTINCT
                    ce.metadata->'structured_data'->>'coverage_name' as coverage_name
                FROM clause_embedding ce
                WHERE ce.metadata->'structured_data'->>'coverage_name' IS NOT NULL
                  AND ce.metadata->'structured_data'->>'coverage_name' != ''
            """)

            # 기존 담보명 set 생성 (중복 방지)
            existing_names = {c['name'] for c in self._coverage_cache}

            # structured_data의 담보명 추가 (중복 제외)
            for row in cur.fetchall():
                coverage_name = row[0]
                if coverage_name and coverage_name not in existing_names:
                    # ID는 None (coverage 테이블에 없는 담보)
                    self._coverage_cache.append({
                        "id": None,
                        "name": coverage_name,
                        "coverage_group": "기타"
                    })
                    existing_names.add(coverage_name)

    def _load_disease_cache(self):
        """질병 코드 정보 캐시 로드"""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT dc.code, dc.description_kr
                FROM disease_code dc
                LIMIT 1000  -- 성능을 위해 제한
            """)
            self._disease_cache = [
                {"code": row[0], "name": row[1] or row[0]}
                for row in cur.fetchall()
            ]

    def get_filtered_search_params(
        self,
        query: str,
        base_limit: int = 10
    ) -> Dict[str, Any]:
        """
        질의를 파싱하여 벡터 검색 파라미터 생성

        Args:
            query: 자연어 질의
            base_limit: 기본 검색 결과 개수

        Returns:
            검색 파라미터 딕셔너리
        """
        entities = self.extract_entities(query)

        params = {
            "query": query,
            "top_k": base_limit,
            "company_id": entities["filters"].get("company_id"),
            "product_id": entities["filters"].get("product_id"),
            "doc_type": None  # 필요시 추가
        }

        return params

    def explain_entities(self, query: str) -> str:
        """
        추출된 엔티티를 사람이 읽을 수 있는 형태로 설명

        Args:
            query: 자연어 질의

        Returns:
            엔티티 설명 텍스트
        """
        entities = self.extract_entities(query)

        lines = [f"Query: {query}", ""]

        if entities["companies"]:
            lines.append(f"🏢 Companies: {', '.join(entities['companies'])}")

        if entities["products"]:
            lines.append(f"📦 Products: {', '.join(entities['products'])}")

        if entities["coverages"]:
            lines.append(f"🛡️ Coverages: {', '.join(entities['coverages'])}")

        if entities["diseases"]:
            lines.append(f"🏥 Diseases: {', '.join(entities['diseases'])}")

        if entities["amount_filter"]:
            amt = entities["amount_filter"]
            if amt["min"] and amt["max"]:
                if amt["min"] == amt["max"]:
                    lines.append(f"💰 Amount: {amt['min']:,}원")
                else:
                    lines.append(f"💰 Amount: {amt['min']:,}원 ~ {amt['max']:,}원")
            elif amt["min"]:
                lines.append(f"💰 Amount: ≥ {amt['min']:,}원")
            elif amt["max"]:
                lines.append(f"💰 Amount: ≤ {amt['max']:,}원")

        if entities["gender_filter"]:
            lines.append(f"👤 Gender: {entities['gender_filter']}")

        if entities["age_filter"]:
            age = entities["age_filter"]
            if age["min"] and age["max"]:
                if age["min"] == age["max"]:
                    lines.append(f"🎂 Age: {age['min']}세")
                else:
                    lines.append(f"🎂 Age: {age['min']}세 ~ {age['max']}세")
            elif age["min"]:
                lines.append(f"🎂 Age: ≥ {age['min']}세")
            elif age["max"]:
                lines.append(f"🎂 Age: ≤ {age['max']}세")

        if entities["keywords"]:
            lines.append(f"🔑 Keywords: {', '.join(entities['keywords'])}")

        if entities["filters"]:
            lines.append(f"\n📌 Filters: {entities['filters']}")

        return "\n".join(lines)

    def close(self):
        """리소스 정리"""
        if self.pg_conn:
            self.pg_conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# 편의 함수
def extract_entities_from_query(query: str, postgres_url: str = None) -> Dict[str, Any]:
    """
    질의에서 엔티티 추출 (원샷 함수)

    Args:
        query: 자연어 질의
        postgres_url: PostgreSQL 연결 문자열

    Returns:
        추출된 엔티티 딕셔너리
    """
    with NLMapper(postgres_url) as mapper:
        return mapper.extract_entities(query)
