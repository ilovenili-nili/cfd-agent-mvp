import json
from pathlib import Path
import pytest,yaml,httpx
from cfd_agent.llm.parser import parse_request,MissingParameters

class Client:
    def __init__(self,response):self.response=response
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def post(self,*args,**kwargs):
        assert kwargs['headers']['Authorization']=='Bearer test-only'
        assert kwargs['json']['temperature']==0
        return self.response

def configure(monkeypatch,payload,status=200):
    monkeypatch.setenv('GLM_API_KEY','test-only')
    response=httpx.Response(status,json={'choices':[{'message':{'content':json.dumps(payload)}}]})
    monkeypatch.setattr('cfd_agent.llm.parser.httpx.Client',lambda **kw:Client(response))

def test_glm_missing_questions(monkeypatch):
    configure(monkeypatch,{'questions':['请补充主管内径'],'parameters':{}})
    with pytest.raises(MissingParameters) as e:parse_request('冷热混合')
    assert e.value.questions==['请补充主管内径']

def test_glm_structured_success(monkeypatch):
    parameters=yaml.safe_load(Path('examples/mixing_tee.yaml').read_text())
    configure(monkeypatch,{'questions':[],'parameters':parameters})
    assert parse_request('完整工况').geometry.diameter==.05

def test_glm_schema_missing_even_if_model_claims_complete(monkeypatch):
    configure(monkeypatch,{'questions':[],'parameters':{'geometry':{}}})
    with pytest.raises(MissingParameters):parse_request('工况')

def test_glm_http_error_omits_body(monkeypatch):
    configure(monkeypatch,{},401)
    with pytest.raises(RuntimeError,match='HTTP 401'):parse_request('工况')

def test_glm_missing_key(monkeypatch):
    monkeypatch.delenv('GLM_API_KEY',raising=False);monkeypatch.delenv('ZHIPU_API_KEY',raising=False)
    with pytest.raises(RuntimeError,match='GLM_API_KEY'):parse_request('工况')
