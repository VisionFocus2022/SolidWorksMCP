"""Template path discovery helpers."""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from solidworks_mcp.config import get_config

logger = logging.getLogger(__name__)


# Common installation locations for SolidWorks part templates.
# Order matters: more specific / current version first.
DEFAULT_PART_TEMPLATE_CANDIDATES: List[str] = [
    r"C:\ProgramData\SolidWorks\SolidWorks 2026\templates\gb_part.prtdot",
    r"C:\ProgramData\SolidWorks\SolidWorks 2026\templates\Part.prtdot",
    r"C:\ProgramData\SolidWorks\SolidWorks 2026\templates\零件.prtdot",
    r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\english\part.prtdot",
    r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\chinese-simplified\part.prtdot",
    r"C:\Program Files\SOLIDWORKS Corp (x64)\SOLIDWORKS\lang\english\part.prtdot",
    r"C:\Program Files\SOLIDWORKS Corp (x64)\SOLIDWORKS\lang\chinese-simplified\part.prtdot",
]

DEFAULT_ASSEMBLY_TEMPLATE_CANDIDATES: List[str] = [
    r"C:\ProgramData\SolidWorks\SolidWorks 2026\templates\gb_assembly.asmdot",
    r"C:\ProgramData\SolidWorks\SolidWorks 2026\templates\Assembly.asmdot",
    r"C:\ProgramData\SolidWorks\SolidWorks 2026\templates\装配体.asmdot",
    r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\english\assembly.asmdot",
    r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\chinese-simplified\assembly.asmdot",
]

DEFAULT_DRAWING_TEMPLATE_CANDIDATES: List[str] = [
    r"C:\ProgramData\SolidWorks\SolidWorks 2026\templates\gb_a4p.drwdot",
    r"C:\ProgramData\SolidWorks\SolidWorks 2026\templates\Drawing.drwdot",
    r"C:\ProgramData\SolidWorks\SolidWorks 2026\templates\工程图.drwdot",
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
    candidates = ([configured] if configured else []) + DEFAULT_PART_TEMPLATE_CANDIDATES
    return find_template(candidates)


def get_assembly_template() -> Optional[str]:
    """Locate the default SolidWorks assembly template."""
    configured = get_config().assembly_template
    candidates = ([configured] if configured else []) + DEFAULT_ASSEMBLY_TEMPLATE_CANDIDATES
    return find_template(candidates)


def get_drawing_template() -> Optional[str]:
    """Locate the default SolidWorks drawing template."""
    configured = get_config().drawing_template
    candidates = ([configured] if configured else []) + DEFAULT_DRAWING_TEMPLATE_CANDIDATES
    return find_template(candidates)
