import re,time

def monitor(text,start_time,max_seconds):
    if time.monotonic()-start_time>max_seconds:
        raise TimeoutError('Runtime budget exceeded between solver batches; this is not a hard RPC timeout')
    if re.search(r'floating point exception|divergence detected|\b(?:nan|infinity)\b|error:.*fatal',text,re.I):
        raise RuntimeError('Fluent transcript indicates numerical divergence or fatal error')
