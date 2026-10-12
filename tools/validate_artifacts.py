"""Recompute saved certificates and verify offline HTML links/audio payloads."""
import base64
from fractions import Fraction
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from echoproof import verify_witness, verify_audit
from echoproof.cues import verify_plan
from echoproof.intervals import verify_threshold_certificate
from echoproof.compiled import verify_recording_witness
from echoproof.semantic_cues import verify_validation
from echoproof.alignment import verify_alignment
from echoproof.multi_alignment import verify_multi_alignment
from echoproof.interval_tasks import verify_task_certificate
from echoproof.trace import verify_trace
from echoproof.study_export import check_study
from echoproof.partition import verify_partition, PartitionEncoder
from echoproof.decision import decision_bound, verify_decision_bound, verify_decision_comparison
from echoproof.serialization import same_json
from echoproof.model import Mapping, Render, Event
from echoproof.uncertainty import verify_observation_certificate
from echoproof.diagnosis import verify_diagnosis
from echoproof.contracts import verify_threshold_contract
from echoproof.model import encode
from echoproof.audio import wav_bytes


class PageCheck(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.links = 0
        self.audio = 0
        self.errors = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if 'autoplay' in attrs:
            self.errors.append('Unexpected autoplay')
        if tag == 'a' and 'href' in attrs:
            link = urlsplit(attrs['href'])
            if not link.scheme and link.path:
                self.links += 1
                target = self.path.parent / unquote(link.path)
                if not target.is_file():
                    self.errors.append('Missing link: ' + attrs['href'])
        if tag == 'source' and attrs.get('src', '').startswith('data:audio/wav;base64,'):
            self.audio += 1
            data = base64.b64decode(attrs['src'].split(',', 1)[1], validate=True)
            with wave.open(io.BytesIO(data)) as stream:
                if stream.getnchannels() != 1 or stream.getsampwidth() != 2:
                    self.errors.append('Invalid audio format')


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / 'artifacts')
    verified = 0
    recordings_verified = 0
    finite_audits_verified = 0
    traces_verified = 0
    study_trials_verified = 0
    real_partition_windows_verified = 0
    figure_prior_points_verified = 0
    pages = 0
    audio = 0
    links = 0
    for path in root.rglob('*.json'):
        record = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(record, dict):
            continue
        if record.get('claim_type') == 'finite_task_audit':
            assert verify_audit(record), path
            finite_audits_verified += 1
        if path.name == 'repairs.json':
            for candidate in record.values():
                if isinstance(candidate, dict) and candidate.get('claim_type') == 'finite_task_audit':
                    assert verify_audit(candidate), path
                    finite_audits_verified += 1
        if record.get('claim') == 'exact_render_collision':
            assert verify_witness(record), path
            verified += 1
            left = path.with_name(path.name.replace('.witness.json', '.left.wav'))
            right = path.with_name(path.name.replace('.witness.json', '.right.wav'))
            if left.exists() or right.exists():
                assert left.read_bytes() == right.read_bytes(), path
        elif record.get('claim_type') == 'matched_study_materials':
            stats = check_study(path.parent.parent)
            study_trials_verified += stats['trial_wav_verified']
        elif record.get('claim_type') == 'paired_deletion_trace':
            parent = json.loads((path.parent/'audit.json').read_text(encoding='utf-8'))
            assert verify_trace(record,parent), path
            traces_verified += 1
        elif record.get('claim_type') == 'continuous_interval_threshold':
            assert verify_threshold_certificate(record), path
            verified += 1
        elif record.get('claim_type') == 'continuous_interval_task':
            assert verify_task_certificate(record), path
            verified += 1
        elif record.get('claim_type') == 'finite_task_sufficient_cues':
            assert verify_plan(record), path
            verified += 1
        elif record.get('claim_type') == 'compiled_recording_collision':
            assert verify_recording_witness(record), path
            recordings_verified += 1
        elif record.get('claim_type') == 'fixed_semantic_cue_validation':
            assert verify_validation(record), path
            verified += 1
        elif record.get('claim_type') == 'simultaneous_threshold_alignment':
            assert verify_multi_alignment(record), path
            verified += 1
        elif record.get('claim_type') == 'threshold_diagnosis':
            assert verify_diagnosis(record),path
            verified += 1
        elif record.get('claim_type') == 'numeric_threshold_contract':
            assert verify_threshold_contract(record),path
            verified += 1
        elif record.get('claim_type') == 'interval_observation_identifiability':
            assert verify_observation_certificate(record),path
            verified += 1
            for kind,render_data in record['reported_only_outputs'].items():
                rendered=Render(tuple(Event(**e) for e in render_data['events']),render_data['duration_ms'])
                expected=wav_bytes(rendered)
                for side in ('lower','upper'):
                    assert (path.parent/('%s-world.reported.%s.wav' % (side,kind))).read_bytes()==expected,path
        elif record.get('claim_type') == 'finite_prior_decision_comparison':
            assert verify_decision_comparison(record),path
            verified += 1
        elif record.get('claim_type') == 'finite_prior_decision_bound':
            assert verify_decision_bound(record),path
            verified += 1
        elif record.get('claim_type') == 'archived_threshold_partition_validation':
            from real_data_partition import verify_record
            source_path = Path(__file__).resolve().parents[1]/'research/data/noaa/co2_annmean_mlo.csv'
            assert verify_record(record,source_path),path
            real_partition_windows_verified += len(record['windows'])
            encoder = PartitionEncoder(record['partition'])
            for threshold,pair in record['selected_examples'].items():
                for side in ('left','right'):
                    values=record['windows'][pair[side+'_window_index']]['values']
                    for name,rendered in (('original',encode(values,encoder.mapping)),('partition',encoder.encode(values))):
                        assert (path.parent/('threshold%s.%s.%s.wav' % (threshold,side,name))).read_bytes() == wav_bytes(rendered),path
        elif record.get('claim_type') == 'nonuniform_threshold_partition':
            assert verify_partition(record), path
            verified += 1
            if record['status'] == 'preserved':
                encoder = PartitionEncoder(record)
                for i,value in enumerate(record['lower_bound']['singleton_representatives']):
                    for name,rendered in (('base',encode([value],encoder.mapping)),('partition',encoder.encode([value]))):
                        assert (path.parent/('case%d.%s.wav' % (i,name))).read_bytes() == wav_bytes(rendered), path
        elif record.get('claim_type') == 'threshold_range_alignment':
            assert verify_alignment(record), path
            verified += 1
    real_data_verified = 0
    for path in root.rglob('selected_pair.json'):
        if path.parent.name == 'noaa-windows':
            from real_data_case import verify_selected
            source_path = Path(__file__).resolve().parents[1]/'research/data/noaa/co2_annmean_mlo.csv'
            assert verify_selected(path,source_path), path
            real_data_verified += 1
    plot_data=root/'figures/decision-tradeoffs-data.json'
    if plot_data.exists():
        data=json.loads(plot_data.read_text())
        comparison_path=root/'decision-comparison/comparison.json'
        comparison=json.loads(comparison_path.read_text())
        assert data['comparison_sha256']==hashlib.sha256(comparison_path.read_bytes()).hexdigest()
        assert same_json(data['comparison_metrics'],comparison['metrics'])
        producer=Path(__file__).resolve().parent/'figures.py'
        assert data['producer_sha256']==hashlib.sha256(producer.read_bytes()).hexdigest()
        example=data['prior_example']
        mapping=Mapping(domain_high='100',pitch_step_cents=1200)
        domain={'series':[['50'],['51']],'threshold':'51'}
        assert same_json(example['mapping'],mapping.to_dict()) and same_json(example['domain'],domain)
        assert same_json(example['weight_order'],['threshold_false_input','threshold_true_input'])
        expected=[]
        for i in range(21):
            mass=Fraction(i,20)
            base=decision_bound(mapping,domain,['threshold'],'51',[1-mass,mass])
            cues=decision_bound(mapping,domain,['threshold'],'51',[1-mass,mass],{'kind':'fixed_semantic_cues'})
            expected.append({'true_input_mass':str(mass),'original_maximum_accuracy':base['joint_bound']['maximum_accuracy'],
                             'cued_maximum_accuracy':cues['joint_bound']['maximum_accuracy']})
        assert same_json(example['samples'],expected),plot_data
        figure_prior_points_verified=len(expected)
    for path in root.rglob('*.html'):
        checker = PageCheck(path)
        checker.feed(path.read_text(encoding='utf-8'))
        assert not checker.errors, (path, checker.errors)
        pages += 1
        audio += checker.audio
        links += checker.links
    print(json.dumps({'verified_certificates': verified, 'verified_complete_finite_audits': finite_audits_verified, 'deletion_traces_with_parent_membership': traces_verified, 'study_trial_wav_files_verified': study_trials_verified, 'real_data_partition_windows_verified': real_partition_windows_verified, 'figure_prior_points_verified': figure_prior_points_verified, 'verified_recording_witnesses_backend_not_rerun': recordings_verified, 'real_data_window_pairs_verified_against_archive': real_data_verified, 'html_pages': pages,
                      'embedded_wav_payloads': audio, 'valid_local_links': links,
                      'visual_inspection': 'not performed: local browser access blocked'}, indent=2))


if __name__ == '__main__':
    main()
