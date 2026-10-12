import argparse
import json
from pathlib import Path
from .audit import audit, repair_candidates, verify_witness, verify_audit
from .model import Mapping
from .report import write_report, write_demo_index, write_cue_report, write_compiled_report, write_semantic_report, write_alignment_report, write_interval_report
from .tasks import TASKS
from .intervals import threshold_certificate, verify_threshold_certificate
from .probe import probe_csv
from .cues import plan_from_audit, verify_plan, CueEncoder
from .audio import wav_bytes
from .compiled import audit_compiled, verify_recording_witness, SCOPES
from .semantic_cues import plan as semantic_plan, validate_domain, verify_validation
from .alignment import align_threshold, verify_alignment
from .multi_alignment import align_thresholds, verify_multi_alignment
from .interval_tasks import task_certificate, verify_task_certificate
from .trace import verify_trace
from .study import prepare_study, verify_study
from .study_export import write_study, check_study
from .partition import partition_thresholds, verify_partition
from .report import write_partition_report, write_decision_report
from .decision import decision_bound, verify_decision_bound, verify_decision_comparison
from .uncertainty import observation_certificate, verify_observation_certificate
from .report import write_observation_report, write_diagnosis_report
from .diagnosis import diagnose, verify_diagnosis
from .contracts import verify_threshold_contract

DEMOS = {
    "normalization": {"title": "各自归一化抹掉绝对值", "mapping": Mapping(normalization="per_series"), "levels": [1, 2, 3], "lengths": [2, 3], "tasks": ["threshold", "total"], "threshold": "2"},
    "quantization": {"title": "音高取整抹掉阈值与微小趋势", "mapping": Mapping(domain_high="100", pitch_step_cents=1200), "levels": [49, 50, 51], "lengths": [2, 3], "tasks": ["threshold", "endpoint_trend", "peak_indices"], "threshold": "51"},
    "missing": {"title": "把缺失当成零，抹掉缺失信息", "mapping": Mapping(missing="zero"), "levels": [0, 5, 10], "lengths": [2, 3], "tasks": ["missing_count", "endpoint_trend"], "include_missing": True},
    "sampling": {"title": "漏采样藏住尖峰", "mapping": Mapping(stride=2), "levels": [0, 5, 10], "lengths": [3, 4], "tasks": ["threshold", "peak_indices", "endpoint_trend"], "threshold": "5"},
    "clipping": {"title": "截断范围抹掉范围外的变化", "mapping": Mapping(), "levels": [9, 10, 11, 12], "lengths": [2, 3], "tasks": ["threshold", "endpoint_trend", "total"], "threshold": "11"},
}


def run_audit(config, output, repair=False):
    config = dict(config)
    title = config.pop("title", None)
    result = audit(**config)
    repairs = []
    if repair:
        for label, mapping in repair_candidates(config["mapping"], config["levels"]):
            candidate = dict(config, mapping=mapping)
            repairs.append((label, audit(**candidate)))
    path = write_report(result, output, title, repairs)
    print(str(path.resolve()))
    print("%d series, %d render classes" % (result["search"]["series_count"], result["search"]["render_classes"]))
    for task, detail in result["tasks"].items():
        print("%s: %s (%d disagreeing pairs)" % (task, detail["status"], detail["disagreeing_pairs"]))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Task-aware exact collision auditing of discrete sonification mappings")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Run five reproducible failure scenarios")
    demo.add_argument("--out", default="artifacts/demo")
    test = commands.add_parser("audit", help="Exhaustively audit a finite measurement grid")
    test.add_argument("--spec", help="Mapping JSON file; defaults to shared 0..10 scale")
    test.add_argument("--levels", default="0,2,4,6,8,10")
    test.add_argument("--lengths", default="2,3,4")
    test.add_argument("--tasks", default=",".join(TASKS))
    test.add_argument("--threshold", default="5")
    test.add_argument("--include-missing", action="store_true")
    test.add_argument("--repair", action="store_true")
    test.add_argument("--out", default="artifacts/audit")
    verify = commands.add_parser("verify", help="Independently recompute a witness certificate")
    verify.add_argument("path")
    verify.add_argument("--audit", help="Parent finite audit for deletion-trace input membership")
    intervals = commands.add_parser("threshold", help="Prove preservation or construct a collision over a closed real interval")
    intervals.add_argument("--spec")
    intervals.add_argument("--threshold", required=True)
    intervals.add_argument("--input-low", required=True)
    intervals.add_argument("--input-high", required=True)
    intervals.add_argument("--out", default="artifacts/threshold.json")
    probe = commands.add_parser("probe", help="Audit a reproducible mutation neighborhood of a CSV series")
    probe.add_argument("path")
    probe.add_argument("--column", required=True)
    probe.add_argument("--spec")
    probe.add_argument("--threshold", default="5")
    probe.add_argument("--tasks", default=",".join(TASKS))
    probe.add_argument("--out", default="artifacts/probe")
    cues = commands.add_parser("cues", help="Synthesize minimum-length binary task cues for a saved finite audit domain")
    cues.add_argument("audit_path")
    cues.add_argument("--out", default="artifacts/cues")
    compiled = commands.add_parser("compiled", help="Check recorded backend outputs; Erie full queue includes speech by default")
    compiled.add_argument("path")
    compiled.add_argument("--scope", choices=SCOPES, default="erie_full_queue")
    compiled.add_argument("--threshold", default="5")
    compiled.add_argument("--tasks", default=",".join(TASKS))
    compiled.add_argument("--out", default="artifacts/compiled")
    semantic = commands.add_parser("semantic-cues", help="Add globally fixed threshold/trend answer cues and validate the saved domain")
    semantic.add_argument("audit_path")
    semantic.add_argument("--tasks", default="threshold,endpoint_trend")
    semantic.add_argument("--out", default="artifacts/semantic-cues")
    alignment = commands.add_parser("align-threshold", help="Keep pitch steps and move one range endpoint to preserve a threshold")
    alignment.add_argument("--spec")
    alignment.add_argument("--threshold", required=True)
    alignment.add_argument("--input-low", required=True)
    alignment.add_argument("--input-high", required=True)
    alignment.add_argument("--out", default="artifacts/alignment.json")
    multiple = commands.add_parser("align-thresholds", help="Preserve several thresholds together, or certify infeasibility")
    multiple.add_argument("--spec")
    multiple.add_argument("--thresholds", required=True)
    multiple.add_argument("--input-low", required=True)
    multiple.add_argument("--input-high", required=True)
    multiple.add_argument("--out", default="artifacts/multi-alignment.json")
    interval = commands.add_parser("interval-audit", help="Check all supported tasks over a whole closed real interval")
    interval.add_argument("--spec")
    interval.add_argument("--tasks", default=",".join(TASKS))
    interval.add_argument("--threshold", default="5")
    interval.add_argument("--input-low", required=True)
    interval.add_argument("--input-high", required=True)
    interval.add_argument("--out", default="artifacts/interval-audit")
    study = commands.add_parser("study-kit", help="Prepare matched original/cued listening materials; no human results")
    study.add_argument("audit_path")
    study.add_argument("--tasks", default="threshold,endpoint_trend")
    study.add_argument("--groups", type=int, default=2)
    study.add_argument("--repetitions", type=int, default=2)
    study.add_argument("--seed", type=int, default=20261012)
    study.add_argument("--out", default="artifacts/study-kit")
    check = commands.add_parser("check-study", help="Replay and verify participant sheets and exact WAV files")
    check.add_argument("path")
    partition = commands.add_parser("partition-thresholds", help="Construct nonuniform threshold bins within the original pitch alphabet")
    partition.add_argument("--spec")
    partition.add_argument("--thresholds", required=True)
    partition.add_argument("--input-low", required=True)
    partition.add_argument("--input-high", required=True)
    partition.add_argument("--out", default="artifacts/partition-thresholds")
    decision = commands.add_parser("decision-bound", help="Exact ideal-decoder accuracy under a declared finite input prior")
    decision.add_argument("audit_path")
    decision.add_argument("--tasks", help="Comma-separated task list; defaults to source audit task order")
    decision.add_argument("--weights", help="JSON rational weight list in normalized distinct input order")
    decision.add_argument("--representation", choices=("base","conditional_task_cues","fixed_semantic_cues","threshold_partition"), default="base")
    decision.add_argument("--partition", help="Partition certificate; required only for threshold_partition")
    decision.add_argument("--out", default="artifacts/decision-bound")
    uncertainty = commands.add_parser("uncertain-threshold", help="Threshold identifiability under caller-declared actual-value intervals")
    uncertainty.add_argument("path", help="JSON with reported, intervals and threshold")
    uncertainty.add_argument("--spec", help="Mapping JSON; outputs use reported values only")
    uncertainty.add_argument("--out", default="artifacts/uncertain-threshold")
    diagnosis = commands.add_parser("diagnose", help="One scoped threshold diagnosis: observations, mapping, designs and regressions")
    diagnosis.add_argument("path", help="JSON with mapping, thresholds, reported_input_interval; optional reported and actual_intervals")
    diagnosis.add_argument("--out", default="artifacts/diagnosis")
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            record = json.loads(Path(args.path).read_text(encoding="utf-8"))
            if args.audit and (not isinstance(record, dict) or record.get("claim_type") != "paired_deletion_trace"):
                raise ValueError("--audit applies to deletion traces only; a plain witness check does not validate domain membership")
            if not isinstance(record, dict):
                valid = False
            elif record.get("claim_type") == "threshold_diagnosis":
                valid = verify_diagnosis(record)
                print("DIAGNOSIS_VERIFIED (scopes and constraints retained)" if valid else "INVALID")
                return 0 if valid else 1
            elif record.get("claim_type") == "numeric_threshold_contract":
                valid = verify_threshold_contract(record)
            elif record.get("claim_type") == "interval_observation_identifiability":
                valid = verify_observation_certificate(record)
                print("OBSERVATION_CERTIFICATE_VERIFIED (declared intervals; no probabilities)" if valid else "INVALID")
                return 0 if valid else 1
            elif record.get("claim_type") == "finite_prior_decision_comparison":
                valid = verify_decision_comparison(record)
                print("DECISION_COMPARISON_VERIFIED (same finite domain and prior)" if valid else "INVALID")
                return 0 if valid else 1
            elif record.get("claim_type") == "finite_prior_decision_bound":
                valid = verify_decision_bound(record)
                print("DECISION_BOUND_VERIFIED (declared prior; no human results)" if valid else "INVALID")
                return 0 if valid else 1
            elif record.get("claim_type") == "nonuniform_threshold_partition":
                valid = verify_partition(record)
            elif record.get("claim_type") == "matched_study_materials":
                valid = verify_study(record)
            elif record.get("claim_type") == "paired_deletion_trace":
                parent = json.loads(Path(args.audit).read_text(encoding="utf-8")) if args.audit else None
                valid = verify_trace(record, parent)
                print(("TRACE_AND_DOMAIN_VERIFIED" if parent is not None else "TRACE_VERIFIED (domain membership not checked)") if valid else "INVALID")
                return 0 if valid else 1
            elif record.get("claim_type") == "finite_task_audit":
                valid = verify_audit(record)
            elif record.get("claim_type") == "continuous_interval_threshold":
                valid = verify_threshold_certificate(record)
            elif record.get("claim_type") == "continuous_interval_task":
                valid = verify_task_certificate(record)
            elif record.get("claim_type") == "finite_task_sufficient_cues":
                valid = verify_plan(record)
            elif record.get("claim_type") == "compiled_recording_collision":
                valid = verify_recording_witness(record)
                print("RECORDING_VERIFIED (backend not rerun)" if valid else "INVALID")
                return 0 if valid else 1
            elif record.get("claim_type") == "fixed_semantic_cue_validation":
                valid = verify_validation(record)
            elif record.get("claim_type") == "simultaneous_threshold_alignment":
                valid = verify_multi_alignment(record)
            elif record.get("claim_type") == "threshold_range_alignment":
                valid = verify_alignment(record)
            else:
                valid = verify_witness(record)
            print("VERIFIED" if valid else "INVALID")
            return 0 if valid else 1
        if args.command == "diagnose":
            source = json.loads(Path(args.path).read_text(encoding="utf-8"))
            required={"mapping","thresholds","reported_input_interval"}
            allowed=required|{"reported","actual_intervals","question"}
            if not isinstance(source,dict) or not required<=set(source) or set(source)-allowed:
                raise ValueError("Unexpected or missing diagnosis fields")
            interval=source["reported_input_interval"]
            if not isinstance(interval,list) or len(interval)!=2:
                raise ValueError("reported_input_interval must have two endpoints")
            record=diagnose(Mapping(**source["mapping"]),source["thresholds"],*interval,reported=source.get("reported"),actual_intervals=source.get("actual_intervals"),question=source.get("question","reported"))
            print(write_diagnosis_report(record,args.out).resolve())
            print(record["status"])
            return 0
        if args.command == "uncertain-threshold":
            source = json.loads(Path(args.path).read_text(encoding="utf-8"))
            if not isinstance(source,dict) or set(source)!={"reported","intervals","threshold"}:
                raise ValueError("Observation input requires exactly reported, intervals and threshold")
            mapping = Mapping(**json.loads(Path(args.spec).read_text(encoding="utf-8"))) if args.spec else Mapping()
            record = observation_certificate(mapping,source["reported"],source["intervals"],source["threshold"])
            print(write_observation_report(record,args.out).resolve())
            print(record["status"] + ": " + str(record["possible_actual_answers"]))
            return 0
        if args.command == "decision-bound":
            source = json.loads(Path(args.audit_path).read_text(encoding="utf-8"))
            if not verify_audit(source):
                raise ValueError("Require a verified finite source audit")
            tasks = args.tasks.split(",") if args.tasks else source["task_order"]
            weights = json.loads(Path(args.weights).read_text(encoding="utf-8")) if args.weights else None
            representation = {"kind":args.representation}
            if args.representation == "threshold_partition":
                if not args.partition: raise ValueError("threshold_partition requires --partition")
                representation["partition"] = json.loads(Path(args.partition).read_text(encoding="utf-8"))
            elif args.partition:
                raise ValueError("--partition applies to threshold_partition only")
            record = decision_bound(Mapping(**source["mapping"]),source["domain"],tasks,source["domain"]["threshold"],weights,representation)
            print(write_decision_report(record,args.out).resolve())
            print(json.dumps(record["joint_bound"],indent=2))
            return 0
        if args.command == "partition-thresholds":
            mapping = Mapping(**json.loads(Path(args.spec).read_text(encoding="utf-8"))) if args.spec else Mapping()
            record = partition_thresholds(mapping,args.thresholds.split(","),args.input_low,args.input_high)
            print(write_partition_report(record,args.out).resolve())
            print(record["status"] + ": " + record["reason"])
            return 0
        if args.command == "study-kit":
            source = json.loads(Path(args.audit_path).read_text(encoding="utf-8"))
            record = prepare_study(source,args.tasks.split(","),args.groups,args.repetitions,args.seed)
            print(write_study(record,args.out).resolve())
            print(json.dumps(record["statistics"],indent=2))
            return 0
        if args.command == "check-study":
            print(json.dumps(check_study(args.path),indent=2))
            return 0
        if args.command == "interval-audit":
            mapping = Mapping(**json.loads(Path(args.spec).read_text(encoding="utf-8"))) if args.spec else Mapping()
            certificates = {t:task_certificate(mapping,t,args.input_low,args.input_high,args.threshold) for t in dict.fromkeys(args.tasks.split(","))}
            print(write_interval_report(certificates,args.out).resolve())
            print(json.dumps({t:c["status"] for t,c in certificates.items()},indent=2))
            return 0
        if args.command == "align-thresholds":
            mapping = Mapping(**json.loads(Path(args.spec).read_text(encoding="utf-8"))) if args.spec else Mapping()
            record = align_thresholds(mapping, args.thresholds.split(","), args.input_low, args.input_high)
            path = Path(args.out)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(record["status"] + ": " + record["reason"])
            print(path.resolve())
            return 0
        if args.command == "align-threshold":
            mapping = Mapping(**json.loads(Path(args.spec).read_text(encoding="utf-8"))) if args.spec else Mapping()
            record = align_threshold(mapping, args.threshold, args.input_low, args.input_high)
            path = Path(args.out)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(path.resolve())
            print("%d candidates; pitch range and step retained" % len(record["candidates"]))
            print(write_alignment_report(record, path.with_suffix("")).resolve())
            return 0
        if args.command == "semantic-cues":
            result = json.loads(Path(args.audit_path).read_text(encoding="utf-8"))
            definition = semantic_plan(Mapping(**result["mapping"]), args.tasks.split(","), result["domain"]["threshold"])
            validation = validate_domain(definition, result["domain"])
            print(write_semantic_report(validation, args.out).resolve())
            print(json.dumps(validation["statistics"], indent=2))
            return 0
        if args.command == "compiled":
            corpus = json.loads(Path(args.path).read_text(encoding="utf-8"))
            result = audit_compiled(corpus, args.scope, args.tasks.split(","), args.threshold)
            print(write_compiled_report(result, args.out).resolve())
            print("%d recordings, %d projected output classes; scope=%s" % (result["recording_count"], result["projection_classes"], args.scope))
            return 0
        if args.command == "cues":
            result = json.loads(Path(args.audit_path).read_text(encoding="utf-8"))
            plan = plan_from_audit(result)
            if not verify_plan(plan):
                raise ValueError("Synthesized cue plan failed verification")
            directory = Path(args.out)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            encoder = CueEncoder(plan)
            examples = []
            selected_base = None
            # Use original corpus members, because minimized witnesses may lie outside its lengths.
            from .cues import domain_corpus
            from .model import encode
            for values in domain_corpus(plan["domain"]):
                base = encode(values, encoder.mapping)
                augmented = encoder.encode(values)
                if augmented != base and (selected_base is None or base == selected_base):
                    answers = encoder.decode(augmented)
                    if examples and answers == examples[0]["answers"]:
                        continue
                    selected_base = base
                    example_index = len(examples)
                    (directory / ("example%d.base.wav" % example_index)).write_bytes(wav_bytes(base))
                    (directory / ("example%d.cued.wav" % example_index)).write_bytes(wav_bytes(augmented))
                    examples.append({"values": list(values), "answers": encoder.decode(augmented), "base": base.to_dict(), "cued": augmented.to_dict()})
                if len(examples) == 2:
                    break
            (directory / "examples.json").write_text(json.dumps(examples, indent=2) + "\n", encoding="utf-8")
            write_cue_report(plan, examples, directory)
            print(directory.resolve())
            print(json.dumps(plan["statistics"], indent=2))
            return 0
        if args.command == "threshold":
            mapping = Mapping(**json.loads(Path(args.spec).read_text(encoding="utf-8"))) if args.spec else Mapping()
            result = threshold_certificate(mapping, args.threshold, args.input_low, args.input_high)
            path = Path(args.out)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(result["status"] + ": " + result["reason"])
            print(path.resolve())
            return 0
        if args.command == "probe":
            mapping = Mapping(**json.loads(Path(args.spec).read_text(encoding="utf-8"))) if args.spec else Mapping()
            result = probe_csv(args.path, args.column, mapping, args.threshold, args.tasks.split(","))
            print(write_report(result, args.out, "EchoProof · 数据文件的候选变换检查").resolve())
            print("%d explicit candidates; coverage is limited to the saved corpus" % result["search"]["series_count"])
            return 0
        if args.command == "demo":
            results = {}
            for name, config in DEMOS.items():
                print("\n" + name)
                results[name] = run_audit(config, Path(args.out) / name, repair=True)
            parent = Path(args.out).parent
            for threshold in (50, 51):
                certificate = threshold_certificate(DEMOS["quantization"]["mapping"], threshold, 0, 100)
                (parent / ("threshold%d.json" % threshold)).write_text(json.dumps(certificate, indent=2) + "\n", encoding="utf-8")
            print("\nOverview: " + str(write_demo_index(results, args.out).resolve()))
        else:
            mapping = Mapping(**json.loads(Path(args.spec).read_text(encoding="utf-8"))) if args.spec else Mapping()
            config = {"mapping": mapping, "levels": args.levels.split(","), "lengths": [int(x) for x in args.lengths.split(",")],
                      "tasks": args.tasks.split(","), "threshold": args.threshold, "include_missing": args.include_missing}
            run_audit(config, args.out, args.repair)
        return 0
    except (ValueError, TypeError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, "error: %s\n" % exc)


if __name__ == "__main__":
    raise SystemExit(main())
