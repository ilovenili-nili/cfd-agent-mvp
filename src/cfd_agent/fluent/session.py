from contextlib import contextmanager
from pathlib import Path
import os

def diagnose():
    import shutil
    roots=[n for n in os.environ if n.startswith('AWP_ROOT')]
    return {'fluent_on_path':bool(shutil.which('fluent')),
            'ansys_root_variables':roots,
            'explicit_path_exists':bool(os.environ.get('FLUENT_EXECUTABLE') and Path(os.environ['FLUENT_EXECUTABLE']).is_file()),
            'license_variable_present':bool(os.environ.get('ANSYSLMD_LICENSE_FILE')),
            'glm_key_present':bool(os.environ.get('GLM_API_KEY') or os.environ.get('ZHIPU_API_KEY')),
            'note':'License-variable absence does not prove unavailable license; actual launch is authoritative.'}

@contextmanager
def launch(mode, processors, run_dir):
    import ansys.fluent.core as pyfluent
    kwargs={'mode':mode,'precision':'double','dimension':3,'processor_count':processors,
            'cwd':str(run_dir.resolve()),'start_timeout':120,'cleanup_on_exit':True,
            'product_version':'24.2', 'start_transcript':False}
    if os.environ.get('FLUENT_EXECUTABLE'):
        kwargs['fluent_path']=os.environ['FLUENT_EXECUTABLE']
    try:
        session=pyfluent.launch_fluent(**kwargs)
    except KeyError as exc:
        if exc.args == ('AWP_ROOT242',):
            raise RuntimeError('Fluent 2024 R2 not found. Run this harness on the local Windows machine and set FLUENT_EXECUTABLE to its fluent.exe path.') from exc
        raise
    try:
        from ansys.fluent.core.utils.fluent_version import FluentVersion
        version=session.get_fluent_version()
        if version != FluentVersion.v242:
            raise RuntimeError(f'This adapter targets Fluent 2024 R2; detected {version}')
        session.transcript.start(file_name=str((run_dir/'logs'/f'{mode}.log').resolve()))
        yield session
    finally:
        session.exit()
