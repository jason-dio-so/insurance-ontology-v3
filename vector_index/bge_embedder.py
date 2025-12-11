"""
BGE-M3 Embeddings 구현

BAAI의 BGE-M3 (BERT General Embedding Multi-lingual, Multi-task, Multi-granularity) 모델을 사용합니다.
- 다국어 지원 (한국어 우수)
- 1024 차원
- 로컬 실행 (API rate limit 없음)
- GPU 가속 지원

Reference: https://huggingface.co/BAAI/bge-m3
"""

import os
from typing import List, Optional
import torch
from sentence_transformers import SentenceTransformer
from .embedder import BaseEmbedder


class BGEEmbedder(BaseEmbedder):
    """BGE-M3 Embeddings 구현"""

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        device: Optional[str] = None,
        normalize_embeddings: bool = True
    ):
        """
        Args:
            model_name: HuggingFace 모델 이름 (기본: BAAI/bge-m3)
            device: 실행 디바이스 ("cuda", "cpu", None=자동 감지)
            normalize_embeddings: 임베딩 정규화 여부 (cosine similarity 최적화)
        """
        self.model_name = model_name
        self.normalize_embeddings = normalize_embeddings

        # 디바이스 자동 감지
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device

        print(f"Loading BGE-M3 model on {self.device}...")
        self.model = SentenceTransformer(model_name, device=self.device)
        print(f"Model loaded: {model_name}")

        # BGE-M3는 1024 차원 고정
        self.dimension = 1024

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        문서를 임베딩합니다.

        BGE-M3는 문서와 쿼리를 동일하게 처리하지만,
        검색 성능을 위해 passage prefix를 추가할 수 있습니다.

        Args:
            texts: 임베딩할 문서 리스트

        Returns:
            임베딩 벡터 리스트
        """
        # BGE 모델은 passage에 "Represent this sentence for searching relevant passages: " 추가 권장
        # 하지만 한국어에서는 prefix 없이도 좋은 성능을 보이므로 생략
        embeddings = self.model.encode(
            texts,
            normalize_embeddings=self.normalize_embeddings,
            batch_size=32,  # 배치 크기
            show_progress_bar=False,
            convert_to_numpy=True
        )

        # numpy array를 list로 변환
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        """
        쿼리를 임베딩합니다.

        BGE 모델은 쿼리에 "Represent this sentence for searching relevant passages: " prefix 추가 권장
        하지만 한국어에서는 생략해도 무방

        Args:
            text: 임베딩할 쿼리

        Returns:
            임베딩 벡터
        """
        # 쿼리 prefix 추가 (선택적)
        # query_text = f"Represent this sentence for searching relevant passages: {text}"

        embedding = self.model.encode(
            text,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=False,
            convert_to_numpy=True
        )

        return embedding.tolist()

    def get_dimension(self) -> int:
        """임베딩 차원 반환 (BGE-M3는 1024 고정)"""
        return self.dimension

    def get_model_name(self) -> str:
        """모델 이름 반환"""
        return f"bge-m3-1024d"

    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32
    ) -> List[List[float]]:
        """
        대량의 문서를 배치 단위로 임베딩합니다.

        로컬 실행이므로 rate limit 없이 빠르게 처리 가능

        Args:
            texts: 임베딩할 문서 리스트
            batch_size: 배치 크기 (GPU 메모리에 따라 조정)

        Returns:
            임베딩 벡터 리스트
        """
        embeddings = self.model.encode(
            texts,
            normalize_embeddings=self.normalize_embeddings,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True
        )

        return embeddings.tolist()
