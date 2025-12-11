"""
임베딩 모델 추상 인터페이스

모든 임베딩 모델은 이 인터페이스를 구현해야 합니다.
쉽게 다른 임베딩 모델로 교체 가능하도록 설계되었습니다.
"""

from abc import ABC, abstractmethod
from typing import List


class BaseEmbedder(ABC):
    """임베딩 모델 추상 클래스"""

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        문서 리스트를 임베딩합니다.

        Args:
            texts: 임베딩할 문서 리스트

        Returns:
            임베딩 벡터 리스트 (각 벡터는 float 리스트)
        """
        pass

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """
        검색 쿼리를 임베딩합니다.

        일부 모델(Jina 등)은 문서 임베딩과 쿼리 임베딩을 다르게 처리합니다.

        Args:
            text: 임베딩할 쿼리

        Returns:
            임베딩 벡터 (float 리스트)
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """
        임베딩 차원을 반환합니다.

        Returns:
            임베딩 벡터의 차원 (예: 512, 1024, 1536)
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """
        모델 이름을 반환합니다.

        Returns:
            모델 이름 (예: "jina-embeddings-v3", "text-embedding-3-small")
        """
        pass

    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """
        대량의 문서를 배치 단위로 임베딩합니다.

        API rate limit을 고려하여 배치 처리합니다.

        Args:
            texts: 임베딩할 문서 리스트
            batch_size: 배치 크기

        Returns:
            임베딩 벡터 리스트
        """
        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = self.embed_documents(batch)
            embeddings.extend(batch_embeddings)

        return embeddings
