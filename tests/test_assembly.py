"""Assembly selection and mate orchestration tests without SolidWorks."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from solidworks_mcp.solidworks_api.assembly import add_component, add_mate


class FakeMate:
    Name = "Mate1"


class FakeExtension:
    def __init__(self):
        self.selection_names = []

    def SelectByID2(
        self,
        name,
        entity_type,
        x,
        y,
        z,
        append,
        mark,
        callout,
        option,
    ):
        self.selection_names.append(name)
        return True


class LocalizedExtension(FakeExtension):
    def SelectByID2(self, name, *args):
        self.selection_names.append(name)
        return name.startswith("前视基准面@")

class FakeAssembly:
    def __init__(self):
        self.Extension = FakeExtension()

    def GetType(self):
        return 2

    def GetTitle(self):
        return "Assembly1"

    def ClearSelection2(self, clear_all):
        return None

    def AddMate5(self, *args):
        return FakeMate()


class FakeSolidWorks:
    def __init__(self):
        self.model = FakeAssembly()

    def get_active_document(self):
        return self.model


class TestAssemblyMate(unittest.TestCase):
    def test_reference_plane_alias_falls_back_to_solidworks_locale(self):
        sw = FakeSolidWorks()
        sw.model.Extension = LocalizedExtension()
        result = add_mate(
            sw,
            "coincident",
            "Front Plane@Component1",
            "Front Plane@Component2",
            entity1_type="PLANE",
            entity2_type="PLANE",
        )
        self.assertTrue(result["success"])
        self.assertIn(
            "前视基准面@Component1@Assembly1",
            sw.model.Extension.selection_names,
        )
    def test_component_reference_uses_full_assembly_context_first(self):
        sw = FakeSolidWorks()
        result = add_mate(
            sw,
            "coincident",
            "Top Plane@Component1",
            "Top Plane@Component2",
            entity1_type="PLANE",
            entity2_type="PLANE",
        )
        self.assertTrue(result["success"])
        self.assertEqual(
            sw.model.Extension.selection_names[:2],
            [
                "Top Plane@Component1@Assembly1",
                "Top Plane@Component2@Assembly1",
            ],
        )

    @patch("solidworks_mcp.solidworks_api.assembly.validate_extension", return_value=(True, ""))
    @patch("solidworks_mcp.solidworks_api.assembly.validate_path", return_value=(True, ""))
    def test_invalid_component_coordinate_has_invalid_parameter_code(self, _path, _extension):
        result = add_component(Mock(), "part.sldprt", x=float("nan"))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "INVALID_PARAMETER")


if __name__ == "__main__":
    unittest.main()