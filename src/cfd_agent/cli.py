import argparse,json,sys
from pathlib import Path
import yaml
from cfd_agent.schemas import SimulationSpec
from cfd_agent.llm.parser import parse_request,MissingParameters

def main():
    parser=argparse.ArgumentParser(description='Fixed mixing-elbow CFD engineering harness')
    sub=parser.add_subparsers(dest='command',required=True)
    doctor=sub.add_parser('doctor',help='Report local prerequisite presence without exposing credentials')
    doctor.add_argument('--launch',action='store_true',help='Actually launch and close local Fluent 2024 R2 solver')
    p=sub.add_parser('parse',help='GLM natural-language extraction')
    p.add_argument('request',type=Path);p.add_argument('--output',type=Path,default=Path('parsed-spec.json'))
    p.add_argument('--model',default='glm-4-flash')
    r=sub.add_parser('run',help='Run structured simulation specification')
    r.add_argument('spec',type=Path);r.add_argument('--geometry-only',action='store_true')
    r.add_argument('--rules',type=Path,help='Validation threshold overrides as YAML')
    r.add_argument('--output',type=Path,default=Path('runs'))
    args=parser.parse_args()
    try:
        if args.command=='doctor':
            from cfd_agent.fluent.session import diagnose
            info=diagnose()
            if args.launch:
                import tempfile
                from cfd_agent.fluent.session import launch
                with tempfile.TemporaryDirectory(prefix='cfd-doctor-') as directory:
                    root=Path(directory);(root/'logs').mkdir()
                    with launch('solver',1,root) as session:
                        info['actual_launch']='PASS'
                        info['fluent_version']=str(session.get_fluent_version())
            print(json.dumps(info,ensure_ascii=False,indent=2));return 0
        if args.command=='parse':
            spec=parse_request(args.request.read_text(encoding='utf-8'),args.model)
            args.output.write_text(spec.model_dump_json(indent=2),encoding='utf-8')
            print(args.output);return 0
        data=yaml.safe_load(args.spec.read_text(encoding='utf-8'))
        if args.rules:
            data['validation']={**data.get('validation',{}), **yaml.safe_load(args.rules.read_text(encoding='utf-8'))}
        spec=SimulationSpec.model_validate(data)
        from cfd_agent.orchestrator import run
        folder,record=run(spec,args.output,args.geometry_only)
        print(f'{record.status}: {folder}')
        return 1 if record.status in ['failed','results_not_validated'] else 0
    except MissingParameters as exc:
        print(json.dumps({'status':'needs_input','questions':exc.questions},ensure_ascii=False,indent=2))
        return 2
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}',file=sys.stderr);return 1

if __name__=='__main__':
    raise SystemExit(main())
