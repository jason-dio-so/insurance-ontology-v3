"""
Jina Embeddings v3 구현

Jina AI의 jina-embeddings-v3 모델을 사용합니다.
- 다국어 지원 (한국어 포함)
- Task-specific 임베딩 (retrieval.passage, retrieval.query)
- 무료 API (1M tokens/day)
- 로컬 실행 옵션 (HuggingFace)

Reference: https://jina.ai/embeddings
"""

import os
from typing import List
import requests
from .embedder import BaseEmbedder


class JinaEmbedder(BaseEmbedder):
    """Jina Embeddings v3 구현"""

    def __init__(
        self,
        api_key: str = None,
        model: str = "jina-embeddings-v3",
        dimension: int = 512
    ):
        """
        Args:
            api_key: Jina API Key (환경 변수에서 자동 로드)
            model: 모델 이름 (기본: jina-embeddings-v3)
            dimension: 임베딩 차원 (512 for base, 1024 for large)
        """
        self.api_key = api_key or os.getenv("JINA_API_KEY")
        if not self.api_key:
            raise ValueError(
                "JINA_API_KEY is required. "
                "Set it via environment variable or constructor parameter."
            )

        self.model = model
        self.dimension = dimension
        self.api_url = "https://api.jina.ai/v1/embeddings"

    def _call_api(self, texts: List[str], task: str) -> List[List[float]]:
        """
        Jina API 호출

        Args:
            texts: 임베딩할 텍스트 리스트
            task: 태스크 타입 (retrieval.passage, retrieval.query, classification, etc.)

        Returns:
            임베딩 벡터 리스트
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "input": texts,
            "task": task,
            "dimensions": self.dimension
        }

        response = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=60
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Jina API error: {response.status_code} - {response.text}"
            )

        data = response.json()
        return [item["embedding"] for item in data["data"]]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        문서를 임베딩합니다 (retrieval.passage task 사용)

        Args:
            texts: 임베딩할 문서 리스트

        Returns:
            임베딩 벡터 리스트
        """
        return self._call_api(texts, task="retrieval.passage")

    def embed_query(self, text: str) -> List[float]:
        """
        쿼리를 임베딩합니다 (retrieval.query task 사용)

        Args:
            text: 임베딩할 쿼리

        Returns:
            임베딩 벡터
        """
        embeddings = self._call_api([text], task="retrieval.query")
        return embeddings[0]

    def get_dimension(self) -> int:
        """임베딩 차원 반환"""
        return self.dimension

    def get_model_name(self) -> str:
        """모델 이름 반환"""
        return f"{self.model}-{self.dimension}d"
