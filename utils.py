from pathlib import Path
import shutil
import os

TEADATA_REPO = "/Users/adpena/PycharmProjects/teadata"
KNOWLEDGE = "/Users/adpena/PycharmProjects/teadata-mcp/knowledge"

def copy_repo_to_knowledge(nest=True):
    """
    Copy the entire TEADATA_REPO into KNOWLEDGE.
    - nest=True  -> copies into KNOWLEDGE/<repo_name> (e.g., knowledge/teadata)
    - nest=False -> copies the *contents* directly into KNOWLEDGE
    Excludes: .git, __pycache__, *.pyc, .DS_Store
    """
    src = Path(TEADATA_REPO).resolve()
    dst = Path(KNOWLEDGE).resolve()

    if nest:
        dst = dst / src.name  # e.g., knowledge/teadata

    dst.mkdir(parents=True, exist_ok=True)

    ignore = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".DS_Store")

    # Copy directory tree; Python 3.8+ supports dirs_exist_ok to merge into existing dirs
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, symlinks=True, ignore=ignore, dirs_exist_ok=True)
        else:
            if not any(pat in item.name for pat in (".DS_Store",)):
                shutil.copy2(item, target)

    print(f"Copied from {src} -> {dst}")

# Example:
copy_repo_to_knowledge(nest=True)   # copies into knowledge/teadata
# copy_repo_to_knowledge(nest=False)  # copies contents into knowledge/
