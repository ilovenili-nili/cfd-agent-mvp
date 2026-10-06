from pathlib import Path
import math
import pytest,yaml
from pydantic import ValidationError
from cfd_agent.schemas import SimulationSpec
from cfd_agent.validation.physics import preflight,expected_temperature
from cfd_agent.validation.mesh import validate_mesh
from cfd_agent.validation.common import gate
from cfd_agent.validation.results import validate_results
from cfd_agent.fluent.meshing import metrics_from_log
from cfd_agent.fluent.results import residuals_from_log

@pytest.fixture
def spec():
    return SimulationSpec.model_validate(yaml.safe_load(Path('examples/mixing_tee.yaml').read_text()))

def test_missing_dimension(spec):
    data=spec.model_dump();del data['geometry']['diameter']
    with pytest.raises(ValidationError): SimulationSpec.model_validate(data)

def test_transient_needs_step(spec):
    data=spec.model_dump();data['controls']['mode']='transient'
    with pytest.raises(ValidationError): SimulationSpec.model_validate(data)

def test_bend_self_intersection(spec):
    data=spec.model_dump();data['geometry']['bend_radius']=.01
    with pytest.raises(ValidationError): SimulationSpec.model_validate(data)

def test_nonfinite_input(spec):
    data=spec.model_dump();data['cold']['temperature']=float('nan')
    with pytest.raises(ValidationError): SimulationSpec.model_validate(data)

def test_unknown_parameter(spec):
    data=spec.model_dump();data['controls']['typo']=1
    with pytest.raises(ValidationError): SimulationSpec.model_validate(data)

def test_ideal_mixing(spec):
    assert expected_temperature(spec)==pytest.approx((293.15+333.15*.24)/1.24)

def test_material_risk(spec):
    assert any(c.name=='provenance' and c.status=='WARNING' for c in preflight(spec))

def test_mesh_missing_blocks():
    with pytest.raises(RuntimeError):gate(validate_mesh({}))

def test_negative_volume_blocks():
    metrics=dict(min_volume=-1,max_skewness=.5,min_orthogonal_quality=.3,max_aspect_ratio=10)
    with pytest.raises(RuntimeError):gate(validate_mesh(metrics))

def test_mesh_log():
    text='Minimum cell volume: 1e-9\nMaximum skewness = 0.7\nMinimum Orthogonal Quality = 0.25\nMaximum Aspect Ratio = 20'
    gate(validate_mesh(metrics_from_log(text)))

def test_missing_results_not_pass(spec):
    assert any(c.status=='UNVERIFIED' for c in validate_results(spec,{}))

def test_unphysical_temperature(spec):
    checks=validate_results(spec,{'temperature_min':290,'temperature_max':500})
    assert any(c.name=='temperature_bounds' and c.status=='BLOCKER' for c in checks)

def test_residual_parser():
    r=residuals_from_log('iter continuity x-velocity energy\n1 1e-3 1e-4 1e-8 0:00\n2 1e-5 1e-6 1e-9 0:00')
    assert r['continuity']==1e-5 and r['energy']==1e-9

def test_geometry_roundtrip(spec,tmp_path):
    import cadquery as cq
    from cfd_agent.geometry.mixing_tee import build_geometry
    path=tmp_path/'fluid.step'
    info=build_geometry(spec.geometry,path)
    restored=cq.importers.importStep(str(path))
    assert len(restored.solids().vals())==1
    assert restored.val().isValid()
    assert restored.val().Volume()/1e9==pytest.approx(info['volume_m3'],rel=1e-5)
    assert set(info['ports'])=={'cold_inlet','hot_inlet','mixed_outlet'}

def test_geometry_only_report(spec,tmp_path):
    from cfd_agent.orchestrator import run
    folder,record=run(spec,tmp_path,geometry_only=True)
    assert record.status=='geometry_only_complete'
    assert (folder/'report.md').exists()
    assert any(c.stage=='mesh' and c.status=='UNVERIFIED' for c in record.checks)
    assert not list((folder/'case').glob('*.cas.h5'))

def test_infinite_dimension_rejected(spec):
    data=spec.model_dump();data['geometry']['diameter']=float('inf')
    with pytest.raises(ValidationError):SimulationSpec.model_validate(data)

def test_pressure_nonphysical(spec):
    checks=validate_results(spec,{'pressure_min':-200000,'pressure_max':0})
    assert any(c.name=='pressure_plausibility' and c.status=='BLOCKER' for c in checks)

def test_transient_checks_each_step(spec):
    data=spec.model_dump();data['controls'].update(mode='transient',time_step=.001,time_steps=2)
    transient=SimulationSpec.model_validate(data)
    checks=validate_results(transient,{'per_step_residuals':[{'continuity':1}]})
    assert any(c.name=='per_step_convergence' and c.status=='UNVERIFIED' for c in checks)
    assert not any(c.name=='monitor_stability' for c in checks)

def test_runtime_divergence():
    from cfd_agent.validation.runtime import monitor
    import time
    with pytest.raises(RuntimeError):monitor('Divergence detected in AMG solver',time.monotonic(),60)

def test_runtime_timeout():
    from cfd_agent.validation.runtime import monitor
    import time
    with pytest.raises(TimeoutError):monitor('',time.monotonic()-20,1)

def test_water_saturation():
    from cfd_agent.materials import water_saturation_pressure
    assert water_saturation_pressure(373.15)==pytest.approx(101418,rel=.001)
    assert water_saturation_pressure(293.15)==pytest.approx(2339,rel=.001)

def test_policy_override(spec):
    from cfd_agent.schemas import ValidationPolicy
    metrics=dict(min_volume=1e-9,max_skewness=.8,min_orthogonal_quality=.3,max_aspect_ratio=10)
    with pytest.raises(RuntimeError):gate(validate_mesh(metrics,ValidationPolicy(max_skewness=.7)))

def test_mesh_si_scaling():
    from cfd_agent.fluent.units import scaling_factor
    assert scaling_factor([[-150,0,0],[-150,1,0],[-150,0,1]],.15)==.001
    assert scaling_factor([[-.15,0,0],[-.15,.01,0],[-.15,0,.01]],.15)==1
    with pytest.raises(ValueError):scaling_factor([[12,0,0],[12,1,0],[12,0,1]],.15)

def test_mesh_failure_preserves_report(spec,tmp_path,monkeypatch):
    from contextlib import contextmanager
    from cfd_agent.orchestrator import run
    @contextmanager
    def unavailable(*args,**kwargs):
        raise RuntimeError('Test-only local Fluent unavailable')
        yield
    monkeypatch.setattr('cfd_agent.fluent.session.launch',unavailable)
    folder,record=run(spec,tmp_path)
    assert record.status=='failed'
    assert 'mesh:' in record.error
    assert (folder/'geometry'/'fluid_domain.step').exists()
    assert (folder/'report.md').exists()
    assert not (folder/'case'/'mixing_tee.cas.h5').exists()
