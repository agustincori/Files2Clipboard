"""
files2clipboard.py
──────────────────
Version:
    2.0.2
──────────────────   
Copy a directory tree – and optionally file contents – to the clipboard.
Can interactively split very large payloads into ChatGPT‑friendly chunks.

Usage example
-------------
from files2clipboard import files_to_clipboard

files_to_clipboard(
    path=".",
    subdirectories=True,
    technology_filter={
        "structured-data": True,
        "sql": True,
    },
    copy_content=True,       # include file contents
    chatgpt_split=True       # split into ≤7 000‑token chunks
)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable, List, Set

import pyperclip

# ──────────────────────────────────────────────────────────────────────────────
# Configuration constants
# ──────────────────────────────────────────────────────────────────────────────
MAX_TOKENS_PER_CHUNK = 50_000          # leave head‑room below GPT‑4‑o 8 192 limit
TOKENS_PER_CHAR_EST  = 0.25           # back‑up estimate if tiktoken missing
CHATGPT_SPLIT_GLOBAL = False          # flip once, enable everywhere

try:
    import tiktoken

    _ENCODER = tiktoken.encoding_for_model("gpt-4o-mini")

    def _count_tokens(text: str) -> int:
        """Token count via *tiktoken*."""
        return len(_ENCODER.encode(text))

except Exception:  # pragma: no cover – optional dependency
    _ENCODER = None

    def _count_tokens(text: str) -> int:     # type: ignore[override]
        """Roughly estimate tokens if *tiktoken* is unavailable."""
        return int(len(text) * TOKENS_PER_CHAR_EST)


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────
def files_to_clipboard(                   # pylint: disable=too-many-arguments
    path: str | os.PathLike[str],
    *,
    file_extension: str = ".*",
    subdirectories: bool = False,
    technology_filter: dict[str, bool] | None = None,
    copy_content: bool = True,
    chatgpt_split: bool = False,
    max_tokens: int = MAX_TOKENS_PER_CHUNK,
) -> None:
    """
    Copy directory tree – and optionally file contents – to the clipboard.

    Parameters
    ----------
    path : str | Path
        Root directory.
    file_extension : str, default ".*"
        Filter by extension; ".*" means “all”.
    subdirectories : bool, default False
        If False, only scan *path* itself; if True, walk recursively.
    technology_filter : dict[str, bool] | None
        Enable per‑tech presets (e.g. {"python": True, "sql": True}).
    copy_content : bool, default True
        If False, only copy the tree (no file bodies).
    chatgpt_split : bool, default False
        When True (or when CHATGPT_SPLIT_GLOBAL is True) and the resulting
        text exceeds *max_tokens*, split it into interactive chunks that you
        can paste one‑by‑one into ChatGPT.
    max_tokens : int, default 7 000
        Hard ceiling for each chunk.
    """
    root           = Path(path).resolve()
    exts           = _filter_by_technology(file_extension, technology_filter)
    excludes       = _filter_directories(technology_filter)
    script_name    = Path(__file__).name
    buffer         : list[str] = []

    # ------------------------------------------------------------------ tree
    try:
        tree = _generate_tree(root, excludes)
    except Exception as exc:  # pragma: no cover
        print(f"[error] Could not generate directory tree: {exc}", file=sys.stderr)
        tree = ""

    if not copy_content:
        payload = f"Directory tree of {root} (filtered):\n{tree}"
        _commit_to_clipboard(payload)

        lines = payload.count("\n") + 1          # count \n plus the last line
        print(f"✓ Directory tree copied ({lines:,} lines).")
        return

    # ------------------------------------------------------------ file bodies
    if subdirectories:
        for dir_path in _walk_dirs(root, excludes):
            _read_files_into_buffer(
                dir_path,
                buffer,
                allowed_exts=exts,
                root_label=_relative_label(dir_path, root),
                script_name=script_name,
            )
    else:
        _read_files_into_buffer(
            root,
            buffer,
            allowed_exts=exts,
            root_label="./",
            script_name=script_name,
        )

    if not buffer and not tree:
        print("[info] Nothing to copy – no matching files found.")
        return

    content = (
        f"Directory tree of {root} (filtered):\n{tree}\n\n" if subdirectories else ""
    ) + "".join(buffer)

    _split_or_copy(content, chatgpt_split or CHATGPT_SPLIT_GLOBAL, max_tokens)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers – tree generation & walking
# ──────────────────────────────────────────────────────────────────────────────
def _walk_dirs(root: Path, excludes: Set[str]) -> Iterable[Path]:
    """Yield *root* and every sub‑directory not in *excludes*."""
    for dir_path, dir_names, _ in os.walk(root):
        # prune in‑place to avoid descending into excluded dirs
        dir_names[:] = [d for d in dir_names if d not in excludes]
        yield Path(dir_path)


def _generate_tree(root: Path, excludes: Set[str]) -> str:
    """Return an ASCII tree of *root* excluding *excludes* directories."""
    lines: list[str] = []
    for current_root, dir_names, file_names in os.walk(root):
        dir_names[:] = [d for d in dir_names if d not in excludes]
        rel          = os.path.relpath(current_root, root)
        depth        = 0 if rel == "." else rel.count(os.sep) + 1
        indent       = "│   " * (depth - 1) + ("├── " if depth else "")
        base         = os.path.basename(current_root) or current_root
        lines.append(f"{indent}{base}/")
        for idx, fname in enumerate(file_names):
            connector = "└── " if idx == len(file_names) - 1 else "├── "
            lines.append(f"{indent}{connector}{fname}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers – file selection & reading
# ──────────────────────────────────────────────────────────────────────────────
def _read_files_into_buffer(
    directory: Path,
    buffer: list[str],
    *,
    allowed_exts: List[str] | str,
    root_label: str,
    script_name: str,
) -> None:
    """Append every eligible file in *directory* to *buffer*."""
    for fname in os.listdir(directory):
        if fname == script_name:
            continue                                    # 1) never copy myself
        if allowed_exts != ".*" and not any(
            fname.endswith(ext) for ext in allowed_exts
        ):
            continue                                    # 2) wrong extension
        full_path = directory / fname
        try:
            data = full_path.read_text(encoding="utf-8")
        except Exception as exc:  # pragma: no cover
            print(f"[warn] Could not read {full_path}: {exc}", file=sys.stderr)
            continue
        lines = data.count("\n") + 1
        buffer.append(f"{root_label}{fname} ({lines} lines)\n{data}\n\n")
        print(f"[read] {full_path} ({lines} lines)")


def _filter_by_technology(
    file_extension: str, technology_filter: dict[str, bool] | None
) -> List[str] | str:
    """Return list of allowed extensions given *technology_filter*."""
    tech_exts: dict[str, List[str]] = {
        "web":             [".html", ".php", ".js", ".jsx", ".css", ".scss", ".sass"],
        "react":           [".js", ".jsx", ".ts", ".tsx", ".css", ".scss",
                            ".env", "package.json", ".babelrc", ".prettierrc"],
        "python":          [".py"],
        "java":            [".java"],
        "csharp":          [".cs"],
        "ruby":            [".rb"],
        "go":              [".go"],
        "cpp":             [".cpp", ".hpp", ".h"],
        "bash":            [".sh"],
        "typescript":      [".ts", ".tsx"],
        "rust":            [".rs", ".toml", ".rlib", ".cargo"],
        "vb":              [".vb"],
        "structured-data": [".yml", ".yaml", ".json"],
        "markdown":        [".md", ".markdown"],
        "sql":             [".sql", ".psql", ".pgsql", ".ddl", ".dml"],
        "terraform":       [".tf", ".tf.json", ".tfvars", ".tfvars.json", ".hcl", ".tftpl"],
    }
    if technology_filter:
        selected: list[str] = [
            ext
            for tech, enabled in technology_filter.items()
            if enabled
            for ext in tech_exts.get(tech, [])
        ]
        if selected:
            return selected
    return [file_extension] if file_extension != ".*" else ".*"


def _filter_directories(technology_filter: dict[str, bool] | None) -> Set[str]:
    """Return a set of directory names to ignore."""
    global_ignores: Set[str] = {
        # VCS
        ".git", ".svn", ".hg", ".bzr",
        # Python
        "__pycache__", "venv", ".venv", "env", ".egg-info",
        # Node/web
        "node_modules", "bower_components", "dist", "build", ".cache",
        # Common outputs
        "target", "bin", "obj", "pkg",
        # Misc
        "log", "logs", "tmp", "coverage", ".nyc_output",
        ".idea", ".vscode", ".DS_Store", "vendor", ".bundle",
    }
    tech_specific: dict[str, Set[str]] = {
        "web":              {"public", "static"},
        "react":            {"public", "build"},
        "python":           {"dist"},
        "java":             {"build", ".gradle"},
        "csharp":           {".vs"},
        "ruby":             {"tmp"},
        "go":               {"vendor"},
        "rust":             {"target"},
        "sql":              {"migrations", "migration", "seeds", "seed",
                             "database", "db", "sql", "ddl", "dml"},
        "terraform":        {".terraform", ".terraform.lock.hcl"},                             
    }
    if technology_filter:
        for tech, enabled in technology_filter.items():
            if enabled:
                global_ignores.update(tech_specific.get(tech, set()))
    return global_ignores


# ──────────────────────────────────────────────────────────────────────────────
# Helpers – clipboard commit & chunking
# ──────────────────────────────────────────────────────────────────────────────
def _split_or_copy(text: str, do_split: bool, max_tokens: int) -> None:
    """Either copy in one go or interactively split into ≤*max_tokens* chunks."""
    total_tokens = _count_tokens(text)
    total_lines  = text.count("\n") + 1

    if do_split and total_tokens > max_tokens:
        chunks = _split_text(text, max_tokens)
        parts  = len(chunks)
        print(
            f"\n[ChatGPT] {total_lines:,} lines ≈ {total_tokens:,} tokens "
            f"→ {parts} chunk(s) (≤ {max_tokens} tokens)."
        )
        for idx, chunk in enumerate(chunks, 1):
            _commit_to_clipboard(chunk)
            lines  = chunk.count("\n") + 1
            tokens = _count_tokens(chunk)
            end    = "" if idx == parts else " – press <Enter> for next (q to quit)"
            if input(f"[{idx}/{parts}] Copied {lines:,} lines "
                     f"(≈{tokens:,} tokens){end}: ").lower().startswith("q"):
                break
        else:
            print("✓ All chunks copied.")
    else:
        _commit_to_clipboard(text)
        print(f"✓ Copied {total_lines:,} lines (≈{total_tokens:,} tokens).")


def _split_text(text: str, max_tokens: int) -> List[str]:
    """Split *text* on line boundaries, keeping each part ≤ max_tokens."""
    chunks, buf, buf_tok = [], [], 0
    for line in text.splitlines(keepends=True):
        tok = _count_tokens(line)
        if buf and buf_tok + tok > max_tokens:
            chunks.append("".join(buf))
            buf, buf_tok = [], 0
        buf.append(line)
        buf_tok += tok
    if buf:
        chunks.append("".join(buf))
    return chunks


def _commit_to_clipboard(data: str) -> None:
    """Copy *data* to clipboard, falling back gracefully."""
    try:
        pyperclip.copy(data)
    except Exception as exc:  # pragma: no cover
        print(f"[error] Clipboard failure: {exc}", file=sys.stderr)
        raise


def _relative_label(current: Path, root: Path) -> str:
    """Return './' for root or './sub/dir/' for children."""
    return "./" if current == root else f"./{current.relative_to(root)}/"


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry‑point for quick testing
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    files_to_clipboard(
        path=Path(__file__).parent,
        subdirectories=True,
        technology_filter = {
            'web':             False,
            'react':           False,
            'python':          False,
            'java':            False,
            'rust':            False,
            'cpp':             False,
            'vb':              False,
            'structured-data': False,
            'sql':             False,
            'terraform':       False,
            'go':              True,
            'markdown':        True,
        },
        copy_content=False,
        chatgpt_split=True,
    )
