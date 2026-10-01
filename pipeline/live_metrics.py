"""Label-only metrics: no correction of ground truth using predicted text."""
from collections import defaultdict
from .eval.metrics import compute, normal, edit_distance, accuracy


def verdict(n, accuracy):
    if n >= 100 and accuracy >= .9:
        return 'Meets target (point estimate)'
    if n >= 30 and accuracy < .9:
        return 'Below target'
    return f'Inconclusive: too few labelled samples (N = {n})'


def score(files, labels, blind):
    rows = []
    bins = defaultdict(list)
    for file in files:
        plates = file.get('tracks') or file.get('plates') or []
        # A missing detection is still one scored abstention when the file is labelled.
        if not plates and labels.get(file['file']):
            plates = [{'track_id': None, 'status': 'abstain', 'voted': None, 'vote_confidence': 0}]
        for i, plate in enumerate(plates):
            key = f"{file['file']}#{plate.get('track_id') if plate.get('track_id') is not None else i}"
            expected = normal(labels[key] if key in labels else (labels.get(file['file'], '') if len(plates) == 1 else ''))
            predicted = normal(plate.get('voted') or '') if plate.get('status') == 'read' else ''
            plate.update(expected=expected or None, exact_match=None, cer=None, label_key=key)
            if not expected:
                continue
            correct = bool(predicted) and predicted == expected
            plate.update(exact_match=correct, cer=edit_distance(expected, predicted) / len(expected))
            confidence = plate.get('vote_confidence', 0)
            rows.append({'clip_id': file['file'], 'track_id': plate.get('track_id') or i,
                         'plate': expected, 'prediction': predicted, 'confidence': confidence,
                         'candidate': normal((plate.get('alternatives') or [{}])[0].get('text') or plate.get('normalised') or '') if plate.get('format_valid') else '',
                         'readable': True, 'plate_height_px': 0})
            if predicted:
                bins[min(9, int(confidence * 10))].append((confidence, correct))
    result = compute(rows)
    result['coverage_curve'] = []
    for t in range(0,11):
        selected = [{**r, 'prediction':r['candidate']} for r in rows if r['candidate'] and r['confidence']>=t/10]
        result['coverage_curve'].append({'threshold':t/10,'coverage':len(selected)/len(rows) if rows else 0,
                                         'accuracy':accuracy(selected)['value']})
    n = len(rows)
    result.update(n_scored=n, blind=bool(blind and n), source='LIVE RUN (this upload)',
                  verdict=verdict(n, result['plate_accuracy_all']['value'] if n else 0),
                  reliability=[{'bin': f'{b/10:.1f}–{(b+1)/10:.1f}', 'n': len(values),
                                'confidence': sum(v[0] for v in values)/len(values),
                                'accuracy': sum(v[1] for v in values)/len(values)} for b, values in sorted(bins.items())])
    for error in result['error_cases']:
        p, e = error['predicted'] or '', error['expected']
        error['category'] = ('missed plate' if not p else 'partial read' if len(p) < len(e)
                             else 'wrong length' if len(p) != len(e) else 'character confusion')
    return result
