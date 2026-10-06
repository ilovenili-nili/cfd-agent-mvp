import json,time
from cfd_agent.fluent.results import Reports,residuals_from_log
from cfd_agent.validation.runtime import monitor

def solve(session,spec,run_dir):
    reports=Reports(session)
    history=[];steps=[];start=time.monotonic()
    calc=session.settings.solution.run_calculation
    transcript=run_dir/'logs'/'solver.log'
    offset=0
    def sample():
        nonlocal offset
        text=transcript.read_text(errors='replace') if transcript.exists() else ''
        segment=text[offset:];offset=len(text)
        monitor(segment,start,spec.controls.max_runtime_seconds)
        data=reports.sample()
        history.append(data['outlet_temperature'])
        (run_dir/'monitors'/'progress.json').write_text(json.dumps({'samples':history,'latest':data},indent=2,allow_nan=False),encoding='utf-8')
        return residuals_from_log(segment)
    if spec.controls.mode=='steady':
        remaining=spec.controls.iterations
        while remaining:
            monitor('',start,spec.controls.max_runtime_seconds)
            batch=min(10,remaining)
            calc.iterate(iter_count=batch)
            sample();remaining-=batch
    else:
        for _ in range(spec.controls.time_steps):
            monitor('',start,spec.controls.max_runtime_seconds)
            calc.dual_time_iterate(time_step_count=1,max_iter_per_step=spec.controls.iterations_per_step)
            steps.append(sample())
    result=reports.finalize(reports.sample())
    result['outlet_temperature_history']=history
    result['per_step_residuals']=steps
    session.settings.file.write_case_data(file_name=str((run_dir/'case'/'mixing_tee.cas.h5').resolve()))
    session.transcript.stop()
    text=transcript.read_text(errors='replace')
    monitor(text,start,spec.controls.max_runtime_seconds)
    result['residuals']=residuals_from_log(text)
    return result
