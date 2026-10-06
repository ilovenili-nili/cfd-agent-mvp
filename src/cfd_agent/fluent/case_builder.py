import math
from cfd_agent.validation.common import check

def configure(session,spec,mesh_path):
    s=session.settings
    s.file.read_mesh(file_name=str(mesh_path.resolve()))
    from cfd_agent.fluent.units import ensure_si_mesh
    unit_check=ensure_si_mesh(session,spec)
    s.setup.general.solver.type='pressure-based'
    s.setup.general.solver.time='steady' if spec.controls.mode=='steady' else 'unsteady-2nd-order'
    s.setup.general.operating_conditions.operating_pressure=101325
    s.setup.general.operating_conditions.gravity.enable=False
    s.setup.models.energy.enabled=True
    s.setup.models.energy.viscous_dissipation=False
    s.setup.models.viscous.model='laminar' if spec.controls.model=='laminar' else 'k-omega'
    if spec.controls.model=='sst': s.setup.models.viscous.k_omega_model='sst'
    materials=s.setup.materials.fluid
    materials.create(name='harness-water')
    water=materials['harness-water']
    for name in ['density','viscosity','specific_heat','thermal_conductivity']:
        value=getattr(spec.material,'conductivity' if name=='thermal_conductivity' else name)
        getattr(water,name).set_state({'option':'constant','value':value})
    zones=s.setup.cell_zone_conditions.fluid
    if len(zones.get_object_names())!=1:
        raise RuntimeError('Expected exactly one fluid cell zone')
    for name in zones.get_object_names(): zones[name].general.material='harness-water'
    bc=s.setup.boundary_conditions
    if set(bc.velocity_inlet.get_object_names())!={'cold_inlet','hot_inlet'} or set(bc.pressure_outlet.get_object_names())!={'mixed_outlet'}:
        raise RuntimeError('Unexpected inlet/outlet zones; manual inspection required')
    for name,inlet,d in [('cold_inlet',spec.cold,spec.geometry.diameter),('hot_inlet',spec.hot,spec.geometry.branch_diameter)]:
        b=bc.velocity_inlet[name]
        b.momentum.velocity.value=inlet.velocity
        b.thermal.temperature.value=inlet.temperature
        if spec.controls.model=='sst':
            b.turbulence.turbulence_specification='Intensity and Hydraulic Diameter'
            b.turbulence.turbulent_intensity=100*inlet.turbulence_intensity
            b.turbulence.hydraulic_diameter=d
    out=bc.pressure_outlet['mixed_outlet']
    out.momentum.gauge_pressure.value=0
    out.thermal.backflow_total_temperature.value=spec.cold.temperature
    if spec.controls.model=='sst':
        out.turbulence.turbulence_specification='Intensity and Hydraulic Diameter'
        out.turbulence.backflow_turbulent_intensity=5
        out.turbulence.backflow_hydraulic_diameter=spec.geometry.diameter
    for name in bc.wall.get_object_names():
        wall=bc.wall[name]
        wall.thermal.thermal_condition='Heat Flux'
        wall.thermal.heat_flux.value=0
    equations=s.solution.monitor.residual.equations
    s.solution.monitor.residual.options.print=True
    for name in equations.get_object_names():
        equations[name].monitor=True
        equations[name].check_convergence=True
        equations[name].absolute_criteria=spec.validation.energy_residual if name=='energy' else spec.validation.residual
    if spec.controls.mode=='transient': s.solution.run_calculation.transient_controls.time_step_size=spec.controls.time_step
    checks=[unit_check]+verify_case(session,spec)
    from cfd_agent.validation.common import gate
    gate(checks)
    s.solution.initialization.hybrid_initialize()
    return checks

def verify_case(session,spec):
    s=session.settings
    values=[('energy',s.setup.models.energy.enabled(),True),
            ('solver_time',s.setup.general.solver.time(),'steady' if spec.controls.mode=='steady' else 'unsteady-2nd-order'),
            ('viscous_model',s.setup.models.viscous.model(),'laminar' if spec.controls.model=='laminar' else 'k-omega')]
    if spec.controls.model=='sst': values.append(('sst',s.setup.models.viscous.k_omega_model(),'sst'))
    values.append(('gravity_disabled',s.setup.general.operating_conditions.gravity.enable(),False))
    values.append(('viscous_dissipation',s.setup.models.energy.viscous_dissipation(),False))
    values.append(('operating_pressure',s.setup.general.operating_conditions.operating_pressure(),101325))
    for name,inlet,d in [('cold_inlet',spec.cold,spec.geometry.diameter),('hot_inlet',spec.hot,spec.geometry.branch_diameter)]:
        b=s.setup.boundary_conditions.velocity_inlet[name]
        values.extend([(name+'_velocity',b.momentum.velocity.value(),inlet.velocity),
                       (name+'_temperature',b.thermal.temperature.value(),inlet.temperature)])
        if spec.controls.model=='sst':
            values.extend([(name+'_intensity_percent',b.turbulence.turbulent_intensity(),100*inlet.turbulence_intensity),
                           (name+'_hydraulic_diameter',b.turbulence.hydraulic_diameter(),d)])
    out=s.setup.boundary_conditions.pressure_outlet['mixed_outlet']
    values.extend([('outlet_pressure',out.momentum.gauge_pressure.value(),0),
                   ('backflow_temperature',out.thermal.backflow_total_temperature.value(),spec.cold.temperature)])
    if spec.controls.model=='sst':
        values.extend([('backflow_intensity_percent',out.turbulence.backflow_turbulent_intensity(),5),
                       ('backflow_hydraulic_diameter',out.turbulence.backflow_hydraulic_diameter(),spec.geometry.diameter)])
    for name in s.setup.boundary_conditions.wall.get_object_names():
        wall=s.setup.boundary_conditions.wall[name]
        values.extend([(name+'_thermal_condition',wall.thermal.thermal_condition(),'Heat Flux'),
                       (name+'_heat_flux',wall.thermal.heat_flux.value(),0)])
    for name in s.solution.monitor.residual.equations.get_object_names():
        target=spec.validation.energy_residual if name=='energy' else spec.validation.residual
        values.append((name+'_criterion',s.solution.monitor.residual.equations[name].absolute_criteria(),target))
    if spec.controls.mode=='transient': values.append(('time_step',s.solution.run_calculation.transient_controls.time_step_size(),spec.controls.time_step))
    for name in ['density','viscosity','specific_heat','thermal_conductivity']:
        target=getattr(spec.material,'conductivity' if name=='thermal_conductivity' else name)
        values.append((name,getattr(s.setup.materials.fluid['harness-water'],name).value(),target))
    for name in s.setup.cell_zone_conditions.fluid.get_object_names():
        values.append(('zone_material',s.setup.cell_zone_conditions.fluid[name].general.material(),'harness-water'))
    return [check('case',name,'PASS' if (math.isclose(actual,expected,rel_tol=1e-8,abs_tol=1e-10)
                   if isinstance(expected,(int,float)) and not isinstance(expected,bool) else actual==expected) else 'BLOCKER',
                   f'Expected {expected}; read back {actual}') for name,actual,expected in values]
