"""Static 2024 R2 schema checks; these do not replace live Fluent validation."""
from ansys.fluent.core.generated.solver import settings_242 as s
from ansys.fluent.core.generated.meshing import tui_242 as m

def test_2024r2_boundary_paths():
    inlet=s.velocity_inlet.child_object_type
    assert 'momentum' in inlet.child_names
    assert 'velocity' in inlet._child_classes['momentum'].child_names
    assert 'temperature' in inlet._child_classes['thermal'].child_names
    outlet=s.pressure_outlet.child_object_type
    assert 'backflow_turbulent_intensity' in outlet._child_classes['turbulence'].child_names
    assert 'backflow_hydraulic_diameter' in outlet._child_classes['turbulence'].child_names

def test_2024r2_meshing_and_report_paths():
    assert hasattr(m.main_menu.mesh,'check_quality')
    assert hasattr(m.main_menu.mesh,'check_quality_level')
    assert 'surface_names' in s.report_definitions._child_classes['surface'].child_object_type.child_names
    assert 'cell_zones' in s.report_definitions._child_classes['volume'].child_object_type.child_names
    assert 'time_step_count' in s.dual_time_iterate.argument_names

def test_2024r2_version_check():
    from ansys.fluent.core.utils.fluent_version import FluentVersion
    assert FluentVersion('24.2.0')==FluentVersion.v242
    assert not str(FluentVersion.v242).startswith('24.2')
