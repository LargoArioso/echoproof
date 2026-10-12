"""Synthetic single-entry diagnosis cases with explicit question scopes."""
from dataclasses import replace
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from echoproof.model import Mapping
from echoproof.diagnosis import diagnose
from echoproof.report import write_diagnosis_report, STYLE


def main(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    base=Mapping(domain_high='100',pitch_step_cents=1200)
    cases=(('joint','同时保留50和51',base,[50,51],None,None,'reported'),
           ('single','只修复51并检查原边界回归',base,[51],None,None,'reported'),
           ('normalized','逐序列标尺的绝对阈值问题',replace(base,normalization='per_series'),[50],None,None,'reported'),
           ('sampling','漏采样的阈值问题',replace(base,stride=2),[50],None,None,'reported'),
           ('actual','报告映射正确，实际问题仍无法确定',base,[50],[50],[['49.9','50.1']],'admissible_actual'),
           ('capacity','固定单音字母表容量不足',replace(base,pitch_step_cents=5000),[50,51],None,None,'reported'))
    cards=[]
    for name,title,mapping,thresholds,reported,intervals,question in cases:
        result=diagnose(mapping,thresholds,0,100,reported,intervals,question)
        write_diagnosis_report(result,directory/name)
        cards.append('<li><a href="%s/index.html">%s</a></li>' % (name,title))
    (directory/'index.html').write_text('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EchoProof · 综合阈值诊断案例</title><style>'+STYLE+'</style></head><body><main><h1>先确定问题，再看证据与设计。</h1><p>六个合成案例使用同一个诊断入口；观测限制、映射冲突、约束构造及回归边界分别核对。没有人耳结果或全局推荐。</p><ul>'+''.join(cards)+'</ul></main></body></html>',encoding='utf-8')
    print(directory.resolve())


if __name__=='__main__': main(sys.argv[1] if len(sys.argv)>1 else ROOT/'artifacts/diagnosis-cases')
