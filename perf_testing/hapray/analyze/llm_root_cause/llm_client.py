"""
llm_client.py

多后端 LLM 客户端，自动识别 provider：
  - anthropic : 使用 anthropic SDK（api.anthropic.com）
  - openai    : 使用 openai SDK，兼容任意 OpenAI-compatible 接口
                （OpenAI、DeepSeek、通义、Ollama、OpenRouter 等）

provider 检测规则（按优先级）：
  1. config 里显式设置 provider: anthropic / openai
  2. base_url 包含 "anthropic.com" → anthropic
  3. 其余默认 openai
"""

import os
from typing import Iterator


def _resolve_key(key: str) -> str:
    """支持 ${ENV_VAR} 格式从环境变量读取。"""
    if isinstance(key, str) and key.startswith("${") and key.endswith("}"):
        env_name = key[2:-1]
        value = os.environ.get(env_name, "")
        if not value:
            raise ValueError(f"环境变量 {env_name} 未设置，请设置后重试。")
        return value
    return key


# ── Anthropic 后端 ────────────────────────────────────────────────────────

class _AnthropicClient:
    def __init__(self, api_key: str, model: str, max_tokens: int):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens

    def _get_client(self):
        try:
            import anthropic
        except ImportError:
            raise ImportError("请先安装 anthropic 库：pip install anthropic")
        return anthropic.Anthropic(api_key=self.api_key)

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client()
        message = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text

    def chat_stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        client = self._get_client()
        with client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text


# ── OpenAI-compatible 后端 ────────────────────────────────────────────────

class _OpenAIClient:
    def __init__(self, base_url: str, api_key: str, model: str, max_tokens: int):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens

    def _get_client(self):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("请先安装 openai 库：pip install openai")
        return OpenAI(base_url=self.base_url, api_key=self.api_key)

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content

    def chat_stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        client = self._get_client()
        stream = client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            stream=True,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


# ── 统一外部接口 ──────────────────────────────────────────────────────────

class LLMClient:
    """
    统一 LLM 客户端，内部自动路由到对应后端。
    外部只需调用 chat() / chat_stream()。
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int = 4096,
        base_url: str = "https://api.openai.com/v1",
        provider: str = "auto",
    ):
        resolved_key = _resolve_key(api_key)
        detected = self._detect_provider(provider, base_url)

        if detected == "anthropic":
            self._backend: _AnthropicClient | _OpenAIClient = _AnthropicClient(
                api_key=resolved_key,
                model=model,
                max_tokens=max_tokens,
            )
        else:
            self._backend = _OpenAIClient(
                base_url=base_url,
                api_key=resolved_key,
                model=model,
                max_tokens=max_tokens,
            )
        self.provider = detected
        self.model = model

    @staticmethod
    def _detect_provider(provider: str, base_url: str) -> str:
        if provider in ("anthropic", "openai"):
            return provider
        if "anthropic.com" in base_url:
            return "anthropic"
        return "openai"

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        return self._backend.chat(system_prompt, user_prompt)

    def chat_stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        return self._backend.chat_stream(system_prompt, user_prompt)


def load_client_from_config(config: dict) -> LLMClient:
    llm_cfg = config.get("llm", {})
    return LLMClient(
        api_key=llm_cfg.get("api_key", "${LLM_API_KEY}"),
        model=llm_cfg.get("model", "claude-sonnet-4-5"),
        max_tokens=llm_cfg.get("max_tokens", 4096),
        base_url=llm_cfg.get("base_url", "https://api.anthropic.com"),
        provider=llm_cfg.get("provider", "auto"),
    )
