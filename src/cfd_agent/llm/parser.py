import json, os
import httpx
from pydantic import ValidationError
from cfd_agent.schemas import SimulationSpec

class MissingParameters(ValueError):
    def __init__(self, questions):
        self.questions = questions
        super().__init__('; '.join(questions))

def parse_request(text: str, model: str = 'glm-4-flash') -> SimulationSpec:
    key = os.environ.get('GLM_API_KEY') or os.environ.get('ZHIPU_API_KEY')
    if not key:
        raise RuntimeError('Set GLM_API_KEY securely to parse natural language; structured YAML needs no key.')
    schema = SimulationSpec.model_json_schema()
    prompt = ('Extract only explicitly supplied engineering parameters. Convert lengths to m, '
              'temperatures to K, speeds to m/s. Never invent required dimensions or inlet values. '
              'Return JSON {"parameters": {...}, "questions": [Chinese questions for missing required values]}. '
              'Defaults allowed only where the schema specifies defaults. Schema: ' + json.dumps(schema))
    with httpx.Client(timeout=60) as client:
        response = client.post('https://open.bigmodel.cn/api/paas/v4/chat/completions',
            headers={'Authorization': 'Bearer ' + key},
            json={'model':model,'temperature':0,'response_format':{'type':'json_object'},
                  'messages':[{'role':'system','content':prompt},{'role':'user','content':text}]})
        if response.status_code >= 400:
            raise RuntimeError(f'GLM request failed with HTTP {response.status_code}; response body omitted')
        payload = json.loads(response.json()['choices'][0]['message']['content'])
    if payload.get('questions'):
        raise MissingParameters(payload['questions'])
    try:
        return SimulationSpec.model_validate(payload['parameters'])
    except ValidationError as exc:
        raise MissingParameters(['请补充或修正 ' + '.'.join(map(str,e['loc'])) + ': ' + e['msg']
                                 for e in exc.errors()]) from exc
