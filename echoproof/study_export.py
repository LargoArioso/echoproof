"""Export opaque trial audio, participant sheets and a separate researcher key."""
import csv
import json
from pathlib import Path
from .audio import wav_bytes
from .model import Render, Event
from .study import verify_study
from .serialization import same_json
from .semantic_cues import legend


def render(record):
    return Render(tuple(Event(**e) for e in record['events']),record['duration_ms'])


def write_study(record,directory):
    if not verify_study(record):
        raise ValueError('Invalid study-material definition')
    directory=Path(directory)
    if directory.exists() and (not directory.is_dir() or any(directory.iterdir())):
        raise ValueError('Study destination must be empty; existing responses and materials are preserved')
    directory.mkdir(parents=True,exist_ok=True)
    researcher=directory/'researcher';researcher.mkdir(exist_ok=True)
    (researcher/'materials.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    audio=directory/'audio';audio.mkdir(exist_ok=True)
    cases={case['case_id']:case for case in record['cases']}
    for session,rows in record['participant_sessions'].items():
        (directory/(session+'.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        with (directory/(session+'.responses.csv')).open('w',encoding='utf-8',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['participant_id','trial_id','response','response_time_ms'])
            writer.writerows(['',row['trial_id'],'',''] for row in rows)
        for row,key in zip(rows,record['researcher_keys'][session]):
            case=cases[key['case_id']]
            (directory/row['audio']).write_bytes(wav_bytes(render(case[key['condition']])))
    training=directory/'training';training.mkdir(exist_ok=True)
    for index,entry in enumerate(legend()):
        (training/('legend%d.wav'%index)).write_bytes(wav_bytes(render(entry['render'])))
    (training/'legend.json').write_text(json.dumps(legend(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (directory/'PROTOCOL.md').write_text('''# 配对声音材料：尚未开展真人实验

研究问题：固定答案提示是否帮助完成阈值／首尾趋势判断；需要同时考虑播放更长的成本。

一个参与者只使用一个 session。两种 session 使用相同案例和顺序，分别是原始声音与对应任务的固定提示；分组由研究者在收集前随机分配并记录。不是让同一参与者先听答案提示、再猜同一材料的原始声音。两个session的含义在 researcher/materials.json 里；提示可以被听到，不声称参与者无法识别条件。

参与者只收到其 session JSON、对应audio、空白responses表及明确分配的训练材料。不要把researcher目录或未分配的session给参与者：它们包含答案。训练图例有答案词汇；研究者应事先固定两条件各自的教学流程、训练时长和反馈规则，不能把训练差异悄悄算成提示效果。

participant_id仅为研究者指定的不含姓名的编号。本工具不招募、不上传、不记录个人资料。response填写JSON列出的值；毫秒反应时间只在有可靠计时工具时记录，空值保留为空，不凭空补值。

主指标、训练方案、随机分组与排除规则需要在收集前定好。本材料不指定样本量、不提供功效或人类易学性结论。收集之后应同时报告正确率与播放／反应时成本，按参与者和刺激案例处理重复测量；不能把每个重复试次当作独立参与者。

每个选中组有相同原始声音字节，却有多个不同任务答案，各答案重复次数相等。这个构造说明原始事件中有歧义，不提供真人听觉成绩。材料针对原始审计范围，不能推广到全部图表或所有听众。

校验：`python3 -m echoproof verify researcher/materials.json` 重建材料定义；`python3 -m echoproof check-study .` 核对participant表、训练与试次WAV。空白responses表供使用者填写，校验不会要求它永久为空。
''',encoding='utf-8')
    return directory/'PROTOCOL.md'


def check_study(directory):
    directory=Path(directory)
    record=json.loads((directory/'researcher/materials.json').read_text(encoding='utf-8'))
    if not verify_study(record):
        raise ValueError('Material definition failed replay')
    cases={case['case_id']:case for case in record['cases']}
    checked=0
    for session,rows in record['participant_sessions'].items():
        if not same_json(rows,json.loads((directory/(session+'.json')).read_text(encoding='utf-8'))):
            raise ValueError('Participant sheet changed')
        for row,key in zip(rows,record['researcher_keys'][session]):
            expected=wav_bytes(render(cases[key['case_id']][key['condition']]))
            if (directory/row['audio']).read_bytes()!=expected:
                raise ValueError('Trial audio differs from its exact definition')
            checked+=1
    if not same_json(legend(),json.loads((directory/'training/legend.json').read_text(encoding='utf-8'))):
        raise ValueError('Training labels or definition changed')
    for index,entry in enumerate(legend()):
        if (directory/'training'/('legend%d.wav'%index)).read_bytes()!=wav_bytes(render(entry['render'])):
            raise ValueError('Training WAV differs from fixed vocabulary')
    return {'trial_wav_verified':checked,'training_wav_verified':len(legend()),'participant_results_inspected':False,
            'scope':'Materials only; response collection or human efficacy not verified.'}
