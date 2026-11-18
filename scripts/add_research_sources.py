"""Attach curated research examples and extract two NCRB statute sections."""
import hashlib
import html
import json
from pathlib import Path
import re

DATA = Path(__file__).resolve().parents[1] / 'data'
path = DATA / 'sources.json'
rows = {row['id']: row for row in json.loads(path.read_text(encoding='utf-8'))}


def section(code, number, title, heading, issue, meaning, use, limits, questions, keywords):
    raw = (DATA / f'{code.lower()}-official.html').read_bytes()
    fragment = raw.decode('utf-8').split(f'<span id="{number}">', 1)[1].split(f'<span id="{number + 1}">', 1)[0]
    paragraphs = [
        ' '.join(html.unescape(re.sub(r'<[^>]*>', '', p)).split())
        for p in re.findall(r'<p\b[^>]*>(.*?)</p>', fragment, re.S)
    ]
    if not any(re.match(rf'^{number}\s*\.', p) for p in paragraphs):
        raise ValueError(f'Could not find the statutory text for {code} {number}.')
    source_id = f'{code.lower()}-{number}'
    rows[source_id] = dict(
        id=source_id, kind='statute', title=title, section=f'Section {number} — {heading}',
        url=f'https://www.ncrb.mha.gov.in/uploads/SankalanPortal/Chapters{code}.html#{number}',
        text='\n'.join(paragraphs), context_text=' '.join((meaning, use, limits)),
        issue=issue, plain_explanation=meaning, when_to_use=use, do_not_use_when=limits,
        helpful_material=questions, keywords=keywords, domains=['criminal_procedure'],
        case_stage='follow_up', effective_from='2024-07-01', verified_on='2026-11-18',
        version='Official NCRB statute text. Check applicability and transitional provisions.',
        status='Excerpt extracted from the official NCRB publication.',
        sha256=hashlib.sha256(raw).hexdigest(), examples=[],
    )


section('BNSS', 173, 'Bharatiya Nagarik Suraksha Sanhita, 2023', 'Information in cognizable cases',
        'Was information about a possible cognizable offence recorded?',
        'This provision covers giving information about cognizable offences, copies of recorded information, and a route when the station officer refuses to record it.',
        'Consider it for questions about recording a report or getting a copy, once the offence category and applicable procedure have been checked.',
        'An informal complaint or missing acknowledgement alone does not show that information was formally recorded or that refusal occurred.',
        'When, where and how did you report it? What exactly did the station say or give you?',
        ['fir', 'cognizable offence', 'copy of fir', 'refused to register', 'police acknowledgement'])
section('BSA', 63, 'Bharatiya Sakshya Adhiniyam, 2023', 'Admissibility of electronic records',
        'Will a computer output be offered as evidence?',
        'This provision sets conditions for admitting computer outputs and includes requirements for a certificate when submitting them under the section.',
        'Consider it when a party plans to use an electronic copy or output in a proceeding to which this evidence law applies.',
        'A screenshot by itself does not settle authenticity or admissibility. A preliminary account can still be organised without a certificate.',
        'Keep the original record or device details where available. Clarify how the copy was made and what the proceeding requires.',
        ['electronic evidence', 'electronic record', 'computer output', 'digital evidence certificate'])


def example(ids, title, date, reference, url, takeaway, difference):
    item = dict(title=title, court='Supreme Court of India', date=date, reference=reference,
                url=url, takeaway=takeaway, difference=difference)
    for source_id in ids:
        rows[source_id]['examples'] = [item]


example(('sra-5', 'sra-34', 'sra-38'), 'Anathula Sudhakar v. P. Buchi Reddy',
        '2008-03-25', 'Civil Appeal 6191 of 2001 · para. 17, PDF pp. 6–7',
        'https://api.sci.gov.in/jonew/judis/31000.pdf#page=6',
        'The Court distinguished interference with possession from disputes where title or recovery of possession also needs to be decided.',
        'Compare who possessed the property, whether title is seriously disputed, and the relief sought. The decision concerned competing claims to vacant plots.')
example(('pocso-7',), 'Attorney General for India v. Satish and connected appeals',
        '2021-11-18', 'Criminal Appeal 1410 of 2021 and connected appeals · majority paras. 33–35',
        'https://api.sci.gov.in/supremecourt/2021/2286/2286_2021_32_1501_31537_Judgement_18-Nov-2021.pdf#page=24',
        'The Court held that physical contact through clothing can fall within section 7. Sexual intent remains a factual question.',
        'Compare the kind of contact, age and surrounding facts. The interpretation alone does not establish what happened in another case.')
example(('cpa-2-11', 'cpa-39'), 'Pioneer Urban Land & Infrastructure Ltd. v. Govindan Raghavan',
        '2019-04-02', 'Civil Appeal 12238 of 2018 · paras. 9–10, PDF pp. 20–21',
        'https://api.sci.gov.in/supremecourt/2018/46308/46308_2018_Judgement_02-Apr-2019.pdf#page=20',
        'The Court upheld a refund with interest where a builder offered possession of a flat after substantial delay.',
        'The case concerned a flat purchase under the 1986 Act and specific contractual facts. Compare those facts and the law applicable to the present dispute.')
example(('fssa-26', 'fssa-59', 'cpa-38'), 'Nestle India Ltd. v. Union of India',
        '2019-01-03', 'Civil Appeal 14539 of 2015 · order, PDF pp. 5–6',
        'https://api.sci.gov.in/supremecourt/2015/41646/41646_2015_Order_03-Jan-2019.pdf#page=5',
        'The Court allowed the consumer commission to evaluate a laboratory report from court-directed food sampling.',
        'This order dealt with testing and the next procedural step under the 1986 consumer Act. It left the merits open and does not establish a rule for private samples.')

path.write_text(json.dumps(list(rows.values()), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
