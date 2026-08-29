"""N2: capabilities/docstring 与实现同步的防漂移契约。"""
import json
import unittest

from solidworks_mcp import server
from solidworks_mcp.solidworks_api.design import DESIGN_PLAN_OPERATIONS


def _registered():
    return {t.name: t for t in server.mcp._tool_manager.list_tools()}


class TestCapabilitiesSync(unittest.TestCase):
    def test_execute_plan_docstring_lists_all_operations(self):
        desc = _registered()["solidworks_design_execute_plan"].description
        for op in DESIGN_PLAN_OPERATIONS:
            self.assertIn(op, desc)

    def test_capabilities_json_lists_all_operations(self):
        caps_text = json.dumps(server._capabilities(), ensure_ascii=False)
        for op in DESIGN_PLAN_OPERATIONS:
            self.assertIn(op, caps_text)

    def test_example_types_match_operations(self):
        examples = server._capabilities()["design_plan_operations"]
        self.assertEqual({e["type"] for e in examples}, set(DESIGN_PLAN_OPERATIONS))

    def test_no_stale_negations_for_registered_domains(self):
        registered_domains = {
            "drawing": "solidworks_drawing_",
            "sheet metal": "solidworks_sheet_metal_",
            "assembly": "solidworks_assembly_",
        }
        caps = server._capabilities()
        for line in caps["limitations"]:
            if "not yet" not in line:
                continue
            for domain, prefix in registered_domains.items():
                if domain in line.lower():
                    self.assertFalse(
                        any(t.startswith(prefix) for t in caps["tools"]),
                        f"stale limitation: {line!r}",
                    )

    def test_add_mate_states_unit_semantics(self):
        desc = _registered()["solidworks_assembly_add_mate"].description
        self.assertIn("degrees", desc)
        self.assertIn("millimeter", desc.lower())


if __name__ == "__main__":
    unittest.main()
