"""Template path discovery helpers."""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from solidworks_mcp.config import get_config

logger = logging.getLogger(__name__)


# ProgramData template names, most specific first; the SolidWorks version
# directory is derived from SOLIDWORKS_MCP_SOLIDWORKS_VERSION at call time.
_PART_TEMPLATE_NAMES = ["gb_part.prtdot", "Part.prtdot", "零件.prtdot"]
_ASSEMBLY_TEMPLATE_NAMES = ["gb_assembly.asmdot", "Assembly.asmdot", "装配体.asmdot"]
_DRAWING_TEMPLATE_NAMES = ["gb_a4p.drwdot", "Drawing.drwdot", "工程图.drwdot"]

# Common installation fallbacks for lang-specific template locations.
DEFAULT_PART_TEMPLATE_FALLBACKS: List[str] = [
    r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\english\part.prtdot",
    r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\chinese-simplified\part.prtdot",
    r"C:\Program Files\SOLIDWORKS Corp (x64)\SOLIDWORKS\lang\english\part.prtdot",
    r"C:\Program Files\SOLIDWORKS Corp (x64)\SOLIDWORKS\lang\chinese-simplified\part.prtdot",
]

DEFAULT_ASSEMBLY_TEMPLATE_FALLBACKS: List[str] = [
    r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\english\assembly.asmdot",
    r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\chinese-simplified\assembly.asmdot",
    r"C:\Program Files\SOLIDWORKS Corp (x64)\SOLIDWORKS\lang\english\assembly.asmdot",
    r"C:\Program Files\SOLIDWORKS Corp (x64)\SOLIDWORKS\lang\chinese-simplified\assembly.asmdot",
]

DEFAULT_DRAWING_TEMPLATE_FALLBACKS: List[str] = [
    r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\english\drawing.drwdot",
    r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\chinese-simplified\drawing.drwdot",
    r"C:\Program Files\SOLIDWORKS Corp (x64)\SOLIDWORKS\lang\english\drawing.drwdot",
    r"C:\Program Files\SOLIDWORKS Corp (x64)\SOLIDWORKS\lang\chinese-simplified\drawing.drwdot",
]


def _programdata_candidates(template_names: List[str]) -> List[str]:
    """Build ProgramData candidate paths for the configured SolidWorks version."""
    version = get_config().solidworks_version
    return [
        rf"C:\ProgramData\SolidWorks\SolidWorks {version}\templates\{name}"
        for name in template_names
    ]


def find_template(candidates: List[str]) -> Optional[str]:
    """Return the first existing template path from the candidate list."""
    for candidate in candidates:
        normalized = os.path.normpath(candidate)
        if os.path.isfile(normalized):
            logger.info("Found template: %s", normalized)
            return normalized
    return None


def get_part_template() -> Optional[str]:
    """Locate the default SolidWorks part template."""
    configured = get_config().part_template
    candidates = ([configured] if configured else []) + _programdata_candidates(
        _PART_TEMPLATE_NAMES
    ) + DEFAULT_PART_TEMPLATE_FALLBACKS
    return find_template(candidates)


def get_assembly_template() -> Optional[str]:
    """Locate the default SolidWorks assembly template."""
    configured = get_config().assembly_template
    candidates = ([configured] if configured else []) + _programdata_candidates(
        _ASSEMBLY_TEMPLATE_NAMES
    ) + DEFAULT_ASSEMBLY_TEMPLATE_FALLBACKS
    return find_template(candidates)


def get_drawing_template() -> Optional[str]:
    """Locate the default SolidWorks drawing template."""
    configured = get_config().drawing_template
    candidates = ([configured] if configured else []) + _programdata_candidates(
        _DRAWING_TEMPLATE_NAMES
    ) + DEFAULT_DRAWING_TEMPLATE_FALLBACKS
    return find_template(candidates)
