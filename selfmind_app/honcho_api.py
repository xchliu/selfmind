"""SelfMind Honcho API Data Source

Fetches memory data from Honcho API (conclusions, peer cards, representations)
and normalizes into SelfMind's entry dict format for integration with the graph.
"""

import logging
import re
from datetime import datetime
from hashlib import md5
from typing import Optional

import urllib.request
import urllib.error
import json

logger = logging.getLogger(__name__)


def _http_get(url: str, timeout: int = 10) -> Optional[dict]:
    """Simple HTTP GET returning parsed JSON, or None on failure."""
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Honcho API GET {url} failed: {exc}")
        return None


def _http_post(url: str, body: dict, timeout: int = 15) -> Optional[dict | list]:
    """Simple HTTP POST returning parsed JSON, or None on failure."""
    try:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Honcho API POST {url} failed: {exc}")
        return None


def fetch_conclusions(base_url: str, workspace: str, page_size: int = 200) -> list[dict]:
    """Fetch all conclusions from Honcho API (paginated)."""
    url = f"{base_url}/workspaces/{workspace}/conclusions/list"
    all_items: list[dict] = []
    page = 1

    while True:
        result = _http_post(url, {"page": page, "size": page_size})
        if result is None:
            break

        items = result.get("items", [])
        if not items:
            break

        all_items.extend(items)

        total_pages = result.get("pages", 1)
        if page >= total_pages:
            break
        page += 1

    return all_items


def fetch_peer_context(base_url: str, workspace: str, peer_id: str) -> Optional[dict]:
    """Fetch peer context (representation + peer_card) for a given peer."""
    url = f"{base_url}/workspaces/{workspace}/peers/{peer_id}/context"
    return _http_get(url)


def fetch_peers(base_url: str, workspace: str) -> list[str]:
    """Fetch list of peer IDs in workspace."""
    url = f"{base_url}/workspaces/{workspace}/peers/list"
    result = _http_get(url)
    if result is None:
        return []
    # Result is a list of peer dicts with "id" field
    return [p.get("id", "") for p in result if p.get("id")]


def _make_entry(
    text: str,
    source_profile: str,
    source_file: str,
    classify_fn,  # Callable: (text) -> (primary, secondary)
    label_fn,     # Callable: (text, max_len) -> str
) -> dict:
    """Create an entry dict in SelfMind's standard format."""
    stripped = text.strip()
    if len(stripped) < 5:
        return None

    node_id = "n_" + md5(stripped.encode()).hexdigest()[:8]
    label = label_fn(stripped)
    primary, secondary = classify_fn(stripped)
    description = re.sub(r"\*\*", "", stripped).strip()[:150]

    return {
        "text": stripped,
        "label": label,
        "primary": primary,
        "secondary": secondary,
        "description": description,
        "node_id": node_id,
        "source_profile": source_profile,
        "source_file": source_file,
    }


def parse_honcho_api(
    api_config: dict,
    profile_name: str,
    classify_fn,
    label_fn,
) -> list[dict]:
    """Fetch Honcho API data and normalize into SelfMind entry dicts.

    api_config should contain:
      - base_url: e.g. "http://localhost:8888/v3"
      - workspace: e.g. "hermes"
      - peers: list of peer IDs to fetch context for, e.g. ["liuxiaocheng", "hermes"]

    Returns list of entry dicts compatible with parse_memories() output.
    """
    base_url = api_config.get("base_url", "http://localhost:8000/v3")
    workspace = api_config.get("workspace", "hermes")
    configured_peers = api_config.get("peers", ["liuxiaocheng", "hermes"])

    entries: list[dict] = []

    # 1. Fetch all conclusions
    logger.info(f"Fetching Honcho conclusions from {base_url}/workspaces/{workspace}")
    conclusions = fetch_conclusions(base_url, workspace)

    for conclusion in conclusions:
        content = conclusion.get("content", "")
        if not content or len(content.strip()) < 5:
            continue

        observer = conclusion.get("observer_id", "")
        observed = conclusion.get("observed_id", "")

        # Prefix with observer/observed context for richer classification
        enriched_text = content
        if observer and observed:
            enriched_text = f"[{observer}→{observed}] {content}"

        entry = _make_entry(
            enriched_text,
            source_profile=profile_name,
            source_file="conclusions",
            classify_fn=classify_fn,
            label_fn=label_fn,
        )
        if entry:
            # Override label: use original content (not enriched) for cleaner labels
            entry["label"] = label_fn(content.strip(), max_len=20)
            entries.append(entry)

    logger.info(f"  → {len(conclusions)} conclusions fetched, {len(entries)} entries created")

    # 2. Fetch peer context for each configured peer
    for peer_id in configured_peers:
        logger.info(f"Fetching Honcho peer context for {peer_id}")
        context = fetch_peer_context(base_url, workspace, peer_id)
        if context is None:
            continue

        # Peer card items → individual entries
        peer_card = context.get("peer_card")
        if peer_card and isinstance(peer_card, list):
            for card_item in peer_card:
                text = f"[social/key_people] {card_item} (Peer Card: {peer_id})"
                entry = _make_entry(
                    text,
                    source_profile=profile_name,
                    source_file=f"peer_card/{peer_id}",
                    classify_fn=classify_fn,
                    label_fn=label_fn,
                )
                if entry:
                    entry["label"] = f"{peer_id}: {label_fn(card_item, max_len=12)}"
                    entries.append(entry)

        # Representation → split into sections, process each
        representation = context.get("representation", "")
        if representation:
            # Split representation by "##" headers or double newlines
            sections = re.split(r"\n##\s+", representation)
            for section in sections:
                section = section.strip()
                if len(section) < 10:
                    continue

                # Tag with peer source
                tagged = f"[Honcho/{peer_id}] {section}"
                entry = _make_entry(
                    tagged,
                    source_profile=profile_name,
                    source_file=f"representation/{peer_id}",
                    classify_fn=classify_fn,
                    label_fn=label_fn,
                )
                if entry:
                    entries.append(entry)

    logger.info(f"  → Total Honcho entries: {len(entries)}")
    return entries


def honcho_api_health(base_url: str, timeout: int = 5) -> dict:
    """Check Honcho API health for poll endpoint."""
    url = base_url.rstrip("/v3") + "/health"
    result = _http_get(url, timeout=timeout)
    if result is None:
        return {"status": "unreachable", "conclusion_count": 0}
    return {
        "status": "ok",
        "conclusion_count": result.get("conclusion_count", 0) if isinstance(result, dict) else 0,
    }