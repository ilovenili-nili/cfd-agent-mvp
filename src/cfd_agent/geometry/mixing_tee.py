import math
from pathlib import Path
import cadquery as cq
from cfd_agent.schemas import Geometry

def build_geometry(g: Geometry, output: Path):
    """XY plane: cold +X, hot +Y, mixed outlet +Y; Z is transverse."""
    # OpenCASCADE STEP exporter declares millimetres: build in mm explicitly.
    g=g.model_copy(update={name:getattr(g,name)*1000 for name in
                          ['diameter','branch_diameter','bend_radius','inlet_length','outlet_length','branch_length']})
    r, d = g.bend_radius, g.diameter
    arc = cq.Edge.makeCircle(r, (0,r,0), (0,0,1), 270, 360)
    wire = cq.Wire.assembleEdges([
        cq.Edge.makeLine((-g.inlet_length,0,0),(0,0,0)), arc,
        cq.Edge.makeLine((r,r,0),(r,r+g.outlet_length,0))])
    main = cq.Workplane('YZ', origin=(-g.inlet_length,0,0)).circle(d/2).sweep(wire)
    angle = math.radians(g.junction_angle)
    x, y = r*math.sin(angle), r*(1-math.cos(angle))
    start_y = y - d/2 - g.branch_length
    branch = cq.Solid.makeCylinder(g.branch_diameter/2, y-start_y,
                                   (x,start_y,0),(0,1,0))
    fluid = main.union(cq.Workplane().newObject([branch])).clean()
    shape = fluid.val()
    if not shape.isValid() or len(fluid.solids().vals()) != 1 or shape.Volume() <= 0:
        raise ValueError('Geometry is invalid or not a single connected solid')
    ports = {'cold_inlet':[-g.inlet_length,0,0], 'hot_inlet':[x,start_y,0],
             'mixed_outlet':[r,r+g.outlet_length,0]}
    caps = {}
    for name, point in ports.items():
        candidates = [f for f in shape.Faces() if f.geomType() == 'PLANE' and
                      (f.Center()-cq.Vector(*point)).Length < 1e-7]
        if len(candidates) != 1:
            raise ValueError(f'Cannot uniquely identify boundary {name}')
        face=candidates[0]
        expected_area=math.pi*(g.branch_diameter if name=='hot_inlet' else g.diameter)**2/4
        if not math.isclose(face.Area(),expected_area,rel_tol=1e-6):
            raise ValueError(f'Boundary area inconsistent for {name}')
        caps[name] = face
    if len([f for f in shape.Faces() if f.geomType() == 'PLANE']) != 3:
        raise ValueError('Unexpected planar end faces')
    output.parent.mkdir(parents=True, exist_ok=True)
    assembly = cq.Assembly(fluid, name='fluid_domain')
    for name, face in caps.items():
        assembly.addSubshape(face, name=name)
    assembly.export(str(output), exportType='STEP', mode='default')
    return {'volume_m3':shape.Volume()/1e9,'ports':{name:[v/1000 for v in point] for name,point in ports.items()},
            'step_length_unit':'mm','faces':len(shape.Faces()),
            'boundary_names_require_fluent_verification':True}
