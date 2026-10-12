"""Keep threshold positions/counts in unmodified NOAA windows with task bins."""
from collections import defaultdict
from fractions import Fraction
import hashlib
from itertools import combinations
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from real_data_case import read_annual, SOURCE_URL, CREDIT
from echoproof.model import Mapping, encode
from echoproof.partition import partition_thresholds, PartitionEncoder
from echoproof.serialization import same_json
from echoproof.report import STYLE, esc, sound, data_table
from echoproof.audio import wav_bytes


def direct_profiles(values,queries):
    profiles={}
    for t in queries:
        indices=[i for i,x in enumerate(values) if Fraction(x)>=Fraction(t)]
        profiles[str(t)]={'sample_count':len(values),'at_or_above_count':len(indices),'indices':indices,
                          'any':bool(indices),'all':len(indices)==len(values),
                          'first_index':indices[0] if indices else None,'last_index':indices[-1] if indices else None}
    return profiles


def create_record(source):
    raw,rows=read_annual(source)
    mapping=Mapping(domain_low='310',domain_high='430',pitch_step_cents=1200)
    partition=partition_thresholds(mapping,[350,400,420],310,430)
    encoder=PartitionEncoder(partition)
    windows=[]
    original_groups=defaultdict(list);revised_groups=defaultdict(list)
    for start in range(len(rows)-2):
        data=rows[start:start+3]
        values=[r['mean'] for r in data]
        original=encode(values,mapping);revised=encoder.encode(values)
        expected=direct_profiles(values,partition['thresholds'])
        decoded=encoder.profiles(revised)
        if not same_json(expected,decoded): raise AssertionError('Threshold profile mismatch')
        window={'years':[r['year'] for r in data],'values':values,'original_render':original.to_dict(),
                'partition_render':revised.to_dict(),'threshold_profiles':decoded}
        original_groups[original].append(len(windows));revised_groups[revised].append(len(windows))
        windows.append(window)
    conflict_counts={t:{'original':0,'partition':0} for t in partition['thresholds']}
    examples={}
    for name,groups in (('original',original_groups),('partition',revised_groups)):
        for indices in groups.values():
            for left,right in combinations(indices,2):
                for threshold in partition['thresholds']:
                    if windows[left]['threshold_profiles'][threshold] != windows[right]['threshold_profiles'][threshold]:
                        conflict_counts[threshold][name]+=1
                        if name=='original': examples.setdefault(threshold,{'left_window_index':left,'right_window_index':right})
    if any(c['partition'] for c in conflict_counts.values()): raise AssertionError('Repaired collision')
    return {'schema_version':1,'claim_type':'archived_threshold_partition_validation',
            'source':{'url':SOURCE_URL,'raw_sha256':hashlib.sha256(raw).hexdigest(),'credit':CREDIT,'units':'ppm'},
            'partition':partition,'windows':windows,'selected_examples':examples,
            'statistics':{'observations':len(rows),'windows':len(windows),'original_render_classes':len(original_groups),
                          'partition_render_classes':len(revised_groups),'profile_disagreeing_pairs':conflict_counts,'profile_decode_failures':0},
            'scope':'Every unmodified consecutive three-year window in the supplied archived annual observations. Original mapping here is fixed 310..430, not per-window normalization. Profile means exact rounded sample positions and counts, not exposure duration or risk. Relative time only; absolute years/ppm are not encoded. Source archive consistency and event-level results; no human hearing, data-source authenticity, or full real chart claim.'}


def verify_record(record,source):
    try: return same_json(record,create_record(source))
    except (KeyError,TypeError,ValueError,OSError): return False


def build(source,directory):
    record=create_record(source)
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    (directory/'validation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    encoder=PartitionEncoder(record['partition'])
    cards=[]
    for threshold,pair in record['selected_examples'].items():
        windows=[record['windows'][pair[side+'_window_index']] for side in ('left','right')]
        audio=[]
        for side,window in zip(('left','right'),windows):
            for name,rendered in (('original',encode(window['values'],encoder.mapping)),('partition',encoder.encode(window['values']))):
                (directory/('threshold%s.%s.%s.wav' % (threshold,side,name))).write_bytes(wav_bytes(rendered))
                audio.append('<div>%s</div>' % sound(rendered,('%s %s：%s' % (side,'原映射' if name=='original' else '分区映射',window['years']))))
        details=''.join('<p>窗口 %s：≥%s 的位置 %s，共 %d 个采样。</p>' % (esc(w['years']),esc(threshold),esc(w['threshold_profiles'][threshold]['indices']),w['threshold_profiles'][threshold]['at_or_above_count']) for w in windows)
        cards.append('<article><h2>阈值 %s ppm</h2>%s%s<div class="pair">%s</div></article>' % (esc(threshold),data_table(windows[0]['values'],windows[1]['values']),details,''.join(audio)))
    stats=record['statistics']
    rows=''.join('<tr><th scope="row">%s ppm</th><td>%d</td><td>%d</td></tr>' % (t,c['original'],c['partition']) for t,c in stats['profile_disagreeing_pairs'].items())
    body='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EchoProof · 真实窗口的阈值位置与计数</title><style>%s</style></head><body><main>
<header><div class="eyebrow">ECHOPROOF / TASK COUNTS IN OBSERVED DATA</div><h1>相同的声音种类数量，保留的信息可以不同。</h1><p class="lead">原始NOAA观测不改动。等距音高改为按350、400、420 ppm边界分区，比较达到阈值的采样位置与计数。</p></header>
<p class="note">只播放相同相对时间。范围310–430 ppm、每点一个音、四个原有音高，保留音符时长与时间槽。计数对应四舍五入后的原始年度观测，不代表暴露时间或风险；没有真人听辨结果或完整现实图表错误结论。</p>
<p>%d个完整三年窗口，原映射%d个事件类别，分区后%d个事件类别，位置与计数解码失败%d次。</p>
<table><caption>同声音但阈值位置/计数不同的输入对</caption><thead><tr><th scope="col">判断边界</th><th scope="col">原映射</th><th scope="col">分区后</th></tr></thead><tbody>%s</tbody></table>
%s<p><a href="validation.json">全部原始窗口、事件、结果和存档哈希</a></p><p>数据来源：<a href="%s">NOAA 原始CSV</a>。%s</p></main></body></html>''' % (STYLE,stats['windows'],stats['original_render_classes'],stats['partition_render_classes'],stats['profile_decode_failures'],rows,''.join(cards),SOURCE_URL,esc(CREDIT))
    (directory/'index.html').write_text(body,encoding='utf-8')
    print(json.dumps(stats,indent=2))
    return record


if __name__=='__main__':
    target=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'artifacts/noaa-partition'
    source=ROOT/'research/data/noaa/co2_annmean_mlo.csv'
    record=build(source,target)
    assert verify_record(record,source)
