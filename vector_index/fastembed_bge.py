"""
FastEmbed BGE-M3 Embeddings 구현

FastEmbed를 사용한 경량화된 BGE-M3 임베딩
- 메모리 효율적
- M1 Mac 최적화
- 빠른 로딩 및 추론 속도

Reference: https://github.com/qdrant/fastembed
"""

from typing import List
from fastembed import TextEmbedding
from .embedder import BaseEmbedder


class FastEmbedBGE(BaseEmbedder):
    """FastEmbed BGE-M3 Embeddings 구현"""

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",  # 경량 모델 사용
        max_length: int = 512,
        cache_dir: str = None
    ):
        """
        Args:
            model_name: FastEmbed 모델 이름
            max_length: 최대 토큰 길이
            cache_dir: 모델 캐시 디렉토리
        """
        self.model_name = model_name
        self.max_length = max_length

        print(f"Loading FastEmbed model: {model_name}...")
        self.model = TextEmbedding(
            model_name=model_name,
            max_length=max_length,
            cache_dir=cache_dir
        )
        print(f"Model loaded successfully")

        # BGE-small-en-v1.5는 384차원
        self.dimension = 384

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        문서를 임베딩합니다.

        FastEmbed는 제너레이터를 반환하므로 리스트로 변환합니다.

        Args:
            texts: 임베딩할 문서 리스트

        Returns:
            임베딩 벡터 리스트
        """
        # FastEmbed는 제너레이터 반환
        embeddings = list(self.model.embed(texts))

        # numpy array를 list로 변환
        return [emb.tolist() for emb in embeddings]

    def embed_query(self, text: str) -> List[float]:
        """
        쿼리를 임베딩합니다.

        Args:
            text: 임베딩할 쿼리

        Returns:
            임베딩 벡터
        """
        # 단일 텍스트를 리스트로 래핑
        embeddings = list(self.model.embed([text]))
        return embeddings[0].tolist()

    def get_dimension(self) -> int:
        """임베딩 차원 반환"""
        return self.dimension

    def get_model_name(self) -> str:
        """모델 이름 반환"""
        return f"fastembed-bge-small-384d"

    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32
    ) -> List[List[float]]:
        """
        대량의 문서를 배치 단위로 임베딩합니다.

        FastEmbed는 내부적으로 배치 처리를 최적화합니다.

        Args:
            texts: 임베딩할 문서 리스트
            batch_size: 배치 크기 (참고용, FastEmbed가 자동 최적화)

        Returns:
            임베딩 벡터 리스트
        """
        embeddings = list(self.model.embed(texts, batch_size=batch_size))
        return [emb.tolist() for emb in embeddings]
