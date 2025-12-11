"""
정보 추출기 (InfoExtractor)

단일 보험사의 상품/담보에 대한 특정 정보를 추출합니다.
- 보장개시일
- 보장한도
- 가입나이
- 면책사항
- 갱신기간 및 비율
"""

import re
from typing import Dict, Any, Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor


class InfoExtractor:
    """단일 보험사 상품/담보 정보 추출기"""

    def __init__(self, postgres_url: str):
        self.pg_url = postgres_url

    def _get_connection(self):
        """PostgreSQL 연결"""
        return psycopg2.connect(self.pg_url)

    def extract_info(
        self,
        company: str,
        coverage_keyword: str,
        info_type: str,
        query_keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        특정 정보 타입을 추출합니다.

        Args:
            company: 보험사명
            coverage_keyword: 담보 키워드
            info_type: 정보 타입 (coverage-start-date, coverage-limit, enrollment-age, exclusions, renewal-info)
            query_keywords: 쿼리에서 추출한 키워드 리스트

        Returns:
            추출된 정보를 포함한 딕셔너리
        """
        # 1. 해당 보험사/담보의 상품 정보 조회
        product_info = self._find_product_coverage(company, coverage_keyword, query_keywords)

        if not product_info:
            return {
                "status": "no_data",
                "message": f"{company}의 {coverage_keyword} 관련 상품을 찾을 수 없습니다."
            }

        # 2. 정보 타입에 따라 추출 로직 분기
        if info_type == "coverage-start-date":
            return self._extract_coverage_start_date(product_info)
        elif info_type == "coverage-limit":
            return self._extract_coverage_limit(product_info)
        elif info_type == "enrollment-age":
            return self._extract_enrollment_age(product_info)
        elif info_type == "exclusions":
            return self._extract_exclusions(product_info)
        elif info_type == "renewal-info":
            return self._extract_renewal_info(product_info)
        else:
            return {
                "status": "error",
                "message": f"지원하지 않는 정보 타입: {info_type}"
            }

    def _find_product_coverage(
        self,
        company: str,
        coverage_keyword: str,
        query_keywords: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        보험사와 담보 키워드로 상품/담보 정보 조회

        Returns:
            {
                "company_name": str,
                "product_id": int,
                "product_name": str,
                "coverage_id": int,
                "coverage_name": str,
                "benefit_amount": float
            }
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 키워드 우선순위 설정 (query_keywords 우선)
                keywords = []
                if query_keywords:
                    # 암 관련 키워드 우선순위
                    if "제자리암" in query_keywords:
                        keywords.append("제자리암")
                    elif "경계성종양" in query_keywords:
                        keywords.append("경계성종양")
                    elif "유사암" in query_keywords or "4대유사암" in query_keywords:
                        keywords.append("유사암")
                    elif "암" in query_keywords:
                        keywords.append("암")

                    # 기타 키워드 추가
                    for kw in query_keywords:
                        if kw not in ["암", "유사암", "제자리암", "경계성종양"] and kw not in keywords:
                            keywords.append(kw)

                # coverage_keyword도 추가
                if coverage_keyword and coverage_keyword not in keywords:
                    keywords.append(coverage_keyword)

                # LIKE 조건 생성
                like_conditions = " OR ".join([f"cov.coverage_name LIKE %s" for _ in keywords])
                like_params = [f'%{kw}%' for kw in keywords]

                # 유사암 제외 조건
                exclude_condition = ""
                if "유사암" in keywords:
                    exclude_condition = " AND cov.coverage_name NOT LIKE '%%유사암제외%%' AND cov.coverage_name NOT LIKE '%%유사암 제외%%'"
                elif "암" in keywords:
                    exclude_condition = " AND (cov.coverage_name NOT LIKE '%%유사암%%' OR cov.coverage_name LIKE '%%유사암제외%%' OR cov.coverage_name LIKE '%%유사암 제외%%')"

                query = f"""
                    SELECT
                        comp.company_name,
                        p.id as product_id,
                        p.product_name,
                        cov.id as coverage_id,
                        cov.coverage_name,
                        b.benefit_amount
                    FROM coverage cov
                    JOIN product p ON cov.product_id = p.id
                    JOIN company comp ON p.company_id = comp.id
                    LEFT JOIN benefit b ON cov.id = b.coverage_id
                    WHERE comp.company_name = %s
                      AND ({like_conditions})
                      {exclude_condition}
                    ORDER BY
                        b.benefit_amount DESC NULLS LAST
                    LIMIT 1
                """

                params = (company, *like_params)
                cur.execute(query, params)
                result = cur.fetchone()

                return dict(result) if result else None
        finally:
            conn.close()

    def _extract_coverage_start_date(self, product_info: Dict[str, Any]) -> Dict[str, Any]:
        """보장개시일 추출"""
        company = product_info["company_name"]
        product_name = product_info["product_name"]
        coverage_name = product_info["coverage_name"]
        benefit_amount = product_info.get("benefit_amount")

        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 기본계약인 경우 상품 전체 보장개시일 검색
                # 특별약관인 경우 해당 담보명 포함 조항 검색
                is_main_coverage = coverage_name in ["기본계약", "주계약", "Main Coverage"]

                if is_main_coverage:
                    # 기본계약: 상품 전체의 보장개시일 조항 검색
                    cur.execute("""
                        SELECT dc.clause_title, dc.clause_text, dc.clause_number
                        FROM document_clause dc
                        JOIN document d ON dc.document_id = d.id
                        JOIN product p ON d.product_id = p.id
                        JOIN company comp ON p.company_id = comp.id
                        WHERE comp.company_name = %s
                          AND p.product_name = %s
                          AND (
                              dc.clause_text LIKE '%%보장개시%%'
                              OR dc.clause_text LIKE '%%면책기간%%'
                              OR dc.clause_text LIKE '%%책임개시%%'
                              OR dc.clause_text LIKE '%%책임이시작되는날%%'
                          )
                          AND dc.clause_text NOT LIKE '%%특별약관%%'
                        ORDER BY
                            CASE
                                WHEN dc.clause_title LIKE '%%보장개시%%' THEN 1
                                WHEN dc.clause_title LIKE '%%면책%%' THEN 2
                                WHEN dc.clause_title LIKE '%%책임개시%%' THEN 3
                                ELSE 4
                            END
                        LIMIT 5
                    """, (company, product_name))
                else:
                    # 특별약관: 담보명 포함 조항 검색
                    # Check if coverage has parent (for hierarchy support)
                    cur.execute("""
                        SELECT c.id, c.parent_coverage_id, parent.coverage_name as parent_name
                        FROM coverage c
                        JOIN product p ON c.product_id = p.id
                        JOIN company comp ON p.company_id = comp.id
                        LEFT JOIN coverage parent ON c.parent_coverage_id = parent.id
                        WHERE comp.company_name = %s
                          AND p.product_name = %s
                          AND c.coverage_name = %s
                    """, (company, product_name, coverage_name))

                    coverage_info = cur.fetchone()
                    parent_coverage_name = coverage_info["parent_name"] if coverage_info and coverage_info["parent_coverage_id"] else None

                    # Build search query with both direct and parent coverage names
                    coverage_patterns = [f'%{coverage_name}%']
                    if parent_coverage_name:
                        coverage_patterns.append(f'%{parent_coverage_name}%')

                    # Search for clauses matching any of the coverage patterns
                    # Use UNION to combine direct and parent results, prioritizing parent clauses
                    if parent_coverage_name:
                        query = """
                            SELECT DISTINCT dc.clause_title, dc.clause_text, dc.clause_number,
                                   CASE
                                       WHEN (dc.clause_text LIKE %s OR dc.clause_title LIKE %s) THEN 1
                                       ELSE 2
                                   END as source_priority,
                                   CASE
                                       WHEN dc.clause_title LIKE '%%보장개시%%' THEN 1
                                       WHEN dc.clause_title LIKE '%%면책%%' THEN 2
                                       ELSE 3
                                   END as title_priority
                            FROM document_clause dc
                            JOIN document d ON dc.document_id = d.id
                            JOIN product p ON d.product_id = p.id
                            JOIN company comp ON p.company_id = comp.id
                            WHERE comp.company_name = %s
                              AND p.product_name = %s
                              AND (
                                  dc.clause_text LIKE '%%보장개시%%'
                                  OR dc.clause_text LIKE '%%면책기간%%'
                                  OR dc.clause_text LIKE '%%책임개시%%'
                              )
                              AND (
                                  dc.clause_text LIKE %s
                                  OR dc.clause_title LIKE %s
                                  OR dc.clause_text LIKE %s
                                  OR dc.clause_title LIKE %s
                              )
                            ORDER BY source_priority, title_priority
                            LIMIT 5
                        """
                        cur.execute(query, (
                            f'%{parent_coverage_name}%', f'%{parent_coverage_name}%',  # source_priority
                            company, product_name,
                            f'%{coverage_name}%', f'%{coverage_name}%',
                            f'%{parent_coverage_name}%', f'%{parent_coverage_name}%'
                        ))
                    else:
                        # No parent, search only direct coverage
                        cur.execute("""
                            SELECT dc.clause_title, dc.clause_text, dc.clause_number, 1,
                                   CASE
                                       WHEN dc.clause_title LIKE '%%보장개시%%' THEN 1
                                       WHEN dc.clause_title LIKE '%%면책%%' THEN 2
                                       ELSE 3
                                   END as title_priority
                            FROM document_clause dc
                            JOIN document d ON dc.document_id = d.id
                            JOIN product p ON d.product_id = p.id
                            JOIN company comp ON p.company_id = comp.id
                            WHERE comp.company_name = %s
                              AND p.product_name = %s
                              AND (
                                  dc.clause_text LIKE '%%보장개시%%'
                                  OR dc.clause_text LIKE '%%면책기간%%'
                                  OR dc.clause_text LIKE '%%책임개시%%'
                              )
                              AND (
                                  dc.clause_text LIKE %s
                                  OR dc.clause_title LIKE %s
                              )
                            ORDER BY title_priority
                            LIMIT 5
                        """, (company, product_name, f'%{coverage_name}%', f'%{coverage_name}%'))

                    # Fetch results and remove priority columns
                    raw_clauses = cur.fetchall()
                    clauses = [{"clause_title": c["clause_title"], "clause_text": c["clause_text"], "clause_number": c["clause_number"]}
                               for c in raw_clauses]

                if not clauses:
                    return {
                        "status": "no_data",
                        "company": company,
                        "product": product_name,
                        "coverage": coverage_name,
                        "benefit_amount": benefit_amount,
                        "message": "보장개시일 정보를 찾을 수 없습니다."
                    }

                # 보장개시일 패턴 추출
                start_date_info = self._parse_coverage_start_date(clauses)

                return {
                    "status": "success",
                    "company": company,
                    "product": product_name,
                    "coverage": coverage_name,
                    "benefit_amount": benefit_amount,
                    "info": start_date_info,
                    "sources": [
                        {
                            "clause_number": c["clause_number"],
                            "clause_title": c["clause_title"],
                            "clause_text": c["clause_text"][:300]
                        }
                        for c in clauses[:3]
                    ]
                }
        finally:
            conn.close()

    def _parse_coverage_start_date(self, clauses: List[Dict]) -> str:
        """보장개시일 텍스트 파싱"""
        patterns = [
            r'계약일부터\s*(\d+)일',
            r'가입일부터\s*(\d+)일',
            r'책임개시일부터\s*(\d+)일',
            r'면책기간\s*(\d+)일',
            r'(\d+)일\s*이후',
        ]

        for clause in clauses:
            text = clause["clause_text"]
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    days = match.group(1)
                    # 90일이면 "계약일로부터 91일째" 형식으로 반환
                    return f"계약일로부터 {days}일 경과 후 (면책기간 {days}일)"

        # 패턴 매칭 실패 시 첫 번째 조항 텍스트 요약 반환
        if clauses:
            text = clauses[0]["clause_text"]
            # 보장개시일 관련 문장 추출 (최대 200자)
            sentences = text.split('.')
            for sent in sentences:
                if any(kw in sent for kw in ["보장개시", "면책기간", "책임개시"]):
                    return sent.strip()[:200]

        return "약관 참조 필요"

    def _extract_coverage_limit(self, product_info: Dict[str, Any]) -> Dict[str, Any]:
        """보장한도 추출"""
        company = product_info["company_name"]
        product_name = product_info["product_name"]
        coverage_name = product_info["coverage_name"]
        benefit_amount = product_info.get("benefit_amount")

        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 보장한도, 지급제한 관련 조항 검색
                # Step 1: Try direct coverage name match
                cur.execute("""
                    SELECT dc.clause_title, dc.clause_text, dc.clause_number
                    FROM document_clause dc
                    JOIN document d ON dc.document_id = d.id
                    JOIN product p ON d.product_id = p.id
                    JOIN company comp ON p.company_id = comp.id
                    WHERE comp.company_name = %s
                      AND p.product_name = %s
                      AND (
                          dc.clause_text LIKE '%%보장한도%%'
                          OR dc.clause_text LIKE '%%지급한도%%'
                          OR dc.clause_text LIKE '%%지급제한%%'
                          OR dc.clause_text LIKE '%%1회당%%'
                          OR dc.clause_text LIKE '%%연간%%'
                      )
                      AND (
                          dc.clause_text LIKE %s
                          OR dc.clause_title LIKE %s
                      )
                    ORDER BY
                        CASE
                            WHEN dc.clause_title LIKE '%%보장한도%%' THEN 1
                            WHEN dc.clause_title LIKE '%%지급제한%%' THEN 2
                            ELSE 3
                        END
                    LIMIT 5
                """, (company, product_name, f'%{coverage_name}%', f'%{coverage_name}%'))

                clauses = cur.fetchall()

                # Step 2: If no results, try parent coverage hierarchy
                if not clauses:
                    # Get coverage_id and check for parent
                    cur.execute("""
                        SELECT c.id, c.parent_coverage_id, parent.coverage_name
                        FROM coverage c
                        JOIN product p ON c.product_id = p.id
                        JOIN company comp ON p.company_id = comp.id
                        LEFT JOIN coverage parent ON c.parent_coverage_id = parent.id
                        WHERE comp.company_name = %s
                          AND p.product_name = %s
                          AND c.coverage_name = %s
                    """, (company, product_name, coverage_name))

                    coverage_info = cur.fetchone()
                    if coverage_info and coverage_info[1]:  # Has parent
                        parent_coverage_name = coverage_info[2]

                        # Search for clauses with parent coverage name
                        cur.execute("""
                            SELECT dc.clause_title, dc.clause_text, dc.clause_number
                            FROM document_clause dc
                            JOIN document d ON dc.document_id = d.id
                            JOIN product p ON d.product_id = p.id
                            JOIN company comp ON p.company_id = comp.id
                            WHERE comp.company_name = %s
                              AND p.product_name = %s
                              AND (
                                  dc.clause_text LIKE '%%보장한도%%'
                                  OR dc.clause_text LIKE '%%지급한도%%'
                                  OR dc.clause_text LIKE '%%지급제한%%'
                                  OR dc.clause_text LIKE '%%1회당%%'
                                  OR dc.clause_text LIKE '%%연간%%'
                              )
                              AND (
                                  dc.clause_text LIKE %s
                                  OR dc.clause_title LIKE %s
                              )
                            ORDER BY
                                CASE
                                    WHEN dc.clause_title LIKE '%%보장한도%%' THEN 1
                                    WHEN dc.clause_title LIKE '%%지급제한%%' THEN 2
                                    ELSE 3
                                END
                            LIMIT 5
                        """, (company, product_name, f'%{parent_coverage_name}%', f'%{parent_coverage_name}%'))

                        clauses = cur.fetchall()

                if not clauses:
                    # 보장한도 정보가 없으면 기본 benefit_amount만 반환
                    benefit_str = f"{int(benefit_amount):,}원" if benefit_amount else "N/A"

                    return {
                        "status": "success",
                        "company": company,
                        "product": product_name,
                        "coverage": coverage_name,
                        "benefit_amount": benefit_amount,
                        "info": f"기본 보장금액: {benefit_str}\n(별도 한도 제한 없음)",
                        "sources": []
                    }

                # 보장한도 정보 파싱
                limit_info = self._parse_coverage_limit(clauses)

                return {
                    "status": "success",
                    "company": company,
                    "product": product_name,
                    "coverage": coverage_name,
                    "benefit_amount": benefit_amount,
                    "info": limit_info,
                    "sources": [
                        {
                            "clause_number": c["clause_number"],
                            "clause_title": c["clause_title"],
                            "clause_text": c["clause_text"][:300]
                        }
                        for c in clauses[:3]
                    ]
                }
        finally:
            conn.close()

    def _parse_coverage_limit(self, clauses: List[Dict]) -> str:
        """보장한도 텍스트 파싱"""
        limit_parts = []

        for clause in clauses:
            text = clause["clause_text"]

            # 1회당, 연간 한도 패턴
            patterns = [
                (r'1회당\s*(\d{1,3}(?:,\d{3})*)\s*만원', '1회당'),
                (r'연간\s*(\d{1,3}(?:,\d{3})*)\s*만원', '연간'),
                (r'연\s*(\d+)회', '연간 횟수'),
                (r'최대\s*(\d{1,3}(?:,\d{3})*)\s*만원', '최대'),
            ]

            for pattern, label in patterns:
                match = re.search(pattern, text)
                if match:
                    limit_parts.append(f"{label} {match.group(0)}")

        if limit_parts:
            return "\n".join(f"- {part}" for part in limit_parts)

        # 패턴 매칭 실패 시 첫 번째 조항 텍스트 요약
        if clauses:
            text = clauses[0]["clause_text"]
            sentences = text.split('.')
            for sent in sentences:
                if any(kw in sent for kw in ["한도", "제한", "1회당", "연간"]):
                    return sent.strip()[:200]

        return "약관 참조 필요"

    def _extract_enrollment_age(self, product_info: Dict[str, Any]) -> Dict[str, Any]:
        """가입나이 추출 (compare.py의 _get_age_conditions 로직 재사용)"""
        company = product_info["company_name"]
        product_name = product_info["product_name"]
        coverage_name = product_info["coverage_name"]
        benefit_amount = product_info.get("benefit_amount")

        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Step 1: Try direct coverage name match
                cur.execute("""
                    SELECT dc.clause_text, dc.clause_title, dc.clause_number
                    FROM document_clause dc
                    JOIN document d ON dc.document_id = d.id
                    JOIN product p ON d.product_id = p.id
                    JOIN company comp ON p.company_id = comp.id
                    WHERE comp.company_name = %s
                      AND p.product_name = %s
                      AND (dc.clause_text LIKE %s OR dc.clause_title LIKE %s)
                      AND dc.clause_text LIKE '%%가입%%나이%%'
                    LIMIT 5
                """, (company, product_name, f'%{coverage_name}%', f'%{coverage_name}%'))

                rows = cur.fetchall()

                # Step 2: If no results, try parent coverage hierarchy
                if not rows:
                    # Get coverage_id and check for parent
                    cur.execute("""
                        SELECT c.id, c.parent_coverage_id, parent.coverage_name
                        FROM coverage c
                        JOIN product p ON c.product_id = p.id
                        JOIN company comp ON p.company_id = comp.id
                        LEFT JOIN coverage parent ON c.parent_coverage_id = parent.id
                        WHERE comp.company_name = %s
                          AND p.product_name = %s
                          AND c.coverage_name = %s
                    """, (company, product_name, coverage_name))

                    coverage_info = cur.fetchone()
                    if coverage_info and coverage_info[1]:  # Has parent
                        parent_coverage_name = coverage_info[2]

                        # Search for clauses with parent coverage name
                        cur.execute("""
                            SELECT dc.clause_text, dc.clause_title, dc.clause_number
                            FROM document_clause dc
                            JOIN document d ON dc.document_id = d.id
                            JOIN product p ON d.product_id = p.id
                            JOIN company comp ON p.company_id = comp.id
                            WHERE comp.company_name = %s
                              AND p.product_name = %s
                              AND (dc.clause_text LIKE %s OR dc.clause_title LIKE %s)
                              AND dc.clause_text LIKE '%%가입%%나이%%'
                            LIMIT 5
                        """, (company, product_name, f'%{parent_coverage_name}%', f'%{parent_coverage_name}%'))

                        rows = cur.fetchall()

                if not rows:
                    return {
                        "status": "no_data",
                        "company": company,
                        "product": product_name,
                        "coverage": coverage_name,
                        "benefit_amount": benefit_amount,
                        "message": "가입나이 정보를 찾을 수 없습니다."
                    }

                # 나이 범위 추출
                age_pattern = re.compile(r'만?(\d+)세\s*~\s*(\d+)세')

                for row in rows:
                    clause_text = row["clause_text"]
                    lines = clause_text.split('\n')

                    for i, line in enumerate(lines):
                        if coverage_name in line or '가입나이' in line:
                            # 컨텍스트: 앞뒤 1-2줄
                            context = '\n'.join(lines[max(0, i-1):min(len(lines), i+3)])
                            match = age_pattern.search(context)

                            if match:
                                min_age, max_age = match.groups()
                                age_range = f"{min_age}세~{max_age}세"

                                return {
                                    "status": "success",
                                    "company": company,
                                    "product": product_name,
                                    "coverage": coverage_name,
                                    "benefit_amount": benefit_amount,
                                    "info": f"가입 가능 나이: 만 {age_range}",
                                    "sources": [
                                        {
                                            "clause_number": row["clause_number"],
                                            "clause_title": row["clause_title"],
                                            "clause_text": context[:300]
                                        }
                                    ]
                                }

                # 패턴 매칭 실패 시 첫 번째 조항 반환
                return {
                    "status": "success",
                    "company": company,
                    "product": product_name,
                    "coverage": coverage_name,
                    "benefit_amount": benefit_amount,
                    "info": "약관 참조 필요 (나이 범위 파싱 실패)",
                    "sources": [
                        {
                            "clause_number": rows[0]["clause_number"],
                            "clause_title": rows[0]["clause_title"],
                            "clause_text": rows[0]["clause_text"][:300]
                        }
                    ]
                }
        finally:
            conn.close()

    def _extract_exclusions(self, product_info: Dict[str, Any]) -> Dict[str, Any]:
        """면책사항 추출"""
        company = product_info["company_name"]
        product_name = product_info["product_name"]
        coverage_name = product_info["coverage_name"]
        benefit_amount = product_info.get("benefit_amount")

        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 면책, 보장제외 관련 조항 검색
                # Step 1: Try direct coverage name match
                cur.execute("""
                    SELECT dc.clause_title, dc.clause_text, dc.clause_number
                    FROM document_clause dc
                    JOIN document d ON dc.document_id = d.id
                    JOIN product p ON d.product_id = p.id
                    JOIN company comp ON p.company_id = comp.id
                    WHERE comp.company_name = %s
                      AND p.product_name = %s
                      AND (
                          dc.clause_text LIKE '%%면책%%'
                          OR dc.clause_text LIKE '%%보장제외%%'
                          OR dc.clause_text LIKE '%%보상하지%%'
                          OR dc.clause_title LIKE '%%면책%%'
                          OR dc.clause_title LIKE '%%제외%%'
                      )
                      AND (
                          dc.clause_text LIKE %s
                          OR dc.clause_title LIKE %s
                      )
                    ORDER BY
                        CASE
                            WHEN dc.clause_title LIKE '%%면책%%' THEN 1
                            WHEN dc.clause_title LIKE '%%제외%%' THEN 2
                            ELSE 3
                        END
                    LIMIT 5
                """, (company, product_name, f'%{coverage_name}%', f'%{coverage_name}%'))

                clauses = cur.fetchall()

                # Step 2: If no results, try parent coverage hierarchy
                if not clauses:
                    # Get coverage_id and check for parent
                    cur.execute("""
                        SELECT c.id, c.parent_coverage_id, parent.coverage_name
                        FROM coverage c
                        JOIN product p ON c.product_id = p.id
                        JOIN company comp ON p.company_id = comp.id
                        LEFT JOIN coverage parent ON c.parent_coverage_id = parent.id
                        WHERE comp.company_name = %s
                          AND p.product_name = %s
                          AND c.coverage_name = %s
                    """, (company, product_name, coverage_name))

                    coverage_info = cur.fetchone()
                    if coverage_info and coverage_info[1]:  # Has parent
                        parent_coverage_name = coverage_info[2]

                        # Search for clauses with parent coverage name
                        cur.execute("""
                            SELECT dc.clause_title, dc.clause_text, dc.clause_number
                            FROM document_clause dc
                            JOIN document d ON dc.document_id = d.id
                            JOIN product p ON d.product_id = p.id
                            JOIN company comp ON p.company_id = comp.id
                            WHERE comp.company_name = %s
                              AND p.product_name = %s
                              AND (
                                  dc.clause_text LIKE '%%면책%%'
                                  OR dc.clause_text LIKE '%%보장제외%%'
                                  OR dc.clause_text LIKE '%%보상하지%%'
                                  OR dc.clause_title LIKE '%%면책%%'
                                  OR dc.clause_title LIKE '%%제외%%'
                              )
                              AND (
                                  dc.clause_text LIKE %s
                                  OR dc.clause_title LIKE %s
                              )
                            ORDER BY
                                CASE
                                    WHEN dc.clause_title LIKE '%%면책%%' THEN 1
                                    WHEN dc.clause_title LIKE '%%제외%%' THEN 2
                                    ELSE 3
                                END
                            LIMIT 5
                        """, (company, product_name, f'%{parent_coverage_name}%', f'%{parent_coverage_name}%'))

                        clauses = cur.fetchall()

                if not clauses:
                    return {
                        "status": "no_data",
                        "company": company,
                        "product": product_name,
                        "coverage": coverage_name,
                        "benefit_amount": benefit_amount,
                        "message": "면책사항 정보를 찾을 수 없습니다."
                    }

                # 면책사항 요약
                exclusion_summary = self._parse_exclusions(clauses)

                return {
                    "status": "success",
                    "company": company,
                    "product": product_name,
                    "coverage": coverage_name,
                    "benefit_amount": benefit_amount,
                    "info": exclusion_summary,
                    "sources": [
                        {
                            "clause_number": c["clause_number"],
                            "clause_title": c["clause_title"],
                            "clause_text": c["clause_text"][:300]
                        }
                        for c in clauses[:3]
                    ]
                }
        finally:
            conn.close()

    def _parse_exclusions(self, clauses: List[Dict]) -> str:
        """면책사항 텍스트 파싱"""
        exclusion_items = []

        for clause in clauses:
            text = clause["clause_text"]
            title = clause["clause_title"]

            # 조항 제목이 명확하면 제목 사용
            if "면책" in title or "제외" in title:
                exclusion_items.append(f"**{title}**")

            # 문장 단위로 분리하여 면책 관련 내용 추출
            sentences = text.split('.')
            for sent in sentences:
                if any(kw in sent for kw in ["면책", "보장하지", "제외", "보상하지"]):
                    sent_clean = sent.strip()
                    if len(sent_clean) > 10 and len(sent_clean) < 200:
                        exclusion_items.append(f"- {sent_clean}")

                    if len(exclusion_items) >= 5:  # 최대 5개 항목
                        break

            if len(exclusion_items) >= 5:
                break

        if exclusion_items:
            return "\n".join(exclusion_items[:5])

        # 패턴 매칭 실패 시 첫 번째 조항 요약
        if clauses:
            return clauses[0]["clause_text"][:300]

        return "약관 참조 필요"

    def _extract_renewal_info(self, product_info: Dict[str, Any]) -> Dict[str, Any]:
        """갱신기간 및 비율 추출"""
        company = product_info["company_name"]
        product_name = product_info["product_name"]
        coverage_name = product_info["coverage_name"]
        benefit_amount = product_info.get("benefit_amount")

        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 갱신, 감액 관련 조항 검색
                # Step 1: Try direct coverage name match
                cur.execute("""
                    SELECT dc.clause_title, dc.clause_text, dc.clause_number
                    FROM document_clause dc
                    JOIN document d ON dc.document_id = d.id
                    JOIN product p ON d.product_id = p.id
                    JOIN company comp ON p.company_id = comp.id
                    WHERE comp.company_name = %s
                      AND p.product_name = %s
                      AND (
                          dc.clause_text LIKE '%%갱신%%'
                          OR dc.clause_text LIKE '%%감액%%'
                          OR dc.clause_title LIKE '%%갱신%%'
                      )
                      AND (
                          dc.clause_text LIKE %s
                          OR dc.clause_title LIKE %s
                      )
                    ORDER BY
                        CASE
                            WHEN dc.clause_title LIKE '%%갱신%%' THEN 1
                            ELSE 2
                        END
                    LIMIT 5
                """, (company, product_name, f'%{coverage_name}%', f'%{coverage_name}%'))

                clauses = cur.fetchall()

                # Step 2: If no results, try parent coverage hierarchy
                if not clauses:
                    # Get coverage_id and check for parent
                    cur.execute("""
                        SELECT c.id, c.parent_coverage_id, parent.coverage_name
                        FROM coverage c
                        JOIN product p ON c.product_id = p.id
                        JOIN company comp ON p.company_id = comp.id
                        LEFT JOIN coverage parent ON c.parent_coverage_id = parent.id
                        WHERE comp.company_name = %s
                          AND p.product_name = %s
                          AND c.coverage_name = %s
                    """, (company, product_name, coverage_name))

                    coverage_info = cur.fetchone()
                    if coverage_info and coverage_info[1]:  # Has parent
                        parent_coverage_name = coverage_info[2]

                        # Search for clauses with parent coverage name
                        cur.execute("""
                            SELECT dc.clause_title, dc.clause_text, dc.clause_number
                            FROM document_clause dc
                            JOIN document d ON dc.document_id = d.id
                            JOIN product p ON d.product_id = p.id
                            JOIN company comp ON p.company_id = comp.id
                            WHERE comp.company_name = %s
                              AND p.product_name = %s
                              AND (
                                  dc.clause_text LIKE '%%갱신%%'
                                  OR dc.clause_text LIKE '%%감액%%'
                                  OR dc.clause_title LIKE '%%갱신%%'
                              )
                              AND (
                                  dc.clause_text LIKE %s
                                  OR dc.clause_title LIKE %s
                              )
                            ORDER BY
                                CASE
                                    WHEN dc.clause_title LIKE '%%갱신%%' THEN 1
                                    ELSE 2
                                END
                            LIMIT 5
                        """, (company, product_name, f'%{parent_coverage_name}%', f'%{parent_coverage_name}%'))

                        clauses = cur.fetchall()

                if not clauses:
                    return {
                        "status": "success",
                        "company": company,
                        "product": product_name,
                        "coverage": coverage_name,
                        "benefit_amount": benefit_amount,
                        "info": "비갱신형 (또는 갱신 정보 없음)",
                        "sources": []
                    }

                # 갱신 정보 파싱
                renewal_info = self._parse_renewal_info(clauses)

                return {
                    "status": "success",
                    "company": company,
                    "product": product_name,
                    "coverage": coverage_name,
                    "benefit_amount": benefit_amount,
                    "info": renewal_info,
                    "sources": [
                        {
                            "clause_number": c["clause_number"],
                            "clause_title": c["clause_title"],
                            "clause_text": c["clause_text"][:300]
                        }
                        for c in clauses[:3]
                    ]
                }
        finally:
            conn.close()

    def _parse_renewal_info(self, clauses: List[Dict]) -> str:
        """갱신 정보 텍스트 파싱"""
        renewal_parts = []

        for clause in clauses:
            text = clause["clause_text"]

            # 갱신 주기 패턴
            period_patterns = [
                r'(\d+)년마다\s*갱신',
                r'(\d+)년\s*주기',
                r'(\d+)년형',
            ]

            for pattern in period_patterns:
                match = re.search(pattern, text)
                if match:
                    years = match.group(1)
                    renewal_parts.append(f"갱신 주기: {years}년마다")
                    break

            # 감액 비율 패턴
            rate_patterns = [
                r'(\d+)%\s*감액',
                r'감액.*?(\d+)%',
            ]

            for pattern in rate_patterns:
                match = re.search(pattern, text)
                if match:
                    rate = match.group(1)
                    renewal_parts.append(f"감액 비율: {rate}%")
                    break

        if renewal_parts:
            return "\n".join(f"- {part}" for part in renewal_parts)

        # 패턴 매칭 실패 시 첫 번째 조항 요약
        if clauses:
            text = clauses[0]["clause_text"]
            sentences = text.split('.')
            for sent in sentences:
                if any(kw in sent for kw in ["갱신", "감액"]):
                    return sent.strip()[:200]

        return "갱신형 (상세 정보는 약관 참조)"
