"""Rebuild core reports in an empty isolated directory, without network access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, help='New or empty destination directory')
    parser.add_argument('--recordings', action='store_true', help='Recheck saved external recordings; does not rerun backends')
    parser.add_argument('--tests', action='store_true', help='Also run the automated checks')
    args = parser.parse_args()
    output = Path(args.out).resolve()
    if output.exists() and any(output.iterdir()):
        parser.error('Destination must be empty; existing reports are never deleted')
    output.mkdir(parents=True, exist_ok=True)
    for filename in ('README.md', 'LICENSE'):
        shutil.copy2(ROOT/filename, output/filename)
    shutil.copytree(ROOT/'research', output/'research', ignore=shutil.ignore_patterns('vendor', '__pycache__'))
    artifacts = output/'artifacts'
    artifacts.mkdir()
    stages=[]
    environment = dict(os.environ, PYTHONPATH=str(ROOT))
    def run(label, arguments, command=None):
        actual = command or [sys.executable, '-m', 'echoproof']+arguments
        result = subprocess.run(actual, cwd=output, env=environment, text=True, capture_output=True)
        stages.append({'label':label, 'command':actual, 'exit_code':result.returncode, 'stdout':result.stdout, 'stderr':result.stderr})
        if result.returncode:
            (output/'failure.json').write_text(json.dumps(stages,indent=2)+'\n',encoding='utf-8')
            raise RuntimeError('Reproduction stage failed: '+label)
    run('five finite domains and two analytic certificates', ['demo','--out',str(artifacts/'demo')])
    run('finite conditional binary cues',['cues',str(artifacts/'demo/quantization/audit.json'),'--out',str(artifacts/'cues-quantization')])
    run('ideal decoder bound: original events',['decision-bound',str(artifacts/'demo/quantization/audit.json'),'--out',str(artifacts/'decision-base')])
    run('ideal decoder bound: conditional cues',['decision-bound',str(artifacts/'demo/quantization/audit.json'),'--representation','conditional_task_cues','--out',str(artifacts/'decision-cued')])
    run('matched listening materials' ,['study-kit',str(artifacts/'demo/quantization/audit.json'),'--out',str(artifacts/'study-kit')])
    run('listening material files', ['check-study', str(artifacts/'study-kit')])
    run('fixed semantic cues',['semantic-cues',str(artifacts/'demo/normalization/audit.json'),'--out',str(artifacts/'semantic-normalization')])
    run('CSV candidate corpus',['probe',str(ROOT/'examples/measurements.csv'),'--column','value','--spec',str(ROOT/'examples/per-series.json'),'--threshold','3','--out',str(artifacts/'csv-probe')])
    run('single threshold repair',['align-threshold','--spec',str(ROOT/'examples/coarse-pitch.json'),'--threshold','51','--input-low','0','--input-high','100','--out',str(artifacts/'threshold51-alignment.json')])
    run('unmodified archived NOAA windows',[],[sys.executable,str(ROOT/'tools/real_data_case.py'),str(artifacts/'noaa-windows')])
    run('archived threshold positions and counts',[],[sys.executable,str(ROOT/'tools/real_data_partition.py'),str(artifacts/'noaa-partition')])
    run('continuous task preservation',['interval-audit','--input-low','0','--input-high','10','--out',str(artifacts/'continuous-tasks')])
    run('simultaneous infeasibility',['align-thresholds','--spec',str(ROOT/'examples/coarse-pitch.json'),'--thresholds','50,51','--input-low','0','--input-high','100','--out',str(artifacts/'multi-threshold50-51.json')])
    run('nonuniform task partition',['partition-thresholds','--spec',str(ROOT/'examples/coarse-pitch.json'),'--thresholds','50,51','--input-low','0','--input-high','100','--out',str(artifacts/'partition-thresholds')])
    run('same-domain decision comparison',[],[sys.executable,str(ROOT/'tools/decision_comparison.py'),str(artifacts)])
    run('observation interval identifiability',[],[sys.executable,str(ROOT/'tools/observation_cases.py'),str(artifacts/'observation-uncertainty')])
    run('single-entry scoped threshold diagnosis',[],[sys.executable,str(ROOT/'tools/diagnosis_cases.py'),str(artifacts/'diagnosis-cases')])
    if args.recordings:
        for filename,scope,threshold,folder in (
            ('erie-corpus/aggregate-mean.corpus.json','erie_full_queue','3','erie-mean-full'),
            ('erie-corpus/auto-domain.corpus.json','erie_full_queue','3','erie-auto-full'),
            ('erie-corpus/auto-domain.corpus.json','erie_tone_stream','3','erie-auto-tone'),
            ('highcharts-mapping/corpus.json','highcharts_mapped_instrument','51','highcharts-threshold51'),
            ('highcharts-mapping/corpus.json','highcharts_mapped_instrument','50','highcharts-threshold50')):
            target = artifacts/filename
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/'artifacts'/filename,target)
            run('saved recording recheck: '+folder,['compiled',str(target),'--scope',scope,'--threshold',threshold,'--out',str(artifacts/folder)])
    # Refresh overview after additional reports exist; use this run's results.
    sys.path.insert(0,str(ROOT))
    from echoproof.report import write_demo_index
    write_demo_index({p.parent.name:json.loads(p.read_text()) for p in (artifacts/'demo').glob('*/audit.json')},artifacts/'demo')
    run('artifact certificates, links and WAV',[],[sys.executable,str(ROOT/'tools/validate_artifacts.py'),str(artifacts)])
    if args.tests:
        run('automated tests',[],[sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-q'])
    report={'schema_version':1,'offline':True,'external_backend_execution':False,
            'recordings_mode':'saved recordings rechecked, backend not rerun' if args.recordings else 'not included',
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'echoproof').glob('*.py'))},
            'stage_count':len(stages),'stages':stages,
            'scope':'Rebuilt in an isolated empty output directory using the source identified above. No network access requested. Structural checks do not establish browser visual or auditory validation.'}
    (output/'reproduction.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(output),'stages_passed':len(stages),'external_backend_rerun':False,'entry':str(artifacts/'demo/index.html')},indent=2))


if __name__=='__main__':
    main()
