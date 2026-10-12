"""Synthetic declared-feasible-set cases; no measured confidence intervals."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from echoproof.model import Mapping
from echoproof.uncertainty import observation_certificate
from echoproof.report import write_observation_report, STYLE


def main(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    mapping=Mapping(domain_high='100',pitch_step_cents=1200)
    cases=(('ambiguous','报告值达到，实际两种情况都允许',[50],[['49.9','50.1']]),
           ('determined-true','至少一个下界已经达到阈值',[48,51],[[47,49],[50,52]]),
           ('determined-false','所有上界都低于阈值',[48,49],[[47,49],[48,'49.9']]),
           ('declared-bias','报告值与声明实际区间不同',[100],[[0,1]]))
    links=[]
    for name,title,reported,intervals in cases:
        record=observation_certificate(mapping,reported,intervals,50)
        write_observation_report(record,directory/name)
        links.append('<li><a href="%s/index.html">%s</a>：%s</li>' % (name,title,record['status']))
    body='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EchoProof · 观测可确定性案例</title><style>%s</style></head><body><main><header><div class="eyebrow">ECHOPROOF / DECLARED INTERVAL CASES</div><h1>声音正确编码报告，也未必能确定实际情况。</h1><p class="lead">四个合成案例使用显式声明的区间。它们展示确定真、确定假和无法确定，以及报告值可能存在声明偏差的情况。</p></header><p class="note">区间的全部组合假定可行，没有概率、真人结果或真实来源覆盖率。这些区间没有来自NOAA不确定度列，也不作为测量保证界。</p><ul>%s</ul></main></body></html>''' % (STYLE,''.join(links))
    (directory/'index.html').write_text(body,encoding='utf-8')
    print(directory.resolve())


if __name__=='__main__': main(sys.argv[1] if len(sys.argv)>1 else ROOT/'artifacts/observation-uncertainty')
