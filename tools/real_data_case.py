"""Audit only unmodified rolling windows from an archived public NOAA series."""
import csv
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from echoproof import Mapping, encode
from echoproof.audit import audit_explicit, witness, verify_witness
from echoproof.report import write_report, STYLE, esc, data_table, sound
from echoproof.audio import wav_bytes
from echoproof.tasks import answer

SOURCE_URL='https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_annmean_mlo.csv'
CREDIT='Xin Lan, NOAA/GML, and Ralph Keeling, Scripps Institution of Oceanography; early measurements by C. David Keeling/SIO. Original archive comments retained.'


def read_annual(path):
    raw=Path(path).read_bytes()
    if len(raw)>1024*1024:
        raise ValueError('Dataset exceeds 1 MiB')
    lines=[line for line in raw.decode('utf-8-sig').splitlines() if line and not line.startswith('#')]
    reader=csv.DictReader(lines)
    if reader.fieldnames != ['year','mean','unc']:
        raise ValueError('Unexpected NOAA annual data schema')
    rows=[]
    previous=None
    for row in reader:
        year=int(row['year'])
        value=Fraction(row['mean'])
        uncertainty=Fraction(row['unc'])
        if previous is not None and year != previous+1:
            raise ValueError('Require consecutive annual rows')
        if value<=0 or uncertainty<0:
            raise ValueError('Invalid or missing annual concentration/uncertainty')
        rows.append({'year':year,'mean':row['mean'],'unc':row['unc']})
        previous=year
    if not 3<=len(rows)<=200:
        raise ValueError('Need 3..200 annual observations')
    return raw,rows


def build(path,directory):
    raw,rows=read_annual(path)
    windows=[{'years':[r['year'] for r in rows[i:i+3]],'values':[r['mean'] for r in rows[i:i+3]]} for i in range(len(rows)-2)]
    provenance={'url':SOURCE_URL,'raw_sha256':hashlib.sha256(raw).hexdigest(),'credit':CREDIT,
                'method':'Every consecutive 3-year window, values copied unchanged from archived annual means. No synthetic mutations, scaling, resampling or uncertainty perturbation.',
                'units':'ppm (micromol/mol in dry air)','windows':windows,
                'display_assumptions':'Each window starts at time zero with equal sample spacing. Absolute years and ppm labels are not encoded or spoken.',
                'coverage':'Only these archived rolling windows and exact rounded annual means, not all data or a human auditory result.'}
    mapping=Mapping(normalization='per_series',domain_low='300',domain_high='450')
    audit=audit_explicit(mapping,[w['values'] for w in windows],threshold='400',provenance=provenance)
    directory=Path(directory)
    write_report(audit,directory/'audit','EchoProof · NOAA 原始年度观测窗口')
    # Preserve a complete measured window pair, rather than claiming a minimized
    # deletion witness is itself a complete rolling window from the corpus.
    pair=None
    groups={}
    for window in windows:
        key=encode(window['values'],mapping)
        prior=groups.get(key)
        if prior is not None and answer(prior['values'],'threshold',400)!=answer(window['values'],'threshold',400):
            pair=(prior,window);break
        groups.setdefault(key,window)
    if pair is None:
        raise ValueError('No measured threshold pair found; do not manufacture one')
    record=witness(pair[0]['values'],pair[1]['values'],mapping,'threshold',400)
    assert verify_witness(record)
    payload={'source':provenance,'left_window':pair[0],'right_window':pair[1],'witness':record,
             'scope':'Both complete 3-year sequences are unmodified archived observations; their relative-time EchoProof events match. Years and numeric labels excluded by the declared mapping, not by a full real-world chart audit.'}
    (directory/'selected_pair.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (directory/'complete-pair.witness.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    rendered=encode(pair[0]['values'],mapping)
    for side in ('left','right'):
        (directory/('complete-pair.'+side+'.wav')).write_bytes(wav_bytes(rendered))
    body='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EchoProof · 真实观测窗口</title><style>%s</style></head><body><main>
<header><div class="eyebrow">ECHOPROOF / ARCHIVED REAL OBSERVATIONS</div><h1>两段真实观测，也可能产生相同声音。</h1><p class="lead">NOAA 年度 CO₂ 平均值的全部三年窗口，逐窗口归一化后播放。原始数值未经改动。</p></header>
<p class="note">只审计本工具的相对时间与音高事件。每段都从相同起点播放，不朗读绝对年份或 ppm；原始来源与年份在报告里保留。不是完整现实图表的错误结论，也没有真人听觉验证。</p>
<div class="metrics"><div class="metric"><strong>%d</strong>原始年度观测</div><div class="metric"><strong>%d</strong>完整三年窗口</div><div class="metric"><strong>%d</strong>阈值400的冲突对</div></div>
<article><h2>完整窗口 A：%s；B：%s</h2>%s<p>是否达到400 ppm：A %s；B %s。</p><div class="pair">%s%s</div></article>
<p><a href="audit/index.html">全部窗口与五项任务审计</a> · <a href="selected_pair.json">原始窗口、来源和证书</a></p><p>数据来源：<a href="%s">NOAA 原始 CSV</a>；<a href="https://gml.noaa.gov/ccgg/trends/data.html">方法与引用说明</a>。%s</p>
<p class="muted">源文件SHA-256：%s。存档的观测值可能被数据提供方后续修订，本报告固定使用本地原始文件。</p></main></body></html>''' % (STYLE,len(rows),len(windows),audit['tasks']['threshold']['disagreeing_pairs'],esc(pair[0]['years']),esc(pair[1]['years']),data_table(pair[0]['values'],pair[1]['values']),record['left_answer'],record['right_answer'],sound(rendered,'窗口 A'),sound(rendered,'窗口 B'),SOURCE_URL,esc(CREDIT),provenance['raw_sha256'])
    (directory/'index.html').write_text(body,encoding='utf-8')
    print(json.dumps({'observations':len(rows),'windows':len(windows),'classes':audit['search']['render_classes'],'task_pairs':{t:v['disagreeing_pairs'] for t,v in audit['tasks'].items()},'full_pair_years':[w['years'] for w in pair],'raw_sha256':provenance['raw_sha256']},indent=2))
    return payload


def _verify_selected(path,source_path):
    record=json.loads(Path(path).read_text(encoding='utf-8'))
    raw,rows=read_annual(source_path)
    if record['source']['url']!=SOURCE_URL or hashlib.sha256(raw).hexdigest()!=record['source']['raw_sha256']:
        return False
    by_year={r['year']:r['mean'] for r in rows}
    for side in ('left','right'):
        window=record[side+'_window']
        years=window['years']
        if len(years)!=3 or years!=list(range(years[0],years[0]+3)):
            return False
        if window['values'] != [by_year[y] for y in years]:
            return False
        if list(map(Fraction,record['witness'][side])) != list(map(Fraction,window['values'])):
            return False
    return verify_witness(record['witness'])


def verify_selected(path,source_path):
    try:
        return _verify_selected(path,source_path)
    except (KeyError,TypeError,ValueError,OSError,IndexError):
        return False


if __name__=='__main__':
    target=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'artifacts/noaa-windows'
    source=ROOT/'research/data/noaa/co2_annmean_mlo.csv'
    build(source,target)
    assert verify_selected(target/'selected_pair.json',source)
