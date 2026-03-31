"""
Swarms AI Complex GameDev Team - Modular Python Raylib Projects

Uses AgentRearrange for:
    ProjectArchitect -> SystemsDesigner -> GameplayDeveloper -> ProjectReviewer

Runs ProjectDebugger only when project validation finds structural, syntax,
or pyray API issues.

Workspace layout (rooted at WORKSPACE_DIR, default: agent_workspace/):
    agent_workspace/
    ├── agents/
    │   ├── ProjectArchitect-<uuid>/
    │   ├── SystemsDesigner-<uuid>/
    │   ├── GameplayDeveloper-<uuid>/
    │   ├── ProjectReviewer-<uuid>/
    │   └── ProjectDebugger-<uuid>/
    └── games/
        └── <slug>-<timestamp>/
            ├── src/
            ├── data/
            ├── docs/
            │   ├── gdd.md
            │   ├── architect_spec.json
            │   └── systems_plan.json
            ├── manifest.json
            └── trace.json
"""

import argparse
import ast
import datetime
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from dotenv import load_dotenv
from swarms import Agent, AgentRearrange
from swarms.utils.litellm_wrapper import LiteLLM
import pyray as _rl  # used only for dir() - no window opened

load_dotenv()

# ---------------------------------------------------------------------------
# Monkey-patch: LiteLLM.output_for_tools drops the text content when the LLM
# returns a plain message (no tool_calls) while tools are configured.  This
# makes Agent._run() receive None, wasting entire loops.  The patch falls
# back to message.content when tool_calls is absent.
# ---------------------------------------------------------------------------
_original_output_for_tools = LiteLLM.output_for_tools

def _patched_output_for_tools(self, response):
    try:
        tool_calls = response.choices[0].message.tool_calls
        if tool_calls:
            return _original_output_for_tools(self, response)
    except (IndexError, AttributeError):
        pass
    # Fallback: return text content so the agent loop keeps it.
    try:
        content = response.choices[0].message.content
        if content:
            return content
    except (IndexError, AttributeError):
        pass
    return None

LiteLLM.output_for_tools = _patched_output_for_tools

MODEL = "openrouter/google/gemini-3-flash-preview"
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", "agent_workspace")
DEFAULT_TASK = (
    "Create a modular top-down arena shooter with WASD movement, mouse aim, "
    "enemy waves, score, health, dash, and simple neon vector visuals."
)
PROFILE_SETTINGS = {
    "prototype": {
        "max_files": 8,
        "target_range": "4-8 generated files",
        "focus": (
            "One playable mode, one config file, and a compact set of systems."
        ),
    },
    "mid-size": {
        "max_files": 12,
        "target_range": "6-12 generated files",
        "focus": (
            "A slightly richer project with menus or additional gameplay systems, "
            "but still small enough for one validation pass."
        ),
    },
    "system-heavy": {
        "max_files": 16,
        "target_range": "8-16 generated files",
        "focus": (
            "A more modular project with multiple gameplay systems, while still "
            "avoiding external asset pipelines."
        ),
    },
}
EXTENSION_TO_KIND = {
    ".py": "python",
    ".json": "json",
    ".md": "markdown",
}
GENERATED_ARTIFACTS = (
    "src",
    "data",
    "docs",
    "README.md",
    "manifest.json",
    "trace.json",
)
PROJECT_FLOW = (
    "ProjectArchitect -> SystemsDesigner -> GameplayDeveloper -> ProjectReviewer"
)
PROJECT_MANIFEST_FENCED_RE = re.compile(
    r"PROJECT_MANIFEST_JSON\s*```json\s*(?P<json>.*?)```\s*END_PROJECT_MANIFEST_JSON",
    re.IGNORECASE | re.DOTALL,
)
PROJECT_MANIFEST_BARE_RE = re.compile(
    r"PROJECT_MANIFEST_JSON\s*(?P<json>\{.*?\})\s*END_PROJECT_MANIFEST_JSON",
    re.IGNORECASE | re.DOTALL,
)
FILE_BLOCK_RE = re.compile(
    r"FILE:\s*(?P<path>[^\n]+?)\s*\n```(?P<lang>[^\n`]*)\n(?P<content>.*?)\n```\s*END_FILE",
    re.DOTALL,
)
_PYRAY_ATTRS = set(dir(_rl))
GDD_SECTION_TITLES = {
    "design_pillars": "Design Pillars",
    "player_fantasy": "Player Fantasy",
    "target_session": "Target Session",
    "core_loop": "Core Loop",
    "moment_to_moment": "Moment To Moment",
    "controls": "Controls",
    "player_kit": "Player Kit",
    "game_objects": "Game Objects",
    "systems": "Systems",
    "progression": "Progression",
    "difficulty_curve": "Difficulty Curve",
    "ui": "UI And HUD",
    "visual_style": "Visual Style",
    "technical_notes": "Technical Notes",
    "edge_cases": "Edge Cases",
    "win_lose": "Win And Lose",
}
GDD_SECTION_ORDER = [
    "design_pillars",
    "player_fantasy",
    "target_session",
    "core_loop",
    "moment_to_moment",
    "controls",
    "player_kit",
    "game_objects",
    "systems",
    "progression",
    "difficulty_curve",
    "ui",
    "visual_style",
    "technical_notes",
    "edge_cases",
    "win_lose",
]
TOOL_TEXT_EXTENSIONS = {".py", ".json", ".md", ".txt"}
_ACTIVE_PROJECT_DEBUG_CONTEXT: dict[str, Any] = {
    "root": None,
    "profile": None,
    "project": None,
    "errors": [],
    "mutations": [],
}


def make_project_slug(task: str) -> str:
    """Turn the task prompt into a filesystem-safe short slug."""
    words = re.sub(r"[^a-zA-Z0-9 ]", "", task.lower()).split()
    return "-".join(words[:4]) or "project"


def make_project_dir(slug: str) -> str:
    """Create a timestamped output directory for a generated project."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    project_dir = os.path.join(WORKSPACE_DIR, "games", f"{slug}-{timestamp}")
    os.makedirs(project_dir, exist_ok=True)
    return project_dir


def clean_workspace_dir() -> None:
    """Remove the generated workspace tree for a clean run."""
    if os.path.isdir(WORKSPACE_DIR):
        for name in os.listdir(WORKSPACE_DIR):
            path = os.path.join(WORKSPACE_DIR, name)
            try:
                if os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            except PermissionError:
                if os.path.basename(path).lower() == "error.txt":
                    try:
                        with open(path, "w", encoding="utf-8") as handle:
                            handle.write("")
                    except OSError:
                        pass
                    continue
                raise
    os.makedirs(WORKSPACE_DIR, exist_ok=True)


def get_final_agent_output(agent: Agent, fallback: str = "") -> str:
    """Get the final agent message from short memory using swarms' API."""
    if hasattr(agent, "short_memory") and agent.short_memory is not None:
        getter = getattr(agent.short_memory, "get_final_message_content", None)
        if callable(getter):
            content = getter()
            if isinstance(content, str) and content.strip():
                return content.strip()

    return fallback.strip()


def get_agent_message_contents(
    agent: Agent, role: str | None = None
) -> list[str]:
    """Return non-empty string contents from an agent's short-memory history."""
    if not hasattr(agent, "short_memory") or agent.short_memory is None:
        return []

    history = getattr(agent.short_memory, "conversation_history", [])
    contents: list[str] = []
    for message in history:
        if role is not None and message.get("role") != role:
            continue

        content = message.get("content")
        if isinstance(content, str) and content.strip():
            contents.append(content.strip())

    return contents


def enable_trace_metadata(agent: Agent) -> None:
    """Ensure runtime agent messages include timestamps and message IDs."""
    if hasattr(agent, "short_memory") and agent.short_memory is not None:
        agent.short_memory.time_enabled = True
        agent.short_memory.message_id_on = True


def get_conversation_trace(conversation: object) -> list[dict]:
    """Return machine-readable trace data from a Swarms Conversation."""
    if conversation is None:
        return []

    to_dict = getattr(conversation, "to_dict", None)
    if callable(to_dict):
        trace = to_dict()
        if isinstance(trace, list):
            return trace

    history = getattr(conversation, "conversation_history", [])
    return history if isinstance(history, list) else []


def unwrap_string_literal(text: str) -> str:
    """Decode string-literal wrappers some model outputs add around payloads."""
    text = (text or "").strip()
    if len(text) < 2:
        return text

    if text[0] == text[-1] and text[0] in ('"', "'"):
        try:
            decoded = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            return text

        if isinstance(decoded, str):
            return decoded.strip()

    return text


def collect_json_candidate_snippets(text: str) -> list[str]:
    """Collect plausible JSON object snippets from an agent response."""
    payload = unwrap_string_literal(text)
    candidates: list[str] = []

    fenced_blocks = re.findall(
        r"```json\s*(.*?)```",
        payload,
        re.IGNORECASE | re.DOTALL,
    )
    candidates.extend(block.strip() for block in reversed(fenced_blocks))
    candidates.append(payload)

    snippets: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        local_snippets = [candidate]
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end != -1 and end > start:
            local_snippets.append(candidate[start : end + 1])

        for snippet in local_snippets:
            normalized = snippet.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            snippets.append(normalized)

    return snippets


def try_extract_json_payload(text: str) -> dict[str, Any] | None:
    """Best-effort JSON object extraction without raising on failure."""
    for snippet in collect_json_candidate_snippets(text):
        try:
            data = json.loads(snippet)
        except json.JSONDecodeError:
            continue

        if isinstance(data, dict):
            return data

    return None


def repair_json_payload(
    text: str,
    label: str,
    repair_agent: Agent,
) -> str:
    """Ask a small repair agent to fix malformed JSON-only output."""
    payload = unwrap_string_literal(text)
    repair_task = f"""Repair malformed JSON from {label}.

Rules:
- Preserve the original data and structure as closely as possible.
- Fix JSON syntax only.
- Use double quotes for every key and every string value.
- Do not add commentary, markdown prose, comments, or trailing commas.
- Return ONLY one valid JSON object wrapped in a ```json``` block.

Malformed output:
```text
{payload}
```"""
    result = repair_agent.run(repair_task)
    return get_final_agent_output(repair_agent, str(result))


def extract_json_payload(
    text: str,
    label: str,
    repair_agent: Agent | None = None,
) -> dict[str, Any]:
    """Extract a JSON object from agent output, with optional repair fallback."""
    data = try_extract_json_payload(text)
    if data is not None:
        return data

    if repair_agent is not None:
        repaired_text = repair_json_payload(text, label, repair_agent)
        data = try_extract_json_payload(repaired_text)
        if data is not None:
            return data

    raise ValueError(f"{label} did not return valid JSON.")


def normalize_relative_path(path: str) -> str:
    """Normalize a generated project file path and reject unsafe paths."""
    cleaned = (path or "").strip().replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]

    if not cleaned:
        raise ValueError("Path cannot be empty.")
    if cleaned.startswith("/") or re.match(r"^[a-zA-Z]:", cleaned):
        raise ValueError("Path must be relative to the project root.")
    if cleaned.endswith("/"):
        raise ValueError("Path must point to a file, not a directory.")

    parts = cleaned.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("Path cannot contain '.', '..', or empty segments.")

    return "/".join(parts)


def infer_kind_from_path(path: str) -> str | None:
    """Infer a generated file kind from its extension."""
    return EXTENSION_TO_KIND.get(os.path.splitext(path)[1].lower())


def ensure_trailing_newline(content: str) -> str:
    """Keep written text files newline-terminated for cleaner output."""
    content = content.replace("\r\n", "\n")
    return content if content.endswith("\n") else content + "\n"


def canonicalize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Normalize manifest ordering so no-op debugger outputs can be detected."""
    project = manifest.get("project", {})
    if not isinstance(project, dict):
        project = {}

    files: list[dict[str, Any]] = []
    for file_record in manifest.get("files", []):
        path = str(file_record.get("path") or "")
        files.append(
            {
                "path": path,
                "kind": file_record.get("kind") or infer_kind_from_path(path),
                "content": ensure_trailing_newline(str(file_record.get("content") or "")),
            }
        )

    files.sort(key=lambda file_record: file_record["path"])
    return {"project": dict(project), "files": files}


def manifests_differ(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Return True when two manifests differ in project metadata or file contents."""
    return canonicalize_manifest(left) != canonicalize_manifest(right)


def record_project_debug_mutation(action: str, path: str, changed: bool) -> None:
    """Track debugger file mutations so the host can reject no-op passes."""
    mutations = _ACTIVE_PROJECT_DEBUG_CONTEXT.setdefault("mutations", [])
    if isinstance(mutations, list):
        mutations.append(
            {
                "action": action,
                "path": path,
                "changed": changed,
            }
        )


def get_project_debug_mutations() -> list[dict[str, Any]]:
    """Return recorded debugger workspace mutations for the active pass."""
    mutations = _ACTIVE_PROJECT_DEBUG_CONTEXT.get("mutations", [])
    if not isinstance(mutations, list):
        return []
    return [dict(mutation) for mutation in mutations if isinstance(mutation, dict)]


def activate_project_debug_workspace(
    project_dir: str,
    profile: str,
    project: dict[str, Any],
    errors: list[str],
) -> None:
    """Activate the sandbox used by ProjectDebugger tools."""
    _ACTIVE_PROJECT_DEBUG_CONTEXT["root"] = os.path.abspath(project_dir)
    _ACTIVE_PROJECT_DEBUG_CONTEXT["profile"] = profile
    _ACTIVE_PROJECT_DEBUG_CONTEXT["project"] = dict(project)
    _ACTIVE_PROJECT_DEBUG_CONTEXT["errors"] = list(errors)
    _ACTIVE_PROJECT_DEBUG_CONTEXT["mutations"] = []


def clear_project_debug_workspace() -> None:
    """Clear any active sandbox used by ProjectDebugger tools."""
    _ACTIVE_PROJECT_DEBUG_CONTEXT["root"] = None
    _ACTIVE_PROJECT_DEBUG_CONTEXT["profile"] = None
    _ACTIVE_PROJECT_DEBUG_CONTEXT["project"] = None
    _ACTIVE_PROJECT_DEBUG_CONTEXT["errors"] = []
    _ACTIVE_PROJECT_DEBUG_CONTEXT["mutations"] = []


def get_project_debug_workspace_root() -> str:
    """Return the active debugger sandbox root."""
    root = _ACTIVE_PROJECT_DEBUG_CONTEXT.get("root")
    if not isinstance(root, str) or not root:
        raise RuntimeError("Project debugger workspace is not active.")
    return root


def resolve_project_debug_path(
    path: str, allow_root: bool = False
) -> tuple[str, str]:
    """Resolve a tool path safely against the active debugger sandbox."""
    root = get_project_debug_workspace_root()
    cleaned = (path or "").strip().replace("\\", "/")
    if allow_root and cleaned in ("", ".", "./"):
        return "", root

    normalized = normalize_relative_path(cleaned)
    absolute_path = os.path.abspath(os.path.join(root, *normalized.split("/")))
    if os.path.commonpath([root, absolute_path]) != root:
        raise ValueError("Path escapes the active debugger workspace.")

    return normalized, absolute_path


def list_workspace_files(path: str = ".") -> str:
    """List files inside the active ProjectDebugger workspace using relative paths."""
    try:
        _, absolute_path = resolve_project_debug_path(path, allow_root=True)
        root = get_project_debug_workspace_root()
        if os.path.isfile(absolute_path):
            return os.path.relpath(absolute_path, root).replace("\\", "/")
        if not os.path.isdir(absolute_path):
            return f"Error: path not found: {path}"

        results: list[str] = []
        for current_root, dirnames, filenames in os.walk(absolute_path):
            dirnames[:] = sorted(
                dirname for dirname in dirnames if dirname != "__pycache__"
            )
            for filename in sorted(filenames):
                absolute_file = os.path.join(current_root, filename)
                relative_file = os.path.relpath(absolute_file, root).replace("\\", "/")
                if "__pycache__" in relative_file.split("/"):
                    continue
                results.append(relative_file)
                if len(results) >= 200:
                    results.append("...")
                    return "\n".join(results)

        return "\n".join(results) if results else "(no files found)"
    except Exception as exc:
        return f"Error: {exc}"


def search_workspace_text(
    query: str,
    path: str = ".",
    max_results: int = 40,
) -> str:
    """Search text files in the active ProjectDebugger workspace."""
    try:
        if not query.strip():
            return "Error: query cannot be empty."

        _, absolute_path = resolve_project_debug_path(path, allow_root=True)
        root = get_project_debug_workspace_root()
        candidate_files: list[str] = []
        if os.path.isfile(absolute_path):
            candidate_files.append(absolute_path)
        elif os.path.isdir(absolute_path):
            for current_root, dirnames, filenames in os.walk(absolute_path):
                dirnames[:] = [
                    dirname for dirname in dirnames if dirname != "__pycache__"
                ]
                for filename in filenames:
                    extension = os.path.splitext(filename)[1].lower()
                    if extension in TOOL_TEXT_EXTENSIONS:
                        candidate_files.append(os.path.join(current_root, filename))
        else:
            return f"Error: path not found: {path}"

        matches: list[str] = []
        lowered_query = query.lower()
        for candidate_file in sorted(candidate_files):
            try:
                with open(candidate_file, "r", encoding="utf-8") as handle:
                    for line_number, line in enumerate(handle, start=1):
                        if lowered_query in line.lower():
                            relative_file = os.path.relpath(candidate_file, root).replace(
                                "\\", "/"
                            )
                            matches.append(
                                f"{relative_file}:{line_number}: {line.rstrip()}"
                            )
                            if len(matches) >= max_results:
                                return "\n".join(matches)
            except UnicodeDecodeError:
                continue

        return "\n".join(matches) if matches else "(no matches found)"
    except Exception as exc:
        return f"Error: {exc}"


def read_workspace_file(
    path: str,
    start_line: int = 1,
    end_line: int = 200,
) -> str:
    """Read a text file from the active ProjectDebugger workspace."""
    try:
        relative_path, absolute_path = resolve_project_debug_path(path)
        if not os.path.isfile(absolute_path):
            return f"Error: file not found: {path}"
        if start_line < 1 or end_line < start_line:
            return "Error: invalid line range."

        with open(absolute_path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()

        snippet = []
        for line_number in range(start_line, min(end_line, len(lines)) + 1):
            snippet.append(f"{line_number}: {lines[line_number - 1].rstrip()}")

        header = f"FILE: {relative_path}"
        return header + ("\n" + "\n".join(snippet) if snippet else "\n(empty range)")
    except Exception as exc:
        return f"Error: {exc}"


def write_workspace_file(path: str, content: str) -> str:
    """Overwrite or create a text file inside the active ProjectDebugger workspace."""
    try:
        relative_path, absolute_path = resolve_project_debug_path(path)
        extension = os.path.splitext(relative_path)[1].lower()
        if extension and extension not in TOOL_TEXT_EXTENSIONS:
            return f"Error: unsupported editable file type: {relative_path}"

        previous_content = None
        if os.path.isfile(absolute_path):
            with open(absolute_path, "r", encoding="utf-8") as handle:
                previous_content = ensure_trailing_newline(handle.read())

        next_content = ensure_trailing_newline(content)
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
        with open(absolute_path, "w", encoding="utf-8") as handle:
            handle.write(next_content)

        changed = previous_content != next_content
        record_project_debug_mutation("write", relative_path, changed)
        return f"Wrote {relative_path}" if changed else f"Wrote {relative_path} (unchanged)"
    except Exception as exc:
        return f"Error: {exc}"


def replace_text_in_workspace_file(
    path: str,
    old_text: str,
    new_text: str,
) -> str:
    """Replace one exact text occurrence inside a workspace file."""
    try:
        relative_path, absolute_path = resolve_project_debug_path(path)
        if not os.path.isfile(absolute_path):
            return f"Error: file not found: {path}"

        with open(absolute_path, "r", encoding="utf-8") as handle:
            current_content = handle.read()

        occurrences = current_content.count(old_text)
        if occurrences != 1:
            return (
                f"Error: expected exactly 1 occurrence in {relative_path}, "
                f"found {occurrences}."
            )

        updated_content = current_content.replace(old_text, new_text, 1)
        with open(absolute_path, "w", encoding="utf-8") as handle:
            handle.write(ensure_trailing_newline(updated_content))

        changed = updated_content != current_content
        record_project_debug_mutation("replace", relative_path, changed)
        return (
            f"Updated {relative_path}"
            if changed
            else f"Updated {relative_path} (unchanged)"
        )
    except Exception as exc:
        return f"Error: {exc}"


def get_workspace_validation_errors() -> str:
    """Return the host validation errors for the active ProjectDebugger pass."""
    errors = _ACTIVE_PROJECT_DEBUG_CONTEXT.get("errors", [])
    return format_validation_errors(errors) if errors else "No errors found."


def workspace_file_tool(
    action: str,
    path: str = ".",
    query: str = "",
    content: str = "",
    old_text: str = "",
    new_text: str = "",
    start_line: int = 1,
    end_line: int = 200,
    max_results: int = 40,
) -> str:
    """Operate on files in the active ProjectDebugger workspace.

    Actions:
    - list: list files under path
    - search: search query across files under path
    - read: read file lines from start_line to end_line
    - write: overwrite or create file with content
    - replace: replace one exact old_text occurrence with new_text
    """
    normalized_action = (action or "").strip().lower()
    if normalized_action == "list":
        return list_workspace_files(path)
    if normalized_action == "search":
        return search_workspace_text(query=query, path=path, max_results=max_results)
    if normalized_action == "read":
        return read_workspace_file(path=path, start_line=start_line, end_line=end_line)
    if normalized_action == "write":
        return write_workspace_file(path=path, content=content)
    if normalized_action == "replace":
        return replace_text_in_workspace_file(
            path=path,
            old_text=old_text,
            new_text=new_text,
        )
    return f"Error: unsupported workspace_file_tool action: {action}"


def write_manifest_files_to_workspace(
    project_dir: str,
    manifest: dict[str, Any],
    *,
    reset_existing: bool,
) -> None:
    """Materialize manifest files into a debugger workspace."""
    if reset_existing and os.path.isdir(project_dir):
        shutil.rmtree(project_dir)
    os.makedirs(project_dir, exist_ok=True)

    for file_record in manifest.get("files", []):
        write_relative_file(project_dir, file_record["path"], file_record["content"])

    manifest_path = os.path.join(project_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, default=str)


def build_manifest_from_workspace(
    project_dir: str,
    project: dict[str, Any],
) -> dict[str, Any]:
    """Rebuild a manifest from files currently present in a debugger workspace."""
    files: list[dict[str, Any]] = []
    candidate_paths: list[str] = []

    readme_path = os.path.join(project_dir, "README.md")
    if os.path.isfile(readme_path):
        candidate_paths.append("README.md")

    for top_level in ("src", "data"):
        absolute_dir = os.path.join(project_dir, top_level)
        if not os.path.isdir(absolute_dir):
            continue
        for current_root, dirnames, filenames in os.walk(absolute_dir):
            dirnames[:] = [dirname for dirname in dirnames if dirname != "__pycache__"]
            for filename in filenames:
                relative_path = os.path.relpath(
                    os.path.join(current_root, filename), project_dir
                ).replace("\\", "/")
                candidate_paths.append(relative_path)

    for relative_path in sorted(candidate_paths):
        kind = infer_kind_from_path(relative_path)
        if kind is None:
            continue

        absolute_path = os.path.join(project_dir, *relative_path.split("/"))
        with open(absolute_path, "r", encoding="utf-8") as handle:
            files.append(
                {
                    "path": relative_path,
                    "kind": kind,
                    "content": ensure_trailing_newline(handle.read()),
                }
            )

    return {"project": dict(project), "files": files}


def run_workspace_validation() -> str:
    """Run manifest, compile, and smoke validation inside the active ProjectDebugger workspace."""
    try:
        root = get_project_debug_workspace_root()
        profile = _ACTIVE_PROJECT_DEBUG_CONTEXT.get("profile") or "prototype"
        project = _ACTIVE_PROJECT_DEBUG_CONTEXT.get("project") or {
            "title": "Untitled Project",
            "genre": "Arcade Action",
            "summary": "",
            "profile": profile,
            "entrypoint": "src/main.py",
        }
        manifest = build_manifest_from_workspace(root, project)
        manifest, structural_errors = normalize_manifest(manifest, profile)
        content_errors = (
            validate_manifest_contents(manifest) if not structural_errors else []
        )
        errors = structural_errors + content_errors
        if not errors:
            errors.extend(compile_saved_project(manifest, root))
        if not errors:
            errors.extend(smoke_run_saved_project(manifest, root))

        return "No errors found." if not errors else format_validation_errors(errors)
    except Exception as exc:
        return f"Error: {exc}"


def workspace_validation_tool(action: str = "run") -> str:
    """Inspect or validate the active ProjectDebugger workspace.

    Actions:
    - run: execute manifest, compile, and smoke validation
    - errors: show the current host-provided validation errors
    """
    normalized_action = (action or "run").strip().lower()
    if normalized_action == "run":
        return run_workspace_validation()
    if normalized_action == "errors":
        return get_workspace_validation_errors()
    return f"Error: unsupported workspace_validation_tool action: {action}"


def parse_project_manifest(text: str, label: str) -> dict[str, Any]:
    """Parse the sectioned project manifest format emitted by coding agents."""
    payload = unwrap_string_literal(text)
    project_match = PROJECT_MANIFEST_FENCED_RE.search(payload)
    if project_match is None:
        project_match = PROJECT_MANIFEST_BARE_RE.search(payload)
    if project_match is None:
        raise ValueError(
            f"{label} did not return a PROJECT_MANIFEST_JSON block."
        )

    try:
        project = json.loads(project_match.group("json"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} returned invalid project JSON: {exc}") from exc

    files: list[dict[str, Any]] = []
    for match in FILE_BLOCK_RE.finditer(payload):
        path = match.group("path").strip()
        lang = match.group("lang").strip().lower()
        content = match.group("content")
        inferred_kind = infer_kind_from_path(path)
        kind = inferred_kind
        if inferred_kind is None and lang:
            if lang in ("python", "py"):
                kind = "python"
            elif lang == "json":
                kind = "json"
            elif lang in ("markdown", "md"):
                kind = "markdown"

        files.append(
            {
                "path": path,
                "kind": kind,
                "content": ensure_trailing_newline(content),
            }
        )

    if not files:
        raise ValueError(f"{label} did not return any FILE blocks.")

    return {"project": project, "files": files}


def parse_file_blocks(text: str, label: str) -> list[dict[str, Any]]:
    """Parse FILE blocks without requiring a full project header."""
    payload = unwrap_string_literal(text)
    files: list[dict[str, Any]] = []

    for match in FILE_BLOCK_RE.finditer(payload):
        path = match.group("path").strip()
        lang = match.group("lang").strip().lower()
        content = match.group("content")
        inferred_kind = infer_kind_from_path(path)
        kind = inferred_kind
        if inferred_kind is None and lang:
            if lang in ("python", "py"):
                kind = "python"
            elif lang == "json":
                kind = "json"
            elif lang in ("markdown", "md"):
                kind = "markdown"

        files.append(
            {
                "path": path,
                "kind": kind,
                "content": ensure_trailing_newline(content),
            }
        )

    if not files:
        raise ValueError(f"{label} did not return any FILE blocks.")

    return files


def merge_manifest_files(
    manifest: dict[str, Any], file_updates: list[dict[str, Any]]
) -> dict[str, Any]:
    """Merge replacement or missing FILE blocks into an existing manifest."""
    merged = {
        "project": dict(manifest.get("project", {})),
        "files": [dict(file_record) for file_record in manifest.get("files", [])],
    }
    files_by_path = {file_record["path"]: file_record for file_record in merged["files"]}

    for update in file_updates:
        files_by_path[update["path"]] = update

    merged["files"] = list(files_by_path.values())
    return merged


def module_name_to_generated_path(
    module_name: str, manifest: dict[str, Any]
) -> str | None:
    """Resolve a local module name to one generated file path when possible."""
    normalized = module_name.strip().replace("/", ".")
    if not normalized:
        return None

    candidate_paths = [
        f"src/{normalized.replace('.', '/')}.py",
        f"src/{normalized.replace('.', '/')}/__init__.py",
    ]
    manifest_paths = {file_record["path"] for file_record in manifest.get("files", [])}

    for candidate in candidate_paths:
        if candidate in manifest_paths:
            return candidate

    return candidate_paths[0]


def collect_debug_target_paths(
    errors: list[str], manifest: dict[str, Any]
) -> list[str]:
    """Infer which files the debugger should regenerate or patch."""
    candidates: list[str] = []
    entrypoint = str(manifest.get("project", {}).get("entrypoint") or "")

    patterns = [
        re.compile(r"Manifest entrypoint '([^']+)' is missing from files\."),
        re.compile(r"Entrypoint '([^']+)' must"),
        re.compile(r"^([^:]+):"),
        re.compile(r"File '([^']+)'"),
    ]
    module_patterns = [
        re.compile(r"from '([^']+)'"),
        re.compile(r"import-from '([^']+)'"),
        re.compile(r"import '([^']+)'"),
        re.compile(r"relative import '([^']+)'"),
    ]

    for error in errors:
        for pattern in patterns:
            match = pattern.search(error)
            if match is None:
                continue

            path = match.group(1).strip()
            try:
                candidates.append(normalize_relative_path(path))
            except ValueError:
                pass

        for pattern in module_patterns:
            match = pattern.search(error)
            if match is None:
                continue

            module_path = module_name_to_generated_path(match.group(1).strip(), manifest)
            if module_path is None:
                continue

            try:
                candidates.append(normalize_relative_path(module_path))
            except ValueError:
                pass

    if entrypoint and any("Entrypoint" in error for error in errors):
        try:
            candidates.append(normalize_relative_path(entrypoint))
        except ValueError:
            pass

    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)

    return ordered


def summarize_manifest_files(manifest: dict[str, Any]) -> str:
    """Create a compact file inventory for debugger prompts."""
    lines = []
    for file_record in manifest.get("files", []):
        kind = file_record.get("kind") or infer_kind_from_path(file_record["path"])
        lines.append(f"- {file_record['path']} ({kind})")
    return "\n".join(lines) or "- None"


def serialize_manifest_for_agent(manifest: dict[str, Any]) -> str:
    """Serialize a manifest back into the sectioned format for review/debug."""
    project_json = json.dumps(manifest.get("project", {}), indent=2)
    parts = [
        "PROJECT_MANIFEST_JSON",
        "```json",
        project_json,
        "```",
        "END_PROJECT_MANIFEST_JSON",
        "",
    ]

    for file_record in manifest.get("files", []):
        kind = file_record.get("kind") or infer_kind_from_path(file_record["path"])
        language_key = kind if isinstance(kind, str) else ""
        language = {
            "python": "python",
            "json": "json",
            "markdown": "markdown",
        }.get(language_key, "text")
        parts.extend(
            [
                f"FILE: {file_record['path']}",
                f"```{language}",
                file_record["content"].rstrip("\n"),
                "```",
                "END_FILE",
                "",
            ]
        )

    return "\n".join(parts).strip() + "\n"


def module_name_from_path(path: str) -> str | None:
    """Convert src-relative file paths into importable module names."""
    if not path.startswith("src/") or not path.endswith(".py"):
        return None

    relative = path[len("src/") :]
    if relative.endswith("/__init__.py"):
        module = relative[: -len("/__init__.py")]
    else:
        module = relative[: -len(".py")]

    return module.replace("/", ".") if module else None


def module_exists(module_name: str, local_modules: set[str]) -> bool:
    """Return True if a module or package path exists in the local project."""
    if module_name in local_modules:
        return True
    return any(candidate.startswith(module_name + ".") for candidate in local_modules)


def resolve_relative_import(
    importer_module: str,
    is_package: bool,
    module: str | None,
    level: int,
) -> str | None:
    """Resolve relative imports against a source module path."""
    if not importer_module:
        return None

    package_parts = importer_module.split(".")
    if not is_package:
        package_parts = package_parts[:-1]

    if level < 1:
        base_parts = package_parts
    else:
        trim = level - 1
        if trim > len(package_parts):
            return None
        base_parts = package_parts[: len(package_parts) - trim]

    if module:
        base_parts.extend(part for part in module.split(".") if part)

    resolved = ".".join(part for part in base_parts if part)
    return resolved or None


def iter_assigned_names(target: ast.expr) -> set[str]:
    """Collect simple local names assigned by an AST target."""
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for item in target.elts:
            names.update(iter_assigned_names(item))
        return names
    return set()


def build_local_symbol_tables(
    manifest: dict[str, Any],
) -> tuple[dict[str, set[str]], dict[str, dict[str, set[str]]]]:
    """Index top-level exported names and class methods for local Python modules."""
    module_exports: dict[str, set[str]] = {}
    class_methods: dict[str, dict[str, set[str]]] = {}

    for file_record in manifest["files"]:
        if file_record["kind"] != "python":
            continue

        module_name = module_name_from_path(file_record["path"])
        if not module_name:
            continue

        try:
            tree = ast.parse(file_record["content"])
        except SyntaxError:
            continue

        exported_names: set[str] = set()
        module_classes: dict[str, set[str]] = {}

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                exported_names.add(node.name)
                module_classes[node.name] = {
                    child.name
                    for child in node.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                exported_names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    exported_names.update(iter_assigned_names(target))
            elif isinstance(node, ast.AnnAssign):
                exported_names.update(iter_assigned_names(node.target))

        module_exports[module_name] = exported_names
        class_methods[module_name] = module_classes

    return module_exports, class_methods


def infer_local_class_instantiation(
    node: ast.AST,
    imported_local_classes: dict[str, tuple[str, str]],
    local_module_aliases: dict[str, str],
    class_methods: dict[str, dict[str, set[str]]],
) -> tuple[str, str] | None:
    """Infer the local class behind a simple constructor call."""
    if not isinstance(node, ast.Call):
        return None

    if isinstance(node.func, ast.Name):
        return imported_local_classes.get(node.func.id)

    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
        module_name = local_module_aliases.get(node.func.value.id)
        class_name = node.func.attr
        if module_name and class_name in class_methods.get(module_name, {}):
            return module_name, class_name

    return None


def check_python_file_code(relative_path: str, code: str) -> list[str]:
    """Run syntax and pyray API checks against a single Python source file."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"{relative_path}: SyntaxError at line {exc.lineno}: {exc.msg}"]

    rl_names: set[str] = set()
    errors: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pyray":
                    rl_names.add(alias.asname or "pyray")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "pyray":
                for alias in node.names:
                    rl_names.add(alias.asname or alias.name)

    if not rl_names:
        return errors

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in rl_names
            and node.attr not in _PYRAY_ATTRS
        ):
            suggestions = ", ".join(
                candidate
                for candidate in _PYRAY_ATTRS
                if node.attr.replace("_", "") in candidate.replace("_", "")
            )[:120]
            errors.append(
                f"{relative_path}: line {node.lineno}: pyray has no attribute "
                f"'{node.attr}'"
                + (f". Close matches: {suggestions}" if suggestions else ".")
            )

    return errors


def normalize_manifest(
    manifest: dict[str, Any],
    profile: str,
) -> tuple[dict[str, Any], list[str]]:
    """Validate the manifest shape and normalize paths and file records."""
    errors: list[str] = []
    raw_project = manifest.get("project", {})
    raw_files = manifest.get("files", [])

    if not isinstance(raw_project, dict):
        errors.append("Manifest field 'project' must be an object.")
        raw_project = {}
    if not isinstance(raw_files, list):
        errors.append("Manifest field 'files' must be a list.")
        raw_files = []

    normalized_project = {
        "title": str(raw_project.get("title") or "Untitled Project"),
        "genre": str(raw_project.get("genre") or "Arcade Action"),
        "summary": str(raw_project.get("summary") or ""),
        "profile": profile,
        "entrypoint": "src/main.py",
    }

    entrypoint_candidate = str(raw_project.get("entrypoint") or "src/main.py")
    try:
        normalized_project["entrypoint"] = normalize_relative_path(entrypoint_candidate)
    except ValueError as exc:
        errors.append(f"Manifest entrypoint is invalid: {exc}")

    if normalized_project["entrypoint"] != "src/main.py":
        errors.append("Entrypoint must be src/main.py in v1.")

    max_files = PROFILE_SETTINGS[profile]["max_files"]
    if not raw_files:
        errors.append("Manifest must include at least one generated file.")
    if len(raw_files) > max_files:
        errors.append(
            f"Manifest has {len(raw_files)} files but profile '{profile}' allows at most {max_files}."
        )

    normalized_files: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    for index, file_record in enumerate(raw_files, start=1):
        if not isinstance(file_record, dict):
            errors.append(f"File record #{index} must be an object.")
            continue

        raw_path = file_record.get("path")
        if not isinstance(raw_path, str):
            errors.append(f"File record #{index} is missing a string 'path'.")
            continue

        try:
            path = normalize_relative_path(raw_path)
        except ValueError as exc:
            errors.append(f"File '{raw_path}' is invalid: {exc}")
            continue

        kind = infer_kind_from_path(path)
        if kind is None:
            errors.append(
                f"File '{path}' must end in one of: {', '.join(sorted(EXTENSION_TO_KIND))}."
            )
            continue

        content = file_record.get("content")
        if not isinstance(content, str) or not content.strip():
            errors.append(f"File '{path}' must include non-empty text content.")
            continue

        if path in seen_paths:
            errors.append(f"Manifest contains duplicate path '{path}'.")
            continue

        seen_paths.add(path)

        if kind == "python" and not path.startswith("src/"):
            errors.append(f"Python file '{path}' must live under src/.")
        elif kind == "json" and not path.startswith("data/"):
            errors.append(f"JSON file '{path}' must live under data/.")
        elif kind == "markdown" and path != "README.md" and not path.startswith("docs/"):
            errors.append(
                f"Markdown file '{path}' must be README.md or live under docs/."
            )

        normalized_files.append(
            {
                "path": path,
                "kind": kind,
                "content": ensure_trailing_newline(content),
            }
        )

    normalized_manifest = {
        "project": normalized_project,
        "files": normalized_files,
    }

    path_set = {file_record["path"] for file_record in normalized_files}
    if normalized_project["entrypoint"] not in path_set:
        errors.append(
            f"Manifest entrypoint '{normalized_project['entrypoint']}' is missing from files."
        )

    python_count = sum(1 for file_record in normalized_files if file_record["kind"] == "python")
    if python_count < 2:
        errors.append("Complex projects must generate at least two Python files.")

    return normalized_manifest, errors


def validate_local_imports(manifest: dict[str, Any]) -> list[str]:
    """Validate that local imports refer to generated project modules."""
    errors: list[str] = []
    python_files = [
        file_record for file_record in manifest["files"] if file_record["kind"] == "python"
    ]
    modules_by_path = {
        file_record["path"]: module_name_from_path(file_record["path"])
        for file_record in python_files
    }
    local_modules = {module for module in modules_by_path.values() if module}
    local_roots = {module.split(".")[0] for module in local_modules}
    module_exports, class_methods = build_local_symbol_tables(manifest)

    for file_record in python_files:
        relative_path = file_record["path"]
        importer_module = modules_by_path.get(relative_path)
        is_package = relative_path.endswith("/__init__.py")
        imported_local_classes: dict[str, tuple[str, str]] = {}
        local_module_aliases: dict[str, str] = {}
        variable_types: dict[str, tuple[str, str]] = {}

        try:
            tree = ast.parse(file_record["content"])
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name
                    if imported == "src" or imported.startswith("src."):
                        errors.append(
                            f"{relative_path}: import '{imported}' should not use the 'src.' prefix. "
                            "Import local modules directly or through packages inside src/."
                        )
                        continue
                    imported_root = imported.split(".")[0]
                    if imported_root in local_roots and not module_exists(imported, local_modules):
                        errors.append(
                            f"{relative_path}: import '{imported}' does not match any generated module."
                        )
                        continue
                    if imported in local_modules:
                        local_module_aliases[alias.asname or imported.split(".")[-1]] = imported
            elif isinstance(node, ast.ImportFrom):
                imported = None
                if node.level > 0:
                    resolved = resolve_relative_import(
                        importer_module or "",
                        is_package,
                        node.module,
                        node.level,
                    )
                    if resolved is None:
                        errors.append(
                            f"{relative_path}: relative import at line {node.lineno} could not be resolved."
                        )
                        continue
                    imported = resolved
                    if not module_exists(imported, local_modules):
                        errors.append(
                            f"{relative_path}: relative import '{imported}' does not match any generated module."
                        )
                        continue
                elif node.module:
                    imported = node.module
                    if imported == "src" or imported.startswith("src."):
                        errors.append(
                            f"{relative_path}: import-from '{imported}' should not use the 'src.' prefix. "
                            "Import local modules directly or through packages inside src/."
                        )
                        continue
                    imported_root = imported.split(".")[0]
                    if imported_root in local_roots and not module_exists(imported, local_modules):
                        errors.append(
                            f"{relative_path}: import-from '{imported}' does not match any generated module."
                        )
                        continue

                if imported not in local_modules:
                    continue

                for alias in node.names:
                    if alias.name == "*":
                        errors.append(
                            f"{relative_path}: star import from local module '{imported}' is not allowed."
                        )
                        continue

                    exported_names = module_exports.get(imported, set())
                    if alias.name not in exported_names:
                        errors.append(
                            f"{relative_path}: import-from '{imported}' requests missing symbol '{alias.name}'."
                        )
                        continue

                    if alias.name in class_methods.get(imported, {}):
                        imported_local_classes[alias.asname or alias.name] = (
                            imported,
                            alias.name,
                        )

        for node in ast.walk(tree):
            inferred_type = None
            target_names: set[str] = set()

            if isinstance(node, ast.Assign):
                inferred_type = infer_local_class_instantiation(
                    node.value,
                    imported_local_classes,
                    local_module_aliases,
                    class_methods,
                )
                for target in node.targets:
                    target_names.update(iter_assigned_names(target))
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                inferred_type = infer_local_class_instantiation(
                    node.value,
                    imported_local_classes,
                    local_module_aliases,
                    class_methods,
                )
                target_names.update(iter_assigned_names(node.target))

            if inferred_type is not None:
                for target_name in target_names:
                    variable_types[target_name] = inferred_type

            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
            ):
                variable_name = node.func.value.id
                variable_type = variable_types.get(variable_name)
                if variable_type is None:
                    continue

                module_name, class_name = variable_type
                available_methods = class_methods.get(module_name, {}).get(class_name, set())
                if available_methods and node.func.attr not in available_methods:
                    errors.append(
                        f"{relative_path}: '{class_name}' from '{module_name}' has no method '{node.func.attr}'."
                    )

    return errors


def validate_manifest_contents(manifest: dict[str, Any]) -> list[str]:
    """Run pre-save validation against generated file contents."""
    errors: list[str] = []
    python_files = [
        file_record for file_record in manifest["files"] if file_record["kind"] == "python"
    ]
    any_pyray_import = False

    for file_record in python_files:
        code = file_record["content"]
        if "import pyray as rl" in code or "from pyray" in code:
            any_pyray_import = True
        errors.extend(check_python_file_code(file_record["path"], code))

    for file_record in manifest["files"]:
        if file_record["kind"] == "json":
            try:
                json.loads(file_record["content"])
            except json.JSONDecodeError as exc:
                errors.append(
                    f"{file_record['path']}: invalid JSON at line {exc.lineno}: {exc.msg}"
                )

    if any(file_record["kind"] == "json" for file_record in manifest["files"]):
        has_file_relative_path_handling = any(
            marker in file_record["content"]
            for file_record in python_files
            for marker in (
                "__file__",
                "Path(__file__)",
                "os.path.dirname(__file__)",
            )
        )
        if not has_file_relative_path_handling:
            errors.append(
                "Project uses data files but no Python file resolves paths from __file__. "
                "Load JSON through file-relative paths so src/main.py can be executed directly."
            )

    if not any_pyray_import:
        errors.append("Project must import pyray in at least one generated Python file.")

    entrypoint = manifest["project"]["entrypoint"]
    entrypoint_content = next(
        (
            file_record["content"]
            for file_record in manifest["files"]
            if file_record["path"] == entrypoint
        ),
        "",
    )
    if '__name__ == "__main__"' not in entrypoint_content and "__name__ == '__main__'" not in entrypoint_content:
        errors.append(f"Entrypoint '{entrypoint}' must guard execution with if __name__ == '__main__':")

    errors.extend(validate_local_imports(manifest))
    return errors


def compile_saved_project(manifest: dict[str, Any], project_dir: str) -> list[str]:
    """Compile every generated Python file after writing it to disk."""
    errors: list[str] = []
    for file_record in manifest["files"]:
        if file_record["kind"] != "python":
            continue

        absolute_path = os.path.join(project_dir, *file_record["path"].split("/"))
        try:
            py_compile.compile(absolute_path, doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"{file_record['path']}: compile error: {exc.msg}")

    return errors


def smoke_run_saved_project(manifest: dict[str, Any], project_dir: str) -> list[str]:
    """Run a tiny non-visual smoke test against the generated entrypoint."""
    entrypoint = manifest["project"].get("entrypoint", "src/main.py")
    module_name = module_name_from_path(entrypoint)
    if not module_name:
        return [f"{entrypoint}: smoke test could not resolve the entrypoint module."]

    smoke_script = f"""
import importlib
import os
import sys
import types

sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

import pyray as _real_pr

frame_state = {{'count': 0, 'start_pressed': False}}

def no_op(*args, **kwargs):
    return _SafeValue()

class _SafeValue:
    \"\"\"Duck-typed return value for stubbed pyray calls.

    Supports arithmetic, iteration, attribute access, and comparison so
    that generated code doing e.g. `pr.get_screen_width() / 2` or
    `pos.x + 1` won't crash with a TypeError.
    \"\"\"
    def __repr__(self): return '0'
    def __str__(self): return '0'
    def __bool__(self): return False
    def __int__(self): return 0
    def __float__(self): return 0.0
    def __index__(self): return 0
    # Arithmetic
    def __add__(self, o): return _coerce(o)
    def __radd__(self, o): return _coerce(o)
    def __sub__(self, o): return _coerce(o)
    def __rsub__(self, o): return _coerce(o)
    def __mul__(self, o): return _coerce(o)
    def __rmul__(self, o): return _coerce(o)
    def __truediv__(self, o): return 0.0
    def __rtruediv__(self, o): return 0.0
    def __floordiv__(self, o): return 0
    def __rfloordiv__(self, o): return 0
    def __mod__(self, o): return 0
    def __rmod__(self, o): return 0
    def __pow__(self, o): return 0
    def __neg__(self): return 0
    def __pos__(self): return 0
    def __abs__(self): return 0
    # Comparison
    def __eq__(self, o): return o == 0 or o is None
    def __ne__(self, o): return not self.__eq__(o)
    def __lt__(self, o): return True
    def __le__(self, o): return True
    def __gt__(self, o): return False
    def __ge__(self, o): return o == 0 or isinstance(o, _SafeValue)
    # Attribute access (for Vector2-like .x / .y)
    def __getattr__(self, name): return _SafeValue()
    # Iteration / unpacking
    def __iter__(self): return iter([])
    def __len__(self): return 0
    # Callable (in case returned value is called)
    def __call__(self, *a, **kw): return _SafeValue()
    # Hashing
    def __hash__(self): return 0

def _coerce(o):
    if isinstance(o, float):
        return 0.0
    if isinstance(o, int):
        return 0
    return _SafeValue()

def window_should_close():
    frame_state['count'] += 1
    return frame_state['count'] > 2

def is_key_pressed(key):
    start_keys = (getattr(_real_pr, 'KEY_SPACE', None), getattr(_real_pr, 'KEY_ENTER', None))
    if not frame_state['start_pressed'] and key in start_keys:
        frame_state['start_pressed'] = True
        return True
    return False

# Build a proxy module that intercepts ALL pyray attribute access.
# Any callable not explicitly overridden becomes a safe no-op, preventing
# ACCESS_VIOLATION crashes from unpatched C-level raylib calls.

_OVERRIDES = {{
    'window_should_close': window_should_close,
    'is_key_pressed': is_key_pressed,
    'is_key_down': lambda *a, **kw: False,
    'is_mouse_button_down': lambda *a, **kw: False,
    'is_mouse_button_pressed': lambda *a, **kw: False,
    'get_mouse_position': lambda: _real_pr.Vector2(0, 0),
    'get_frame_time': lambda: 1.0 / 60,
    'get_screen_width': lambda: 1280,
    'get_screen_height': lambda: 720,
    'get_time': lambda: 0.0,
    'get_random_value': lambda lo, hi: lo,
    'check_collision_recs': lambda *a, **kw: False,
    'check_collision_circles': lambda *a, **kw: False,
    'check_collision_point_rec': lambda *a, **kw: False,
    'color_alpha': lambda c, a: c,
    'color_brightness': lambda c, f: c,
    'fade': lambda c, a: c,
}}

class _PyrayProxy(types.ModuleType):
    def __getattr__(self, name):
        if name in _OVERRIDES:
            return _OVERRIDES[name]
        real = getattr(_real_pr, name, None)
        if real is None:
            return no_op
        if callable(real) and not isinstance(real, type):
            return no_op
        return real

pr = _PyrayProxy('pyray')
# Patch sys.modules so that 'import pyray' in submodules also gets the proxy
sys.modules['pyray'] = pr

module = importlib.import_module({module_name!r})
main_fn = getattr(module, 'main', None)
if not callable(main_fn):
    raise AttributeError('Entrypoint module does not define callable main()')

main_fn()
"""

    result = subprocess.run(
        [sys.executable, "-c", smoke_script],
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode == 0:
        return []

    lines = [
        line.strip()
        for line in (result.stderr + "\n" + result.stdout).splitlines()
        if line.strip() and "RAYLIB STATIC" not in line
    ]
    detail = lines[-1] if lines else f"process exited with code {result.returncode}"
    return [f"{entrypoint}: smoke test failed: {detail}"]


def format_validation_errors(errors: list[str]) -> str:
    """Convert validation errors into a stable bullet list for agent prompts."""
    return "\n".join(f"- {error}" for error in errors)


def render_markdown_value(value: Any, indent: int = 0) -> str:
    """Render structured values into readable markdown sections."""
    prefix = "  " * indent

    if isinstance(value, list):
        if not value:
            return f"{prefix}- None"

        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(render_markdown_value(item, indent + 1).splitlines())
            else:
                lines.append(f"{prefix}- {item}")
        return "\n".join(lines)

    if isinstance(value, dict):
        if not value:
            return f"{prefix}- None"

        lines = []
        for key, nested in value.items():
            label = str(key).replace("_", " ").title()
            if isinstance(nested, (dict, list)):
                lines.append(f"{prefix}- {label}:")
                lines.extend(render_markdown_value(nested, indent + 1).splitlines())
            else:
                lines.append(f"{prefix}- {label}: {nested}")
        return "\n".join(lines) or "- None"

    text = str(value or "None")
    return text if indent == 0 else f"{prefix}- {text}"


def build_gdd_markdown(spec: dict[str, Any]) -> str:
    """Create a readable GDD markdown file from the architect spec."""
    project = spec.get("project", {}) if isinstance(spec, dict) else {}
    gdd = spec.get("gdd", {}) if isinstance(spec, dict) else {}
    files = spec.get("files", []) if isinstance(spec, dict) else []
    data_files = spec.get("data_files", []) if isinstance(spec, dict) else []
    resolution = project.get("resolution", {}) if isinstance(project, dict) else {}

    if isinstance(resolution, dict) and resolution.get("width") and resolution.get("height"):
        resolution_text = f"{resolution['width']}x{resolution['height']}"
    else:
        resolution_text = "Unknown"

    lines = [
        f"# {project.get('title', 'Untitled Project')}",
        "",
        f"- Genre: {project.get('genre', 'Unknown')}",
        f"- Profile: {project.get('profile', 'prototype')}",
        f"- Entrypoint: {project.get('entrypoint', 'src/main.py')}",
        f"- Resolution: {resolution_text}",
        f"- Summary: {project.get('summary', '')}",
        "",
    ]

    rendered_sections: set[str] = set()
    for key in GDD_SECTION_ORDER:
        value = gdd.get(key)
        if value in (None, "", [], {}):
            continue

        rendered_sections.add(key)
        lines.extend(
            [
                f"## {GDD_SECTION_TITLES[key]}",
                render_markdown_value(value),
                "",
            ]
        )

    for key, value in gdd.items():
        if key in rendered_sections or value in (None, "", [], {}):
            continue

        lines.extend(
            [
                f"## {str(key).replace('_', ' ').title()}",
                render_markdown_value(value),
                "",
            ]
        )

    lines.extend(
        [
            "## Planned Source Files",
            render_markdown_value(files),
            "",
            "## Planned Data Files",
            render_markdown_value(data_files),
            "",
        ]
    )

    return "\n".join(lines)


def summarize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Keep trace artifacts compact by summarizing the final file manifest."""
    return {
        "project": manifest.get("project", {}),
        "files": [
            {"path": file_record["path"], "kind": file_record["kind"]}
            for file_record in manifest.get("files", [])
        ],
    }


def build_trace(
    task: str,
    profile: str,
    final_agent_name: str,
    validation_result: str,
    team_conversation: object,
    agents: dict[str, Agent],
    architect_spec: dict[str, Any],
    systems_plan: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Build the structured trace output for complex project generation."""
    return {
        "generated_at": datetime.datetime.now().isoformat(),
        "task": task,
        "profile": profile,
        "flow": PROJECT_FLOW,
        "final_agent": final_agent_name,
        "final_validation": validation_result,
        "artifacts": {
            "architect_spec": architect_spec,
            "systems_plan": systems_plan,
            "manifest_summary": summarize_manifest(manifest),
        },
        "team_trace": get_conversation_trace(team_conversation),
        "agent_traces": {
            name: get_conversation_trace(getattr(agent, "short_memory", None))
            for name, agent in agents.items()
        },
    }


def save_trace(trace_data: dict[str, Any], project_dir: str) -> str:
    """Save structured trace output next to the generated project."""
    trace_path = os.path.join(project_dir, "trace.json")
    with open(trace_path, "w", encoding="utf-8") as handle:
        json.dump(trace_data, handle, indent=2, default=str)
    return trace_path


def reset_project_artifacts(project_dir: str) -> None:
    """Remove previously written project artifacts inside one run directory."""
    for name in GENERATED_ARTIFACTS:
        path = os.path.join(project_dir, name)
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.remove(path)


def write_relative_file(project_dir: str, relative_path: str, content: str) -> str:
    """Write a generated file relative to a project directory."""
    absolute_path = os.path.join(project_dir, *relative_path.split("/"))
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
    with open(absolute_path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return absolute_path


def save_project_outputs(
    manifest: dict[str, Any],
    architect_spec: dict[str, Any],
    systems_plan: dict[str, Any],
    project_dir: str,
) -> dict[str, str]:
    """Write the generated project files, docs, and manifest to disk."""
    reset_project_artifacts(project_dir)

    for file_record in manifest["files"]:
        write_relative_file(project_dir, file_record["path"], file_record["content"])

    docs_dir = os.path.join(project_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)

    gdd_path = os.path.join(docs_dir, "gdd.md")
    with open(gdd_path, "w", encoding="utf-8") as handle:
        handle.write(build_gdd_markdown(architect_spec))

    architect_path = os.path.join(docs_dir, "architect_spec.json")
    with open(architect_path, "w", encoding="utf-8") as handle:
        json.dump(architect_spec, handle, indent=2, default=str)

    systems_path = os.path.join(docs_dir, "systems_plan.json")
    with open(systems_path, "w", encoding="utf-8") as handle:
        json.dump(systems_plan, handle, indent=2, default=str)

    manifest_path = os.path.join(project_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, default=str)

    entrypoint_path = os.path.join(
        project_dir,
        *manifest["project"]["entrypoint"].split("/"),
    )

    return {
        "entrypoint": entrypoint_path,
        "manifest": manifest_path,
        "gdd": gdd_path,
        "architect": architect_path,
        "systems": systems_path,
    }


def build_team_task(task: str, profile: str) -> str:
    """Combine user request and profile settings into one shared swarm task."""
    settings = PROFILE_SETTINGS[profile]
    return f"""Build a runnable modular 2D pyray project.

Requested profile: {profile}
Profile target: {settings['target_range']}
Profile focus: {settings['focus']}
Hard cap: {settings['max_files']} generated files from the coding manifest

Project rules:
- Use only built-in Python and pyray.
- Do not rely on external image, audio, or font assets.
- Keep Python files under src/ and JSON files under data/.
- Use src/main.py as the entrypoint.
- Keep exported class, function, and constant names stable across files.
- Keep the project playable and coherent in one pass.
- Produce an implementation-ready GDD with concrete mechanics, tuning, UI, and edge cases.

User request:
{task}
"""


def build_systems_task(
    task: str,
    profile: str,
    architect_spec: dict[str, Any],
) -> str:
    """Build the SystemsDesigner input from a validated architect spec."""
    return f"""Create machine-readable module contracts for this modular pyray project.

Original task:
{task}

Profile:
{profile}

Validated architect spec:
```json
{json.dumps(architect_spec, indent=2)}
```
"""


def build_developer_task(
    task: str,
    profile: str,
    architect_spec: dict[str, Any],
    systems_plan: dict[str, Any],
) -> str:
    """Build the GameplayDeveloper input from validated planning artifacts."""
    return f"""Implement this modular pyray project as a complete project manifest.

Original task:
{task}

Profile:
{profile}

Validated architect spec:
```json
{json.dumps(architect_spec, indent=2)}
```

Validated systems plan:
```json
{json.dumps(systems_plan, indent=2)}
```
"""


def build_reviewer_task(
    task: str,
    profile: str,
    architect_spec: dict[str, Any],
    systems_plan: dict[str, Any],
    manifest: dict[str, Any],
) -> str:
    """Build the ProjectReviewer input from validated upstream artifacts."""
    return f"""Review and correct this modular pyray project manifest.

Original task:
{task}

Profile:
{profile}

Validated architect spec:
```json
{json.dumps(architect_spec, indent=2)}
```

Validated systems plan:
```json
{json.dumps(systems_plan, indent=2)}
```

Current manifest:
{serialize_manifest_for_agent(manifest)}
"""


def run_json_stage(
    agent: Agent,
    task: str,
    label: str,
    repair_agent: Agent,
) -> tuple[dict[str, Any], str]:
    """Run one structured planning stage and return validated JSON plus raw output."""
    result = agent.run(task)
    raw_output = get_final_agent_output(agent, str(result))
    parsed_output = extract_json_payload(
        raw_output,
        label,
        repair_agent=repair_agent,
    )
    return parsed_output, raw_output


def run_manifest_stage(
    agent: Agent,
    task: str,
    label: str,
) -> tuple[dict[str, Any], str]:
    """Run one manifest-producing stage and parse the returned project manifest."""
    result = agent.run(task)
    raw_output = get_final_agent_output(agent, str(result))
    parsed_manifest = parse_project_manifest(raw_output, label)
    return parsed_manifest, raw_output


def build_fallback_systems_plan(raw_output: str) -> dict[str, Any]:
    """Keep generation moving even if systems metadata is not strict JSON."""
    return {
        "raw_output": (raw_output or "").strip(),
        "parse_status": "fallback_raw_text",
    }


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the modular project swarm."""
    parser = argparse.ArgumentParser(
        description="Generate modular pyray game projects with a Swarms team.",
    )
    parser.add_argument(
        "task",
        nargs="?",
        help="High-level game request. If omitted, stdin or prompt input is used.",
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILE_SETTINGS),
        default="prototype",
        help="Complexity profile for the generated project.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete the configured WORKSPACE_DIR before generation.",
    )
    return parser.parse_args()


def resolve_task(args: argparse.Namespace) -> str:
    """Resolve the task from argv, stdin, or interactive input."""
    if isinstance(args.task, str) and args.task.strip():
        return args.task.strip()

    if not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        if piped:
            return piped

    task = input("\nWhat modular game project do you want to create?\n> ").strip()
    if task:
        return task

    print(f"\n(Using default task: {DEFAULT_TASK})")
    return DEFAULT_TASK


def debug_manifest(
    task: str,
    profile: str,
    architect_spec: dict[str, Any],
    systems_plan: dict[str, Any],
    manifest: dict[str, Any],
    errors: list[str],
    debugger: Agent,
    existing_project_dir: str | None = None,
) -> dict[str, Any]:
    """Ask the debugger agent to repair a manifest based on validation errors."""
    # Reset debugger memory to avoid context bloat across successive passes.
    # Agent.run() does NOT re-inject the system prompt, so we must restore it
    # (and any rules) manually after clearing.
    if hasattr(debugger, "short_memory") and debugger.short_memory is not None:
        debugger.short_memory.clear()
        # Re-inject system prompt + rules that _initialize_new_conversation() added at init
        if getattr(debugger, "system_prompt", None):
            debugger.short_memory.add(role="System", content=debugger.system_prompt)
        if getattr(debugger, "rules", None):
            debugger.short_memory.add(
                role=getattr(debugger, "user_name", "User"),
                content=debugger.rules,
            )

    target_paths = collect_debug_target_paths(errors, manifest)
    os.makedirs(WORKSPACE_DIR, exist_ok=True)

    workspace_dir = (
        existing_project_dir
        if existing_project_dir is not None
        else tempfile.mkdtemp(prefix="project-debug-", dir=WORKSPACE_DIR)
    )
    cleanup_workspace = existing_project_dir is None
    write_manifest_files_to_workspace(
        workspace_dir,
        manifest,
        reset_existing=cleanup_workspace,
    )
    activate_project_debug_workspace(
        workspace_dir,
        profile,
        manifest.get("project", {}),
        errors,
    )

    available_tools = """
Available sandboxed coding tools:
- workspace_file_tool(action='list'|'search'|'read'|'write'|'replace', ...)
- workspace_validation_tool(action='errors'|'run')

workspace_file_tool usage:
- list files: action='list', path='.'
- search code: action='search', path='src', query='Player'
- read file: action='read', path='src/main.py', start_line=1, end_line=160
- overwrite file: action='write', path='src/main.py', content='...'
- exact replacement: action='replace', path='src/main.py', old_text='...', new_text='...'

workspace_validation_tool usage:
- current host errors: action='errors'
- rerun validation: action='run'

All tool paths are relative to the active sandbox root. Do not reference files outside it.
Prefer reading the current workspace and patching targeted files with tools instead of regenerating large files from memory.
Because this pass only runs after host validation found errors, do not reply with "Passed" or "No need for debug".
You may return TOOL_EDIT_COMPLETE only after at least one successful write or replace edit.
""".strip()

    try:
        if target_paths:
            existing_targets = []
            manifest_files = {
                file_record["path"]: file_record
                for file_record in manifest.get("files", [])
            }
            for path in target_paths:
                if path in manifest_files:
                    existing_targets.extend(
                        [
                            f"FILE: {path}",
                            f"```{manifest_files[path]['kind'] or infer_kind_from_path(path) or 'text'}",
                            manifest_files[path]["content"].rstrip("\n"),
                            "```",
                            "END_FILE",
                            "",
                        ]
                    )
                else:
                    existing_targets.append(f"MISSING FILE: {path}")

            debug_task = f"""Fix specific files in this modular pyray project.

Original task:
{task}

Profile:
{profile}

Architect spec:
```json
{json.dumps(architect_spec, indent=2)}
```

Systems plan:
```json
{json.dumps(systems_plan, indent=2)}
```

Validation errors:
{format_validation_errors(errors)}

Current project file inventory:
{summarize_manifest_files(manifest)}

Sandbox workspace on disk:
{os.path.abspath(workspace_dir)}

{available_tools}

Files to create or replace (PRIORITY — write these FIRST):
{os.linesep.join(f'- {path}' for path in target_paths)}

Current contents for those files:
{os.linesep.join(existing_targets)}

IMPORTANT: Write the listed target files FIRST using workspace tools.
If a target file depends on another missing file, create the dependency and then the target file in the same pass.
Do not spend loops only reading — read what you need, then write immediately.

You may return FILE blocks using the exact format:
FILE: path/to/file.py
```python
# content
```
END_FILE

Or use workspace tools to write files directly and then return TOOL_EDIT_COMPLETE after writing at least one target file.
Do not return PROJECT_MANIFEST_JSON unless you are returning a full manifest on purpose.
Do not return explanations.
Do not return unchanged files outside the target list.
"""
        else:
            debug_task = f"""Fix this modular pyray project manifest.

Original task:
{task}

Profile:
{profile}

Architect spec:
```json
{json.dumps(architect_spec, indent=2)}
```

Systems plan:
```json
{json.dumps(systems_plan, indent=2)}
```

Validation errors:
{format_validation_errors(errors)}

Sandbox workspace on disk:
{os.path.abspath(workspace_dir)}

{available_tools}

Current manifest:
{serialize_manifest_for_agent(manifest)}

Return ONLY a changed corrected full project manifest using the exact PROJECT_MANIFEST_JSON + FILE blocks format, or edit the workspace with tools and return TOOL_EDIT_COMPLETE after at least one successful write or replace edit.
Do not answer with "Passed", "No need for debug", or any other no-op text.
"""

        result = debugger.run(debug_task)
        candidate_outputs: list[str] = []
        seen_outputs: set[str] = set()
        workspace_manifest = build_manifest_from_workspace(
            workspace_dir,
            manifest.get("project", {}),
        )
        workspace_mutations = get_project_debug_mutations()
        workspace_changed = manifests_differ(workspace_manifest, manifest)

        for candidate in [
            get_final_agent_output(debugger, str(result)),
            str(result).strip(),
            *reversed(get_agent_message_contents(debugger, debugger.agent_name)),
        ]:
            if not candidate or candidate in seen_outputs:
                continue
            seen_outputs.add(candidate)
            candidate_outputs.append(candidate)

        candidate_manifests: list[tuple[str, dict[str, Any]]] = []
        if workspace_changed and any(
            mutation.get("changed") for mutation in workspace_mutations
        ):
            candidate_manifests.append(("workspace_tools", workspace_manifest))

        for candidate in candidate_outputs:
            if target_paths:
                try:
                    file_updates = parse_file_blocks(candidate, "ProjectDebugger")
                except ValueError:
                    file_updates = []

                if file_updates:
                    merged_manifest = merge_manifest_files(manifest, file_updates)
                    if not manifests_differ(merged_manifest, manifest):
                        continue
                    candidate_manifests.append(
                        (
                            "file_blocks",
                            merged_manifest,
                        )
                    )

            try:
                parsed_manifest = parse_project_manifest(candidate, "ProjectDebugger")
            except ValueError:
                continue

            if not manifests_differ(parsed_manifest, manifest):
                continue
            candidate_manifests.append(("full_manifest", parsed_manifest))

        best_manifest: dict[str, Any] | None = None
        best_errors: list[str] | None = None
        best_source: str | None = None

        for source, candidate_manifest in candidate_manifests:
            normalized_candidate, structural_errors = normalize_manifest(
                candidate_manifest, profile
            )
            content_errors = (
                validate_manifest_contents(normalized_candidate)
                if not structural_errors
                else []
            )
            candidate_errors = structural_errors + content_errors
            manifest_paths = {
                file_record["path"]
                for file_record in normalized_candidate.get("files", [])
            }
            if target_paths and not all(
                path in manifest_paths for path in target_paths
            ):
                continue

            if best_errors is None or len(candidate_errors) < len(best_errors):
                best_manifest = normalized_candidate
                best_errors = candidate_errors
                best_source = source

            if not candidate_errors:
                return normalized_candidate

        if best_manifest is not None:
            return best_manifest

        # Agent made no concrete progress — return input manifest unchanged
        # so the outer retry loop can re-attempt or continue gracefully.
        return manifest
    finally:
        clear_project_debug_workspace()
        if cleanup_workspace:
            shutil.rmtree(workspace_dir, ignore_errors=True)


project_architect = Agent(
    agent_name="ProjectArchitect",
    agent_description="Designs modular pyray projects and emits a JSON project spec",
    system_prompt="""You are a principal game architect for small modular 2D pyray projects.

Given a game request and complexity profile, output ONLY JSON wrapped in a ```json``` block.

Depth is more important than brevity. Fill the GDD with rich details, explicit mechanics, implementation notes, and tuning guidance.
Assume downstream agents will rely on your spec directly, so reduce guesswork as much as possible.

Rules:
- Target a runnable modular pyray project with src/main.py as the entrypoint.
- No external image, audio, or font assets.
- Use simple shapes, particles, and JSON config files instead of assets.
- Keep scope inside the requested file budget.
- Only plan Python files under src/, JSON under data/, and optional markdown as README.md.
- The returned object must parse with Python's json.loads.
- Use double quotes for every key and every string value.
- Do not emit comments, bare text after a colon, or trailing commas.

Return a JSON object with keys:
- project: {title, genre, profile, summary, entrypoint, resolution}
- gdd: {
    design_pillars,
    player_fantasy,
    target_session,
    core_loop,
    moment_to_moment,
    controls,
    player_kit,
    game_objects,
    systems,
    progression,
    difficulty_curve,
    ui,
    visual_style,
    technical_notes,
    edge_cases,
    win_lose,
    tuning_values,
    content_beats
    }
- files: [{path, purpose}]
- data_files: [{path, purpose, keys}]

Rich-detail expectations for the gdd object:
- design_pillars: 3-5 short bullets.
- core_loop: a concrete loop, not a slogan.
- moment_to_moment: a vivid description of 10-30 seconds of play.
- controls: either a list of mappings or an object with state-specific inputs.
- player_kit: nested movement, offense, defense, resources, cooldowns, and failure states.
- game_objects: a list of objects with name, role, behaviour, interactions, spawn rules, and suggested tuning.
- systems: a list or object describing collisions, spawning, progression, scoring, damage, timers, and feedback.
- progression: wave structure, escalation rules, and reward structure.
- difficulty_curve: early, mid, and late game pacing with concrete escalation notes.
- ui: HUD layout, overlays, readability priorities, and state transitions.
- technical_notes and edge_cases: explicit implementation hazards and things the coder should guard against.
- tuning_values: concrete recommended defaults and ranges for speed, health, cooldowns, spawn timing, score thresholds, and similar knobs.
- content_beats: a short sequence of what the player encounters as a run unfolds.

Use concrete mechanics, entity responsibilities, UI behaviour, tuning notes, and failure cases rather than vague summaries.
Prefer nested objects and lists over long flat paragraphs when structure makes the spec clearer.

No commentary outside the JSON block.""",
    model_name=MODEL,
    max_loops=1,
    output_type="final",
    autosave=True,
    artifacts_on=True,
    artifacts_file_extension=".json",
    reasoning_prompt_on=False,
    print_on=False,
    verbose=False,
)

structured_output_repair_agent = Agent(
    agent_name="StructuredOutputRepair",
    agent_description="Repairs malformed JSON outputs from structured planning agents",
    system_prompt="""You repair malformed JSON objects emitted by other agents.

Rules:
- Preserve the original structure, keys, and values as closely as possible.
- Fix syntax only.
- Return ONLY one valid JSON object wrapped in a ```json``` block.
- Use double quotes for every key and every string value.
- Do not add explanations, comments, or markdown outside the json block.
""",
    model_name=MODEL,
    max_loops=1,
    output_type="final",
    autosave=False,
    reasoning_prompt_on=False,
    print_on=False,
    verbose=False,
)

systems_designer = Agent(
    agent_name="SystemsDesigner",
    agent_description="Turns an architect spec into machine-readable module contracts",
    system_prompt="""You are a senior gameplay systems designer for modular pyray projects.

Given the architect JSON, output ONLY JSON wrapped in a ```json``` block.

Rules:
- Preserve src/main.py as the entrypoint.
- Do not add external assets.
- Keep the module count inside the requested file budget.
- Describe contracts clearly enough for a coding agent to implement them without placeholders.
- The returned object must parse with Python's json.loads.
- Use double quotes for every key and every string value.
- Do not emit comments, bare text after a colon, or trailing commas.

Return a JSON object with keys:
- project: {title, profile, entrypoint}
- module_contracts: [{path, purpose, exports, depends_on}]
- data_contracts: [{path, purpose, keys}] where keys is a flat list of strings such as "max_score" or "colors.player_one"
- runtime_flow: [ordered runtime steps]
- implementation_order: [ordered file implementation steps]
- risk_checks: [specific mistakes to avoid]

Rules for module_contracts:
- exports must be a list of explicit symbols other files may import.
- Each export must use the shape {name, kind, methods, signature, notes}.
- For classes, methods must list the exact callable method names other modules will use.
- Do not describe APIs only in prose. Downstream agents will treat exports as the contract.

Use valid JSON only. Do not include pseudo-code placeholders like [r, g, b, a].

No commentary outside the JSON block.""",
    model_name=MODEL,
    max_loops=1,
    output_type="final",
    autosave=True,
    artifacts_on=True,
    artifacts_file_extension=".json",
    reasoning_prompt_on=False,
    print_on=False,
    verbose=False,
)

gameplay_developer = Agent(
    agent_name="GameplayDeveloper",
    agent_description="Implements modular pyray projects as a structured project manifest",
    system_prompt="""You are an expert Python game engineer specialising in modular pyray projects.

Given the architect JSON and systems JSON, output ONLY the final project manifest using this exact format:

PROJECT_MANIFEST_JSON
```json
{
  "title": "Project Title",
  "genre": "Genre",
  "summary": "Short summary",
  "profile": "prototype",
  "entrypoint": "src/main.py"
}
```
END_PROJECT_MANIFEST_JSON

FILE: src/main.py
```python
# file contents
```
END_FILE

FILE: data/config.json
```json
{ "key": "value" }
```
END_FILE

Rules:
- Build a runnable multi-file pyray project.
- Use only built-in Python and pyray.
- All custom colors must use rl.Color(r, g, b, a) or named pyray constants.
- Guard launch with if __name__ == "__main__": main().
- Match every local import and instance method call to the exact names declared in the systems module_contracts exports.
- Before finalizing, cross-check every from-local-module import against a real class, function, or constant in that file.
- Use imports that work when src/main.py is executed directly. Do not import from src.*.
- Resolve config/data files relative to __file__ or pathlib.Path(__file__).
- Keep Python files under src/ and JSON files under data/.
- Do not emit docs/gdd.md, docs/*.json, manifest.json, or trace.json.
- Do not emit explanations or markdown outside the required manifest format.
- No TODOs, placeholders, or fake assets.
""",
    model_name=MODEL,
    max_loops=1,
    output_type="final",
    autosave=True,
    reasoning_prompt_on=False,
    print_on=False,
    verbose=False,
)

project_reviewer = Agent(
    agent_name="ProjectReviewer",
    agent_description="Reviews and fixes modular pyray project manifests",
    system_prompt="""You are a senior Python reviewer for modular pyray game projects.

Given a sectioned project manifest, return the COMPLETE corrected project manifest using the exact same PROJECT_MANIFEST_JSON + FILE blocks format.

Review checklist:
1. src/main.py exists and is the entrypoint.
2. Imports line up across local modules.
3. Every local import name exists in the exporting file.
4. Instance method calls match real methods on the constructed class.
5. Shared config keys referenced by code are actually provided.
6. No missing files or empty files.
7. Python syntax is valid.
8. JSON files are valid JSON.
9. Custom colors use rl.Color(r, g, b, a) or named constants.
10. No obvious invalid pyray API names.
11. Do not use src.* imports if the entrypoint is src/main.py.
12. Resolve config/data paths relative to __file__ or pathlib.Path(__file__).
13. Avoid placeholder code and preserve playability.

Return ONLY the corrected manifest and include every generated file, not just edits.
""",
    model_name=MODEL,
    max_loops=1,
    output_type="final",
    autosave=True,
    artifacts_on=True,
    artifacts_file_extension=".txt",
    reasoning_prompt_on=False,
    print_on=False,
    verbose=False,
)

project_debugger = Agent(
    agent_name="ProjectDebugger",
    agent_description="Fixes modular pyray projects with sandboxed file and validation tools",
    system_prompt="""You are an expert Python debugger for modular pyray projects.

You will receive validation errors, an architect spec, a systems plan, and a current project manifest.
You have sandboxed tools: workspace_file_tool (list/search/read/write/replace files) and workspace_validation_tool (run full validation including compile + smoke test).

Workflow — follow this loop:
1. Read the errors and inspect the relevant source files with workspace_file_tool.
2. Write fixes using workspace_file_tool (write or replace).
3. Run workspace_validation_tool(action="run") to check your fixes.
4. If new errors appear, read them and fix. Repeat until validation passes or you run out of loops.
5. When validation passes (or you have done your best), return TOOL_EDIT_COMPLETE.

You may also return a full corrected manifest using PROJECT_MANIFEST_JSON + FILE blocks format instead of using tools.

Rules:
- Keep src/main.py as the entrypoint.
- Fix structural, syntax, import, JSON, and pyray API issues.
- Fix symbol-level drift between files, including missing imported names and missing instance methods.
- Do not use src.* imports if the project is launched through src/main.py.
- Resolve config/data paths relative to __file__ or pathlib.Path(__file__).
- Do not add explanations, summaries, or markdown outside the manifest format.
- Include every file in the corrected manifest, not only changed files.
""",
    model_name=MODEL,
    max_loops=6,
    output_type="final",
    autosave=True,
    tools=[workspace_file_tool, workspace_validation_tool],
    reasoning_prompt_on=False,
    tool_call_summary=False,
    show_tool_execution_output=False,
    print_on=False,
    verbose=False,
)

for agent in (
    project_architect,
    systems_designer,
    gameplay_developer,
    project_reviewer,
    project_debugger,
):
    enable_trace_metadata(agent)


complex_gamedev_team = AgentRearrange(
    name="ComplexGameDevTeam",
    description="Swarm AI team that designs, codes, and reviews modular pyray projects",
    agents=[
        project_architect,
        systems_designer,
        gameplay_developer,
        project_reviewer,
    ],
    flow=PROJECT_FLOW,
    max_loops=1,
    output_type="final",
    verbose=True,
    time_enabled=True,
    message_id_on=True,
)


def main() -> None:
    """Run the modular project generation workflow."""
    args = parse_args()
    if args.clean:
        clean_workspace_dir()

    task = resolve_task(args)
    profile = args.profile
    architect_task = build_team_task(task, profile)

    print("=" * 72)
    print("  Swarms AI Complex GameDev Team - Modular Pyray Projects")
    print(f"  Flow: {PROJECT_FLOW}")
    print("  Validation: stage-gated planning, manifest checks, py_compile, smoke test")
    print(f"  Profile: {profile}")
    print(f"  Workspace: {os.path.abspath(WORKSPACE_DIR)}")
    if args.clean:
        print("  Clean run: yes")
    print("=" * 72)

    print("\nStarting team...\n")
    architect_spec, architect_output = run_json_stage(
        project_architect,
        architect_task,
        "ProjectArchitect",
        structured_output_repair_agent,
    )

    systems_task = build_systems_task(task, profile, architect_spec)
    try:
        systems_plan, systems_output = run_json_stage(
            systems_designer,
            systems_task,
            "SystemsDesigner",
            structured_output_repair_agent,
        )
    except ValueError:
        raw_result = systems_designer.run(systems_task)
        systems_output = get_final_agent_output(systems_designer, str(raw_result))
        systems_plan = build_fallback_systems_plan(systems_output)

    developer_task = build_developer_task(
        task,
        profile,
        architect_spec,
        systems_plan,
    )
    manifest, developer_output = run_manifest_stage(
        gameplay_developer,
        developer_task,
        "GameplayDeveloper",
    )

    reviewer_task = build_reviewer_task(
        task,
        profile,
        architect_spec,
        systems_plan,
        manifest,
    )
    final_agent_name = "ProjectReviewer"
    try:
        manifest, reviewer_output = run_manifest_stage(
            project_reviewer,
            reviewer_task,
            "ProjectReviewer",
        )
    except ValueError:
        reviewer_output = ""
        final_agent_name = "GameplayDeveloper"

    manifest, structural_errors = normalize_manifest(manifest, profile)
    content_errors = validate_manifest_contents(manifest) if not structural_errors else []
    pre_save_errors = structural_errors + content_errors

    max_debug_attempts = 3
    for debug_attempt in range(1, max_debug_attempts + 1):
        if not pre_save_errors:
            break
        print(
            "Manifest validation found issues (attempt %d/%d). Running ProjectDebugger...\n"
            % (debug_attempt, max_debug_attempts)
        )
        try:
            manifest = debug_manifest(
                task=task,
                profile=profile,
                architect_spec=architect_spec,
                systems_plan=systems_plan,
                manifest=manifest,
                errors=pre_save_errors,
                debugger=project_debugger,
            )
        except ValueError as exc:
            print(f"  debug_manifest attempt {debug_attempt} failed: {exc}")
            continue
        manifest, structural_errors = normalize_manifest(manifest, profile)
        content_errors = validate_manifest_contents(manifest) if not structural_errors else []
        pre_save_errors = structural_errors + content_errors
        final_agent_name = "ProjectDebugger"

    if pre_save_errors:
        print(
            "Warning: project still has pre-save validation issues after debugging:\n"
            + format_validation_errors(pre_save_errors)
            + "\nContinuing to save best-effort output...\n"
        )

    slug = make_project_slug(task)
    project_dir = make_project_dir(slug)
    saved_paths = save_project_outputs(
        manifest=manifest,
        architect_spec=architect_spec,
        systems_plan=systems_plan,
        project_dir=project_dir,
    )

    post_save_errors = compile_saved_project(manifest, project_dir)
    post_save_errors.extend(smoke_run_saved_project(manifest, project_dir))
    for post_debug_attempt in range(1, max_debug_attempts + 1):
        if not post_save_errors:
            break
        print(
            "Project compilation found issues (attempt %d/%d). Running ProjectDebugger...\n"
            % (post_debug_attempt, max_debug_attempts)
        )
        try:
            manifest = debug_manifest(
                task=task,
                profile=profile,
                architect_spec=architect_spec,
                systems_plan=systems_plan,
                manifest=manifest,
                errors=post_save_errors,
                debugger=project_debugger,
                existing_project_dir=project_dir,
            )
        except ValueError as exc:
            print(f"  debug_manifest attempt {post_debug_attempt} failed: {exc}")
            continue
        manifest, structural_errors = normalize_manifest(manifest, profile)
        content_errors = validate_manifest_contents(manifest) if not structural_errors else []
        remaining_errors = structural_errors + content_errors
        if remaining_errors:
            print(
                "  Warning: debugger manifest failed structural validation:\n"
                + format_validation_errors(remaining_errors)
            )
            continue

        saved_paths = save_project_outputs(
            manifest=manifest,
            architect_spec=architect_spec,
            systems_plan=systems_plan,
            project_dir=project_dir,
        )
        post_save_errors = compile_saved_project(manifest, project_dir)
        post_save_errors.extend(smoke_run_saved_project(manifest, project_dir))
        final_agent_name = "ProjectDebugger"

    if post_save_errors:
        print(
            "Warning: project still has compilation/smoke-test issues after debugging:\n"
            + format_validation_errors(post_save_errors)
            + "\nSaving best-effort output...\n"
        )

    final_validation = "No errors found."
    trace_path = save_trace(
        build_trace(
            task=task,
            profile=profile,
            final_agent_name=final_agent_name,
            validation_result=final_validation,
            team_conversation=None,
            agents={
                "ProjectArchitect": project_architect,
                "SystemsDesigner": systems_designer,
                "GameplayDeveloper": gameplay_developer,
                "ProjectReviewer": project_reviewer,
                "ProjectDebugger": project_debugger,
            },
            architect_spec=architect_spec,
            systems_plan=systems_plan,
            manifest=manifest,
        ),
        project_dir,
    )

    print("\n" + "=" * 72)
    print(f"  Project dir : {project_dir}")
    print(f"  Entrypoint  : {saved_paths['entrypoint']}")
    print(f"  GDD file    : {saved_paths['gdd']}")
    print(f"  Manifest    : {saved_paths['manifest']}")
    print(f"  Trace file  : {trace_path}")
    print(f"  Agent states saved under: {os.path.abspath(WORKSPACE_DIR)}/agents/")
    print()
    print(f"  Run project : .\\venv\\Scripts\\python \"{saved_paths['entrypoint']}\"")
    print("=" * 72)


if __name__ == "__main__":
    main()