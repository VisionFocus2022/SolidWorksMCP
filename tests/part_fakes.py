"""Shared FakeModel building blocks for the part-feature contract tests
(N41/L-8): the recording extension and the model skeleton were
copy-pasted across test_part_loft / test_part_refgeom /
test_part_primitives — one home now. Specialised sketch/feature managers
stay in their own test files; only the identical parts live here."""

from __future__ import annotations

from unittest.mock import Mock


class RecordingExtension:
    """Extension double that records SelectByID2 calls as 4-tuples."""

    def __init__(self):
        self.selects = []

    def SelectByID2(self, name, sel_type, x, y, z, append, mark, callout, opts):
        self.selects.append((name, sel_type, append, mark))
        return True


class BasePartModel:
    """swDocPART skeleton: wire managers as attributes (or override the
    properties); GetType mirrors the zero-arg COM property."""

    sketch = None
    fm = None

    def __init__(self):
        self.ext = RecordingExtension()

    @property
    def GetType(self):
        return 1  # swDocPART

    @property
    def SketchManager(self):
        return self.sketch

    @property
    def FeatureManager(self):
        return self.fm

    @property
    def Extension(self):
        return self.ext

    def ClearSelection2(self, all):
        pass


def sw_with_model(model):
    """SolidWorksApp double serving one active model document."""
    sw = Mock()
    sw.get_active_document.return_value = model
    return sw
