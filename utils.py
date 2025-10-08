from pathlib import Path
import shutil
import os

SKIP_DIRS = {".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".idea", ".vscode", ".venv", "venv", "node_modules"}
SKIP_FILES = {".DS_Store"}

def _ignore_filter(dirpath, names):
    # Ignore VCS/system dirs and transient caches anywhere in the tree
    ignored = []
    for n in names:
        if n in SKIP_DIRS or n in SKIP_FILES:
            ignored.append(n)
        elif n.endswith((".pyc", ".pyo")):
            ignored.append(n)
    return ignored

TEADATA_GITHUB_URL = "https://github.com/adpena/teadata.git"

TEADATA_REPO = "/Users/adpena/PycharmProjects/teadata"
KNOWLEDGE = "/Users/adpena/PycharmProjects/teadata-mcp/knowledge"

def copy_repo_to_knowledge(nest=True, purge_git=True):
    """
    Copy the entire TEADATA_REPO into KNOWLEDGE while preserving project structure,
    but **do not** copy any Git repositories ('.git' dirs) or common transient files.

    - nest=True  -> copies into KNOWLEDGE/<repo_name> (e.g., knowledge/teadata)
    - nest=False -> copies the *contents* directly into KNOWLEDGE
    - purge_git  -> after copying, remove any nested '.git' dirs that might exist in dst
    """
    src = Path(TEADATA_REPO).resolve()
    dst = Path(KNOWLEDGE).resolve()

    if nest:
        dst = dst / src.name  # e.g., knowledge/teadata

    dst.mkdir(parents=True, exist_ok=True)

    # First, copy top-level items, skipping VCS dirs explicitly
    for item in src.iterdir():
        if item.name in SKIP_DIRS:
            continue  # skip .git, venvs, caches, etc.
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, symlinks=True, ignore=_ignore_filter, dirs_exist_ok=True)
        else:
            if item.name in SKIP_FILES or item.suffix in {'.pyc', '.pyo'}:
                continue
            shutil.copy2(item, target)

    # Safety: ensure no embedded repos landed in the destination
    if purge_git:
        removed = 0
        for gitdir in dst.rglob('.git'):
            try:
                shutil.rmtree(gitdir)
                removed += 1
            except Exception:
                pass
        if removed:
            print(f"Removed {removed} nested .git director(ies) in {dst}")

    print(f"Copied from {src} -> {dst}")

# Example:
copy_repo_to_knowledge(nest=True)   # copies into knowledge/teadata without any embedded Git repos
# copy_repo_to_knowledge(nest=False)  # copies contents into knowledge/
