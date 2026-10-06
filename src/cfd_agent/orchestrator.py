import json, platform, importlib.metadata
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from cfd_agent.schemas import RunRecord
from cfd_agent.geometry.mixing_tee import build_geometry
from cfd_agent.validation.common import check,gate
from cfd_agent.validation.physics import preflight
from cfd_agent.validation.mesh import validate_mesh
from cfd_agent.validation.results import validate_results
from cfd_agent.reporting.builder import write_report

def run(spec,root:Path,geometry_only=False):
    root=root.resolve()
    folder=root/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8])
    folder.mkdir(parents=True)
    for name in ['geometry','mesh','case','logs','monitors']: (folder/name).mkdir()
    (folder/'spec.json').write_text(spec.model_dump_json(indent=2),encoding='utf-8')
    versions={'python':platform.python_version(),'platform':platform.platform()}
    for name in ['cadquery','ansys-fluent-core','pydantic']:
        try: versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: versions[name]='not-installed'
    (folder/'versions.json').write_text(json.dumps(versions,indent=2),encoding='utf-8')
    record=RunRecord()
    stage='requirements'
    try:
        record.checks.append(check(stage,'schema','PASS','Required values, SI units, ranges validated'))
        record.stages.append(stage)
        stage='geometry'
        record.status=stage
        info=build_geometry(spec.geometry,folder/'geometry'/'fluid_domain.step')
        (folder/'geometry'/'metadata.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
        record.checks.append(check(stage,'connected_domain_and_ports','PASS',
                                   'One valid solid, positive volume and exactly three planar port faces',info['volume_m3']))
        record.stages.append(stage)
        record.checks+=preflight(spec)
        gate(record.checks)
        if geometry_only:
            record.status='geometry_only_complete'
            for phase in ['mesh','case','runtime','results']:
                record.checks.append(check(phase,'not_executed','UNVERIFIED','Geometry-only mode: Fluent was not started'))
        else:
            from cfd_agent.fluent.session import launch
            from cfd_agent.fluent.meshing import generate_mesh,metrics_from_log
            from cfd_agent.fluent.case_builder import configure
            from cfd_agent.fluent.runner import solve
            stage='mesh';record.status=stage
            mesh=folder/'mesh'/'fluid_domain.msh.h5'
            with launch('meshing',spec.controls.processors,folder) as session:
                generate_mesh(session,spec,folder/'geometry'/'fluid_domain.step',mesh)
                session.transcript.stop()
            metrics=metrics_from_log((folder/'logs'/'meshing.log').read_text(errors='replace'))
            (folder/'mesh'/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
            record.checks+=validate_mesh(metrics,spec.validation)
            gate(record.checks)
            record.stages.append(stage)
            stage='case';record.status=stage
            with launch('solver',spec.controls.processors,folder) as session:
                versions['fluent']=str(session.get_fluent_version())
                (folder/'versions.json').write_text(json.dumps(versions,indent=2),encoding='utf-8')
                record.checks+=configure(session,spec,mesh)
                gate(record.checks)
                (folder/'case'/'settings.json').write_text(json.dumps(session.settings.setup.get_state(),indent=2),encoding='utf-8')
                record.stages.append(stage)
                stage='runtime';record.status=stage
                results=solve(session,spec,folder)
            record.checks.append(check(stage,'solver_execution','PASS','Solve API returned and result reports were sampled'))
            record.stages.append(stage)
            (folder/'monitors'/'results.json').write_text(json.dumps(results,indent=2,allow_nan=False),encoding='utf-8')
            stage='results';record.status=stage
            record.checks+=validate_results(spec,results)
            record.stages.append(stage)
            record.status='completed_with_risks' if any(c.status!='PASS' for c in record.checks) else 'completed'
            if any(c.status in ('BLOCKER','UNVERIFIED') for c in record.checks): record.status='results_not_validated'
    except Exception as exc:
        record.status='failed'
        record.error=f'{stage}: {type(exc).__name__}: {exc}'
        record.checks.append(check(stage,'execution','BLOCKER',record.error))
    for phase in ['requirements','geometry','mesh','physics','material','case','runtime','results']:
        if not any(c.stage==phase for c in record.checks):
            record.checks.append(check(phase,'not_executed','UNVERIFIED','Stage not reached; no passing evidence'))
    evidence={'requirements':'spec.json','geometry':'geometry/metadata.json','physics':'spec.json',
              'material':'spec.json','mesh':'mesh/metrics.json; logs/meshing.log',
              'case':'case/settings.json; logs/solver.log','runtime':'logs/solver.log; monitors/progress.json',
              'results':'monitors/results.json'}
    for c in record.checks:
        if c.status!='UNVERIFIED':
            paths=evidence.get(c.stage,'').split('; ')
            actual=[path for path in paths if path and (folder/path).exists()]
            c.evidence='; '.join(actual) if actual else 'run.json'
    record.checks.append(check('report','traceability','PASS','Structured input, stage status and check records persisted',evidence='spec.json; run.json; checks.json'))
    write_report(folder,spec,record)
    return folder,record
