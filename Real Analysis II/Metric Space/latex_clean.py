#!/usr/bin/env python3
"""
LaTeX directory cleaner.

Examples:
  # Preview what would be deleted (recommended first)
  python latex_clean.py --dry-run

  # Actually delete junk files in current directory (recursive)
  python latex_clean.py

  # Clean a specific folder
  python latex_clean.py "E:\\MyLatexProject"

  # Also delete minted cache folders
  python latex_clean.py --remove-minted
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

# Common LaTeX build artifacts (safe to delete)
LATEX_JUNK_EXTENSIONS = {
    ".aux", ".log", ".toc", ".out", ".lof", ".lot", ".gz",
    ".bbl", ".bcf", ".blg", ".run.xml",
    ".fls", ".fdb_latexmk", ".synctex.gz",
    ".nav", ".snm", ".vrb",
    ".idx", ".ilg", ".ind",
    ".acn", ".acr", ".alg", ".glg", ".glo", ".gls",
    ".xdy",
    ".thm",
}

# Some tools create files without (standard) extensions or with special patterns
JUNK_BASENAMES = {
    ".DS_Store",  # macOS
}

# Prefix/suffix patterns frequently produced by TeX toolchains
PREFIX_PATTERNS = (
    "texput",      # texput.log / texput.aux, etc.
)

def iter_paths(root: Path) -> Iterable[Path]:
    # Skip very large / irrelevant folders if present
    skip_dirs = {".git", ".svn", ".hg", "__pycache__"}
    for dirpath, dirnames, filenames in os.walk(root):
        # prune directories in-place
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]

        dp = Path(dirpath)
        for fn in filenames:
            yield dp / fn


def is_latex_junk_file(p: Path) -> bool:
    name = p.name

    if name in JUNK_BASENAMES:
        return True

    lower = name.lower()

    # texput* pattern
    if any(lower.startswith(pref) for pref in PREFIX_PATTERNS):
        # only if it looks like a log/aux/out etc.
        if p.suffix.lower() in LATEX_JUNK_EXTENSIONS or lower.endswith(".log"):
            return True

    # normal extension based match
    if p.suffix.lower() in LATEX_JUNK_EXTENSIONS:
        return True

    return False


def find_minted_dirs(root: Path) -> list[Path]:
    # minted often creates folders like "_minted-<jobname>"
    minted_dirs = []
    for dirpath, dirnames, _ in os.walk(root):
        dp = Path(dirpath)
        for d in list(dirnames):
            if d.startswith("_minted"):
                minted_dirs.append(dp / d)
    return minted_dirs


def safe_delete_file(p: Path, dry_run: bool) -> bool:
    try:
        if dry_run:
            return True
        p.unlink()
        return True
    except FileNotFoundError:
        return False
    except PermissionError:
        return False
    except OSError:
        return False


def safe_delete_dir_tree(d: Path, dry_run: bool) -> tuple[int, int]:
    """
    Delete directory tree d.
    Returns (files_deleted, dirs_deleted)
    """
    files_deleted = 0
    dirs_deleted = 0

    # Walk bottom-up so we delete files before directories
    for dirpath, dirnames, filenames in os.walk(d, topdown=False):
        dp = Path(dirpath)
        for fn in filenames:
            fp = dp / fn
            if safe_delete_file(fp, dry_run=dry_run):
                files_deleted += 1
        for dn in dirnames:
            dd = dp / dn
            try:
                if dry_run:
                    dirs_deleted += 1
                else:
                    dd.rmdir()
                    dirs_deleted += 1
            except OSError:
                # not empty or permission error; ignore
                pass

    # Finally remove the root minted dir
    try:
        if dry_run:
            dirs_deleted += 1
        else:
            d.rmdir()
            dirs_deleted += 1
    except OSError:
        pass

    return files_deleted, dirs_deleted


def main() -> int:
    ap = argparse.ArgumentParser(description="Delete LaTeX build artifacts from a project directory.")
    ap.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Root folder to clean (default: current folder).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Only show what would be deleted; do not delete anything.",
    )
    ap.add_argument(
        "--remove-minted",
        action="store_true",
        help="Also remove _minted* folders (minted cache).",
    )

    args = ap.parse_args()
    root = Path(args.path).expanduser().resolve()

    if not root.exists() or not root.is_dir():
        print(f"[ERROR] Not a directory: {root}")
        return 2

    junk_files = [p for p in iter_paths(root) if is_latex_junk_file(p)]

    # Report + delete
    print(f"Root: {root}")
    print(f"Mode: {'DRY RUN (no deletions)' if args.dry_run else 'DELETE'}")
    print(f"Found junk files: {len(junk_files)}")

    deleted = 0
    failed = 0

    for p in junk_files:
        rel = p.relative_to(root)
        if args.dry_run:
            print(f"  would delete: {rel}")
            deleted += 1
        else:
            ok = safe_delete_file(p, dry_run=False)
            if ok:
                print(f"  deleted: {rel}")
                deleted += 1
            else:
                print(f"  FAILED: {rel}")
                failed += 1

    # minted dirs
    if args.remove_minted:
        minted_dirs = find_minted_dirs(root)
        print(f"Found minted dirs: {len(minted_dirs)}")
        for d in minted_dirs:
            rel = d.relative_to(root)
            if args.dry_run:
                print(f"  would delete dir: {rel} (and contents)")
            files_del, dirs_del = safe_delete_dir_tree(d, dry_run=args.dry_run)
            if not args.dry_run:
                print(f"  deleted dir: {rel} (files={files_del}, dirs={dirs_del})")

    print(f"\nDone. {'Planned' if args.dry_run else 'Deleted'}: {deleted} files. Failed: {failed}.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
