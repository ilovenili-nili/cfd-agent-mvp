import math
from cfd_agent.validation.common import check
from cfd_agent.validation.physics import expected_temperature
from cfd_agent.materials import water_saturation_pressure,SATURATION_SOURCE

def residual_check(spec,residuals):
    needed=['continuity','x-velocity','y-velocity','z-velocity','energy']
    if spec.controls.model=='sst': needed+=['k','omega']
    complete=all(n in residuals for n in needed)
    ok=complete and all(math.isfinite(residuals[n]) and 0<=residuals[n]<=
                       (spec.validation.energy_residual if n=='energy' else spec.validation.residual) for n in needed)
    return 'PASS' if ok else ('BLOCKER' if complete else 'UNVERIFIED')

def validate_results(spec,data):
    out=[];p=spec.validation
    required=['mass_imbalance_fraction','energy_imbalance_fraction','temperature_min',
              'temperature_max','outlet_temperature','velocity_max','pressure_min','pressure_max']
    def valid(name): return name in data and isinstance(data[name],(int,float)) and math.isfinite(data[name])
    for name in required:
        v=data.get(name)
        out.append(check('results',name,'UNVERIFIED' if v is None else ('PASS' if valid(name) else 'BLOCKER'),
                         'Finite measured result required',v if valid(name) else None))
    for name,tolerance in [('mass_imbalance_fraction',p.mass_imbalance_fraction),('energy_imbalance_fraction',p.energy_imbalance_fraction)]:
        if valid(name):
            out.append(check('results',name+'_limit','PASS' if 0<=data[name]<=tolerance else 'BLOCKER',
                             f'Nonnegative imbalance fraction must be <= {tolerance}',data[name]))
    if all(valid(k) for k in ['temperature_min','temperature_max']):
        ok=spec.cold.temperature-p.temperature_tolerance<=data['temperature_min']<=data['temperature_max']<=spec.hot.temperature+p.temperature_tolerance
        out.append(check('results','temperature_bounds','PASS' if ok else 'BLOCKER','Adiabatic mixing inlet bounds'))
    if valid('outlet_temperature'):
        delta=abs(data['outlet_temperature']-expected_temperature(spec))
        out.append(check('results','mixing_balance','PASS' if delta<=p.mixing_temperature_warning else 'WARNING',
                         'Outlet vs ideal mass-weighted temperature, K',delta))
    if valid('velocity_max'):
        limit=p.max_velocity_factor*max(spec.cold.velocity,spec.hot.velocity)
        out.append(check('results','velocity_plausibility','BLOCKER' if data['velocity_max']<0 else ('WARNING' if data['velocity_max']>limit else 'PASS'),
                         f'Heuristic velocity screening limit {limit} m/s; project review remains required',data['velocity_max']))
    if valid('pressure_min') and valid('pressure_max'):
        low,high=data['pressure_min']+101325,data['pressure_max']+101325
        status='BLOCKER' if low<=0 or low>high else ('WARNING' if high>p.max_absolute_pressure else 'PASS')
        out.append(check('results','pressure_plausibility',status,
                         'Gauge pressure converted using 101325 Pa operating pressure; broad screening only',low))
        vapor=water_saturation_pressure(max(spec.hot.temperature,273.16))
        out.append(check('results','liquid_phase_margin','WARNING' if low<=vapor else 'PASS',
                         'IAPWS saturation screening at hottest inlet; not a cavitation model. Source: '+SATURATION_SOURCE,low-vapor))
    residuals=data.get('residuals',{})
    out.append(check('results','residuals',residual_check(spec,residuals),
                     'All configured equation residuals must satisfy targets'))
    history=data.get('outlet_temperature_history',[])
    if spec.controls.mode=='steady':
        window=history[-p.monitor_window:]
        stable=len(window)==p.monitor_window and all(math.isfinite(v) for v in window) and max(window)-min(window)<=p.monitor_temperature_span
        out.append(check('results','monitor_stability','PASS' if stable else ('UNVERIFIED' if len(window)<p.monitor_window else 'BLOCKER'),
                         f'Last {p.monitor_window} steady outlet samples must vary <= {p.monitor_temperature_span} K'))
    else:
        steps=data.get('per_step_residuals',[])
        status='UNVERIFIED' if len(steps)!=spec.controls.time_steps else (
            'BLOCKER' if any(residual_check(spec,r)=='BLOCKER' for r in steps) else
            ('UNVERIFIED' if any(residual_check(spec,r)=='UNVERIFIED' for r in steps) else 'PASS'))
        out.append(check('results','per_step_convergence',status,'Every requested timestep requires equation convergence evidence'))
        out.append(check('results','transient_observation_window','WARNING',
                         'Physical observation duration and time-step sensitivity require engineering review; no constant-monitor criterion used'))
    return out
