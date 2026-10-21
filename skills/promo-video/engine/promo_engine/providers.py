"""Voice provider resolution. Explicit, recorded, and never silently substituted.

A provider is usable when its prerequisite is present: an API key in the environment
(OpenRouter, OpenAI), the macOS `say` binary, or the user's own recordings ("files").
Key *values* are never read here, only whether the variable is set.

`auto` resolves only when exactly one API provider is configured. Two configured providers
is a question for the user; none is an explained error that offers the keyless engine.
A provider that fails at generation time is an error; the pipeline never falls back.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from typing import Mapping

from .config import PROVIDER_KEYS
from .util import PromoError


@dataclass
class Resolution:
    provider: str | None
    configured: list[str] = field(default_factory=list)  # API providers with a key set
    local: list[str] = field(default_factory=list)  # keyless engines available here
    reason: str = ""

    @property
    def ambiguous(self) -> bool:
        return self.provider is None and len(self.configured) > 1


def _env(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def configured_api_providers(env: Mapping[str, str] | None = None) -> list[str]:
    e = _env(env)
    return [p for p, var in PROVIDER_KEYS.items() if (e.get(var) or "").strip()]


def local_engines() -> list[str]:
    return ["say"] if shutil.which("say") else []


def resolve(requested: str | None, env: Mapping[str, str] | None = None) -> Resolution:
    """Resolve without raising; callers decide whether an unresolved result is a question or an error."""
    configured, local = configured_api_providers(env), local_engines()
    if requested in (None, "auto"):
        if len(configured) == 1:
            return Resolution(configured[0], configured, local, f"the only configured provider ({PROVIDER_KEYS[configured[0]]} is set)")
        if len(configured) > 1:
            return Resolution(None, configured, local, "both OPENROUTER_API_KEY and OPENAI_API_KEY are set; choose one")
        return Resolution(None, configured, local,
                          "no voice API key is configured (OPENROUTER_API_KEY or OPENAI_API_KEY)"
                          + ("; the local macOS voice (`say`) is available, keyless" if local else ""))
    return Resolution(requested, configured, local, "chosen explicitly")


def require(provider: str, env: Mapping[str, str] | None = None) -> None:
    """Raise unless `provider`'s prerequisite is present. Never suggests a silent swap."""
    e = _env(env)
    if provider in PROVIDER_KEYS:
        var = PROVIDER_KEYS[provider]
        if not (e.get(var) or "").strip():
            raise PromoError(f"voice provider '{provider}' needs {var} in the environment",
                             hint=f"export {var}=… in your shell (never paste keys into chat), "
                                  "or re-run `promo init --audio effects` for a film without narration")
    elif provider == "say":
        if not shutil.which("say"):
            raise PromoError("voice provider 'say' needs macOS", hint="choose openrouter, openai or files")
    elif provider != "files":
        raise PromoError(f"unknown voice provider '{provider}'")


def pick(cfg: dict, env: Mapping[str, str] | None = None) -> str:
    """The provider generation will use. Raises instead of guessing."""
    res = resolve(cfg["voice"]["provider"], env)
    if res.provider is None:
        raise PromoError(f"voice provider is not resolved: {res.reason}",
                         hint="run `promo init --provider openrouter|openai|say|files` (see `promo questions`)")
    require(res.provider, env)
    return res.provider
