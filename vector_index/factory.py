"""
Embedder Factory

환경 변수에 따라 적절한 Embedder를 생성합니다.
"""

import os
from .embedder import BaseEmbedder
from .jina_embedder import JinaEmbedder
from .openai_embedder import OpenAIEmbedder
from .bge_embedder import BGEEmbedder
from .fastembed_bge import FastEmbedBGE


def get_embedder(backend: str = None) -> BaseEmbedder:
    """
    환경 변수 또는 파라미터에 따라 Embedder를 생성합니다.

    Args:
        backend: 임베딩 백엔드 ("jina" 또는 "openai")
                 None인 경우 EMBEDDING_BACKEND 환경 변수 사용

    Returns:
        BaseEmbedder 구현체

    Raises:
        ValueError: 지원하지 않는 backend 지정 시

    Example:
        >>> # .env에 EMBEDDING_BACKEND=jina 설정
        >>> embedder = get_embedder()
        >>>
        >>> # 명시적으로 지정
        >>> embedder = get_embedder(backend="openai")
    """
    if backend is None:
        backend = os.getenv("EMBEDDING_BACKEND", "fastembed").lower()

    if backend == "fastembed":
        # FastEmbed BGE (경량화, M1 Mac 최적화)
        model = os.getenv("FASTEMBED_MODEL", "BAAI/bge-small-en-v1.5")
        max_length = int(os.getenv("FASTEMBED_MAX_LENGTH", "512"))

        return FastEmbedBGE(
            model_name=model,
            max_length=max_length
        )

    elif backend == "bge":
        # BGE-M3 (로컬 실행, rate limit 없음)
        model = os.getenv("BGE_MODEL", "BAAI/bge-m3")
        device = os.getenv("BGE_DEVICE", None)  # None = 자동 감지 (cuda or cpu)

        return BGEEmbedder(
            model_name=model,
            device=device
        )

    elif backend == "jina":
        # Jina Embeddings v3
        model = os.getenv("JINA_MODEL", "jina-embeddings-v3")
        dimension = int(os.getenv("JINA_DIMENSION", "512"))

        return JinaEmbedder(
            model=model,
            dimension=dimension
        )

    elif backend == "openai":
        # OpenAI Embeddings
        model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

        return OpenAIEmbedder(model=model)

    else:
        raise ValueError(
            f"Unknown embedding backend: {backend}. "
            f"Supported backends: 'fastembed', 'bge', 'jina', 'openai'"
        )


def get_dimension(backend: str = None) -> int:
    """
    백엔드에 따른 임베딩 차원을 반환합니다.

    Args:
        backend: 임베딩 백엔드

    Returns:
        임베딩 차원 (int)
    """
    embedder = get_embedder(backend)
    return embedder.get_dimension()
