"""Assembly creation, component, mate, and inspection tests."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from solidworks_mcp.solidworks_api.assembly import (
    _get_or_create_assembly,
    add_component,
    add_mate,
    get_components,
)


class TestAssemblyCreation(unittest.TestCase):
    def test_reuses_active_assembly(self):
        model = Mock()
        model.GetType.return_value = 2
        sw = Mock()
        sw.get_active_document.return_value = model
        self.assertIs(_get_or_create_assembly(sw), model)

    @patch("solidworks_mcp.solidworks_api.assembly.get_assembly_template", return_value="assembly.asmdot")
    def test_creates_assembly_from_template(self, _template):
        created = Mock()
        sw = Mock()
        sw.get_active_document.return_value = None
        sw.app.NewDocument.return_value = created
        self.assertIs(_get_or_create_assembly(sw), created)

    @patch("solidworks_mcp.solidworks_api.assembly.get_assembly_template", return_value=None)
    def test_missing_template_raises(self, _template):
        sw = Mock()
        sw.get_active_document.return_value = None
        with self.assertRaises(RuntimeError):
            _get_or_create_assembly(sw)

    @patch("solidworks_mcp.solidworks_api.assembly.get_assembly_template", return_value="assembly.asmdot")
    def test_new_document_none_raises(self, _template):
        sw = Mock()
        sw.get_active_document.return_value = None
        sw.app.NewDocument.return_value = None
        with self.assertRaises(RuntimeError):
            _get_or_create_assembly(sw)


class TestComponentOperations(unittest.TestCase):
    @patch("solidworks_mcp.solidworks_api.assembly.validate_path", return_value=(False, "unsafe"))
    def test_rejects_invalid_path(self, _path):
        self.assertEqual(add_component(Mock(), "bad.sldprt")["message"], "unsafe")

    @patch("solidworks_mcp.solidworks_api.assembly.validate_extension", return_value=(False, "wrong type"))
    @patch("solidworks_mcp.solidworks_api.assembly.validate_path", return_value=(True, ""))
    def test_rejects_invalid_extension(self, _path, _extension):
        result = add_component(Mock(), "bad.txt")
        self.assertEqual(result["error"]["code"], "INVALID_PARAMETER")

    @patch("solidworks_mcp.solidworks_api.assembly._get_or_create_assembly")
    @patch("solidworks_mcp.solidworks_api.assembly.validate_extension", return_value=(True, ""))
    @patch("solidworks_mcp.solidworks_api.assembly.validate_path", return_value=(True, ""))
    def test_adds_component_with_meter_coordinates(self, _path, _extension, get_assembly):
        model = Mock()
        model.AddComponent4.return_value = SimpleNamespace(Name2="Part1-1")
        get_assembly.return_value = model
        result = add_component(Mock(), "part.sldprt", 10, 20, 30, "Default")
        self.assertTrue(result["success"])
        model.AddComponent4.assert_called_once_with("part.sldprt", "Default", 0.01, 0.02, 0.03)

    @patch("solidworks_mcp.solidworks_api.assembly._get_or_create_assembly")
    @patch("solidworks_mcp.solidworks_api.assembly.validate_extension", return_value=(True, ""))
    @patch("solidworks_mcp.solidworks_api.assembly.validate_path", return_value=(True, ""))
    def test_reports_component_insertion_failure(self, _path, _extension, get_assembly):
        get_assembly.return_value.AddComponent4.return_value = None
        self.assertFalse(add_component(Mock(), "part.sldprt")["success"])


class TestMateAndComponents(unittest.TestCase):
    def test_mate_requires_active_assembly_and_supported_type(self):
        sw = Mock()
        sw.get_active_document.return_value = None
        self.assertFalse(add_mate(sw, "coincident", "A", "B")["success"])
        model = Mock()
        model.GetType.return_value = 2
        sw.get_active_document.return_value = model
        self.assertIn("Unsupported", add_mate(sw, "gear", "A", "B")["message"])

    def test_distance_mate_validates_distance(self):
        model = Mock()
        model.GetType.return_value = 2
        sw = Mock()
        sw.get_active_document.return_value = model
        self.assertEqual(add_mate(sw, "distance", "A", "B")["error"]["code"], "INVALID_PARAMETER")
        self.assertEqual(add_mate(sw, "distance", "A", "B", -1)["error"]["code"], "INVALID_PARAMETER")
        self.assertEqual(add_mate(sw, "distance", "A", "B", float("nan"))["error"]["code"], "INVALID_PARAMETER")

    @patch("solidworks_mcp.solidworks_api.assembly.win32com.client.VARIANT")
    def test_selection_and_mate_failures_are_structured(self, variant):
        variant.return_value = SimpleNamespace(value=7)
        model = Mock()
        model.GetType.return_value = 2
        model.GetTitle.return_value = "Assembly1"
        model.Extension.SelectByID2.return_value = False
        sw = Mock()
        sw.get_active_document.return_value = model
        self.assertIn("select", add_mate(sw, "coincident", "A", "B")["message"])
        model.Extension.SelectByID2.return_value = True
        model.AddMate5.return_value = None
        result = add_mate(sw, "coincident", "A", "B", entity1_type="FACE", entity2_type="FACE")
        self.assertEqual(result["error"]["code"], "SW_API_ERROR")

    def test_get_components_success_empty_and_wrong_document(self):
        sw = Mock()
        sw.get_active_document.return_value = None
        self.assertFalse(get_components(sw)["success"])
        model = Mock()
        model.GetType.return_value = 2
        model.GetComponents.return_value = [SimpleNamespace(Name2="A-1"), SimpleNamespace(Name2="B-1")]
        sw.get_active_document.return_value = model
        self.assertEqual(get_components(sw)["data"]["components"], ["A-1", "B-1"])
        model.GetComponents.return_value = None
        self.assertEqual(get_components(sw)["data"]["count"], 0)

    def test_com_errors_are_structured(self):
        sw = Mock()
        sw.get_active_document.side_effect = RuntimeError("COM")
        self.assertFalse(add_mate(sw, "coincident", "A", "B")["success"])
        self.assertFalse(get_components(sw)["success"])


# --- T11：新建装配 / 组件预开 / mate 扩展与选择顺序 / 干涉 / BOM ---

from solidworks_mcp.solidworks_api.assembly import (  # noqa: E402
    check_interference,
    get_bom,
    new_assembly,
)
from solidworks_mcp.solidworks_api.constants import (  # noqa: E402
    swMateANGLE,
    swMateTANGENT,
    swMateWIDTH,
)


class FakeExtension:
    def __init__(self, accepted_suffix):
        self.calls = []
        self.accepted_suffix = accepted_suffix

    def SelectByID2(self, name, type_, x, y, z, append, mark, callout, option):
        self.calls.append((name, type_, append))
        return name.endswith(self.accepted_suffix)


class FakeInterference:
    def __init__(self, volume_m3, comp_names):
        self._volume_m3 = volume_m3
        self._comp_names = comp_names

    @property
    def Volume(self):
        return self._volume_m3

    @property
    def Components(self):
        return [SimpleNamespace(Name2=n) for n in self._comp_names]


class FakeInterferenceMgr:
    def __init__(self, interferences):
        self._inters = interferences
        self.TreatCoincidenceAsInterference = True

    @property
    def GetInterferences(self):
        return self._inters


class FakeAsmDoc:
    """实机形态：零参成员是属性；GetTitle='装配体1'；干涉经 Mgr。"""

    def __init__(self, comps=None, interferences=None):
        self.comps = comps or []
        self.mgr = FakeInterferenceMgr(interferences or [])
        self.ext = FakeExtension("@装配体1")
        self.add_mate_calls = []
        self.save_calls = []

    @property
    def GetType(self):
        return 2

    @property
    def GetTitle(self):
        return "装配体1"

    @property
    def InterferenceDetectionManager(self):
        return self.mgr

    @property
    def Extension(self):
        return self.ext

    def GetComponents(self, _toplevel):
        return self.comps

    def ClearSelection2(self, _all):
        return None

    def AddMate5(self, *args):
        self.add_mate_calls.append(args)
        return SimpleNamespace(Name="重合1")

    def SaveAs3(self, path, version, options):
        self.save_calls.append(path)
        return 0


def _asm_sw(doc):
    sw = Mock()
    sw.get_active_document.return_value = doc
    return sw


class TestNewAssembly(unittest.TestCase):
    @patch("solidworks_mcp.solidworks_api.assembly.get_assembly_template",
           return_value="gb.asmdot")
    def test_creates_and_reports(self, _tpl):
        doc = FakeAsmDoc()
        sw = Mock()
        sw.app.NewDocument.return_value = doc
        result = new_assembly(sw)
        self.assertTrue(result["success"], result)
        sw.app.NewDocument.assert_called_once_with("gb.asmdot", 0, 0, 0)
        self.assertEqual(result["data"]["title"], "装配体1")
        self.assertEqual(result["data"]["type"], 2)

    @patch("solidworks_mcp.solidworks_api.assembly.get_assembly_template",
           return_value=None)
    def test_missing_template(self, _tpl):
        result = new_assembly(Mock())
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "TEMPLATE_NOT_FOUND")

    @patch("solidworks_mcp.solidworks_api.assembly.get_assembly_template",
           return_value="gb.asmdot")
    def test_new_document_failure(self, _tpl):
        sw = Mock()
        sw.app.NewDocument.return_value = None
        result = new_assembly(sw)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "SW_API_ERROR")

    @patch("solidworks_mcp.solidworks_api.assembly.ensure_sink_path",
           side_effect=lambda path: (True, "", path))
    @patch("solidworks_mcp.solidworks_api.assembly.validate_output_file",
           return_value=(True, ""))
    @patch("solidworks_mcp.solidworks_api.assembly.get_assembly_template",
           return_value="gb.asmdot")
    def test_save_path_uses_saveas3(self, _tpl, _vo, _es):
        doc = FakeAsmDoc()
        sw = Mock()
        sw.app.NewDocument.return_value = doc
        result = new_assembly(sw, save_path="asm1.SLDASM")
        self.assertTrue(result["success"], result)
        self.assertEqual(doc.save_calls, ["asm1.SLDASM"])
        self.assertEqual(result["data"]["saved_path"], "asm1.SLDASM")


class TestComponentPreopen(unittest.TestCase):
    @patch("solidworks_mcp.solidworks_api.assembly._get_or_create_assembly")
    @patch("solidworks_mcp.solidworks_api.assembly.validate_extension",
           return_value=(True, ""))
    @patch("solidworks_mcp.solidworks_api.assembly.validate_path",
           return_value=(True, ""))
    def test_preopens_part_before_add(self, _path, _ext, get_asm):
        # 实机铁律：零件未在会话中打开时 AddComponent4 静默返回 None
        model = Mock()
        model.AddComponent4.return_value = SimpleNamespace(Name2="P-1")
        get_asm.return_value = model
        sw = Mock()
        sw.app.OpenDoc6.return_value = "opened"
        result = add_component(sw, "part.sldprt")
        self.assertTrue(result["success"])
        sw.app.OpenDoc6.assert_called_once()
        self.assertLess(
            sw.app.OpenDoc6.call_count,
            2,
        )


class TestMateExtension(unittest.TestCase):
    def test_constants_match_swconst_values(self):
        self.assertEqual((swMateTANGENT, swMateANGLE, swMateWIDTH), (4, 6, 17))

    def test_title_qualified_name_is_tried_first(self):
        # 实机：裸名选择形态误选导致 AddMate5 None；@装配体标题 全限定先试
        doc = FakeAsmDoc()
        sw = _asm_sw(doc)
        result = add_mate(sw, "coincident", "前视基准面@P1-1", "前视基准面@P2-1",
                          entity1_type="PLANE", entity2_type="PLANE")
        self.assertTrue(result["success"], result)
        first, second = doc.ext.calls[0], doc.ext.calls[1]
        self.assertEqual(first[0], "前视基准面@P1-1@装配体1")
        self.assertEqual(second[0], "前视基准面@P2-1@装配体1")

    def test_second_selection_appends(self):
        doc = FakeAsmDoc()
        sw = _asm_sw(doc)
        add_mate(sw, "coincident", "前视基准面@P1-1", "前视基准面@P2-1",
                 entity1_type="PLANE", entity2_type="PLANE")
        self.assertFalse(doc.ext.calls[0][2])
        self.assertTrue(doc.ext.calls[1][2])

    def test_angle_mate_uses_angle_slot_in_radians(self):
        # 实机：角度必须走 AddMate5 第 10 参 Angle 槽（度→弧度），Distance 槽置 0
        import math

        doc = FakeAsmDoc()
        sw = _asm_sw(doc)
        result = add_mate(sw, "angle", "右视基准面@P1-1", "右视基准面@P2-1",
                          distance=30.0,
                          entity1_type="PLANE", entity2_type="PLANE")
        self.assertTrue(result["success"], result)
        args = doc.add_mate_calls[0]
        self.assertEqual(args[0], swMateANGLE)
        self.assertEqual(args[3], 0.0)  # Distance 槽
        self.assertAlmostEqual(args[8], math.radians(30.0))  # Angle 槽

    def test_tangent_and_width_are_mapped(self):
        doc = FakeAsmDoc()
        sw = _asm_sw(doc)
        add_mate(sw, "tangent", "Face0@P1-1", "Face1@P2-1",
                 entity1_type="FACE", entity2_type="FACE")
        add_mate(sw, "width", "上视基准面@P1-1", "上视基准面@P2-1",
                 entity1_type="PLANE", entity2_type="PLANE")
        self.assertEqual(doc.add_mate_calls[0][0], swMateTANGENT)
        self.assertEqual(doc.add_mate_calls[1][0], swMateWIDTH)


class TestInterference(unittest.TestCase):
    def test_aggregates_volumes_and_components(self):
        doc = FakeAsmDoc(interferences=[
            FakeInterference(4e-05, ["box-1", "box-2"]),
        ])
        result = check_interference(_asm_sw(doc))
        self.assertTrue(result["success"], result)
        self.assertEqual(result["data"]["interference_count"], 1)
        self.assertTrue(result["data"]["has_interference"])
        self.assertEqual(result["data"]["interferences"][0]["volume_mm3"], 40000.0)
        self.assertEqual(result["data"]["interferences"][0]["components"],
                         ["box-1", "box-2"])
        self.assertFalse(doc.mgr.TreatCoincidenceAsInterference)

    def test_no_interference_is_success(self):
        result = check_interference(_asm_sw(FakeAsmDoc()))
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["interference_count"], 0)
        self.assertFalse(result["data"]["has_interference"])

    def test_requires_assembly_document(self):
        sw = Mock()
        sw.get_active_document.return_value = None
        self.assertFalse(check_interference(sw)["success"])


class TestBom(unittest.TestCase):
    def test_aggregates_same_part_instances(self):
        doc = FakeAsmDoc(comps=[
            SimpleNamespace(Name2="box-1", GetPathName=lambda: "e:/a/box.SLDPRT",
                            ReferencedConfiguration=lambda: "默认"),
            SimpleNamespace(Name2="box-2", GetPathName=lambda: "e:/a/box.SLDPRT",
                            ReferencedConfiguration=lambda: "默认"),
            SimpleNamespace(Name2="cyl-1", GetPathName=lambda: "e:/a/cyl.SLDPRT",
                            ReferencedConfiguration=lambda: "默认"),
        ])
        # 零参属性在实机是属性；此处 fake 用可调用形态验证 call_or_value 双兼容
        result = get_bom(_asm_sw(doc))
        self.assertTrue(result["success"], result)
        self.assertEqual(result["data"]["total_components"], 3)
        self.assertEqual(result["data"]["unique_parts"], 2)
        by_name = {i["name"]: i for i in result["data"]["items"]}
        self.assertEqual(by_name["box"]["count"], 2)
        self.assertEqual(by_name["cyl"]["count"], 1)
        self.assertEqual(by_name["box"]["configuration"], "默认")

    def test_requires_assembly_document(self):
        sw = Mock()
        sw.get_active_document.return_value = None
        self.assertFalse(get_bom(sw)["success"])

    def test_com_errors_are_structured(self):
        sw = Mock()
        sw.get_active_document.side_effect = RuntimeError("COM")
        self.assertFalse(check_interference(sw)["success"])
        self.assertFalse(get_bom(sw)["success"])


class TestT11ErrorBranches(unittest.TestCase):
    @patch("solidworks_mcp.solidworks_api.assembly.ensure_sink_path",
           side_effect=lambda path: (True, "", path))
    @patch("solidworks_mcp.solidworks_api.assembly.validate_output_file",
           return_value=(True, ""))
    @patch("solidworks_mcp.solidworks_api.assembly.get_assembly_template",
           return_value="gb.asmdot")
    def test_new_assembly_save_failure(self, _tpl, _vo, _es):
        doc = FakeAsmDoc()
        doc.SaveAs3 = lambda *a: 2
        sw = Mock()
        sw.app.NewDocument.return_value = doc
        result = new_assembly(sw, save_path="x.SLDASM")
        self.assertFalse(result["success"])
        self.assertIn("code 2", result["message"])

    @patch("solidworks_mcp.solidworks_api.assembly.validate_output_file",
           return_value=(False, "outside root"))
    @patch("solidworks_mcp.solidworks_api.assembly.get_assembly_template",
           return_value="gb.asmdot")
    def test_new_assembly_bad_output_path(self, _tpl, _vo):
        sw = Mock()
        sw.app.NewDocument.return_value = FakeAsmDoc()
        result = new_assembly(sw, save_path="x.SLDASM")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "INVALID_OUTPUT_PATH")

    @patch("solidworks_mcp.solidworks_api.assembly._get_or_create_assembly")
    @patch("solidworks_mcp.solidworks_api.assembly.validate_extension",
           return_value=(True, ""))
    @patch("solidworks_mcp.solidworks_api.assembly.validate_path",
           return_value=(True, ""))
    def test_add_component_preopen_failure(self, _path, _ext, get_asm):
        sw = Mock()
        sw.app.OpenDoc6.return_value = None
        result = add_component(sw, "locked.sldprt")
        self.assertFalse(result["success"])
        self.assertIn("AddComponent4 requires", result["message"])
        get_asm.assert_not_called()

    def test_check_interference_detector_missing(self):
        class NoDetectorAsm(FakeAsmDoc):
            @property
            def InterferenceDetectionManager(self):
                return None

        result = check_interference(_asm_sw(NoDetectorAsm()))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "SW_API_ERROR")

    def test_mate_unhandled_com_error_is_structured(self):
        sw = Mock()
        sw.get_active_document.return_value = None
        self.assertFalse(
            add_mate(sw, "coincident", "A", "B")["success"]
        )


if __name__ == "__main__":
    unittest.main()
