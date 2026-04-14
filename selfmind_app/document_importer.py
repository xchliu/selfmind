"""SelfMind Document Importer — Scan documents and extract memories via LLM.

Provides a pipeline for importing knowledge from local documents (.txt, .md)
into structured memory entries classified by the SelfMind TAXONOMY system.

Flow:  scan_directory → read_document → extract_memories → structured entries

Uses only Python stdlib (urllib for HTTP) — zero third-party dependencies.
"""

import json
import logging
import os
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────

SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md"}
KNOWN_BUT_UNSUPPORTED = {".pdf", ".docx"}
ALL_SUPPORTED_EXTENSIONS = SUPPORTED_TEXT_EXTENSIONS | KNOWN_BUT_UNSUPPORTED

CHUNK_SIZE = 8000  # Characters — split documents larger than this

# Full taxonomy reference for LLM prompt
TAXONOMY_REFERENCE = """\
8 primary categories with subcategories:

1. autobiographical — Self-knowledge and identity
   - identity: name, role, personality traits, core identity facts
   - growth: evolution, version changes, capability improvements
   - principles: red lines, boundaries, behavioral rules

2. semantic — Factual knowledge
   - domain: industry knowledge, business strategy, finance
   - technical: architecture, algorithms, protocols, technical concepts
   - methodology: best practices, frameworks, mental models

3. episodic — Experience-based knowledge
   - success: things that worked, effective methods
   - failure: lessons learned, mistakes, things to avoid
   - milestone: key events, turning points, important dates

4. procedural — How-to knowledge
   - development: coding, debugging, architecture design
   - operations: deployment, monitoring, DevOps
   - creative: writing, design, media production
   - research: investigation, analysis, paper searching
   - communication: email, social media, messaging
   - tools: CLI, API, platform operation methods

5. social — People and relationships
   - key_people: important people, their roles and identities
   - relationships: relationship networks, org structure
   - preferences: communication styles, habits, taboos

6. working — Current work context
   - active: currently active projects
   - backlog: queued tasks, ideas, TODOs
   - archived: completed or paused projects

7. spatial — Environment awareness
   - system: OS, hardware, network configuration
   - filesystem: important paths, project locations
   - services: ports, APIs, database locations

8. emotional — Emotional understanding
   - user_mood: emotional patterns, triggers
   - likes_dislikes: preferences, things liked/disliked
   - trust: trust levels, authorization boundaries"""

EXTRACTION_PROMPT = """\
You are a memory extraction system. Analyze the following document and extract \
distinct, meaningful memory entries. Each memory should capture a single fact, \
preference, person, tool, project, principle, or piece of knowledge.

TAXONOMY for classification:
{taxonomy}

For each memory entry, return a JSON object with these fields:
- "text": The original relevant text snippet (keep it concise, under 200 chars)
- "label": A short label/title for this memory (under 20 chars)
- "primary": The primary taxonomy category (one of the 8 categories above)
- "secondary": The subcategory within the primary category
- "description": A clean summary of this memory (under 150 chars)

Rules:
1. Extract ONLY meaningful, specific information — skip filler, boilerplate, formatting
2. Each memory should be self-contained and independently useful
3. Classify each memory using the taxonomy above — pick the best fit
4. If a document mentions a person by name, create a social/key_people entry
5. If a document describes a process or how-to, create a procedural entry
6. Return ONLY a JSON array of memory objects — no other text, no markdown fences

Source file: {source_file}

DOCUMENT CONTENT:
---
{content}
---

Return a JSON array of extracted memory entries:"""


# ────────────────────────────────────────────────────────────────────
# DocumentImporter class
# ────────────────────────────────────────────────────────────────────

class DocumentImporter:
    """Scan local directories for documents and extract structured memories via LLM."""

    def __init__(self) -> None:
        pass

    # ────────────────────────────────────────────────────────────────
    # 1. Directory scanning
    # ────────────────────────────────────────────────────────────────

    def scan_directory(self, dir_path: str) -> list[dict]:
        """Scan a directory for supported document files.

        Args:
            dir_path: Path to the directory to scan.

        Returns:
            List of dicts with keys: path, name, size, type, modified
        """
        directory = Path(dir_path).expanduser().resolve()
        if not directory.is_dir():
            logger.warning("Directory does not exist: %s", dir_path)
            return []

        results: list[dict] = []
        for file_path in sorted(directory.rglob("*")):
            if not file_path.is_file():
                continue
            ext = file_path.suffix.lower()
            if ext not in ALL_SUPPORTED_EXTENSIONS:
                continue

            stat = file_path.stat()
            results.append({
                "path": str(file_path),
                "name": file_path.name,
                "size": stat.st_size,
                "type": ext.lstrip("."),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

        logger.info("Scanned %s — found %d document(s)", dir_path, len(results))
        return results

    # ────────────────────────────────────────────────────────────────
    # 2. Document reading
    # ────────────────────────────────────────────────────────────────

    def read_document(self, file_path: str) -> str:
        """Read a document file and return its text content.

        Supports .txt and .md files directly.
        Logs a warning and returns empty string for .pdf/.docx
        (which require third-party dependencies).

        Args:
            file_path: Path to the document file.

        Returns:
            Document text content, or empty string on failure.
        """
        path = Path(file_path).expanduser().resolve()

        if not path.is_file():
            logger.warning("File not found: %s", file_path)
            return ""

        ext = path.suffix.lower()

        if ext in SUPPORTED_TEXT_EXTENSIONS:
            try:
                return path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Try with latin-1 fallback
                try:
                    return path.read_text(encoding="latin-1")
                except Exception as exc:
                    logger.error("Failed to read %s: %s", file_path, exc)
                    return ""
            except OSError as exc:
                logger.error("Failed to read %s: %s", file_path, exc)
                return ""

        if ext in KNOWN_BUT_UNSUPPORTED:
            logger.warning(
                "Skipping %s — %s format requires additional dependencies "
                "(e.g., PyPDF2 for PDF, python-docx for DOCX). "
                "Only .txt and .md files are supported currently.",
                path.name, ext,
            )
            return ""

        logger.warning("Unsupported file type: %s", ext)
        return ""

    # ────────────────────────────────────────────────────────────────
    # 3. Text chunking
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def _chunk_text(text: str, max_chars: int = CHUNK_SIZE) -> list[str]:
        """Split text into chunks, respecting section/paragraph boundaries.

        Strategy:
        1. Try to split on markdown headings (## or #)
        2. Fall back to splitting on double newlines (paragraphs)
        3. Last resort: split on single newlines
        4. Final fallback: hard split at max_chars
        """
        if len(text) <= max_chars:
            return [text]

        chunks: list[str] = []

        # Try splitting on markdown headings first
        sections = re.split(r"(?=^#{1,3}\s)", text, flags=re.MULTILINE)
        sections = [s.strip() for s in sections if s.strip()]

        # If we got meaningful sections, group them into chunks
        if len(sections) > 1:
            current_chunk = ""
            for section in sections:
                if len(current_chunk) + len(section) + 2 > max_chars and current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = section
                else:
                    current_chunk = current_chunk + "\n\n" + section if current_chunk else section
            if current_chunk.strip():
                chunks.append(current_chunk.strip())

            # Verify all chunks are within limit; if any is too large, sub-split it
            final_chunks: list[str] = []
            for chunk in chunks:
                if len(chunk) <= max_chars:
                    final_chunks.append(chunk)
                else:
                    final_chunks.extend(
                        DocumentImporter._split_by_paragraphs(chunk, max_chars)
                    )
            return final_chunks

        # No heading structure — fall back to paragraph splitting
        return DocumentImporter._split_by_paragraphs(text, max_chars)

    @staticmethod
    def _split_by_paragraphs(text: str, max_chars: int) -> list[str]:
        """Split text by paragraph boundaries (double newline), respecting max size."""
        paragraphs = re.split(r"\n\s*\n", text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        chunks: list[str] = []
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 > max_chars and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk = current_chunk + "\n\n" + para if current_chunk else para

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        # Final safety: hard-split any chunk still over limit
        final: list[str] = []
        for chunk in chunks:
            if len(chunk) <= max_chars:
                final.append(chunk)
            else:
                # Hard split on newlines, then by character count
                lines = chunk.split("\n")
                buf = ""
                for line in lines:
                    if len(buf) + len(line) + 1 > max_chars and buf:
                        final.append(buf.strip())
                        buf = line
                    else:
                        buf = buf + "\n" + line if buf else line
                if buf.strip():
                    final.append(buf.strip())

        # Hard-split any remaining oversized chunks by character count
        result: list[str] = []
        for chunk in (final if final else [text]):
            if len(chunk) <= max_chars:
                result.append(chunk)
            else:
                for start in range(0, len(chunk), max_chars):
                    result.append(chunk[start : start + max_chars])
        return result

    # ────────────────────────────────────────────────────────────────
    # 4. LLM-based memory extraction
    # ────────────────────────────────────────────────────────────────

    def extract_memories(
        self, text: str, source_file: str, config: dict
    ) -> list[dict]:
        """Extract structured memory entries from text using an LLM API.

        Handles chunking for large documents (> CHUNK_SIZE chars).
        Each extracted memory gets status='pending' added.

        Args:
            text: Document text content.
            source_file: Source file name/path for attribution.
            config: Configuration dict with 'llm' section.

        Returns:
            List of memory entry dicts with keys:
            text, label, primary, secondary, description, source_file, status
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for extraction from %s", source_file)
            return []

        llm_config = config.get("llm", {})
        chunks = self._chunk_text(text)
        all_memories: list[dict] = []

        logger.info(
            "Extracting memories from %s (%d chunk(s), %d chars total)",
            source_file, len(chunks), len(text),
        )

        for i, chunk in enumerate(chunks):
            logger.debug("Processing chunk %d/%d for %s", i + 1, len(chunks), source_file)
            try:
                raw_memories = self._call_llm(chunk, source_file, llm_config)
                for mem in raw_memories:
                    mem["source_file"] = source_file
                    mem["status"] = "pending"
                    # Validate required fields
                    if self._validate_memory(mem):
                        all_memories.append(mem)
                    else:
                        logger.warning(
                            "Skipping invalid memory entry from %s: %s",
                            source_file, mem.get("label", "<no label>"),
                        )
            except Exception as exc:
                logger.error(
                    "LLM extraction failed for chunk %d of %s: %s",
                    i + 1, source_file, exc,
                )

        logger.info("Extracted %d memories from %s", len(all_memories), source_file)
        return all_memories

    def _call_llm(self, content: str, source_file: str, llm_config: dict) -> list[dict]:
        """Make an OpenAI-compatible chat completion API call.

        Args:
            content: Text chunk to extract memories from.
            source_file: Source file name for prompt context.
            llm_config: LLM configuration dict.

        Returns:
            List of memory dicts parsed from LLM response.

        Raises:
            RuntimeError: If the API call fails or response is unparseable.
        """
        base_url = llm_config.get("base_url", "https://api.openai.com/v1").rstrip("/")
        api_key = llm_config.get("api_key") or os.environ.get("LLM_API_KEY", "")
        model = llm_config.get("model", "gpt-4o-mini")
        max_tokens = llm_config.get("max_tokens", 4096)

        if not api_key:
            raise RuntimeError(
                "No LLM API key configured. Set 'llm.api_key' in config "
                "or the LLM_API_KEY environment variable."
            )

        prompt = EXTRACTION_PROMPT.format(
            taxonomy=TAXONOMY_REFERENCE,
            source_file=source_file,
            content=content,
        )

        url = f"{base_url}/chat/completions"
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a precise memory extraction engine. "
                        "You ONLY output valid JSON arrays. No markdown, no explanations."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        # Create an SSL context that works broadly
        ctx = ssl.create_default_context()

        try:
            with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = ""
            try:
                error_body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            raise RuntimeError(
                f"LLM API returned HTTP {exc.code}: {error_body[:500]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM API connection error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"LLM API returned invalid JSON: {exc}") from exc

        # Parse response
        try:
            choices = resp_data.get("choices", [])
            if not choices:
                raise RuntimeError("LLM API returned no choices")

            message_content = choices[0].get("message", {}).get("content", "")
            return self._parse_llm_response(message_content)
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Unexpected LLM response structure: {exc}") from exc

    @staticmethod
    def _parse_llm_response(response_text: str) -> list[dict]:
        """Parse LLM response text into a list of memory dicts.

        Handles various response formats:
        - Clean JSON array
        - JSON wrapped in markdown code fences
        - JSON with trailing text
        """
        text = response_text.strip()

        # Remove markdown code fences if present
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

        # Try parsing directly
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                return [result]
        except json.JSONDecodeError:
            pass

        # Try to find a JSON array in the text
        array_match = re.search(r"\[.*\]", text, re.DOTALL)
        if array_match:
            try:
                result = json.loads(array_match.group())
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        logger.warning("Could not parse LLM response as JSON: %s...", text[:200])
        return []

    @staticmethod
    def _validate_memory(mem: dict) -> bool:
        """Validate that a memory entry has all required fields with valid values."""
        required_fields = {"text", "label", "primary", "secondary", "description"}
        if not all(mem.get(f) for f in required_fields):
            return False

        valid_primaries = {
            "autobiographical", "semantic", "episodic", "procedural",
            "social", "working", "spatial", "emotional",
        }
        valid_secondaries = {
            "autobiographical": {"identity", "growth", "principles"},
            "semantic": {"domain", "technical", "methodology"},
            "episodic": {"success", "failure", "milestone"},
            "procedural": {"development", "operations", "creative", "research", "communication", "tools"},
            "social": {"key_people", "relationships", "preferences"},
            "working": {"active", "backlog", "archived"},
            "spatial": {"system", "filesystem", "services"},
            "emotional": {"user_mood", "likes_dislikes", "trust"},
        }

        primary = mem.get("primary", "")
        secondary = mem.get("secondary", "")

        if primary not in valid_primaries:
            logger.debug("Invalid primary category: %s", primary)
            return False

        if secondary not in valid_secondaries.get(primary, set()):
            logger.debug(
                "Invalid secondary category: %s/%s", primary, secondary
            )
            return False

        return True

    # ────────────────────────────────────────────────────────────────
    # 5. Batch processing
    # ────────────────────────────────────────────────────────────────

    def batch_extract(self, dir_path: str, config: dict) -> list[dict]:
        """Scan a directory, read all documents, and extract memories from each.

        This is the main high-level pipeline: scan → read → extract.

        Args:
            dir_path: Path to directory to scan for documents.
            config: Configuration dict with 'llm' section.

        Returns:
            Aggregated list of memory entry dicts from all documents.
        """
        files = self.scan_directory(dir_path)
        if not files:
            logger.info("No documents found in %s", dir_path)
            return []

        all_memories: list[dict] = []
        processed = 0
        skipped = 0

        for file_info in files:
            file_path = file_info["path"]
            logger.info("Processing: %s (%s)", file_info["name"], file_info["type"])

            content = self.read_document(file_path)
            if not content.strip():
                skipped += 1
                continue

            memories = self.extract_memories(content, file_info["name"], config)
            all_memories.extend(memories)
            processed += 1

        logger.info(
            "Batch extraction complete: %d file(s) processed, %d skipped, "
            "%d memories extracted",
            processed, skipped, len(all_memories),
        )
        return all_memories
