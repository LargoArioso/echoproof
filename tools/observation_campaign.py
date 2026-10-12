"""Independent endpoint-world enumeration for declared interval predicates."""
from fractions import Fraction
import hashlib
from itertools import product
import json
from pathlib import Path
import random
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from echoproof.model import Mapping
from echoproof.uncertainty import observation_certificate


def main():
    rng=random.Random(20261012)
    inputs=[];worlds_checked=0;statuses={}
    for _ in range(500):
        length=rng.randint(1,6)
        intervals=[]
        for i in range(length):
            pair=[Fraction(rng.randint(-10,100),rng.randint(1,5)) for _ in range(2)]
            intervals.append(sorted(pair))
        reported=[rng.randint(0,100) for _ in range(length)]
        threshold=Fraction(rng.randint(-10,100),rng.randint(1,5))
        possible=set();counts=[]
        for world in product(*[sorted(set(pair)) for pair in intervals]):
            predicates=[x>=threshold for x in world]
            possible.add(any(predicates));counts.append(sum(predicates));worlds_checked+=1
        record=observation_certificate(Mapping(domain_high='100'),reported,intervals,threshold)
        assert record['possible_actual_answers']==sorted(possible)
        assert record['at_or_above_count_bounds']==[min(counts),max(counts)]
        statuses[record['status']]=statuses.get(record['status'],0)+1
        inputs.append({'reported':reported,'intervals':[[str(x) for x in pair] for pair in intervals],'threshold':str(threshold)})
    result={'seed':20261012,'configurations':len(inputs),'corner_worlds_checked':worlds_checked,'statuses':statuses,'differences':0,
            'input_sha256':hashlib.sha256(json.dumps(inputs,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__).resolve(),ROOT/'echoproof/uncertainty.py')},
            'scope':'500 declared rational closed Cartesian interval sets of 1..6 dimensions. Enumerates every corner world, computes predicates/counts directly without production answer or bound functions. Endpoint enumeration checks the finite corners; continuous sufficiency separately follows monotonicity. Reported values may represent declared bias. No measured errors, calibration, probabilities or human data.'}
    (ROOT/'artifacts/observation-campaign.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
