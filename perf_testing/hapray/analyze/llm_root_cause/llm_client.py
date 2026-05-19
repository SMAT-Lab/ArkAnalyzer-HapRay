"""
llm_client.py

LLM client used by root-cause analysis.

The configuration path intentionally follows tools/symbol_recovery:
  - load .env automatically via python-dotenv when available
  - read LLM_SERVICE_TYPE / LLM_API_KEY / LLM_BASE_URL / LLM_MODEL from env
  - support service-specific keys such as POE_API_KEY / ANTHROPIC_API_KEY
  - skip LLM gracefully when no key is configured

CLI/config-file values are kept as compatibility fallbacks, but environment
variables are the preferred integration point so HapRay can share the same
agent-level LLM configuration as symbol recovery.
"""

import os
from typing import Iterator

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass
except Exception:
    pass


DEFAULT_LLM_MODEL = "GPT-5"
DEFAULT_LLM_TIMEOUT = 30
DEFAULT_MAX_TOKENS = 4096

ENV_KEY_LLM_API_KEY = "LLM_API_KEY"
ENV_KEY_LLM_BASE_URL = "LLM_BASE_URL"
ENV_KEY_LLM_MODEL = "LLM_MODEL"
ENV_KEY_LLM_TIMEOUT = "LLM_TIMEOUT"
ENV_KEY_LLM_TRUST_ENV = "LLM_TRUST_ENV"

_LLM_SERVICE_TYPE = os.getenv("LLM_SERVICE_TYPE", "").lower()
_LLM_API_KEY_ENV_MAP: dict[str, str] = {
    "poe": "POE_API_KEY",
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}
_LLM_BASE_URL_MAP: dict[str, str] = {
    "poe": "https://api.poe.com/v1",
    "openai": "https://api.openai.com/v1",
    "claude": "https://api.anthropic.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
}
_LLM_MODEL_ENV_MAP: dict[str, str] = {
    "poe": "POE_MODEL",
    "openai": "OPENAI_MODEL",
    "claude": "CLAUDE_MODEL",
    "deepseek": "DEEPSEEK_MODEL",
}


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _load_env_api_key() -> str:
    env_key = os.getenv(ENV_KEY_LLM_API_KEY)
    if env_key:
        return env_key
    service_key_name = _LLM_API_KEY_ENV_MAP.get(_LLM_SERVICE_TYPE)
    if service_key_name:
        return os.getenv(service_key_name, "")
    return ""


def _load_env_base_url() -> str:
    env_url = os.getenv(ENV_KEY_LLM_BASE_URL)
    if env_url:
        return env_url
    return _LLM_BASE_URL_MAP.get(_LLM_SERVICE_TYPE, "")


def _load_env_model() -> str:
    env_model = os.getenv(ENV_KEY_LLM_MODEL)
    if env_model:
        return env_model
    service_model_name = _LLM_MODEL_ENV_MAP.get(_LLM_SERVICE_TYPE)
    if service_model_name:
        service_model = os.getenv(service_model_name)
        if service_model:
            return service_model
    return ""


def _load_env_timeout() -> int:
    raw = os.getenv(ENV_KEY_LLM_TIMEOUT, str(DEFAULT_LLM_TIMEOUT))
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_LLM_TIMEOUT


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
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        max_tokens: int,
        timeout: int,
        trust_env: bool,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.trust_env = trust_env

    def _get_client(self):
        try:
            import openai
        except ImportError:
            raise ImportError("请先安装 openai 库：pip install openai")
        client_kwargs = {
            "base_url": self.base_url,
            "api_key": self.api_key,
        }
        if hasattr(openai, "DefaultHttpxClient"):
            client_kwargs["http_client"] = openai.DefaultHttpxClient(trust_env=self.trust_env)
        return openai.OpenAI(**client_kwargs)

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            timeout=self.timeout,
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
            timeout=self.timeout,
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
        max_tokens: int = DEFAULT_MAX_TOKENS,
        base_url: str = "https://api.openai.com/v1",
        provider: str = "auto",
        timeout: int = DEFAULT_LLM_TIMEOUT,
        trust_env: bool = False,
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
                timeout=timeout,
                trust_env=trust_env,
            )
        self.provider = detected
        self.model = model

    @staticmethod
    def _detect_provider(provider: str, base_url: str) -> str:
        if provider in ("anthropic", "openai"):
            return provider
        # symbol_recovery uses OpenAI-compatible chat.completions as the
        # default integration surface.  Only route to the Anthropic SDK when
        # explicitly requested by legacy config.
        if "anthropic.com" in base_url:
            return "openai"
        return "openai"

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        return self._backend.chat(system_prompt, user_prompt)

    def chat_stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        return self._backend.chat_stream(system_prompt, user_prompt)


def resolve_llm_config(config: dict) -> dict:
    """Resolve LLM config with symbol_recovery-compatible env precedence."""
    llm_cfg = config.get("llm", {})
    env_api_key = _load_env_api_key()
    env_base_url = _load_env_base_url()
    env_model = _load_env_model()

    api_key = env_api_key or llm_cfg.get("api_key", "")
    base_url = env_base_url or llm_cfg.get("base_url") or "https://api.openai.com/v1"
    model = env_model or llm_cfg.get("model") or DEFAULT_LLM_MODEL
    provider = llm_cfg.get("provider", "auto")
    if _LLM_SERVICE_TYPE:
        provider = "openai"

    return {
        "api_key": api_key,
        "model": model,
        "max_tokens": llm_cfg.get("max_tokens", DEFAULT_MAX_TOKENS),
        "base_url": base_url,
        "provider": provider,
        "timeout": int(llm_cfg.get("timeout", _load_env_timeout())),
        "trust_env": _env_bool(ENV_KEY_LLM_TRUST_ENV, bool(llm_cfg.get("trust_env", False))),
    }


def is_llm_configured(config: dict) -> bool:
    return bool(str(resolve_llm_config(config).get("api_key", "")).strip())


def load_client_from_config(config: dict) -> LLMClient:
    llm_cfg = resolve_llm_config(config)
    return LLMClient(
        api_key=llm_cfg["api_key"],
        model=llm_cfg["model"],
        max_tokens=llm_cfg["max_tokens"],
        base_url=llm_cfg["base_url"],
        provider=llm_cfg["provider"],
        timeout=llm_cfg["timeout"],
        trust_env=llm_cfg["trust_env"],
    )
