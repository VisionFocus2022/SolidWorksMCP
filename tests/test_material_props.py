"""Material / custom property / equation / configuration tool tests."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from solidworks_mcp.solidworks_api.properties import (
    add_configuration,
    add_equation,
    get_custom_properties,
    get_material,
    list_equations,
    set_custom_property,
    set_material,
)


class ByrefStr:
    """Stand-in for win32com VARIANT(VT_BYREF | VT_BSTR) with a writable value."""

    def __init__(self, value=""):
        self.value = value


class PropertyManager:
    def __init__(self):
        self.props = {}

    def Add3(self, name, field_type, value, overwrite):
        self.props[name] = str(value)
        return 0

    def Get2(self, name, val_out, resolved_out):
        val_out.value = self.props.get(name, "")
        resolved_out.value = self.props.get(name, "")
        return None

    @property
    def GetNames(self):
        return tuple(self.props)

    @property
    def GetCount(self):
        return len(self.props)


class EquationManager:
    def __init__(self):
        self.equations = []

    def Add2(self, index, equation, solve):
        self.equations.append(equation)
        return len(self.equations) - 1

    @property
    def GetCount(self):
        return len(self.equations)

    def Equation(self, index):
        return self.equations[index]

    def Value(self, index):
        return 50.0


class Extension:
    def __init__(self, model):
        self._model = model

    def CustomPropertyManager(self, config):
        return self._model.cpm


class PropsModel:
    """Real-machine shape: byref outs, zero-arg properties, Chinese config."""

    def __init__(self):
        self.cpm = PropertyManager()
        self.configs = ["默认"]
        self.material = ""
        self.database = ""
        self.set_calls = []
        self._equation_mgr = EquationManager()
        # 拒绝语义：不在白名单的材料名被 SW 静默忽略
        self.valid_materials = {"合金钢", "铝合金 1060"}

    @property
    def GetConfigurationNames(self):
        return tuple(self.configs)

    def GetMaterialPropertyName2(self, config, database_ref):
        database_ref.value = self.database
        return self.material

    def SetMaterialPropertyName2(self, config, database, name):
        self.set_calls.append((config, database, name))
        if name in self.valid_materials:
            self.material = name
            self.database = database.lower()
        return None

    @property
    def Extension(self):
        return Extension(self)

    @property
    def GetEquationMgr(self):
        return self._equation_mgr

    @property
    def EditRebuild3(self):
        return True

    def AddConfiguration(self, name, comment, alt, supp, hide, minfm, inherit, flags):
        self.configs.append(name)
        return None


def _sw(model):
    sw = Mock()
    sw.get_active_document.return_value = model
    return sw


class TestMaterial(unittest.TestCase):
    def test_set_and_get_material_roundtrip(self):
        model = PropsModel()
        sw = _sw(model)

        result = set_material(sw, "合金钢")

        self.assertTrue(result["success"])
        self.assertEqual(model.set_calls[0], ("默认", "SOLIDWORKS MATERIALS", "合金钢"))
        read = get_material(sw)
        self.assertEqual(read["data"]["name"], "合金钢")
        self.assertEqual(read["data"]["database"], "solidworks materials")
        self.assertEqual(read["data"]["configuration"], "默认")

    def test_rejected_material_is_reported(self):
        model = PropsModel()  # set never sticks -> read-back mismatch
        model.database = "solidworks materials"
        sw = _sw(model)
        result = set_material(sw, "不存在的材料")
        self.assertFalse(result["success"])
        self.assertIn("rejected", result["message"])

    def test_requires_document_and_handles_com_errors(self):
        sw = Mock()
        sw.get_active_document.return_value = None
        self.assertFalse(set_material(sw, "合金钢")["success"])
        self.assertFalse(get_material(sw)["success"])
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(get_material(sw)["success"])


class TestCustomProperties(unittest.TestCase):
    def test_set_and_get_properties(self):
        model = PropsModel()
        sw = _sw(model)

        result = set_custom_property(sw, "PartNo", "A-1024")
        self.assertTrue(result["success"])

        listing = get_custom_properties(sw)
        self.assertEqual(listing["data"]["properties"], {"PartNo": "A-1024"})
        self.assertEqual(listing["data"]["count"], 1)

    def test_add3_failure_and_validation(self):
        model = PropsModel()
        model.cpm.Add3 = lambda *a: -1  # rejection code
        sw = _sw(model)
        result = set_custom_property(sw, "PartNo", "A-1024")
        self.assertFalse(result["success"])
        self.assertIn("rejected", result["message"])

        sw = _sw(PropsModel())
        for name, value in (("", "x"), ("PartNo", "")):
            self.assertEqual(
                set_custom_property(sw, name, value)["error"]["code"],
                "INVALID_PARAMETER",
            )

    def test_com_errors_are_structured(self):
        sw = Mock()
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(set_custom_property(sw, "A", "B")["success"])
        self.assertFalse(get_custom_properties(sw)["success"])


class TestEquations(unittest.TestCase):
    def test_add_and_list_equations(self):
        model = PropsModel()
        sw = _sw(model)

        added = add_equation(sw, '"x" = 50')
        self.assertTrue(added["success"])
        self.assertEqual(added["data"]["index"], 0)

        listing = list_equations(sw)
        self.assertEqual(
            listing["data"]["equations"],
            [{"text": '"x" = 50', "value": 50.0}],
        )

    def test_rejected_equation_and_validation(self):
        model = PropsModel()
        model.GetEquationMgr.Add2 = lambda *a: -1
        sw = _sw(model)
        result = add_equation(sw, '"x" = 50')
        self.assertFalse(result["success"])
        self.assertIn("rejected", result["message"])

        sw = _sw(PropsModel())
        self.assertEqual(
            add_equation(sw, "")["error"]["code"], "INVALID_PARAMETER"
        )

    def test_com_errors_are_structured(self):
        sw = Mock()
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(add_equation(sw, '"x" = 1')["success"])
        self.assertFalse(list_equations(sw)["success"])


class TestConfigurations(unittest.TestCase):
    def test_add_configuration(self):
        model = PropsModel()
        sw = _sw(model)

        result = add_configuration(sw, "E2E_CFG")
        self.assertTrue(result["success"])
        self.assertIn("E2E_CFG", result["data"]["configurations"])

    def test_duplicate_and_validation(self):
        model = PropsModel()  # AddConfiguration mock never appends on dup
        sw = _sw(model)
        self.assertEqual(
            add_configuration(sw, "")["error"]["code"], "INVALID_PARAMETER"
        )
        model.duplicate = True
        model.AddConfiguration = lambda *a: None  # name never appears
        result = add_configuration(sw, "X")
        self.assertFalse(result["success"])
        self.assertIn("rejected", result["message"])

    def test_com_errors_are_structured(self):
        sw = Mock()
        sw.get_active_document.side_effect = RuntimeError("COM failed")
        self.assertFalse(add_configuration(sw, "X")["success"])


class TestNotRunningPaths(unittest.TestCase):
    def test_all_tools_report_not_running(self):
        from solidworks_mcp.solidworks_api.app import SolidWorksNotRunningError

        sw = Mock()
        sw.get_active_document.side_effect = SolidWorksNotRunningError("not running")
        calls = [
            lambda: set_material(sw, "合金钢"),
            lambda: get_material(sw),
            lambda: set_custom_property(sw, "a", "b"),
            lambda: get_custom_properties(sw),
            lambda: add_equation(sw, '"x" = 1'),
            lambda: list_equations(sw),
            lambda: add_configuration(sw, "X"),
        ]
        for call in calls:
            self.assertFalse(call()["success"])

    def test_models_without_configurations_are_reported(self):
        model = PropsModel()
        model.configs = []  # degenerate: no configurations
        sw = _sw(model)
        self.assertFalse(set_material(sw, "合金钢")["success"])
        self.assertFalse(get_material(sw)["success"])


if __name__ == "__main__":
    unittest.main()
