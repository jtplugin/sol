#!/usr/bin/env python3
"""
SOL API executor — runs a fixture case N times via a model HTTP backend.

Uses an API key + base URL directly instead of the `claude -p` CLI, so it works
with any Anthropic-compatible endpoint and does not require a Claude Code session.

Backends (--backend, or "backend" field per mode in tests/modes.json):
  anthropic — Anthropic Messages API (default); supports E0 and E1.
  ollama    — local Ollama /api/generate; E0 only (no Anthropic tool loop).
              No auth by default; a key, if given, is forwarded as a Bearer token.

Each run:
  1. Stage the input to a temp file
  2. Build a prompt that presents the SOL doc and (for E0) the file content inline,
     or (for E1) the staged path for the model to cat
  3. Call the Messages API directly (single-shot for E0; tool loop for E1)
  4. Parse trace lines + JSON payload from the response text
  5. Score via checker; save RunRecord + ScoreRecord; append to index.jsonl

Context emulation (--context flag):
  E0  — no tools; file content pre-injected into the prompt  [default]
  E1  — bash tool restricted to `cat`; agent reads the staged file itself

Results include runner_type="api" and the api_base_url used, so they can be
distinguished from session-runner results when querying index.jsonl.

Usage:
    python3 tests/runner/api_executor.py \\
        --fixture w2-branching/release-gate \\
        --input i1-blocked \\
        --context E0 \\
        --model claude-opus-4-8 \\
        --runs 3

    python3 tests/runner/api_executor.py \\
        --fixture w2-branching/release-gate \\
        --all-inputs \\
        --context E0 \\
        --model claude-opus-4-8 \\
        --api-url https://api.anthropic.com \\
        --dry-run
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows (cp1252 can't encode em-dash, ×, etc.)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH  = REPO_ROOT / "tests" / "env.json"
MODES_PATH = REPO_ROOT / "tests" / "modes.json"
sys.path.insert(0, str(REPO_ROOT / "tests"))

from runner.schema import Config, Execution, Output, RunRecord, Trace, Usage
from runner.checker import check
from runner.runner import (
    FIXTURES_DIR, RESULTS_DIR,
    InputBundle,
    _load_fixture, _load_input, _stage,
    _record_path, _score_path, _append_index,
    _parse_trace, _extract_payload,
    L1_INSTRUCTION,
)

DEFAULT_TIMEOUT_S  = 300
DEFAULT_API_URL    = "https://api.anthropic.com"
DEFAULT_MAX_TOKENS = 4096
MAX_TOOL_ITERS     = 20

# Tool definition for E1 context (bash restricted to cat)
_BASH_TOOL = {
    "name": "bash",
    "description": "Run a shell command and return its stdout.",
    "input_schema": {
        "type": "object",
        "properties": {"command": {"type": "string", "description": "Shell command to run"}},
        "required": ["command"],
    },
}

# ---------------------------------------------------------------------------
# Ollama model management
# ---------------------------------------------------------------------------

def _ollama_unload(api_url: str, model: str) -> None:
    """Tell Ollama to evict `model` from memory immediately (keep_alive=0)."""
    import urllib.request
    payload = json.dumps({"model": model, "keep_alive": 0}).encode()
    req = urllib.request.Request(
        f"{api_url.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
    except Exception:
        pass  # best-effort; never raise


# ---------------------------------------------------------------------------
# SDK / HTTP backend
# ---------------------------------------------------------------------------

try:
    import anthropic as _anthropic_sdk
    _HAS_SDK = True
except ImportError:
    _HAS_SDK = False


def _post_messages(api_key: str, api_url: str, payload: dict) -> dict:
    """Thin urllib fallback when the anthropic SDK is not installed."""
    import urllib.request
    import urllib.error

    url = api_url.rstrip("/") + "/v1/messages"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT_S) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"API error {e.code}: {body}") from e


def _post_messages_openai(api_url: str, model: str, messages: list, max_tokens: int,
                          api_key: str = "", temperature: float | None = None,
                          system_prompt: str = "", thinking: bool | None = None) -> dict:
    """Call an OpenAI-compatible /v1/chat/completions endpoint -- LM Studio's
    native local-server API surface. Returns a normalised dict matching
    _sdk_create's Anthropic-shaped return: {stop_reason, content, usage}.
    E0-only for now (see run_headless_api), same restriction as 'ollama'."""
    import urllib.request
    import urllib.error

    oa_messages = []
    if system_prompt:
        oa_messages.append({"role": "system", "content": system_prompt})
    for m in messages:
        content = m["content"] if isinstance(m["content"], str) else str(m["content"])
        oa_messages.append({"role": m["role"], "content": content})

    payload: dict = {"model": model, "messages": oa_messages, "max_tokens": max_tokens}
    if temperature is not None:
        payload["temperature"] = temperature
    if thinking is not None:
        payload["chat_template_kwargs"] = {"enable_thinking": thinking}

    url = api_url.rstrip("/") + "/v1/chat/completions"
    data = json.dumps(payload).encode()
    headers = {"content-type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT_S) as resp:
            out = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"OpenAI-compatible API error {e.code}: {body}") from e

    choice = (out.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    text = message.get("content", "")
    # llama-server hands the thinking block back in its own field when the chat
    # template separates it. Reading only `content` made a model that spent its
    # whole budget deliberating indistinguishable from one that returned nothing
    # -- 4 of MAIN's first 5 rows, 13,024 output tokens each, all recorded as
    # no-output. Kept for diagnosis, never merged into the answer: the SOL
    # contract asks for the payload, and deliberating is not delivering.
    reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
    usage = out.get("usage") or {}
    return {
        "stop_reason": choice.get("finish_reason", "stop"),
        "reasoning": reasoning,
        "content": [{"type": "text", "text": text}],
        "usage": {
            "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
        },
    }


def _post_messages_ollama(api_url: str, model: str, prompt: str,
                          max_tokens: int, api_key: str = "",
                          reasoning_budget: int = 0,
                          system_prompt: str = "",
                          temperature: float | None = None) -> dict:
    """Call Ollama /api/generate (streaming) and return a normalised dict.

    Uses stream=True so each token chunk keeps the socket alive and avoids
    the urllib idle-socket timeout that fires with stream=False on slow models.
    A wall-clock deadline (DEFAULT_TIMEOUT_S) is enforced via a daemon thread
    so a slow-but-alive stream cannot run forever.
    """
    import threading
    import urllib.request
    import urllib.error

    url = api_url.rstrip("/") + "/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": True, "think": reasoning_budget > 0}
    if system_prompt:
        payload["system"] = system_prompt
    if temperature is not None:
        payload["options"] = {"temperature": temperature}
    data = json.dumps(payload).encode()
    headers = {"content-type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    result: dict = {}
    exc_box: list = []

    def _stream() -> None:
        chunks: list[str] = []
        prompt_eval_count = None
        eval_count = None
        try:
            # idle-socket timeout: 180 s between tokens (safeguard against stalls;
            # extended for reasoning models that think before first token)
            with urllib.request.urlopen(req, timeout=180) as resp:
                for raw_line in resp:
                    if stop_event.is_set():
                        return
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    chunks.append(chunk.get("response", ""))
                    if chunk.get("done"):
                        prompt_eval_count = chunk.get("prompt_eval_count")
                        eval_count = chunk.get("eval_count")
                        break
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            exc_box.append(RuntimeError(f"Ollama error {e.code}: {body}"))
            return
        except Exception as e:
            exc_box.append(e)
            return
        result["text"]        = "".join(chunks)
        result["tokens_in"]   = prompt_eval_count
        result["tokens_out"]  = eval_count

    stop_event = threading.Event()
    t = threading.Thread(target=_stream, daemon=True)
    t.start()
    t.join(timeout=DEFAULT_TIMEOUT_S)

    if t.is_alive():
        # Wall-clock deadline exceeded — signal thread and raise.
        stop_event.set()
        raise TimeoutError(f"Ollama wall-clock timeout after {DEFAULT_TIMEOUT_S}s")

    if exc_box:
        raise exc_box[0]

    return {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": result.get("text", "")}],
        "usage": {
            "input_tokens":  result.get("tokens_in"),
            "output_tokens": result.get("tokens_out"),
        },
    }


def _sdk_create(api_key: str, api_url: str, model: str, messages: list,
                tools: list | None, max_tokens: int,
                backend: str = "anthropic",
                reasoning_budget: int = 0,
                system_prompt: str = "",
                temperature: float | None = None,
                thinking: bool | None = None) -> dict:
    """Call the API and return a normalised dict with keys:
    stop_reason, content (list of blocks), usage (input_tokens, output_tokens)
    """
    if backend == "ollama":
        # Ollama has no Anthropic-style tool loop; flatten user messages to a prompt.
        prompt = "\n".join(
            m["content"] if isinstance(m["content"], str) else str(m["content"])
            for m in messages if m.get("role") != "system"
        )
        return _post_messages_ollama(api_url, model, prompt, max_tokens, api_key,
                                     reasoning_budget=reasoning_budget,
                                     system_prompt=system_prompt,
                                     temperature=temperature)
    if backend == "openai":
        # LM Studio's native local-server API -- E0 only (see run_headless_api).
        return _post_messages_openai(api_url, model, messages, max_tokens, api_key,
                                     temperature=temperature, system_prompt=system_prompt,
                                     thinking=thinking)
    # Extended thinking requires temperature==1 (or omitted) on the Anthropic
    # API -- a custom temperature alongside reasoning_budget>0 would 400.
    effective_temperature = temperature if reasoning_budget == 0 else None
    if _HAS_SDK:
        client = _anthropic_sdk.Anthropic(api_key=api_key, base_url=api_url)
        kwargs: dict = dict(model=model, max_tokens=max_tokens, messages=messages)
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = tools
        if reasoning_budget > 0:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": reasoning_budget}
        if effective_temperature is not None:
            kwargs["temperature"] = effective_temperature
        resp = client.messages.create(**kwargs)
        return {
            "stop_reason": resp.stop_reason,
            "content": [b.model_dump() if hasattr(b, "model_dump") else vars(b)
                        for b in resp.content],
            "usage": {
                "input_tokens":  resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            },
        }
    else:
        payload: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if tools:
            payload["tools"] = tools
        if reasoning_budget > 0:
            payload["thinking"] = {"type": "enabled", "budget_tokens": reasoning_budget}
        if effective_temperature is not None:
            payload["temperature"] = effective_temperature
        return _post_messages(api_key, api_url, payload)


def _text_from_content(content: list) -> str:
    """Extract concatenated text from a content block list."""
    parts = []
    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        else:
            # SDK object
            if getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", ""))
    return "\n".join(parts)


def _tool_use_blocks(content: list) -> list:
    """Return tool_use blocks from a content list."""
    blocks = []
    for block in content:
        t = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
        if t == "tool_use":
            blocks.append(block)
    return blocks


# ---------------------------------------------------------------------------
# Input discovery
# ---------------------------------------------------------------------------

def _list_inputs(fixture_dir: Path) -> list[str]:
    inputs_dir = fixture_dir / "inputs"
    ids = {p.stem for p in inputs_dir.glob("*.json")}
    ids |= {p.name for p in inputs_dir.iterdir() if p.is_dir()}
    return sorted(ids)


# ---------------------------------------------------------------------------
# Collateral-context scale (--level), doc/experiment-minimum-context.md SS5.1
#
# These are the LEVELS L0-L4 of the L factor. They are not the predictability
# LAYERS of doc/predictability-strategies.md -- the whole L0-L4 scale is an
# empirical calibration of a single one of those layers (the L1 "Linguistic"
# one). Same letters, two taxonomies; conflating them was the bug this scale
# was realigned to fix, on 2026-08-22.
# ---------------------------------------------------------------------------

LEVELS = ("L0", "L1", "L2", "L3", "L4")
PROSE = ("prose-mechanical", "prose-generated")
RENDERINGS = LEVELS + PROSE

EXAMPLES_DIR = REPO_ROOT / "examples"
L4_EXAMPLE_FILES = [
    "daily-briefing.json",
    "review-runner.json",
    "vault-ingest.json",
    "weekly-closure.json",
]


def _normalize_rendering(rendering: str) -> str:
    """The level actually applied, for the record. Unrecognized values fall back
    to L1 (mirrors _build_prompt_e0's fallback — never a crash mid-cell), and the
    record must say L1, because L1 is what the model was given."""
    return rendering if rendering in RENDERINGS else "L1"


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_prompt_e0(sol_doc: dict, bundle: InputBundle, fixture_body: str,
                     level: str = "L1", prose_bodies: dict | None = None) -> str:
    """E0: no tools — file content injected into the markdown fixture template.

    Cumulative collateral-context scale (--level), SS5.1 of the protocol.
    What varies across levels is the EXPLANATION of how SOL is read; what the
    task needs in order to be executable at all — the input data and the SOL
    script itself — is present at every level, L0 included. Each level is a
    strict prefix of the next.
      L0 — fixture_body with placeholders substituted: input data + the SOL
           script, and no prose explaining either.
      L1 — L0 + the minimal instruction, verbatim (default).
      L2 — L1 + l2-glossary.md appended.
      L3 — L2 + spec/sol-0.6.md appended.
      L4 — L3 + each examples/*.json appended, alphabetical order.
    Unrecognized level -> fallback to L1 behavior (never a crash mid-cell).
    """
    if level in PROSE:
        # SS5.4: a prose rendering REPLACES the SOL document, it does not
        # extend it, so no L collateral applies -- the prose document, with
        # the input substituted, is the whole prompt. A missing document is
        # refused, never fallen back on: a SOL prompt filed under a prose
        # cell would be a measurement of SOL recorded as one of prose.
        prose_body = (prose_bodies or {}).get(level)
        if not prose_body:
            raise FileNotFoundError(
                f"no {level} document for this fixture; expected a file "
                f"named <fixture>-{level}.md beside the SOL document")
        if bundle.mode == "single":
            return prose_body.replace(
                "{{file_content}}",
                json.dumps(bundle.payload, indent=2, ensure_ascii=False))
        for stem, text in bundle.files.items():
            prose_body = prose_body.replace("{{" + stem + "}}", text)
        return prose_body

    if bundle.mode == "single":
        fc = json.dumps(bundle.payload, indent=2, ensure_ascii=False)
    else:
        fc = "\n".join(bundle.files.values())

    body = fixture_body
    if bundle.mode == "single":
        body = body.replace("{{file_content}}", fc)
    else:
        for stem, text in bundle.files.items():
            body = body.replace("{{" + stem + "}}", text)

    if level == "L0":
        return body

    body = body + "\n\n" + L1_INSTRUCTION

    if level not in ("L2", "L3", "L4"):
        return body

    glossary_path = (REPO_ROOT / "tests" / "fixtures" / "w2-branching" /
                     "support-intake" / "l2-glossary.md")
    body = body + "\n\n" + glossary_path.read_text(encoding="utf-8")
    if level == "L2":
        return body

    spec_path = REPO_ROOT / "spec" / "sol-0.6.md"
    body = body + "\n\n" + spec_path.read_text(encoding="utf-8")
    if level == "L3":
        return body

    for name in L4_EXAMPLE_FILES:
        body = body + "\n\n" + (EXAMPLES_DIR / name).read_text(encoding="utf-8")
    return body


def _build_prompt_e1(sol_doc: dict, staged_path: Path) -> str:
    """E1: bash tool (cat only) — agent reads the staged file itself."""
    sol_text = json.dumps(sol_doc, ensure_ascii=False)
    return (
        f"SOL. record_path={staged_path}\n"
        f"{sol_text}\n"
        "TODO→verbatim. end: RETURN json. no markdown."
    )


# ---------------------------------------------------------------------------
# Tool execution (E1)
# ---------------------------------------------------------------------------

_SHELL_METACHARS = ";&|<>`$(){}" + chr(10) + chr(13)


def _execute_tool_call(block: dict | object, sandbox: Path) -> str:
    """Execute a tool_use block; only `cat <file>` inside the sandbox is permitted."""
    if isinstance(block, dict):
        name  = block.get("name", "")
        inp   = block.get("input", {})
    else:
        name  = getattr(block, "name", "")
        inp   = getattr(block, "input", {})

    if name != "bash":
        return f"[error] unknown tool: {name}"

    command = inp.get("command", "") if isinstance(inp, dict) else getattr(inp, "command", "")
    stripped = command.strip()
    denied = f"[permission denied] only `cat <file>` commands are allowed in E1 context (got: {stripped!r})"

    # The command never reaches a shell, but metacharacters signal an attempt to
    # chain/expand — refuse instead of silently catting a weirdly named file.
    if any(ch in stripped for ch in _SHELL_METACHARS):
        return denied

    # posix=False on Windows: POSIX mode would eat the backslashes of the
    # absolute record_path handed to the model in the E1 prompt.
    try:
        argv = shlex.split(stripped, posix=(os.name != "nt"))
    except ValueError:
        return denied
    if len(argv) != 2 or argv[0] != "cat":
        return denied

    raw_path = argv[1].strip('"').strip("'")
    sandbox_root = Path(sandbox).resolve()
    target = (sandbox_root / raw_path).resolve()
    if target != sandbox_root and sandbox_root not in target.parents:
        return f"[permission denied] path outside sandbox: {raw_path!r}"

    try:
        result = subprocess.run(
            ["cat", str(target)],
            shell=False,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(sandbox_root),
        )
        return result.stdout if result.returncode == 0 else f"[error] {result.stderr.strip()}"
    except FileNotFoundError:
        # No `cat` on this platform (Windows): read the file directly.
        try:
            return target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"[error] {exc}"
    except subprocess.TimeoutExpired:
        return "[error] command timed out"


# ---------------------------------------------------------------------------
# API invocation
# ---------------------------------------------------------------------------

def _run_tool_loop(
    api_key: str,
    api_url: str,
    model: str,
    messages: list,
    sandbox: Path,
    timeout_s: int,
    reasoning_budget: int = 0,
    system_prompt: str = "",
    temperature: float | None = None,
    thinking: bool | None = None,
) -> tuple[str, list, str, str]:
    """Run an agentic loop for E1 context.

    Returns (full_text, usage_list, reasoning, stop_reason). Every turn's
    reasoning is concatenated and the LAST stop_reason kept: that is the one
    that ended the loop, and the only one that can say the budget ran out."""
    all_text:  list[str] = []
    usage_list: list[dict] = []
    all_reasoning: list[str] = []
    stop_reason = "end_turn"

    for _ in range(MAX_TOOL_ITERS):
        effective_max_tokens = max(DEFAULT_MAX_TOKENS, reasoning_budget + 1024) if reasoning_budget > 0 else DEFAULT_MAX_TOKENS
        resp = _sdk_create(api_key, api_url, model, messages, [_BASH_TOOL], effective_max_tokens,
                           reasoning_budget=reasoning_budget, system_prompt=system_prompt,
                           temperature=temperature, thinking=thinking)
        usage_list.append(resp.get("usage", {}))

        content   = resp.get("content", [])
        stop_reason = resp.get("stop_reason", "end_turn")

        if resp.get("reasoning"):
            all_reasoning.append(resp["reasoning"])
        text = _text_from_content(content)
        if text:
            all_text.append(text)

        if stop_reason == "end_turn":
            break

        if stop_reason == "tool_use":
            tool_blocks = _tool_use_blocks(content)
            if not tool_blocks:
                break

            # Append assistant turn
            messages = messages + [{"role": "assistant", "content": content}]

            # Build tool result(s)
            tool_results = []
            for tb in tool_blocks:
                tid = tb.get("id") if isinstance(tb, dict) else getattr(tb, "id", "")
                result_text = _execute_tool_call(tb, sandbox)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tid,
                    "content": result_text,
                })

            messages = messages + [{"role": "user", "content": tool_results}]
        else:
            break

    return ("\n".join(all_text), usage_list,
            "\n".join(all_reasoning), stop_reason)


def _classify_exc(exc: Exception) -> str:
    """Map an exception to a run status string for Execution.status."""
    import urllib.error
    if isinstance(exc, (TimeoutError, TimeoutError)):
        return "timeout"
    name = type(exc).__name__
    if "Timeout" in name or "timeout" in str(exc).lower():
        return "timeout"
    if isinstance(exc, (ConnectionRefusedError, ConnectionResetError, OSError)):
        return "connection-error"
    if isinstance(exc, urllib.error.URLError):
        reason = str(exc.reason) if hasattr(exc, "reason") else ""
        if any(k in reason.lower() for k in ("refused", "unreachable", "network", "connect")):
            return "connection-error"
        return "connection-error"
    return "error"


def _invoke_api(
    sol_doc: dict,
    bundle: InputBundle,
    staged_path: Path,
    sandbox: Path,
    model: str,
    context: str,
    api_key: str,
    api_url: str,
    timeout_s: int,
    backend: str = "anthropic",
    reasoning_budget: int = 0,
    fixture_meta: dict | None = None,
    temperature: float | None = None,
    thinking: bool | None = None,
    level: str = "L1",
) -> tuple[str, str, list[str], object | None, dict]:
    """
    Returns (status, raw_text, trace_steps, payload, extras).
    Mirrors the signature of executor.py's _invoke.
    """
    meta = (fixture_meta or {}).get("meta", {})
    fixture_body = (fixture_meta or {}).get("body", "")
    system_prompt = meta.get("system_prompt", "")

    if context == "E0":
        prompt = _build_prompt_e0(sol_doc, bundle, fixture_body, level=level,
                                  prose_bodies=(fixture_meta or {}).get("prose"))
        messages = [{"role": "user", "content": prompt}]
        effective_max_tokens = max(DEFAULT_MAX_TOKENS, reasoning_budget + 1024) if reasoning_budget > 0 else DEFAULT_MAX_TOKENS
        try:
            resp = _sdk_create(api_key, api_url, model, messages, None,
                               effective_max_tokens, backend=backend,
                               reasoning_budget=reasoning_budget,
                               system_prompt=system_prompt,
                               temperature=temperature, thinking=thinking)
        except Exception as exc:
            if backend == "ollama":
                _ollama_unload(api_url, model)
            return _classify_exc(exc), str(exc), [], None, {}

        raw_text = _text_from_content(resp.get("content", []))
        usage    = resp.get("usage", {})
        extras   = {
            "tokens_in":  usage.get("input_tokens"),
            "tokens_out": usage.get("output_tokens"),
            "cost":       None,
            "request_messages": messages,
            "reasoning":   resp.get("reasoning", ""),
            "stop_reason": resp.get("stop_reason"),
        }
    else:
        # E1: tool loop
        prompt = _build_prompt_e1(sol_doc, staged_path)
        messages = [{"role": "user", "content": prompt}]
        try:
            raw_text, usage_list, reasoning, stop_reason = _run_tool_loop(
                api_key, api_url, model, messages, sandbox, timeout_s,
                reasoning_budget=reasoning_budget, system_prompt=system_prompt,
                temperature=temperature, thinking=thinking,
            )
        except Exception as exc:
            if backend == "ollama":
                _ollama_unload(api_url, model)
            return _classify_exc(exc), str(exc), [], None, {}

        tokens_in  = sum(u.get("input_tokens",  0) for u in usage_list) or None
        tokens_out = sum(u.get("output_tokens", 0) for u in usage_list) or None
        extras = {"tokens_in": tokens_in, "tokens_out": tokens_out, "cost": None,
                  "request_messages": messages,
                  "reasoning": reasoning, "stop_reason": stop_reason}

    return (
        "done",
        raw_text,
        _parse_trace(raw_text),
        _extract_payload(raw_text),
        extras,
    )


# ---------------------------------------------------------------------------
# Probe helper (mirrors executor.py)
# ---------------------------------------------------------------------------

def _inputs_without_expectation(expectations: dict, input_ids: list[str]) -> list[str]:
    cased = set()
    for c in expectations.get("cases", []):
        raw = c.get("input", "")
        cased.add(raw.removeprefix("inputs/").removesuffix(".json"))
    return [iid for iid in input_ids if iid not in cased]


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_headless_api(
    fixture_id: str,
    input_ids: list[str],
    context: str,
    model_id: str,
    runs: int,
    timeout_s: int,
    api_key: str,
    api_url: str,
    backend: str = "anthropic",
    dry_run: bool = False,
    reasoning_budget: int = 0,
    temperature: float | None = None,
    thinking: bool | None = None,
    ctx_size: int | None = None,
    kv_cache_type: str | None = None,
    n_parallel: int | None = None,
    level: str = "L1",
    mode: str = "",
) -> None:
    if backend in ("ollama", "openai") and context != "E0":
        sys.exit(
            f"E1 context requires a tool loop — not supported for backend={backend!r}. "
            f"Use --context E0."
        )

    fixture_dir, sol_doc, expectations, fixture_meta = _load_fixture(fixture_id)
    total = len(input_ids) * runs

    missing = _inputs_without_expectation(expectations, input_ids)
    if missing:
        print()
        print("!" * 70)
        print("  WARNING — inputs with NO case in expectations.json:")
        for iid in missing:
            print(f"    - {iid}")
        print()
        print("  These run fine, but the checker compares the returned verdict")
        print("  against None, so quality will read as 'wrong-value' no matter")
        print("  what the model actually returns. Add a case with the expected")
        print("  verdict to expectations.json BEFORE trusting the score.")
        print("!" * 70)

    print()
    print("=" * 70)
    print("  SOL API Executor" + ("  [DRY RUN — results not saved]" if dry_run else ""))
    print("=" * 70)
    print(f"  Fixture  : {fixture_id}")
    print(f"  Inputs   : {', '.join(input_ids)}")
    print(f"  Context  : {context}")
    print(f"  Model    : {model_id}")
    print(f"  API URL  : {api_url}")
    print(f"  Backend  : {backend}")
    print(f"  Runner   : api")
    print(f"  Reasoning: {reasoning_budget} tokens" if reasoning_budget > 0 else "  Reasoning: off")
    print(f"  Temp     : {temperature}" if temperature is not None else "  Temp     : (provider default)")
    print(f"  Runs     : {runs} × {len(input_ids)} input(s) = {total} total")
    print()
    print(f"  {'#':<5} {'Input':<35} {'Q':<6} {'F':<6} {'Time':<8} {'Tok':<8} Degrade")
    print("  " + "-" * 80)

    done_count = 0
    pass_q = 0
    pass_f = 0
    fid_eligible = 0

    for input_id in input_ids:
        bundle = _load_input(fixture_dir, input_id)

        for run_n in range(1, runs + 1):
            if backend == "ollama":
                _ollama_unload(api_url, model_id)
            sandbox, staged = _stage(bundle)
            t0 = datetime.now(timezone.utc)

            try:
                status, raw, steps, payload, extras = _invoke_api(
                    sol_doc, bundle, staged, sandbox,
                    model_id, context, api_key, api_url, timeout_s, backend,
                    reasoning_budget=reasoning_budget,
                    fixture_meta=fixture_meta,
                    temperature=temperature,
                    thinking=thinking,
                    level=level,
                )
            finally:
                shutil.rmtree(sandbox, ignore_errors=True)

            elapsed_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)

            ts = datetime.now(timezone.utc)
            run_id = (
                f"{fixture_id.replace('/', '-')}-{input_id}-"
                f"{ts.strftime('%Y%m%dT%H%M%S')}-r{run_n:02d}"
            )

            config = Config(
                fixture_id=fixture_id,
                context=context,
                model_id=model_id,
                env_realization="emulated",
                runner_type="api",
                api_base_url=api_url,
                backend=backend,
                reasoning_budget=reasoning_budget,
                temperature=temperature,
                thinking=thinking,
                ctx_size=ctx_size,
                kv_cache_type=kv_cache_type,
                n_parallel=n_parallel,
                process_rendering=_normalize_rendering(level),
                mode=mode,
            )
            record = RunRecord(
                run_id=run_id,
                timestamp=ts.isoformat(),
                config=config,
                staged_input_id=input_id,
                execution=Execution(
                    stop_reason=extras.get("stop_reason"),
                    status=status,
                    wall_clock_ms=elapsed_ms if status == "done" else None,
                ),
                trace=Trace(steps=steps, request_messages=extras.get("request_messages", [])),
                output=Output(
                    reasoning=extras.get("reasoning", ""),
                    raw=raw,
                    returned_payload=payload if status == "done" else None,
                ),
                usage=Usage(
                    tokens_in=extras.get("tokens_in"),
                    tokens_out=extras.get("tokens_out"),
                    cost=None,
                ),
            )

            score = check(record, expectations)

            if not dry_run:
                rec_path = _record_path(config, run_id)
                record.save(rec_path)
                score.save(_score_path(rec_path))
                _append_index(record, score)

            q_sym = {"pass": "OK", "fail": "XX"}.get(score.quality.result, "--")
            f_sym = {"pass": "OK", "fail": "XX"}.get(score.fidelity.result, "--")
            done_count += 1

            if score.quality.result == "pass":
                pass_q += 1
            if score.fidelity.result == "pass":
                pass_f += 1
            if score.fidelity.result != "not_checkable":
                fid_eligible += 1

            label = f"{input_id} #{run_n}"
            ms = score.efficiency.wall_clock_ms
            time_str = f"{ms/1000:.1f}s" if ms and ms >= 1000 else (f"{ms}ms" if ms else "—")
            tok_in = extras.get("tokens_in") or 0
            tok_out = extras.get("tokens_out") or 0
            tok_str = str(tok_in + tok_out) if (tok_in or tok_out) else "—"
            print(f"  {done_count:<5} {label:<35} {q_sym:<6} {f_sym:<6} {time_str:<8} {tok_str:<8} {score.degradation_mode}")

    print("  " + "-" * 80)
    pct_q = 100 * pass_q // total if total else 0
    pct_f = 100 * pass_f // fid_eligible if fid_eligible else 0
    print(f"  Quality  : {pass_q}/{total} pass ({pct_q}%)")
    fid_label = f"{pass_f}/{fid_eligible}" if fid_eligible else "n/a"
    print(f"  Fidelity : {fid_label} pass ({pct_f}%)"
          + ("" if fid_eligible else "  [no trace emitted]"))
    if dry_run:
        print(f"  (dry run — nothing written to disk)")
    else:
        print(f"  Index    : {(RESULTS_DIR / 'index.jsonl').relative_to(REPO_ROOT)}")
        _regen_dashboard()
    print()


def _regen_dashboard() -> None:
    dashboard_script = REPO_ROOT / "scripts" / "dashboard.py"
    if not dashboard_script.exists():
        return
    try:
        result = subprocess.run(
            [sys.executable, str(dashboard_script)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            print(f"  Dashboard: tests/results/dashboard.html  (regenerated)")
        else:
            print(f"  Dashboard: regeneration failed — {result.stderr.strip()[:120]}")
    except Exception as exc:
        print(f"  Dashboard: regeneration skipped ({exc})")


# ---------------------------------------------------------------------------
# Mode helper (reads tests/modes.json + tests/env.json)
# ---------------------------------------------------------------------------

def _load_mode_entry(mode: str) -> dict:
    """The single reader of tests/modes.json and tests/env.json: return the
    entry for `mode`, with the Anthropic key grafted in when there is one.

    Every other mode accessor in the repo is a projection over this
    function — _load_mode below, run._load_env_entry, and
    scripts/preprocess_p2a._load_mode. Three parsers with three field lists
    meant a field added to the mode config (the 2026-08-19 revision's thinking/ctx_size/
    kv_cache_type/n_parallel) reached only the entrypoint someone remembered
    to wire.

    The configuration lives in tests/modes.json (tracked) and the
    credentials in tests/env.json (gitignored). modes.json missing or invalid
    is fatal; env.json missing, invalid or silent about `mode` is not — the
    entry comes back without a `key` and the guard in _load_mode decides
    whether that is an error. That is what lets a fresh clone run every local
    mode with no credentials at all.
    """
    if not MODES_PATH.exists():
        sys.exit(f"modes.json not found at {MODES_PATH}")
    try:
        modes = json.loads(MODES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"modes.json is not valid JSON: {exc}")
    entries = modes.get("modes", [])
    found = None
    for candidate in entries:
        if candidate.get("mode") == mode:
            found = candidate
            break
    if found is None:
        known = [e.get("mode") for e in entries]
        sys.exit(f"Mode '{mode}' not found in modes.json. Available: {known}")

    # Copy, never the loaded reference: campaign._mode_config caches entries by
    # mode name, and grafting the key into the shared dict would contaminate it.
    entry = dict(found)
    if entry.get("backend") == "anthropic":
        key = _load_mode_key(mode)
        if key:
            entry["key"] = key
    return entry


def _load_mode_key(mode: str) -> str:
    """Return the credential for `mode` from tests/env.json, or "" .

    Every failure is non-fatal by design (file absent, invalid JSON, mode not
    declared, empty key): the caller returns an entry without a key and the
    guard in _load_mode is the one place that decides if that is fatal.
    """
    if not ENV_PATH.exists():
        return ""
    try:
        env = json.loads(ENV_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    for entry in env.get("modes", []):
        if entry.get("mode") == mode:
            return entry.get("key", "") or ""
    return ""


def _load_mode(mode: str) -> tuple[
    str, str, str, str, int, float | None,
    bool | None, int | None, str | None, int | None,
]:
    """Return (api_key, api_url, model, backend, reasoning_budget, temperature,
    thinking, ctx_size, kv_cache_type, n_parallel) for the named mode entry in
    tests/modes.json, with api_key grafted in from tests/env.json when the mode
    declares one. The last four are None when absent from the entry."""
    entry            = _load_mode_entry(mode)
    key              = entry.get("key", "")
    url              = entry.get("url", DEFAULT_API_URL)
    model            = entry.get("model", "claude-opus-4-8")
    backend          = entry.get("backend", "anthropic")
    reasoning_budget = int(entry.get("reasoning", 0))
    temperature      = entry.get("temperature")
    temperature      = float(temperature) if temperature is not None else None
    thinking         = entry.get("thinking")
    ctx_size         = entry.get("ctx_size")
    kv_cache_type    = entry.get("kv_cache_type")
    n_parallel       = entry.get("n_parallel")
    # The key is optional for Ollama/LM Studio (forwarded only if present);
    # the Anthropic backend always requires one -- unless the mode is not an API
    # mode at all. A runner_type='claude-code' entry names an Anthropic model but
    # never opens an HTTP connection: the CLI holds the session and authenticates
    # itself, which is exactly what tests/env.example.json already says about
    # claude-code-local. Before 2026-08-31 this guard fired on every claude-code
    # mode that reached it, so campaign._mode_config could not read one at all.
    if not key and backend not in ("ollama", "openai") and entry.get("runner_type") != "claude-code":
        sys.exit(f"Mode '{mode}' in env.json has no 'key' field")
    return (key, url, model, backend, reasoning_budget, temperature,
            thinking, ctx_size, kv_cache_type, n_parallel)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> None:
    p = argparse.ArgumentParser(
        description="SOL API executor — headless runner via Anthropic Messages API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--fixture", required=True,
                   help="Fixture ID, e.g. w2-branching/release-gate")

    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--input",
                     help="Input ID, e.g. i1-blocked")
    grp.add_argument("--all-inputs", action="store_true",
                     help="Run all inputs in the fixture's inputs/ directory")

    p.add_argument("--context", default="E0",
                   choices=["E0", "E1"],
                   help="Execution context: E0 (no tools) | E1 (Bash/cat) [default: E0]")
    p.add_argument("--model", default=None,
                   help="Model ID [default: claude-opus-4-8, or from --mode]")
    p.add_argument("--runs", type=int, default=1,
                   help="Number of runs per input [default: 1]")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S,
                   help=f"Timeout per run in seconds [default: {DEFAULT_TIMEOUT_S}]")
    p.add_argument("--api-key", default=None,
                   help="Anthropic API key [default: env ANTHROPIC_API_KEY or from --mode]")
    p.add_argument("--api-url", default=None,
                   help=f"API base URL [default: {DEFAULT_API_URL} or from --mode]")
    p.add_argument("--mode", default=None,
                   help="Load api-url, model, backend from tests/modes.json and api-key from tests/env.json (e.g. claude-api)")
    p.add_argument("--backend", default=None, choices=["anthropic", "ollama", "openai"],
                   help="Backend: anthropic (default) | ollama | openai (LM Studio). Overrides --mode's backend.")
    p.add_argument("--reasoning", type=int, default=None,
                   help="Thinking budget in tokens (0 = off). Overrides modes.json 'reasoning' field.")
    p.add_argument("--temperature", type=float, default=None,
                   help="Sampling temperature. Overrides modes.json 'temperature' field. "
                        "Omitted entirely (provider default) if not set anywhere.")
    p.add_argument("--dry-run", action="store_true",
                   help="Execute and score but do not write any files (probe/debug mode)")
    p.add_argument("--level", default="L1", choices=list(RENDERINGS),
                   help="Predictability-layer scale for the E0 prompt [default: L1]")
    args = p.parse_args(argv)

    if args.mode:
        (env_key, env_url, env_model, env_backend, env_reasoning, env_temperature,
         thinking, ctx_size, kv_cache_type, n_parallel) = _load_mode(args.mode)
        api_key          = args.api_key  or env_key
        api_url          = args.api_url  or env_url
        model_id         = args.model    or env_model
        backend          = args.backend  or env_backend
        reasoning_budget = args.reasoning if args.reasoning is not None else env_reasoning
        temperature      = args.temperature if args.temperature is not None else env_temperature
    else:
        api_key          = args.api_key  or os.environ.get("ANTHROPIC_API_KEY", "")
        api_url          = args.api_url  or DEFAULT_API_URL
        model_id         = args.model    or "claude-opus-4-8"
        backend          = args.backend  or "anthropic"
        reasoning_budget = args.reasoning or 0
        temperature      = args.temperature
        thinking = ctx_size = kv_cache_type = n_parallel = None

    # Ollama/LM Studio need no auth; only the Anthropic backend requires a key.
    if not api_key and backend not in ("ollama", "openai"):
        sys.exit(
            "No API key provided. Pass --api-key, --mode, or set ANTHROPIC_API_KEY."
        )

    fixture_dir = FIXTURES_DIR / args.fixture
    if not fixture_dir.is_dir():
        sys.exit(f"Fixture not found: {fixture_dir}")

    if args.all_inputs:
        input_ids = _list_inputs(fixture_dir)
        if not input_ids:
            sys.exit(f"No inputs found in {fixture_dir / 'inputs'}")
    else:
        input_ids = [args.input]

    run_headless_api(
        fixture_id=args.fixture,
        input_ids=input_ids,
        context=args.context,
        model_id=model_id,
        runs=args.runs,
        timeout_s=args.timeout,
        api_key=api_key,
        api_url=api_url,
        backend=backend,
        dry_run=args.dry_run,
        reasoning_budget=reasoning_budget,
        temperature=temperature,
        thinking=thinking,
        ctx_size=ctx_size,
        kv_cache_type=kv_cache_type,
        n_parallel=n_parallel,
        level=args.level,
    )


if __name__ == "__main__":
    main()
