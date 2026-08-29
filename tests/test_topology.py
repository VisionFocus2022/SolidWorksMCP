"""Body/face enumeration and entity naming tests."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from solidworks_mcp.solidworks_api.topology import list_bodies, list_faces


class Surface:
    """Real-machine shape: zero-arg COM members arrive as properties."""

    def __init__(self, kind):
        self._kind = kind

    @property
    def IsPlane(self):
        return self._kind == "PLANE"

    @property
    def IsCylinder(self):
        return self._kind == "CYLINDER"

    @property
    def IsSphere(self):
        return self._kind == "SPHERE"


class Face:
    def __init__(self, kind, area_m2, next_face=None):
        self._surface = Surface(kind)
        self._area = area_m2
        self._next = next_face

    @property
    def GetSurface(self):
        return self._surface

    @property
    def GetArea(self):
        return self._area

    @property
    def GetNextFace(self):
        return self._next


class Body:
    def __init__(self, first_face):
        self._first = first_face

    @property
    def GetFirstFace(self):
        return self._first


class TopologyModel:
    """Real-machine shape: entity naming lives on ModelDoc2, not Extension."""

    def __init__(self, bodies):
        self._bodies = bodies
        self.names = {}

    def GetBodies2(self, body_type, visible_only):
        self.body_args = (body_type, visible_only)
        return self._bodies

    def GetEntityName(self, entity):
        return self.names.get(id(entity), "")

    def SetEntityName(self, entity, name):
        self.names[id(entity)] = name
        return True


class TestListFaces(unittest.TestCase):
    def test_names_unnamed_faces_and_reports_types(self):
        top = Face("PLANE", 0.0024)
        side = Face("CYLINDER", 0.0009, next_face=top)
        sw = Mock()
        sw.get_active_document.return_value = TopologyModel((Body(side),))
        result = list_faces(sw)
        self.assertTrue(result["success"])
        data = result["data"]
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["renamed"], 2)
        self.assertEqual([f["name"] for f in data["faces"]], ["Face0", "Face1"])
        self.assertEqual([f["surface_type"] for f in data["faces"]], ["CYLINDER", "PLANE"])
        self.assertAlmostEqual(data["faces"][0]["area_mm2"], 900.0)

    def test_existing_names_are_kept(self):
        face = Face("PLANE", 0.001)
        model = TopologyModel((Body(face),))
        model.names[id(face)] = "TopFace"
        sw = Mock()
        sw.get_active_document.return_value = model
        result = list_faces(sw)
        self.assertEqual(result["data"]["faces"][0]["name"], "TopFace")
        self.assertEqual(result["data"]["renamed"], 0)

    def test_no_document(self):
        sw = Mock()
        sw.get_active_document.return_value = None
        self.assertFalse(list_faces(sw)["success"])


class TestListBodies(unittest.TestCase):
    def test_counts_faces_per_body(self):
        face = Face("PLANE", 0.001)
        sw = Mock()
        sw.get_active_document.return_value = TopologyModel((Body(face),))
        result = list_bodies(sw)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["bodies"][0]["face_count"], 1)

    def test_com_error_is_tool_error(self):
        sw = Mock()
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(list_faces(sw)["success"])
        self.assertFalse(list_bodies(sw)["success"])


if __name__ == "__main__":
    unittest.main()
