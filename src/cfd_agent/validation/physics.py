import math
from cfd_agent.validation.common import check

def preflight(spec):
    g,m,c = spec.geometry,spec.material,spec.controls
    checks=[]
    for name,inlet,d in [('cold',spec.cold,g.diameter),('hot',spec.hot,g.branch_diameter)]:
        re=m.density*inlet.velocity*d/m.viscosity
        mismatch=(c.model=='laminar' and re>4000) or (c.model=='sst' and re<2300)
        checks.append(check('physics',name+'_reynolds','WARNING' if mismatch else 'PASS',
                            'Review model selection for inlet Reynolds number' if mismatch else 'Model screening passed',re))
    checks.append(check('material','provenance','WARNING' if not m.measured else 'PASS',m.source))
    spread=max(abs(spec.cold.temperature-m.reference_temperature),abs(spec.hot.temperature-m.reference_temperature))
    checks.append(check('material','constant_properties','WARNING' if spread>10 else 'PASS',
                        'Constant water properties require verification over operating temperatures',spread))
    checks.append(check('physics','single_phase','WARNING',
                        'Liquid-water assumption requires absolute-pressure/temperature and cavitation review'))
    if c.mode=='transient':
        co=max(spec.cold.velocity,spec.hot.velocity)*c.time_step/c.mesh_size
        checks.append(check('physics','estimated_courant','WARNING' if co>1 else 'PASS',
                            'Screening uses nominal mesh size; local cell Courant numbers remain unverified',co))
    return checks

def expected_temperature(spec):
    cold=spec.cold.velocity*spec.geometry.diameter**2
    hot=spec.hot.velocity*spec.geometry.branch_diameter**2
    return (cold*spec.cold.temperature+hot*spec.hot.temperature)/(cold+hot)
