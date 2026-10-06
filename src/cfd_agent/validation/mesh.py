import math
from cfd_agent.schemas import ValidationPolicy
from cfd_agent.validation.common import check

def validate_mesh(metrics, policy=None):
    policy=policy or ValidationPolicy()
    rules={'min_volume':(lambda v:v>0,'All cell volumes must be positive'),
           'max_skewness':(lambda v:0<=v<policy.max_skewness,f'Maximum skewness must be below {policy.max_skewness}'),
           'min_orthogonal_quality':(lambda v:policy.min_orthogonal_quality<=v<=1,f'Minimum orthogonal quality must be at least {policy.min_orthogonal_quality}')}
    out=[]
    for name,(predicate,message) in rules.items():
        v=metrics.get(name)
        out.append(check('mesh',name,'UNVERIFIED' if v is None else ('PASS' if math.isfinite(v) and predicate(v) else 'BLOCKER'),message,v if v is not None and math.isfinite(v) else None))
    ar=metrics.get('max_aspect_ratio')
    out.append(check('mesh','max_aspect_ratio','UNVERIFIED' if ar is None else ('BLOCKER' if not math.isfinite(ar) or ar<1 else ('WARNING' if ar>policy.aspect_ratio_warning else 'PASS')),
                     'High aspect ratio requires near-wall interpretation',ar if ar is not None and math.isfinite(ar) else None))
    return out
