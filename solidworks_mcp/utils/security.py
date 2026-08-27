"""Path security and confirmation helpers."""

from __future__ import annotations

import logging
import os
from typing import Iterable, Optional

from solidworks_mcp.config import get_config

logger = logging.getLogger(__name__)


# Default allowed root directory. All file operations must be under this path
# unless explicitly relaxed by configuration.
DEFAULT_ALLOWED_ROOT = os.path.normpath(get_config().allowed_root)


def normalize_path(path: str) -> str:
    """Normalize an absolute path, resolving links/junctions with OS semantics.

    Resolution is component-wise and never lexically folds ``..`` across a
    link: each existing component is canonicalized via ``realpath`` (whose
    ``_getfinalpathname`` resolves junctions the way the file system does),
    and ``..`` pops the already-canonical prefix. This prevents
    ``root\\link\\..\\out`` from folding to ``root\\out`` when ``link``
    actually points outside the root.
    """
    expanded = os.path.expanduser(path)
    if os.path.lexists(expanded):
        return os.path.normpath(os.path.realpath(expanded))
    if not os.path.isabs(expanded):
        expanded = os.getcwd() + os.sep + expanded
    drive, rest = os.path.splitdrive(expanded)
    parts: list = []
    for part in rest.split(os.sep):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
        candidate = drive + os.sep + os.sep.join(parts)
        if os.path.lexists(candidate):
            canonical_drive, canonical_rest = os.path.splitdrive(
                os.path.realpath(candidate)
            )
            drive = canonical_drive or drive
            parts = [p for p in canonical_rest.split(os.sep) if p not in ("", ".")]
    return os.path.normpath(drive + os.sep + os.sep.join(parts))


def is_path_allowed(
    path: str,
    allowed_root: Optional[str] = None,
) -> bool:
    """Check whether a path is within the allowed root directory.

    This prevents directory traversal attacks via ``..`` segments.
    """
    root = normalize_path(allowed_root or DEFAULT_ALLOWED_ROOT)
    target = normalize_path(path)
    # os.path.commonpath can raise ValueError for mixed drive letters on Windows.
    try:
        common = os.path.commonpath([root, target])
    except ValueError:
        return False
    return os.path.normcase(common) == os.path.normcase(root)


def validate_path(
    path: str,
    allowed_root: Optional[str] = None,
    must_exist: bool = False,
    must_not_exist: bool = False,
    parent_must_exist: bool = False,
) -> tuple[bool, str]:
    """Validate a file path for safety.

    Returns:
        A tuple (is_valid, message). When invalid, message explains why.
    """
    if not path or not isinstance(path, str):
        return False, "Path must be a non-empty string"

    normalized = normalize_path(path)

    effective_root = allowed_root or DEFAULT_ALLOWED_ROOT

    if not is_path_allowed(normalized, effective_root):
        return (
            False,
            f"Path '{path}' is outside the allowed working directory. "
            f"Operations are restricted to '{effective_root}'.",
        )

    if must_exist and not os.path.exists(normalized):
        return False, f"Path does not exist: {path}"

    if must_not_exist and os.path.exists(normalized):
        return False, f"File already exists: {path}"

    if parent_must_exist:
        parent = os.path.dirname(normalized) or normalize_path(".")
        if not os.path.isdir(parent):
            return False, f"Parent directory does not exist: {parent}"

    return True, ""


def validate_extension(
    path: str,
    allowed_extensions: Iterable[str],
) -> tuple[bool, str]:
    """Require a file extension from an explicit allowlist."""
    allowed = {
        ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        for ext in allowed_extensions
    }
    actual = os.path.splitext(path)[1].lower()
    if actual not in allowed:
        expected = ", ".join(sorted(allowed))
        return False, f"Expected file extension {expected}; got '{actual or '<none>'}'"
    return True, ""


def check_overwrite_confirm(
    path: str,
    overwrite_confirm: bool = False,
) -> tuple[bool, str]:
    """Check whether overwriting an existing file is allowed.

    In strict mode, ``overwrite_confirm`` must be True before an existing file
    can be overwritten. Returns (allowed, message).
    """
    normalized = normalize_path(path)
    if os.path.exists(normalized):
        if not overwrite_confirm:
            return (
                False,
                f"File already exists: {path}. "
                "Set overwrite_confirm=True to overwrite.",
            )
    return True, ""


def validate_output_file(
    path: str,
    allowed_extensions: Iterable[str],
    overwrite_confirm: bool = False,
    allowed_root: Optional[str] = None,
) -> tuple[bool, str]:
    """Validate a safe output path before any SolidWorks model is mutated."""
    valid, message = validate_path(
        path,
        allowed_root=allowed_root,
        parent_must_exist=True,
    )
    if not valid:
        return valid, message
    valid, message = validate_extension(path, allowed_extensions)
    if not valid:
        return valid, message
    return check_overwrite_confirm(path, overwrite_confirm)
