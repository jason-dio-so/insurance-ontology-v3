"""
Vector Index 모듈 (OpenAI 전용)

임베딩 생성, 벡터 DB 구축을 위한 모듈입니다.
"""

from .openai_embedder import OpenAIEmbedder

__all__ = ['OpenAIEmbedder']
