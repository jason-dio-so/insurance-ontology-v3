"""
TextParser for Insurance Terms Documents (약관)

Purpose: Parse structured text documents (terms/약관) into article-level chunks
Strategy: Extract "제n조" articles with hierarchy (조, 항, 호)
Document Types: terms (약관)

Design: docs/phase0/PHASE0.2_ONTOLOGY_REDESIGN_v2.md
"""

import re
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ArticleChunk:
    """Article chunk from terms document"""
    clause_number: str              # "제1조", "제2조 제1항"
    clause_title: Optional[str]     # "보험금의 지급"
    clause_text: str                # Full article text
    clause_type: str                # 'article', 'paragraph', 'item'
    section_type: Optional[str]     # '보통약관', '특별약관'
    page_number: Optional[int]
    hierarchy_level: int            # 0=조, 1=항, 2=호
    parent_clause_id: Optional[int]


class TextParser:
    """Parser for text-heavy documents (terms/약관)"""

    # Article number patterns
    ARTICLE_PATTERNS = [
        r'제\s*(\d+)\s*조',           # 제1조
        r'제\s*(\d+)\s*조의\s*(\d+)',  # 제1조의2
    ]

    # Paragraph patterns
    PARAGRAPH_PATTERNS = [
        r'①',  # ①
        r'②',
        r'③',
        r'④',
        r'⑤',
        r'⑥',
        r'⑦',
        r'⑧',
        r'⑨',
        r'⑩',
    ]

    # Item patterns (호)
    ITEM_PATTERNS = [
        r'\d+\.',  # 1., 2., 3.
        r'[가-하]\.',  # 가., 나., 다.
    ]

    # Section type patterns
    SECTION_TYPE_PATTERNS = {
        '보통약관': r'보통\s*약관',
        '특별약관': r'특별\s*약관',
        '별표': r'별\s*표',
        '부칙': r'부\s*칙',
    }

    def __init__(self):
        """Initialize text parser"""
        pass

    def parse(self, sections: List[Dict], doc_metadata: Dict) -> List[Dict]:
        """
        Parse terms document into article chunks

        Args:
            sections: List of section dictionaries from convert_documents.py
                [{'text': '...', 'page': 1, 'section_type': '보통약관'}, ...]
            doc_metadata: Document metadata

        Returns:
            List of clause dictionaries for document_clause table
        """
        chunks = []

        for section in sections:
            text = section.get('text', '')
            page = section.get('page')
            section_type = section.get('section_type')

            # Extract articles from section text
            article_chunks = self._extract_articles(text, page, section_type)
            chunks.extend(article_chunks)

        return chunks

    def _extract_articles(
        self,
        text: str,
        page_number: Optional[int],
        section_type: Optional[str]
    ) -> List[Dict]:
        """
        Extract article-level chunks from text

        Args:
            text: Section text
            page_number: Page number
            section_type: Section type (보통약관, 특별약관, etc.)

        Returns:
            List of article chunk dictionaries
        """
        chunks = []

        # Split by article pattern "제n조"
        article_pattern = r'(제\s*\d+\s*조(?:의\s*\d+)?)'
        parts = re.split(article_pattern, text)

        current_article_number = None
        current_article_title = None
        current_article_text = []

        for i, part in enumerate(parts):
            # Check if this part is an article number
            if re.match(article_pattern, part):
                # Save previous article if exists
                if current_article_number and current_article_text:
                    chunks.append(self._create_article_chunk(
                        clause_number=current_article_number,
                        clause_title=current_article_title,
                        clause_text=''.join(current_article_text).strip(),
                        section_type=section_type,
                        page_number=page_number,
                    ))

                # Start new article
                current_article_number = part.strip()
                current_article_text = []
                current_article_title = None

            elif current_article_number:
                # This is article content
                # Try to extract title from first line
                if not current_article_title and i == parts.index(current_article_number) + 1:
                    lines = part.split('\n')
                    if lines and len(lines[0].strip()) > 0 and len(lines[0].strip()) < 100:
                        # First line is likely the title
                        first_line = lines[0].strip()
                        # Check if it's enclosed in brackets or parentheses
                        if '(' in first_line and ')' in first_line:
                            current_article_title = first_line[first_line.index('(')+1:first_line.index(')')].strip()
                            current_article_text.append(part)
                        elif '[' in first_line and ']' in first_line:
                            current_article_title = first_line[first_line.index('[')+1:first_line.index(']')].strip()
                            current_article_text.append(part)
                        else:
                            current_article_title = first_line
                            # Add remaining lines as article text
                            if len(lines) > 1:
                                current_article_text.append('\n'.join(lines[1:]))
                    else:
                        current_article_text.append(part)
                else:
                    current_article_text.append(part)

        # Save last article
        if current_article_number and current_article_text:
            chunks.append(self._create_article_chunk(
                clause_number=current_article_number,
                clause_title=current_article_title,
                clause_text=''.join(current_article_text).strip(),
                section_type=section_type,
                page_number=page_number,
            ))

        return chunks

    def _create_article_chunk(
        self,
        clause_number: str,
        clause_title: Optional[str],
        clause_text: str,
        section_type: Optional[str],
        page_number: Optional[int],
    ) -> Dict:
        """
        Create article chunk dictionary

        Args:
            clause_number: Article number (제1조)
            clause_title: Article title
            clause_text: Article text
            section_type: Section type
            page_number: Page number

        Returns:
            Clause dictionary for document_clause table
        """
        # Ensure clause_text is not empty (PostgreSQL NOT NULL constraint)
        if not clause_text or len(clause_text.strip()) == 0:
            clause_text = clause_title or clause_number or '(내용 없음)'

        return {
            'clause_number': clause_number,
            'clause_title': clause_title,
            'clause_text': clause_text,
            'clause_type': 'article',
            'structured_data': None,  # No structured data for text chunks
            'section_type': section_type,
            'page_number': page_number,
            'hierarchy_level': 0,  # 조 level
            'parent_clause_id': None,
            'attributes': None,
        }

    def detect_section_type(self, text: str) -> Optional[str]:
        """
        Detect section type from text (보통약관, 특별약관, etc.)

        Args:
            text: Section text

        Returns:
            Section type string or None
        """
        for section_type, pattern in self.SECTION_TYPE_PATTERNS.items():
            if re.search(pattern, text):
                return section_type
        return None
