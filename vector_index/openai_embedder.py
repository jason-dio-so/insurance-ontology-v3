"""
OpenAI Embeddings 구현

OpenAI의 text-embedding-3-small/large 모델을 사용합니다.
- 범용 임베딩
- 안정적인 API
- 유료 ($0.02 / 1M tokens for small)

Reference: https://platform.openai.com/docs/guides/embeddings
"""

import os
from typing import List
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class OpenAIEmbedder:
    """OpenAI Embeddings 구현"""

    def __init__(
        self,
        api_key: str = None,
        model: str = "text-embedding-3-small"
    ):
        """
        Args:
            api_key: OpenAI API Key (환경 변수에서 자동 로드)
            model: 모델 이름 (text-embedding-3-small, text-embedding-3-large)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY is required. "
                "Set it via environment variable or constructor parameter."
            )

        self.model = model
        self.client = OpenAI(api_key=self.api_key)

        # 모델별 차원 설정
        self.dimension_map = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536
        }

        if model not in self.dimension_map:
            raise ValueError(
                f"Unknown model: {model}. "
                f"Supported: {list(self.dimension_map.keys())}"
            )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        문서를 임베딩합니다.

        OpenAI는 문서와 쿼리를 동일하게 처리합니다.

        Args:
            texts: 임베딩할 문서 리스트

        Returns:
            임베딩 벡터 리스트
        """
        response = self.client.embeddings.create(
            model=self.model,
            input=texts
        )

        return [item.embedding for item in response.data]

    def embed_query(self, text: str) -> List[float]:
        """
        쿼리를 임베딩합니다.

        OpenAI는 문서와 쿼리를 동일하게 처리합니다.

        Args:
            text: 임베딩할 쿼리

        Returns:
            임베딩 벡터
        """
        response = self.client.embeddings.create(
            model=self.model,
            input=[text]
        )

        return response.data[0].embedding

    def get_dimension(self) -> int:
        """임베딩 차원 반환"""
        return self.dimension_map[self.model]

    def get_model_name(self) -> str:
        """모델 이름 반환"""
        return self.model
