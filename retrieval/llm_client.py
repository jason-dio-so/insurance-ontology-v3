"""
LLM Client

로컬 LLM (Ollama) 또는 OpenAI API를 통한 LLM 호출 인터페이스

주요 기능:
- Ollama 로컬 LLM 지원 (qwen3:8b 등)
- OpenAI API 백업 지원
- 스트리밍 및 일반 응답 지원
- 에러 핸들링 및 재시도

Usage:
    from retrieval.llm_client import LLMClient

    client = LLMClient(backend="ollama", model="qwen3:8b")
    response = client.generate(prompt="안녕하세요")
"""

import os
import requests
import json
from typing import Dict, Any, Optional, Iterator
from dotenv import load_dotenv

load_dotenv()


class LLMClient:
    """LLM 클라이언트 (Ollama 또는 OpenAI)"""

    def __init__(
        self,
        backend: str = None,
        model: str = None,
        base_url: str = None,
        timeout: int = 240  # Increased to 4 minutes for large prompts
    ):
        """
        Args:
            backend: LLM 백엔드 ("ollama" 또는 "openai")
            model: 모델명 (Ollama: "qwen3:8b", OpenAI: "gpt-4")
            base_url: Ollama API URL
            timeout: 요청 타임아웃 (초)
        """
        self.backend = backend or os.getenv("LLM_BACKEND", "ollama")
        self.timeout = timeout

        if self.backend == "ollama":
            self.model = model or os.getenv("OLLAMA_MODEL", "qwen3:8b")
            self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        elif self.backend == "openai":
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4")
            self.api_key = os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY not set in environment")
        else:
            raise ValueError(f"Unsupported backend: {backend}")

    def generate(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        stream: bool = False
    ) -> str:
        """
        LLM 응답 생성

        Args:
            prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트
            temperature: 온도 (0.0 ~ 1.0)
            max_tokens: 최대 토큰 수
            stream: 스트리밍 여부

        Returns:
            LLM 응답 텍스트
        """
        if self.backend == "ollama":
            return self._generate_ollama(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )
        elif self.backend == "openai":
            return self._generate_openai(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )

    def _generate_ollama(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        stream: bool = False
    ) -> str:
        """Ollama API 호출"""
        url = f"{self.base_url}/api/generate"

        # 시스템 프롬프트와 사용자 프롬프트 결합
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        try:
            if stream:
                return self._stream_ollama(url, payload)
            else:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()
                result = response.json()
                return result.get("response", "")

        except requests.exceptions.RequestException as e:
            return f"⚠️ Ollama API 오류: {e}\n\nOllama 서버가 실행 중인지 확인하세요: http://localhost:11434"

    def _stream_ollama(self, url: str, payload: Dict) -> str:
        """Ollama 스트리밍 응답"""
        try:
            response = requests.post(
                url,
                json=payload,
                stream=True,
                timeout=self.timeout
            )
            response.raise_for_status()

            full_response = []
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    if "response" in chunk:
                        text = chunk["response"]
                        full_response.append(text)
                        print(text, end="", flush=True)

                    if chunk.get("done", False):
                        break

            print()  # 줄바꿈
            return "".join(full_response)

        except requests.exceptions.RequestException as e:
            return f"⚠️ Ollama 스트리밍 오류: {e}"

    def _generate_openai(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """OpenAI API 호출 (v1.0+ 형식)"""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            return response.choices[0].message.content

        except Exception as e:
            return f"⚠️ OpenAI API 오류: \n\n{e}"

    def chat(
        self,
        messages: list,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """
        채팅 형식 응답 생성 (Ollama chat API 사용)

        Args:
            messages: 메시지 리스트 [{"role": "user", "content": "..."}]
            temperature: 온도
            max_tokens: 최대 토큰 수

        Returns:
            LLM 응답
        """
        if self.backend == "ollama":
            url = f"{self.base_url}/api/chat"
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }

            try:
                response = requests.post(url, json=payload, timeout=self.timeout)
                response.raise_for_status()
                result = response.json()
                return result.get("message", {}).get("content", "")

            except requests.exceptions.RequestException as e:
                return f"⚠️ Ollama 채팅 오류: {e}"

        elif self.backend == "openai":
            return self._generate_openai(
                prompt=messages[-1]["content"],
                system_prompt=messages[0]["content"] if messages[0]["role"] == "system" else None,
                temperature=temperature,
                max_tokens=max_tokens
            )

    def is_available(self) -> bool:
        """LLM 서비스 가용성 확인"""
        if self.backend == "ollama":
            try:
                response = requests.get(
                    f"{self.base_url}/api/tags",
                    timeout=5
                )
                return response.status_code == 200
            except:
                return False

        elif self.backend == "openai":
            return bool(self.api_key)

        return False

    def list_models(self) -> list:
        """사용 가능한 모델 목록 조회 (Ollama만 지원)"""
        if self.backend == "ollama":
            try:
                response = requests.get(
                    f"{self.base_url}/api/tags",
                    timeout=5
                )
                response.raise_for_status()
                result = response.json()
                return [model["name"] for model in result.get("models", [])]
            except:
                return []

        return [self.model]


# 편의 함수
def get_llm_client(backend: str = None, model: str = None) -> LLMClient:
    """
    LLM 클라이언트 팩토리 함수

    Args:
        backend: "ollama" 또는 "openai"
        model: 모델명

    Returns:
        LLMClient 인스턴스
    """
    return LLMClient(backend=backend, model=model)
