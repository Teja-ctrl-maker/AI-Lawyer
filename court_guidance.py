"""Case comparisons drawn from a small, reviewed library of official decisions."""
from research import has_phrase, normalise


FIR_RULE = {
    'title': 'Imran Pratapgadhi v. State of Gujarat and Anr.',
    'court': 'Supreme Court of India',
    'date': '28 March 2025',
    'reference': '2025 INSC 410 · paras. 23–25',
    'url': 'https://api.sci.gov.in/supremecourt/2025/3511/3511_2025_4_1501_60508_Judgement_28-Mar-2025.pdf',
    'takeaway': 'The Court explained how police should handle information that discloses a cognizable offence. BNSS section 173(3) allows a preliminary inquiry in certain cases, with the required approval.',
    'difference': 'This case concerned an FIR over a social media post. Its discussion helps with police procedure. The alleged offence, punishment range and applicable procedural law still need checking for your case.',
}

THEFT = {
    'title': 'Pyare Lal Bhargava v. State of Rajasthan',
    'court': 'Supreme Court of India',
    'date': '22 October 1962',
    'reference': 'AIR 1963 SC 1094 · PDF p. 6',
    'url': 'https://api.sci.gov.in/jonew/judis/3730.pdf#page=6',
    'takeaway': 'Temporarily taking a government file could amount to theft where the taking was dishonest and the other elements were met.',
    'difference': 'The Court applied the former IPC to a government file. Apply the law in force for your incident. If an item is missing, the movement, lack of consent and dishonesty still need support from the facts.',
}

PRODUCT_DEFECT = {
    'title': 'Maruti Udyog Ltd. v. Susheel Kumar Gabgotra',
    'court': 'Supreme Court of India',
    'date': '29 March 2006',
    'reference': 'Civil Appeal 3734 of 2000 · PDF pp. 3–4',
    'url': 'https://api.sci.gov.in/jonew/judis/27602.pdf#page=3',
    'takeaway': 'For the particular car warranty and defect, the Court ordered free replacement of the defective clutch assembly and a payment for specified expenses and inconvenience instead of replacement of the whole car.',
    'difference': 'The Court applied the former Jammu and Kashmir consumer law and a specific vehicle warranty. Your options depend on the applicable law, warranty, evidence and remedy requested.',
}


def build_court_guidance(record, sources, procedure=None):
    facts = normalise(' '.join([record.get('summary', '')] + [
        event['description'] for event in record.get('events', [])
    ]))
    details = normalise((procedure or {}).get('details', ''))
    stage = (procedure or {}).get('stage', 'unknown')
    source_map = {source['id']: source for source in sources}
    suggestions = []
    route = None

    def matches(*terms):
        return any(has_phrase(facts, term) for term in terms)

    def add(decision, purpose, connection, preparation):
        suggestions.append(dict(decision, purpose=purpose, connection=connection, preparation=preparation))

    def add_example(source_id, purpose, connection, preparation):
        examples = source_map.get(source_id, {}).get('examples', [])
        if examples:
            add(examples[0], purpose, connection, preparation)

    theft = ('bns-303' in source_map and matches('theft', 'stolen', 'stole', 'taken without',
                                                  'snatched', 'robbed', 'चोरी', 'छीन'))
    police_step = any(has_phrase(text, term) for text in (facts, details)
                      for term in ('fir', 'refused to register', 'police refused', 'cognizable offence'))
    dated_events = [event['date'] for event in record.get('events', []) if event.get('date')]
    older_record = dated_events and max(dated_events) < '2024-07-01'
    other_criminal_issue = source_map.keys() & {'bns-63', 'bns-64', 'bns-74', 'bns-75', 'pocso-3', 'pocso-7'}
    if (police_step or theft or other_criminal_issue) and not older_record:
        add(FIR_RULE, 'Police reporting',
            'Your account raises a possible criminal or police-reporting issue. This decision helps check the registration process if the facts disclose a cognizable offence.',
            'Write down what was reported, when and to whom, and keep any acknowledgement or written response.' if stage != 'starting' else
            'Prepare a factual account identifying what happened, where and when, and list the material you can provide.')
        route = {
            'title': 'BNSS section 173 · Reporting a cognizable offence',
            'details': 'If BNSS applies and the station officer refuses to record the information covered by section 173, subsection (4) gives a route to send the substance in writing and by post to the Superintendent of Police. If that route does not resolve the refusal, check the application process before the Magistrate.',
            'url': 'https://www.ncrb.mha.gov.in/uploads/SankalanPortal/ChaptersBNSS.html#173',
        }

    if theft:
        add(THEFT, 'Understand the issue', 'The account describes a possible taking of property.',
            'Separate when you last had the item, when you noticed it missing, who had access, and what supports an actual taking without consent.')
    if matches('food poisoning', 'contaminated food', 'unsafe food', 'adulterated', 'expired food',
               'foreign object', 'food contamination', 'ill after eating', 'खाना', 'भोजन') or (
        matches('food', 'meal', 'restaurant', 'milk') and matches('vomiting', 'sick', 'ill', 'expired', 'contaminated')
    ):
        add_example('fssa-26', 'Prepare for proceedings', 'Your account raises a food safety concern where the product or a test result could be disputed.',
                    'List the batch number, purchase details, photographs and any official sampling or lab report. Check which testing procedure applies in your forum.')
    if matches('land', 'boundary', 'encroachment', 'possession', 'title deed', 'dispossessed',
               'inherited house', 'जमीन', 'कब्जा'):
        add_example('sra-5', 'Court filing', 'Your account raises an issue about possession, ownership or interference with land.',
                    'Work out who currently has possession, whether ownership is disputed and what order you want the court to make.')
    if matches('builder', 'developer', 'housing project', 'flat possession', 'apartment handover') and matches(
        'delay', 'delayed', 'handover', 'possession', 'delivery'
    ):
        example_id = 'cpa-2-11' if 'cpa-2-11' in source_map else 'cpa-39'
        add_example(example_id, 'Prepare for proceedings', 'Your account describes a builder or housing delivery dispute.',
                    'Compare the promised handover date, actual progress, agreement terms and any refund request.')
    if 'cpa-2-10' in source_map and matches('defect', 'defective', 'broken', 'stopped working', 'faulty', 'खराब'):
        add(PRODUCT_DEFECT, 'Prepare for proceedings', 'Your account describes an alleged problem with a purchased product.',
            'Put the invoice, warranty, repair offers and any inspection findings together. Explain why your requested remedy fits the problem.')
    add_example('pocso-7', 'Understand the issue',
                'The account raises a possible child sexual-contact issue. The decision helps explain how section 7 treats contact through clothing.',
                'Give only the observations needed to understand what happened. Keep the child’s identity and account private, and seek guidance on the appropriate reporting and support process.')

    if route is None and 'cpa-35' in source_map and any(
        item['purpose'] == 'Prepare for proceedings' for item in suggestions
    ):
        route = {
            'title': 'Consumer Protection Act, 2019 · Section 35',
            'details': 'Section 35 sets out who can make a complaint to the District Commission and permits electronic filing. Check the proper commission, time limits and required documents for your situation.',
            'url': source_map['cpa-35']['url'],
        }

    if stage in ('notice', 'hearing', 'decision'):
        suggestions.sort(key=lambda item: item['purpose'] != 'Prepare for proceedings')

    return {'suggestions': suggestions, 'route': route}
