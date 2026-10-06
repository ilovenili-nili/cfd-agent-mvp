import math
import numpy as np
from cfd_agent.validation.common import check

def scaling_factor(vertices,inlet_length):
    points=np.asarray(vertices)
    if points.ndim!=2 or points.shape[1]!=3 or points.shape[0]<3 or not np.all(np.isfinite(points)):
        raise ValueError('Cold inlet vertices unavailable or invalid')
    x=float((points[:,0].min()+points[:,0].max())/2)
    ratio=-x/inlet_length
    if math.isclose(ratio,1,rel_tol=1e-4):return 1.
    if math.isclose(ratio,1000,rel_tol=1e-4):return .001
    raise ValueError(f'Unexpected cold-inlet position ratio {ratio}; cannot infer safe scale')

def ensure_si_mesh(session,spec):
    from ansys.fluent.core.fields.field_data_interfaces import SurfaceFieldDataRequest,SurfaceDataType
    ports=['cold_inlet','hot_inlet','mixed_outlet']
    request=SurfaceFieldDataRequest(surfaces=ports,data_types=[SurfaceDataType.Vertices])
    fields=session.fields.field_data
    data=fields.get_field_data(request)
    factor=scaling_factor(data['cold_inlet'].vertices,spec.geometry.inlet_length)
    if factor!=1:
        session.settings.mesh.scale(x_scale=factor,y_scale=factor,z_scale=factor)
        data=fields.get_field_data(request)
    g=spec.geometry
    angle=math.radians(g.junction_angle)
    x,y=g.bend_radius*math.sin(angle),g.bend_radius*(1-math.cos(angle))
    expected={'cold_inlet':([-g.inlet_length,0,0],[0,g.diameter,g.diameter]),
              'hot_inlet':([x,y-g.diameter/2-g.branch_length,0],[g.branch_diameter,0,g.branch_diameter]),
              'mixed_outlet':([g.bend_radius,g.bend_radius+g.outlet_length,0],[g.diameter,0,g.diameter])}
    for name,(center,span) in expected.items():
        points=np.asarray(data[name].vertices)
        if points.ndim!=2 or points.shape[1]!=3 or len(points)<3 or not np.all(np.isfinite(points)):
            raise ValueError('Invalid vertices for '+name)
        actual_center=(points.min(axis=0)+points.max(axis=0))/2
        actual_span=points.max(axis=0)-points.min(axis=0)
        if not np.allclose(actual_center,center,atol=g.diameter*.02,rtol=0) or not np.allclose(actual_span,span,atol=g.diameter*.02,rtol=0):
            raise ValueError('SI port coordinates/diameter mismatch for '+name)
    return check('case','mesh_si_units_and_ports','PASS',
                 f'All port positions and diameters checked in m; applied scale factor {factor}',factor)
