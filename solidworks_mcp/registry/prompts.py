"""Guided-workflow prompts (registry/prompts, N14) — moved verbatim from server.py."""

from __future__ import annotations


def solidworks_design_part_prompt(requirements: str) -> str:
    """Convert part requirements into conservative, executable MCP calls."""
    return (
        "You are designing a SolidWorks part through solidworks-mcp.\n"
        "Use millimeters for all tool length parameters. First call "
        "solidworks_design_capabilities and inspect the active document. Prefer one "
        "solidworks_design_execute_plan call for supported geometry. Do not invent "
        "dimensions, planes, feature names, or overwrite approval. If required "
        "geometry is unsupported, explain the exact missing operation and ask only "
        "for the parameter needed to continue. Verify the result with feature and "
        "mass-property tools before export.\n"
        "Perception workflow for refinement rounds: "
        "solidworks_features_get_details lists every feature with its dimensions in "
        "mm; solidworks_dimension_set edits one (angles unsupported), "
        "solidworks_feature_delete removes one; solidworks_get_bounding_box and "
        "solidworks_measure_distance verify extents; solidworks_part_list_faces "
        "gives named faces for solidworks_part_apply_fillet/_chamfer/_shell; "
        "solidworks_part_set_material attaches a material (Chinese library names, "
        "e.g. 合金钢) and add_equation links dimensions parametrically.\n\n"
        f"Design requirements:\n{requirements}"
    )


def solidworks_assembly_prompt(requirements: str) -> str:
    """Guide mating components in an assembly via named entities."""
    return (
        "You are assembling components in SolidWorks through solidworks-mcp.\n"
        "Workflow: solidworks_assembly_new creates the assembly (optionally saving "
        "it), then solidworks_assembly_add_component inserts each saved part "
        "(millimetre coordinates). Before mating, run solidworks_part_list_faces "
        "on the referenced parts to obtain stable face names (Face0, Face1, ...). "
        "solidworks_assembly_add_mate then mates two component-qualified entities "
        "(e.g. \"Face2@box-1\" and \"Face0@cyl-1\") — entity names must carry the "
        "component instance and are matched as \"<name>@<assembly title>\" first. "
        "Verify with solidworks_assembly_check_interference (empty means no "
        "collisions; each hit carries volume_mm3 plus center_mm/bbox_mm for "
        "locating the overlap) and solidworks_assembly_get_bom for the part "
        "list (per-part volume_mm3/mass_g/material). Repair loop: "
        "solidworks_assembly_move_component / _rotate_component transform "
        "the offending component, then re-check interference; "
        "solidworks_assembly_delete_mate removes one mate by exact name. "
        "All lengths are millimetres.\n\n"
        f"Assembly requirements:\n{requirements}"
    )


def solidworks_drawing_prompt(requirements: str) -> str:
    """Guide producing a dimensioned drawing sheet from a saved part."""
    return (
        "You are producing an engineering drawing through solidworks-mcp.\n"
        "Workflow: solidworks_drawing_create_from_part takes a SAVED .sldprt path "
        "and creates a GB A3 sheet with three projected views (the referenced "
        "part is opened automatically). Then solidworks_drawing_insert_dimensions "
        "pulls the model's dimensions into the views. Export with "
        "solidworks_drawing_export_pdf and solidworks_drawing_export_png (paths "
        "under allowed_root; overwrite needs confirmation). The drawing holds the "
        "part open afterwards — close documents when done.\n\n"
        f"Drawing requirements:\n{requirements}"
    )


def solidworks_csg_rebuild_prompt(requirements: str) -> str:
    """Rebuild a cross-engine CSG scene as an SW feature tree."""
    return (
        "You are rebuilding an aicad CSG scene in SolidWorks through "
        "solidworks-mcp.\n"
        "Call solidworks_features_rebuild_csg with one plan (version 1, "
        "units mm; ops: box, cylinder, cone, cut_cylinder). Contract: the "
        "first op must be box (it creates the part and its stock at the "
        "origin); solid ops stack on the axis -- at.z must equal the current "
        "stack top (heights add up); cut_cylinder keeps its x/y offset and "
        "cuts down from the top; a failed plan rolls back atomically, so fix "
        "only the offending op and re-run. Feature names must be unique.\n"
        "Example 4-op plan:\n"
        '{"version": 1, "units": "mm", "operations": [\n'
        '  {"op": "box", "name": "base", "size": [80, 60, 10], "at": [0, 0, 0]},\n'
        '  {"op": "cylinder", "name": "boss", "diameter": 24, "height": 14, '
        '"at": [0, 0, 10]},\n'
        '  {"op": "cut_cylinder", "name": "hole1", "diameter": 8, '
        '"at": [20, 0, 24], "through": true},\n'
        '  {"op": "cut_cylinder", "name": "hole2", "diameter": 8, '
        '"at": [-20, 0, 24], "depth": 12}]}\n'
        "Verify the result with solidworks_features_list and "
        "solidworks_part_get_mass_properties before saving.\n\n"
        f"CSG scene to rebuild:\n{requirements}"
    )


def solidworks_parametric_prompt(requirements: str) -> str:
    """Drive a part family via material, equations, dimensions, configurations."""
    return (
        "You are driving a parametric part family through solidworks-mcp.\n"
        "Workflow: open or build the base part, then solidworks_part_set_material "
        "(Chinese library names, e.g. 合金钢), solidworks_part_add_equation to "
        "link dimensions parametrically (e.g. Height = 2 * Thickness), "
        "solidworks_dimension_set to drive one driving dimension per variant, "
        "and solidworks_part_add_configuration to snapshot each family member; "
        "activate the next configuration and repeat the dimension edits. "
        "Verify every variant with solidworks_part_get_mass_properties and "
        "export with solidworks_file_export_step. All lengths are "
        "millimeters.\n\n"
        f"Part family requirements:\n{requirements}"
    )


def register(mcp) -> None:
    mcp.prompt(title="Design a SolidWorks part")(solidworks_design_part_prompt)
    mcp.prompt(title="Assemble parts with mates")(solidworks_assembly_prompt)
    mcp.prompt(title="Create a drawing from a part")(solidworks_drawing_prompt)
    mcp.prompt(title="Rebuild an aicad CSG plan")(solidworks_csg_rebuild_prompt)
    mcp.prompt(title="Drive a part family parametrically")(solidworks_parametric_prompt)
