"""
Base Parser for Carrier-Specific Table Parsing

Provides abstract base class and common utilities for all carrier parsers.

Validation Modes:
- NORMAL (default): Balanced filtering (348 unique coverages)
- STRICT: Aggressive filtering for Phase 5 accuracy boost (target: 250-270 coverages)
  Set environment variable: COVERAGE_VALIDATION_STRICT=1
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import re
import os


class BaseCarrierParser(ABC):
    """
    Abstract base class for carrier-specific parsers

    Each carrier parser must implement parse_coverage_row() method
    to extract coverage data from table rows according to carrier-specific
    table structure.

    Common utilities:
    - clean_coverage_name(): Remove newlines and normalize whitespace
    - is_row_number(): Detect row numbers like "1", "1.", "13."

    Validation Modes (controlled by COVERAGE_VALIDATION_STRICT env var):
    - NORMAL (default): 348 unique coverages
    - STRICT (set COVERAGE_VALIDATION_STRICT=1): Target 250-270 coverages
    """

    # Check if strict validation mode is enabled
    STRICT_MODE = os.getenv('COVERAGE_VALIDATION_STRICT', '0') == '1'

    @abstractmethod
    def parse_coverage_row(self, cells: List[str]) -> Optional[Dict]:
        """
        Parse coverage row and return structured data

        Args:
            cells: List of cell values from table row

        Returns:
            Parsed coverage data dict or None if row should be skipped

            Example return value:
            {
                'coverage_name': '상해사망·후유장해(20-100%)',
                'coverage_amount': '1백만원',
                'premium': '132',
                'period': '20년/100세'
            }

        Note:
            - Return None to skip rows (e.g., category headers, empty rows)
            - All parsers should use clean_coverage_name() on coverage names
            - Column order varies by carrier - see carrier-specific docs
        """
        pass

    def clean_coverage_name(self, name: str) -> str:
        """
        Clean coverage name from parsing artifacts

        Removes:
        - Newline characters (\\n, \\r)
        - Excessive whitespace
        - Leading/trailing spaces

        Args:
            name: Raw coverage name from PDF

        Returns:
            Cleaned coverage name

        Example:
            >>> parser.clean_coverage_name("지급\\n보험금")
            "지급 보험금"
            >>> parser.clean_coverage_name("  암 진단  ")
            "암 진단"
        """
        if not name:
            return name

        # Remove newlines and carriage returns
        cleaned = name.replace('\n', ' ').replace('\r', ' ')

        # Normalize whitespace (collapse multiple spaces into one)
        cleaned = ' '.join(cleaned.split())

        return cleaned

    def is_row_number(self, text: str) -> bool:
        """
        Check if text is a row number

        Detects patterns like:
        - "1", "2", "13"
        - "1.", "2.", "13."

        Args:
            text: Cell value to check

        Returns:
            True if text matches row number pattern

        Example:
            >>> parser.is_row_number("1")
            True
            >>> parser.is_row_number("1.")
            True
            >>> parser.is_row_number("상해사망")
            False
        """
        if not text:
            return False

        # Pattern: optional digits followed by optional period
        # Examples: "1", "13", "1.", "13."
        return bool(re.match(r'^\d+\.?$', text.strip()))

    def is_empty_or_whitespace(self, text: str) -> bool:
        """
        Check if text is empty or contains only whitespace

        Args:
            text: Cell value to check

        Returns:
            True if text is empty or whitespace-only

        Example:
            >>> parser.is_empty_or_whitespace("")
            True
            >>> parser.is_empty_or_whitespace("   ")
            True
            >>> parser.is_empty_or_whitespace("암진단")
            False
        """
        return not text or not text.strip()

    def filter_empty_cells(self, cells: List[str]) -> List[str]:
        """
        Filter out empty cells from list

        Useful for parsers like KB where pdfplumber creates excessive empty columns.

        Args:
            cells: List of cell values (may contain empty strings)

        Returns:
            List with empty/whitespace-only cells removed

        Example:
            >>> parser.filter_empty_cells(['1', 'coverage', '', 'amount', ''])
            ['1', 'coverage', 'amount']
        """
        return [c for c in cells if c and c.strip()]

    def is_header_row(self, cells: List[str]) -> bool:
        """
        Detect if row is a table header (not data)

        Checks if row contains common header keywords that appear together.

        Args:
            cells: List of cell values from table row

        Returns:
            True if row is likely a header

        Example:
            >>> parser.is_header_row(['순번', '담보명', '가입금액', '보험료'])
            True
            >>> parser.is_header_row(['1', '상해사망', '1000만원', '500'])
            False
        """
        if not cells:
            return False

        # Join all cells to check for header patterns
        row_text = ' '.join([str(c).strip() for c in cells if c])

        # Header keywords that commonly appear in table headers
        # NOTE: Only include terms that are unlikely to appear in data rows
        # Excluded: '보험료', '만기', '납기' (appear in legitimate data like "20년납 100세만기")
        header_keywords = [
            '담보명', '보장내용', '가입금액', '순번', '구분',
            '가입담보', '위험보장', '계약정보',
            '피보험자', '계약자', '보험기간', '납입주기'
        ]

        # Count how many header keywords appear
        keyword_count = sum(1 for kw in header_keywords if kw in row_text)

        # If 2+ header keywords in same row, likely a header
        if keyword_count >= 2:
            return True

        # Special case: Single strong header indicators
        strong_headers = ['담보명 및 보장내용', '위험보장 및 보험금', '가입제안서']
        if any(header in row_text for header in strong_headers):
            return True

        return False

    def is_valid_coverage_name(self, text: str) -> bool:
        """
        Validate if text is a legitimate coverage name vs metadata/header/noise

        Filters out:
        - Table headers/metadata keywords
        - Date patterns
        - Pure numbers/amounts
        - Phone numbers/codes
        - Excessively long text (>150 chars)
        - Single special characters
        - URLs/websites

        Args:
            text: Coverage name candidate

        Returns:
            True if text is likely a valid coverage name

        Example:
            >>> parser.is_valid_coverage_name("암진단비(유사암제외)")
            True
            >>> parser.is_valid_coverage_name("납입주기")
            False
            >>> parser.is_valid_coverage_name("1544-0114")
            False
        """
        if not text or not text.strip():
            return False

        # Clean the text BEFORE validation
        text = self.clean_coverage_name(text)

        # Filter: Single characters or very short text (< 2 chars)
        if len(text) < 2:
            return False

        # Filter: Excessively long text (likely explanatory notes)
        # Reduced from 150 to 80 to catch long descriptions
        if len(text) > 80:
            return False

        # Filter: Table headers and metadata keywords
        metadata_keywords = [
            # Payment/Contract metadata
            '월납', '납입주기', '가입금액', '보험료', '환급금', '구분',
            '계약일', '보험기간', '경과기간', '최저보증이율', '환급률',
            # Generic terms (too broad)
            '지급보험금', '수술', '검사', '치료',
            # Table headers (newly added)
            '담보명', '보장내용', '가입담보', '위험보장', '가입담보명',
            # Common honorifics/metadata
            '고객님', '피보험자', '계약자',
            # Generic short terms (added for Phase 0R validation++)
            '질병사망', '상해사망', '주요 치료', '특정 치료',
            '유사암 수술',  # Too generic without specifics
            '지급 보험금', '지급보험금',  # Too generic
            '통증 완화 치료', '재활 치료',  # Too generic
            '주 요 치 료', '재 활 치 료', '검 사',  # Excessive spacing variants
        ]
        if text in metadata_keywords:
            return False

        # Filter: Excessive whitespace patterns (e.g., "재 활 치 료", "검 사")
        # Pattern 1: Korean characters with 2+ consecutive spaces
        if re.search(r'[가-힣]\s{2,}[가-힣]', text):
            return False

        # Pattern 2: Single-syllable words separated by spaces (e.g., "주 요 치 료")
        # Count: if >25% of characters are spaces, reject (tightened from 40%)
        if len(text) > 0:
            space_ratio = text.count(' ') / len(text)
            if space_ratio > 0.25:
                return False

        # Pattern 3: Very short words (1-2 chars) with spaces
        # Example: "검 사" (each part is ≤2 chars)
        words = text.split()
        if len(words) >= 2:
            short_word_count = sum(1 for w in words if len(w) <= 2 and re.match(r'^[가-힣]+$', w))
            if short_word_count == len(words):  # All words are short
                return False

        # Pattern 4: Broken Korean text (single syllables separated by spaces)
        # Example: "비급 여 (전 액본 인부 담포 함)" - PDF parsing error
        if re.search(r'[가-힣]\s[가-힣]\s[가-힣]', text):
            return False

        # Filter: Phrases containing common header patterns
        # "위험보장 및 보험금 지급내용" type phrases
        if any(keyword in text for keyword in ['위험보장', '지급내용']):
            if len(text.split()) <= 3:  # Short phrases with these keywords
                return False

        # Filter: Date patterns (YYYY-MM-DD, YYYY-MM-DD ~ YYYY-MM-DD)
        if re.match(r'^\d{4}-\d{2}-\d{2}', text):
            return False

        # Filter: Pure numbers (including formatted amounts like "37,209,204")
        # But allow numbers with Korean characters like "1백만원", "10년갱신"
        if re.match(r'^[\d,\.]+$', text):
            return False

        # Filter: Korean currency amounts (numbers ending with "원" or "만원")
        # Examples: "28,403,040원", "1,000만원", "500원"
        if re.match(r'^[\d,\.]+\s*(만)?원$', text):
            return False

        # NOTE: 숫자 prefix (e.g., "119 뇌졸중진단비")는 coverage_pipeline._clean_coverage_name()에서
        # clause_number로 분리되므로 여기서 필터링하지 않음
        # if re.match(r'^\d+\s+', text):
        #     return False

        # Filter: Phone numbers (XXXX-XXXX format)
        if re.match(r'^\d{4}-\d{4}$', text):
            return False

        # Filter: Document codes (pattern like RQ25-53381446)
        if re.match(r'^[A-Z]{2}\d{2}-\d+$', text):
            return False

        # Filter: URLs and websites
        if 'www.' in text or 'http' in text or '.co.kr' in text or '.com' in text:
            return False

        # Filter: Bracket-enclosed section headers
        # Examples: "[보험금을 지급하지 않는 사항]", "[참고사항]"
        if text.startswith('[') and text.endswith(']'):
            return False

        # Filter: "비급여(전액본인부담 포함)" patterns
        # These generate too many variations and are often descriptive rather than coverage names
        # Example: "비급여(전액본인부담 포함) 암(유사암제 외) 항암약물치료"
        # Note: This is aggressive - comment out if these are actually valid coverages
        if text.startswith('비급여(전액본인부담'):
            return False

        # Filter: Plan name patterns (e.g., "07종_(41-75세)_무해지_납중0%/납후50%_...")
        # Pattern: Contains underscores with percentage or 세/만기 terms
        if '_' in text and ('세)' in text or '만기' in text or '%' in text):
            return False

        # Filter: Year-month patterns (e.g., "2024-11", "2025-01")
        if re.match(r'^\d{4}-\d{1,2}$', text):
            return False

        # Filter: Document/Design ID patterns (e.g., "44512215-11-5-0001")
        if re.match(r'^\d{8,}-\d+-\d+-\d+$', text):
            return False

        # Filter: Parsing artifacts with brackets/parentheses noise
        # Examples: "기고]객님 (84102", corrupted text
        if re.search(r'^\S*\][가-힣]+\s*\(\d+', text):
            return False

        # Filter: Product names (starts with "무배당" or contains "보험" with long text)
        if text.startswith('무배당 ') or (len(text) > 20 and '보험' in text and '종합' in text):
            return False

        # Filter: Additional metadata keywords
        additional_metadata = [
            '합계보험료', '총납입보험료', '갱신계약', '1급', '2급', '3급',
        ]
        if text in additional_metadata:
            return False

        # Filter: Long descriptive phrases (commonly found in footnotes)
        # Examples: "보통약관의 보험금을 지급하지 않는 사유와 동일"
        # Pattern: Contains "보통약관", "사유", "동일", "해당" with multiple words
        exclusion_patterns = [
            '보통약관의',
            '지급하지 않는',
            '사유와 동일',
            '보험금을 지급',
            '참고하시기',
            '확인하시기',
        ]
        if any(pattern in text for pattern in exclusion_patterns):
            return False

        # Filter: Person names (Korean name pattern - single Hangul syllable repeated)
        # This is a heuristic - may need refinement
        if len(text) <= 4 and re.match(r'^[가-힣]{2,4}$', text):
            # Common metadata that matches this pattern
            common_non_coverage = [
                '이현기', '질병사망', '상해사망',  # First one is name, others are valid
            ]
            # Actually, we can't reliably distinguish names from coverage
            # Let's skip this check for now
            pass

        # Filter: Percentage values only
        if re.match(r'^[\d\.]+%?$', text):
            return False

        # Filter: Single Korean characters (구분 markers)
        if len(text) == 1 and re.match(r'[가-힣]', text):
            return False

        # Filter: Year markers like "10년경과", "20년경과" (metadata)
        if re.match(r'^\d+년경과$', text):
            return False

        # Filter: Month markers like "10월"
        if re.match(r'^\d+월$', text):
            return False

        # Filter: Age markers like "80세만기"
        if re.match(r'^\d+세만기$', text):
            return False

        # Filter: Plan type patterns (e.g., "영업용 운전자형", "자가용 운전자형", "보험료 납입면제형")
        plan_type_patterns = [
            r'운전자형$',           # Ends with 운전자형
            r'납입면제.*형$',       # 보험료 납입면제형, 보험료 납입면제 미적용형
            r'가전제품.*비용$',     # 12대가전제품 수리비용
        ]
        if any(re.search(p, text) for p in plan_type_patterns):
            return False

        # Filter: Surgery type patterns (e.g., "2종수술", "3종수술", "수술 (1-5종)")
        if re.match(r'^\d+종수술$', text):
            return False
        if re.match(r'^수술\s*\(\d+-\d+종\)$', text):
            return False

        # Filter: Generic diagnosis/surgery terms (too short, no specifics)
        generic_medical_terms = [
            '질병사망', '상해사망', '깁스치료', '재활치료', '주요치료',
            '특정치료', '중환자실치료', '화재벌금', '상해수술비', '질병수술비',
            '유사암수술비', '유사암진단비', '골절/화상', '3대진단',
            '부목치료', '유사암 수술',
        ]
        if text in generic_medical_terms:
            return False

        # Filter: Medical procedure with (급여) suffix - these are procedure codes, not coverages
        # Examples: "CT촬영(급여)", "MRI촬영(급여)", "양전자단층촬영 (PET)(급여)"
        if text.endswith('(급여)'):
            return False

        # Filter: Legal expense patterns (법률비용) - these are rider types
        # Examples: "민사소송법률비용", "부동산소유권 법률비용"
        if '법률비용' in text:
            return False

        # Filter: Patterns starting with parenthesis year/renewal
        # Examples: "(10년갱신)갱신형 다빈치로봇", "(20년갱신)갱신형 중증질환자"
        if re.match(r'^\(\d+년갱신\)', text):
            return False

        # Filter: Common table section headers
        section_headers = [
            '기본계약', '선택계약', '갱신형', '비갱신형',
            '자동갱신특약', '중환자실치료', '재활치료', '주요치료',
            '특정치료', '깁스치료', '부목치료', '영업용운전자형', '자가용운전자형',
        ]
        if text in section_headers:
            # Actually some of these ARE valid coverage names!
            # Let's only filter truly generic ones (section markers, not coverages)
            generic_headers = [
                '기본계약', '선택계약', '자동갱신특약', '갱신형', '비갱신형',
                '주요치료', '영업용운전자형', '자가용운전자형'
            ]
            if text in generic_headers:
                return False

        # ========================================================================
        # OPTION B: STRICT MODE FILTERS (Activate with COVERAGE_VALIDATION_STRICT=1)
        # Target: Reduce from 348 → 250-270 unique coverages
        # Trade-off: May filter some valid coverages for higher Phase 5 accuracy
        # ========================================================================
        if self.STRICT_MODE:
            # STRICT-1: Filter very short coverage names (≤5 Korean characters)
            # Examples to filter: "화상진단비" (5 chars), "상해수술비" (5 chars)
            # Rationale: Too generic, often variations of longer names
            if len(text) <= 5 and re.match(r'^[가-힣()]+$', text):
                return False

            # STRICT-2: Filter coverage names with "(급여)" suffix
            # Examples: "CT촬영(급여)", "양전자단층촬영(PET)(급여)"
            # Rationale: These are medical procedures, not coverage names
            if text.endswith('(급여)'):
                return False

            # STRICT-3: Additional generic medical terms
            strict_terms = [
                '항암방사선치료비', '항암약물치료비',  # Too generic
                '질병수술비', '상해수술비',  # Too generic
                '화재벌금',  # Non-insurance term
            ]
            if text in strict_terms:
                return False

            # STRICT-4: Filter "담보" suffix variations
            # Examples: "뇌출혈진단담보", "화상진단담보"
            # Rationale: Same as "진단비" versions, creates duplicates
            if text.endswith('담보') and len(text) <= 10:
                return False

            # STRICT-5: Meritz-specific aggressive filter
            # If coverage starts with known Meritz patterns, apply length filter
            meritz_patterns = ['암 ', '기타피부암', '양전자', 'CT촬영', '항암']
            if any(text.startswith(p) for p in meritz_patterns):
                if len(text) < 8:  # Filter short Meritz-style names
                    return False

        # END STRICT MODE FILTERS
        # ========================================================================

        return True
