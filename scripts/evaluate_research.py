"""Repeatable comparison of the original keyword search and assisted retrieval."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core


# Fictional cases. Expected IDs specify issues to surface, not legal conclusions.
CASES = [
    ('theft_hinglish', 'On 10 November 2026 koi mera phone le gaya. No witnesses.', {'bns-303'}, set()),
    ('faulty_goods_hinglish', 'Mixer khareeda aur chalna band. Paise wapas chahiye.', {'cpa-2-10'}, {'cpa-2-11'}),
    ('food_illness', 'Khana khake ulti hui. I have no receipt.', {'fssa-26', 'fssa-59'}, set()),
    ('property_lockout', 'They changed the locks while I was away. I want to get back into the house.', {'sra-6'}, set()),
    ('older_taking', 'On 10 November 2022 someone took my phone.', set(), {'bns-303', 'bnss-173'}),
    ('ordinary_child_story', 'My daughter and I inherited a house.', set(), {'pocso-7', 'pocso-19'}),
    ('adult_rape', 'On 10 November 2026 an adult raped me. I have no witness.', {'bns-63'}, {'bns-75', 'pocso-7'}),
    ('digital_evidence_later', 'On 12 November 2026 someone stole my phone.', {'bns-303'}, {'bsa-63'}),
]


def compare():
    results = []
    for name, story, required, excluded in CASES:
        record = core.offline_intake(story, '')
        results.append(evaluate(name, record, required, excluded))
    record = core.offline_intake('On 12 November 2026 someone stole my phone.', '')
    results.append(evaluate('later_police_status', record, {'bns-303', 'bnss-173', 'bsa-63'},
                            set(), {'stage': 'reported', 'details':
                                    'Police gave me no acknowledgement. Can I submit screenshots?'}))
    return results


def evaluate(name, record, required, excluded, procedure=None):
    result = {'case': name, 'required': sorted(required), 'excluded': sorted(excluded)}
    for label, baseline in [('original', True), ('assisted', False)]:
        ids = [source['id'] for source in core.retrieve(record, procedure, baseline=baseline)]
        result[label] = {'ids': ids, 'pass': required.issubset(ids) and not excluded.intersection(ids)}
    return result


def live_example():
    story = 'On 10 November 2026 someone took my phone from my bedroom without my permission. I have no CCTV or witnesses.'
    stage = {'stage': 'starting', 'details': 'I want to understand which law might apply.'}
    record = core.intake(story)
    analysis, candidates = core.analyse(record, procedure=stage)
    ids = [law['source_id'] for law in analysis['laws']]
    return {
        'fictional_story': story,
        'confirmed_fixture': record,
        'candidate_ids': [source['id'] for source in candidates],
        'checks': {'theft_section_surfaced': 'bns-303' in ids, 'all_citations_in_candidates':
                   set(ids).issubset(source['id'] for source in candidates)},
        'analysis': analysis,
        'manual_review': 'Check each claim against its cited text and the facts, especially dates, evidence and next steps.',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='Also send one fictional example to the configured provider.')
    args = parser.parse_args()
    cases = compare()
    report = {'cases': cases, 'total': len(cases),
              'original_pass': sum(case['original']['pass'] for case in cases),
              'assisted_pass': sum(case['assisted']['pass'] for case in cases)}
    if args.live:
        if not core.configured():
            parser.error('--live requires a configured AI provider')
        try:
            report['live'] = live_example()
        except ValueError as error:
            report['live'] = {'error': str(error)}
    print(json.dumps(report, ensure_ascii=True, indent=2))
    live = report.get('live', {})
    sys.exit(int(report['assisted_pass'] != report['total'] or 'error' in live or
                 not all(live.get('checks', {}).values())))
