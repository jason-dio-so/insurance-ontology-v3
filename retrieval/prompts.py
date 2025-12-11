"""
LLM Prompts

보험 약관 QA를 위한 LLM 프롬프트 템플릿

주요 기능:
- 근거 추적 강제 (조항 번호, 문서 ID 인용)
- 구조화된 출력 포맷 (JSON schema)
- 한계 명시 ("문서에 없는 내용은 답변하지 않음")

Usage:
    from retrieval.prompts import PromptBuilder

    builder = PromptBuilder()
    prompt = builder.build_qa_prompt(
        query="암 진단시 보장금액은?",
        context="[조항 내용...]"
    )
"""

from typing import Dict, Any, Optional
import json


class PromptBuilder:
    """프롬프트 빌더"""

    SYSTEM_PROMPT = """당신은 한국 보험 약관 전문가입니다.
다음 지침을 엄격히 따라주세요:

1. **근거 추적**: 모든 답변은 반드시 제공된 조항 번호([1], [2] 등)를 인용해야 합니다.
2. **정확성**: 제공된 문서에 없는 내용은 절대 만들어내지 마세요.
3. **명확성**: 보험 용어를 일반인이 이해하기 쉽게 설명하세요.
4. **한계 인식**: 답변할 수 없는 경우 솔직히 인정하세요.
5. **금액 추출 (Phase 5 v5)**: 보장금액을 답변할 때는 반드시 다음 형식을 따르세요:
   - "💰 보장금액: **N,NNN만원**" 형식의 숫자를 그대로 사용하세요
   - 예: "1,000만원", "3,000만원", "500만원"
   - 컨텍스트에서 "💰 보장금액: **X**" 또는 "가입금액: X"를 찾아 정확히 인용하세요

답변 형식:
- 답변: [조항을 인용하며 명확히 설명, 금액은 정확한 숫자로]
- 근거: [인용한 조항 번호와 문서 정보]
- 주의사항: [있다면 추가 설명]
"""

    def build_qa_prompt(
        self,
        query: str,
        context: str,
        response_format: str = "text"
    ) -> str:
        """
        QA 프롬프트 생성

        Args:
            query: 사용자 질의
            context: 컨텍스트 (조항 내용)
            response_format: 응답 포맷 ("text" 또는 "json")

        Returns:
            완성된 프롬프트
        """
        if response_format == "json":
            return self._build_json_qa_prompt(query, context)
        else:
            return self._build_text_qa_prompt(query, context)

    def _build_text_qa_prompt(self, query: str, context: str) -> str:
        """텍스트 형식 QA 프롬프트"""
        prompt = f"""{self.SYSTEM_PROMPT}

## 제공된 조항

{context}

## 질문

{query}

## 답변 지침

위 조항을 바탕으로 질문에 답변하세요. 반드시 조항 번호([1], [2] 등)를 인용하세요.
제공된 조항에 답이 없다면, "제공된 문서에서 해당 정보를 찾을 수 없습니다"라고 답변하세요.

**금액 추출 필수 사항 (Phase 5 v5):**
- 조항에서 "💰 보장금액: **X**" 형식을 찾으면, X를 정확히 그대로 답변에 포함하세요
- 예시: "💰 보장금액: **1,000만원**" → 답변에 "1,000만원" 포함
- "가입금액: N만원" 형식도 동일하게 처리하세요

**중요: 여러 보험사를 비교하는 질문인 경우, 반드시 다음과 같은 마크다운 표 형식으로 답변하세요:**

| 보험사 | 상품 | 보장 내용 | 보장 금액 | 특이사항 |
|--------|------|-----------|-----------|----------|
| 삼성 | 상품명 | 암진단비 | 3,000만원 | [30] 유사암 포함 |
| 메리츠 | 상품명 | 암진단비 | 2,000만원 | [56] 재진단만 |

표 아래에 각 보험사별 세부 설명을 추가하세요.

답변:"""
        return prompt

    def _build_json_qa_prompt(self, query: str, context: str) -> str:
        """JSON 형식 QA 프롬프트"""
        schema = {
            "answer": "질문에 대한 답변 (조항 인용 포함)",
            "citations": ["인용한 조항 번호 리스트"],
            "confidence": "답변 확신도 (high/medium/low)",
            "limitations": "답변의 한계나 주의사항 (있다면)"
        }

        prompt = f"""{self.SYSTEM_PROMPT}

## 제공된 조항

{context}

## 질문

{query}

## 답변 지침

위 조항을 바탕으로 질문에 답변하세요. 반드시 아래 JSON 형식으로 답변하세요.

JSON Schema:
```json
{json.dumps(schema, ensure_ascii=False, indent=2)}
```

제공된 조항에 답이 없다면, confidence를 "low"로 설정하고 limitations에 이유를 명시하세요.

답변 (JSON):"""
        return prompt

    def build_comparison_prompt(
        self,
        query: str,
        contexts: Dict[str, str],
        products: list
    ) -> str:
        """
        상품 비교 프롬프트 생성

        Args:
            query: 사용자 질의
            contexts: 상품별 컨텍스트 딕셔너리 {product_name: context}
            products: 비교할 상품 리스트

        Returns:
            비교 프롬프트
        """
        context_sections = []
        for product, context in contexts.items():
            context_sections.append(f"### {product}\n\n{context}")

        all_contexts = "\n\n".join(context_sections)

        prompt = f"""{self.SYSTEM_PROMPT}

## 비교 대상 상품

{', '.join(products)}

## 제공된 조항

{all_contexts}

## 질문

{query}

## 답변 지침

위 조항을 바탕으로 상품들을 비교하여 답변하세요.
- 각 상품의 차이점을 명확히 설명하세요
- 반드시 조항 번호([1], [2] 등)를 인용하세요
- 표 형식으로 비교하면 더 좋습니다

답변:"""
        return prompt

    def build_validation_prompt(
        self,
        plan_data: Dict[str, Any],
        constraints: str
    ) -> str:
        """
        가입설계서 검증 프롬프트 생성

        Args:
            plan_data: 설계서 데이터
            constraints: 사업방법서 제약 조건

        Returns:
            검증 프롬프트
        """
        plan_summary = json.dumps(plan_data, ensure_ascii=False, indent=2)

        prompt = f"""{self.SYSTEM_PROMPT}

## 가입설계서 정보

```json
{plan_summary}
```

## 사업방법서 제약 조건

{constraints}

## 검증 요청

위 가입설계서가 사업방법서의 제약 조건을 준수하는지 검증하세요.

검증 항목:
1. 가입 나이 범위
2. 보험 기간 / 납입 기간
3. 담보 조합 가능 여부
4. 가입 금액 한도

위반 사항이 있다면 구체적으로 지적하고, 해당 조항을 인용하세요.

검증 결과:"""
        return prompt

    @staticmethod
    def extract_json_from_response(response: str) -> Optional[Dict]:
        """
        LLM 응답에서 JSON 추출

        Args:
            response: LLM 응답

        Returns:
            파싱된 JSON 딕셔너리 또는 None
        """
        # JSON 코드 블록 추출
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            json_str = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            json_str = response[start:end].strip()
        else:
            # 전체를 JSON으로 시도
            json_str = response.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None
