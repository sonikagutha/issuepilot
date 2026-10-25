# Gemma Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the whole analysis pipeline on Google's open Gemma models, selectable per analysis from the web UI.

**Architecture:** `LLM_PROVIDER=gemma` builds a `ChatGoogleGenerativeAI` with `GEMMA_MODEL`, using the same `GOOGLE_API_KEY` as Gemini. Verified on 2026-10-25: Gemma 4 on the Gemini API accepts system prompts and `with_structured_output(method="json_schema")`, which is LangChain's default for this client. So the nodes are unchanged, and the adapter the roadmap anticipated isn't needed. The web UI can override the provider per request among those with a configured key, and every result is labelled with the model that produced it.

**Tech Stack:** langchain-google-genai, FastAPI, vanilla JS.

**Spec:** `docs/roadmap.md` — Phase 5.

## Global Constraints

- Gemma models available to the key: `gemma-4-26b-a4b-it` (MoE, ~5s per call), `gemma-4-31b-it` (dense, ~30-45s per call). The default is decided in Task 2 by comparing both on a real issue.
- Provider display names: anthropic → "Claude", openai → "OpenAI", google → "Gemini", gemma → "Gemma 4".
- Per-request override is limited to providers whose key is configured; anything else → 400.

## Review Focus

1. Gemma selected but `GOOGLE_API_KEY` missing → 400 naming `GOOGLE_API_KEY`. `test_gemma_missing_key_raises`.
2. A request for a provider with no key → 400, not a 500 from the factory. `test_analyze_unconfigured_provider_is_400`.
3. The override must not mutate the cached process-wide settings. `test_provider_override_does_not_leak`.
4. No provider configured at all → the picker is hidden and the default path still reports the factory's error.
5. The result label matches the model actually used, not the default. `test_analyze_with_provider_override`.

---

### Task 1: Gemma in the factory + provider helpers
**Files:** modify `issuepilot/config.py`, `issuepilot/llm/factory.py`, `.env.example`, `tests/test_llm_factory.py`.
**Produces:** `Provider` Literal incl. `"gemma"`; `Settings.gemma_model`; `PROVIDER_NAMES: dict[Provider, str]`; `available_providers(settings) -> list[Provider]`; `model_label(settings) -> str` (e.g. `"Gemma 4 · gemma-4-26b-a4b-it"`).

### Task 2: Per-analysis provider picker + model label
**Files:** modify `issuepilot/web/server.py`, `templates/analyze.html`, `static/analyze.js`, `static/cozy.css`, `tests/test_web.py`, `README.md`.
**Produces:** `AnalyzeRequest.provider: Provider | None`; response key `model`.
