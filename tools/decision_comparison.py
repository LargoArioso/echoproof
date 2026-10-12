"""Compare four representations for the declared finite quantization case."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from echoproof.audit import verify_audit
from echoproof.model import Mapping
from echoproof.decision import decision_bound, compare_decisions
from echoproof.report import write_decision_comparison


def build(audit_path,partition_path,directory):
    source=json.loads(Path(audit_path).read_text())
    if not verify_audit(source): raise ValueError('Invalid source audit')
    partition=json.loads(Path(partition_path).read_text())
    candidates={}
    mapping=Mapping(**source['mapping'])
    for name,representation in (
        ('Original events',{'kind':'base'}),
        ('Conditional binary cues',{'kind':'conditional_task_cues'}),
        ('Fixed semantic cues',{'kind':'fixed_semantic_cues'}),
        ('Nonuniform partition',{'kind':'threshold_partition','partition':partition})):
        candidates[name]=decision_bound(mapping,source['domain'],['threshold','endpoint_trend'],source['domain']['threshold'],representation=representation)
    comparison=compare_decisions(candidates)
    write_decision_comparison(comparison,directory)
    print(json.dumps({'metrics':comparison['metrics'],'pareto_front':comparison['pareto_front']},indent=2))
    return comparison


if __name__=='__main__':
    artifacts=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'artifacts'
    build(artifacts/'demo/quantization/audit.json',artifacts/'partition-thresholds/partition.json',artifacts/'decision-comparison')
