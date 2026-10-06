from cfd_agent.schemas import CheckResult

def check(stage,name,status,message,value=None,evidence=None):
    return CheckResult(stage=stage,name=name,status=status,message=message,value=value,evidence=evidence)

def gate(checks):
    blocking = [c for c in checks if c.status in ('BLOCKER','UNVERIFIED')]
    if blocking:
        raise RuntimeError('Validation gate: ' + '; '.join(c.name + ': ' + c.message for c in blocking))
