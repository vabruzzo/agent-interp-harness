"""Resample a specific API turn to get N fresh responses.

Reads the raw request dump + captured headers, replays the exact same request
to the same target URL, and saves each response alongside the original run.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx
import typer

logger = logging.getLogger(__name__)


def _session_dir(run_dir: Path, session_index: int) -> Path:
    return run_dir / f"session_{session_index:02d}"


def _load_request(raw_dumps_dir: Path, request_index: int) -> dict:
    """Load a raw request JSON from the dumps directory."""
    req_path = raw_dumps_dir / f"request_{request_index:03d}.json"
    if not req_path.exists():
        raise FileNotFoundError(
            f"No raw dump found at {req_path}. "
            "Ensure the run was captured with API request dumping enabled."
        )
    with open(req_path) as f:
        return json.load(f)


def _load_headers(raw_dumps_dir: Path, request_index: int) -> dict:
    """Load captured request headers. Returns {target, headers} or defaults."""
    hdr_path = raw_dumps_dir / f"request_{request_index:03d}_headers.json"
    if hdr_path.exists():
        with open(hdr_path) as f:
            return json.load(f)
    return {}


def _clean_thinking_signatures(messages: list) -> list:
    """Strip thinking block signatures — they're response-specific."""
    cleaned = []
    for msg in messages:
        if isinstance(msg.get("content"), list):
            cleaned_content = []
            for block in msg["content"]:
                if block.get("type") == "thinking":
                    cleaned_content.append({
                        "type": "thinking",
                        "thinking": block.get("thinking", ""),
                    })
                else:
                    cleaned_content.append(block)
            cleaned.append({**msg, "content": cleaned_content})
        else:
            cleaned.append(msg)
    return cleaned


def _build_headers(
    captured_headers: dict[str, str], api_key: str, target_url: str
) -> dict[str, str]:
    """Build replay headers from captured headers, replacing auth."""
    headers = {**captured_headers}
    # Use the right auth header for the target
    if "openrouter.ai" in target_url:
        headers["Authorization"] = f"Bearer {api_key}"
        headers.pop("x-api-key", None)
    else:
        headers["x-api-key"] = api_key
        headers.pop("Authorization", None)
    # Remove stale/unnecessary headers
    for key in list(headers):
        if key.lower().startswith("x-stainless"):
            del headers[key]
    headers.pop("Connection", None)
    headers.pop("Accept-Encoding", None)
    return headers


async def _call_api(url: str, headers: dict[str, str], request_data: dict) -> dict:
    """Call the API once (non-streaming) with the exact captured request."""
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(url, json=request_data, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def run_resample(
    run_dir: Path,
    session_index: int,
    request_index: int,
    count: int,
    model_override: str | None = None,
) -> Path:
    """Resample a specific request N times and save results.

    Returns the directory containing the resample results.
    """
    import os

    session_dir = _session_dir(run_dir, session_index)
    raw_dumps_dir = session_dir / "raw_dumps"

    # Load the exact request body the SDK sent
    request_data = _load_request(raw_dumps_dir, request_index)

    # Load captured headers to get target URL
    hdr_data = _load_headers(raw_dumps_dir, request_index)
    target_url = hdr_data.get("target")
    captured_headers = hdr_data.get("headers", {})

    if not target_url:
        # Fallback: construct from env
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        target_url = f"{base_url.rstrip('/')}/v1/messages"
        captured_headers = {
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    # Minimal modifications: non-streaming + clean thinking signatures
    request_data["stream"] = False
    if isinstance(request_data.get("messages"), list):
        request_data["messages"] = _clean_thinking_signatures(request_data["messages"])
    if model_override:
        request_data["model"] = model_override

    # Resolve API key based on target
    if "openrouter.ai" in target_url:
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            typer.echo("Error: OPENROUTER_API_KEY not set", err=True)
            raise typer.Exit(1)
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            typer.echo("Error: ANTHROPIC_API_KEY not set", err=True)
            raise typer.Exit(1)

    headers = _build_headers(captured_headers, api_key, target_url)

    # Output directory
    resample_dir = session_dir / "resamples" / f"request_{request_index:03d}"
    resample_dir.mkdir(parents=True, exist_ok=True)

    # Find next sample number (allow appending to existing resamples)
    existing = list(resample_dir.glob("sample_*.json"))
    next_num = len(existing) + 1

    typer.echo(
        f"Resampling request {request_index} from session {session_index} "
        f"({count} samples, model={request_data.get('model')}, target={target_url})..."
    )

    for i in range(count):
        sample_num = next_num + i
        typer.echo(f"  Sample {sample_num}/{next_num + count - 1}...", nl=False)

        try:
            response = await _call_api(target_url, headers, request_data)
            sample_path = resample_dir / f"sample_{sample_num:02d}.json"
            with open(sample_path, "w") as f:
                json.dump(response, f, indent=2)

            # Quick summary
            content = response.get("content", [])
            block_types = [b.get("type", "?") for b in content]
            usage = response.get("usage", {})
            out_tokens = usage.get("output_tokens", "?")
            typer.echo(f" done ({out_tokens} tokens, blocks: {block_types})")

        except httpx.HTTPStatusError as e:
            typer.echo(f" error: {e.response.status_code} {e.response.text[:200]}")
            error_path = resample_dir / f"sample_{sample_num:02d}_error.json"
            with open(error_path, "w") as f:
                json.dump({"error": str(e), "status": e.response.status_code, "body": e.response.text}, f, indent=2)

        except Exception as e:
            typer.echo(f" error: {e}")

    typer.echo(f"\nResults saved to: {resample_dir}")
    return resample_dir
