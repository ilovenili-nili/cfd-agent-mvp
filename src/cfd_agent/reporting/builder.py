import json
from pathlib import Path

def write_report(run_dir,spec,record):
    def dump(name,data):
        (run_dir/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    dump('run.json',record.model_dump())
    dump('checks.json',[c.model_dump() for c in record.checks])
    rows=['# CFD工程可信度报告','',f'运行状态：**{record.status}**','',
          '固定算例：左侧冷水入口、下方热水支管、90°弯头上方混合出口。',
          '单相水、光滑绝热壁面、常物性；几何由Python生成，网格由Fluent Meshing生成。','',
          '## 参数与来源','', '```json',spec.model_dump_json(indent=2),'```','',
          '## 分阶段校验','', '| 阶段 | 检查 | 状态 | 值 | 说明 | 证据 |','|---|---|---|---|---|---|']
    for c in record.checks:
        message=c.message.replace('|','/').replace('\n',' ')
        rows.append(f'| {c.stage} | {c.name} | {c.status} | {c.value if c.value is not None else "—"} | {message} | {c.evidence or "—"} |')
    if record.error: rows+=['','## 失败诊断','',record.error]
    rows+=['','## 适用边界','',
           '未执行网格独立性、时间步敏感性和实验验证。仅用于初步工程趋势分析，不能单独用于产品验收。',
           '库朗数仅按入口速度和名义网格尺寸估算；局部速度及近壁网格可能导致更高库朗数。',
           '常物性、绝热壁面及单相假设需要项目复核；默认物性为示例值，不代表已溯源手册数据。',
           '任何UNVERIFIED或BLOCKER项均不构成通过证据。geometry-only不代表网格或求解成功。','',
           '## 产物','', 'spec.json、run.json、checks.json、geometry/、mesh/、case/、logs/、monitors/。',
           '只有实际成功执行的阶段才会产生对应文件；Fluent真实运行状态见run.json。']
    (run_dir/'report.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
