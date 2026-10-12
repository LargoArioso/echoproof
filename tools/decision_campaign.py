"""Verify finite-prior bounds by enumerating every small decoder policy."""
import hashlib
from itertools import product
import json
from pathlib import Path
import random
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from echoproof.model import Mapping, encode
from echoproof.decision import decision_bound
from fractions import Fraction


def main():
    rng=random.Random(20261012)
    cases=[];policies_checked=0
    for _ in range(500):
        values=sorted(rng.sample(range(101),rng.randint(2,6)))
        threshold=rng.randint(-1,102)
        weights=[rng.randint(0,9) for _ in values]
        if not sum(weights): weights[0]=1
        mapping=Mapping(domain_high='100',pitch_step_cents=rng.randint(50,5000))
        groups={}
        for i,x in enumerate(values): groups.setdefault(encode([x],mapping),[]).append(i)
        best=0
        for policy in product([False,True],repeat=len(groups)):
            score=sum(weights[i] for members,prediction in zip(groups.values(),policy) for i in members if prediction==(values[i]>=threshold))
            best=max(best,score);policies_checked+=1
        record=decision_bound(mapping,{'series':[[x] for x in values],'threshold':str(threshold)},['threshold'],threshold,weights)
        assert Fraction(record['joint_bound']['maximum_accuracy'])==Fraction(best,sum(weights))
        cases.append({'mapping':mapping.to_dict(),'values':values,'threshold':threshold,'weights':weights})
    result={'seed':20261012,'configurations':len(cases),'complete_decoder_policies_checked':policies_checked,'differences':0,
            'input_sha256':hashlib.sha256(json.dumps(cases,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__).resolve(),ROOT/'echoproof/decision.py')},
            'scope':'500 finite singleton domains, 2..6 integer values, nonnegative integer weights including zeros, threshold task. Oracle enumerates every true/false output policy and scores individual inputs directly; no majority-histogram or task-answer function is called by the oracle. Event grouping uses the separately checked core encoder. No human or population claim.'}
    (ROOT/'artifacts/decision-campaign.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
