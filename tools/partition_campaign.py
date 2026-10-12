"""Independent finite oracle for the partition constructor; fixed seed and scope."""
import hashlib
import json
from fractions import Fraction
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from echoproof.model import Mapping
from echoproof.partition import partition_thresholds, PartitionEncoder


def main():
    rng=random.Random(20261012)
    cases=[]
    preserved=impossible=checked=0
    for _ in range(1000):
        pitch_low=rng.randint(1000,6000)
        span=rng.randint(1,300)
        step=rng.randint(1,400)
        low,high=Fraction(rng.randint(-50,0)),Fraction(rng.randint(1,100))
        queries=sorted(set(Fraction(rng.randint(int(low)-3,int(high)+3),rng.randint(1,5)) for _ in range(rng.randint(1,10))))
        mapping=Mapping(domain_low=str(low),domain_high=str(high),pitch_low_cents=pitch_low,pitch_high_cents=pitch_low+span,pitch_step_cents=step)
        record=partition_thresholds(mapping,queries,low,high)
        # Enumerate every integer raw cents value. With integer quantization
        # steps, each reachable rounded cell contains such a value, including
        # the clipped upper endpoint. No production encoder/boundary formula.
        palette=[]
        for raw in range(pitch_low,pitch_low+span+1):
            numerator=2*(raw-pitch_low)+step
            pitch=min(pitch_low+span,pitch_low+(numerator//(2*step))*step)
            if pitch not in palette: palette.append(pitch)
        probes=sorted(set([low,high]+[t for t in queries if low<=t<=high]))
        # Use complete joint singleton labels directly, including every cut's
        # lower side, rather than production cuts or bin-count calculation.
        probes+= [(a+b)/2 for a,b in zip(probes,probes[1:])]
        vectors={tuple(x>=t for t in queries) for x in probes}
        capacity=len(vectors)<=len(palette)
        assert record['available_pitches_cents']==palette
        assert record['lower_bound']['required_pitch_symbols']==len(vectors)
        assert (record['status']=='preserved')==capacity
        if capacity:
            preserved+=1
            encoder=PartitionEncoder(record)
            for _ in range(12):
                values=[rng.choice(probes) for _ in range(rng.randint(1,8))]
                rendered=encoder.encode(values)
                # Separate oracle interprets the saved pitch-to-answer legend
                # by its singleton answer vectors; no production decoder.
                legend=dict(zip(record['selected_pitches_cents'],record['lower_bound']['distinct_answer_vectors']))
                decoded=tuple(any(legend[e.pitch_cents][i] for e in rendered.events) for i in range(len(queries)))
                expected=tuple(any(x>=t for x in values) for t in queries)
                assert decoded==expected
                assert tuple(encoder.decode(rendered).values())==expected
                checked+=1
        else: impossible+=1
        cases.append({'mapping':mapping.to_dict(),'thresholds':list(map(str,queries))})
    result={'seed':20261012,'configurations':len(cases),'preserved':preserved,'capacity_impossible':impossible,'sequences_checked':checked,'differences':0,
            'input_sha256':hashlib.sha256(json.dumps(cases,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__).resolve(),ROOT/'echoproof/partition.py']},
            'scope':'Integer pitch spans 1..300 cents, steps 1..400, rational thresholds, fixed seed. Finite independent alphabet enumeration and direct task-answer oracle; not a continuous proof, human study, or universal fuzzing claim.'}
    path=ROOT/'artifacts/partition-campaign.json'
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
