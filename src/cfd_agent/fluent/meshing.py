import re
from pathlib import Path
from cfd_agent.validation.mesh import validate_mesh
from cfd_agent.validation.common import gate

FLOAT=r'([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)'

def metrics_from_log(text):
    """Conservative extraction: unknown wording is missing evidence, never a passing default."""
    patterns={'min_volume':rf'Minimum\s+(?:cell\s+)?volume\s*[:=]\s*{FLOAT}',
              'max_skewness':rf'Maximum\s+(?:cell\s+)?skewness\s*[:=]\s*{FLOAT}',
              'min_orthogonal_quality':rf'Minimum\s+Orthogonal\s+Quality\s*[:=]\s*{FLOAT}',
              'max_aspect_ratio':rf'Maximum\s+Aspect\s+Ratio\s*[:=]\s*{FLOAT}'}
    result={}
    for name,p in patterns.items():
        matches=re.findall(p,text,re.I)
        if matches: result[name]=float(matches[-1])
    return result

def generate_mesh(session,spec,step_path,mesh_path):
    workflow=session.workflow
    workflow.InitializeWorkflow(WorkflowType='Watertight Geometry')
    tasks=workflow.TaskObject
    def execute(name,args=None):
        task=tasks[name]
        if args: task.Arguments.set_state(args)
        task.Execute()
    execute('Import Geometry',{'FileName':str(step_path.resolve()),'LengthUnit':'mm'})
    execute('Generate the Surface Mesh',{'CFDSurfaceMeshControls':{'MaxSize':spec.controls.mesh_size*1000, 'MinSize':spec.controls.mesh_size*250}})
    execute('Describe Geometry',{'SetupType':'The geometry consists of only fluid regions with no voids'})
    # STEP subshape naming is not assumed to survive import: missing labels fail closed.
    boundary=tasks['Update Boundaries']
    args=boundary.Arguments.get_state()
    labels=args.get('BoundaryLabelList',[])
    types=args.get('BoundaryLabelTypeList',[])
    required={'cold_inlet':'velocity-inlet','hot_inlet':'velocity-inlet','mixed_outlet':'pressure-outlet'}
    if not all(n in labels for n in required) or len(types)!=len(labels):
        raise RuntimeError('Imported boundary labels are not preserved. Inspect Meshing import; '
                           'expected cold_inlet, hot_inlet, mixed_outlet. No guessed zone assignment performed.')
    boundary.Arguments.set_state({'BoundaryLabelList':labels,
        'BoundaryLabelTypeList':[required.get(n,'wall') for n in labels]})
    boundary.Execute()
    execute('Update Regions')
    layers=tasks['Add Boundary Layers']
    layers.Arguments.set_state({'NumberOfLayers':5})
    layers.AddChildToTask()
    layers.InsertCompoundChildTask()
    layers.Execute()
    execute('Generate the Volume Mesh',{'VolumeFill':'poly-hexcore'})
    mesh_path.parent.mkdir(parents=True,exist_ok=True)
    session.tui.mesh.check_mesh()
    session.tui.mesh.check_quality_level(1)
    session.tui.mesh.check_quality()
    session.tui.file.write_mesh(str(mesh_path.resolve()))
    return mesh_path
