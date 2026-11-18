"""Conservative evidence prompts for a person documenting a reported incident."""
import re


def item(title, look_for, why, action):
    return {'title': title, 'look_for': look_for, 'why': why, 'action': action}


CCTV = item(
    'Footage from an authorised keeper',
    'If cameras cover the relevant place, note their owner and the narrow time window from your timeline.',
    'It may show movement or timing. A camera can have blind spots or an inaccurate clock.',
    'Ask the owner or investigating officer to preserve the original recording promptly. Record your request. Use only footage you are authorised to access.',
)

TOPIC_ITEMS = {
    'theft': [
        item('Item identification and last known location',
             'Look for a serial number, receipt, older photo or repair record. Write down when and where you last saw the item and when you noticed it missing.',
             'This can establish which item is missing and narrow the time window. It cannot identify who took it by itself.',
             'Save copies of records you own. If a device location service shows a location, share it with police instead of going there yourself.'),
        CCTV,
    ],
    'physical_incident': [
        CCTV,
        item('Witness position and changes at the scene',
             'Note where you and each witness stood, lighting, what was visible, and what changed before help arrived.',
             'It helps separate direct observations from later accounts and shows where a witness had a limited view.',
             'Let each person describe what they noticed independently. Share witness contact details privately with the authorities and only with permission where appropriate.'),
        item('Injury and professional records',
             'If anyone was injured, keep relevant treatment records when available and note when you first noticed the injury.',
             'An independent record can help establish timing and document what was treated.',
             'Get medical care first. Tell police about objects or marks that may be relevant and leave physical collection to them.'),
    ],
    'sexual_safety': [
        item('Safety, care and specialist support',
             'Consider access to medical care or a trusted support person. Existing treatment records and messages may matter.',
             'A clinician can address health needs. Any formal examination or collection should be guided by qualified professionals.',
             'Do not delay care to gather evidence. Do not collect samples yourself. For a child, avoid repeated questioning and seek trained help.'),
        item('Existing messages and a brief account',
             'If you choose to, note approximate time, location and what you directly remember. Keep messages you already lawfully have.',
             'A short account and contemporaneous messages can help establish sequence without requiring a detailed retelling.',
             'Leave out identifying and graphic material in the app. Share sensitive records privately with a clinician, lawyer or investigating officer.'),
    ],
    'food': [
        item('Product, order and batch',
             'If available, note the seller, order ID, product name, batch, date on the packaging and when it was opened or served.',
             'These details can distinguish the particular product from a general complaint about a shop or brand.',
             'Retain copies of your order and any photos you already took. Do not taste or handle suspect food for evidence. Ask the food safety authority about any sample.'),
        item('Symptoms and timing',
             'Write down when you ate, when symptoms started, and whether anyone else independently reported symptoms. Keep any relevant treatment records.',
             'Timing can guide inquiries. It does not by itself establish what caused the illness.',
             'Seek medical care when needed. Report factual details and let qualified authorities handle formal sampling or testing.'),
    ],
    'consumer': [
        item('Purchase, promised terms and communications',
             'Look for the order confirmation, invoice, payment record and relevant warranty or service terms. Keep the complete email or chat thread.',
             'These can show what was purchased, what was promised and what resolution the seller offered.',
             'Keep the original files or exports. Record dates and ask for copies from the seller or platform if you do not have them.'),
        item('Condition of the product or work',
             'If safe, note the model or order number, the fault and when it appeared. Keep existing dated photos, service requests or repair reports.',
             'A dated record helps distinguish what you observed from a possible explanation of the fault.',
             'Leave suspected electrical or other hazardous damage to a qualified person. Ask the repair provider for a written report if they inspect it.'),
    ],
    'property': [
        item('Possession, title and notices',
             'Gather records you already hold, such as agreements, deeds, orders, rent payments or notices. Note who occupied the property and when that changed.',
             'Documents and the timeline can help distinguish possession from a claim about legal ownership.',
             'Keep full copies and record where each came from. Request records through the issuing office or a lawyer when needed.'),
        item('Location and visible changes',
             'Note the address or boundary reference and any changed lock, barrier or damage you actually observed.',
             'This helps identify the location and the particular change in dispute.',
             'Document only from an area you may safely and lawfully access. Do not enter disputed space or confront anyone.'),
    ],
}

PAPERWORK = {
    'reported': item('Report and acknowledgements', 'Find the date, office or officer, acknowledgement and any reference already supplied.',
                     'This helps connect later evidence to the existing report.',
                     'Keep a copy of what you submitted. Log what you handed over and when. Ask the authority how it wants to receive additions.'),
    'notice': item('Notice and delivery record', 'Keep the entire notice or reply, including attachments, envelope or message headers, and the receipt date.',
                   'The wording and delivery record help establish what was communicated and when.',
                   'Check the original before relying on a date. Take it to an advocate if a response date is close or unclear.'),
    'hearing': item('Hearing papers and evidence list', 'Check the hearing notice, the issues listed and the actual directions about documents.',
                    'This helps identify which facts still need support at the hearing.',
                    'Prepare an index matching each record to the fact it supports, and ask your advocate how to present it.'),
    'decision': item('Decision and case record', 'Keep the full decision, any recorded receipt date and the documents the decision discusses.',
                     'This helps identify what was decided and which records the decision relied on.',
                     'Keep originals and have an advocate review any further procedural steps.'),
}


def build_evidence_plan(record, sources, procedure=None, laws=None):
    # Candidate sources guide the local checklist; they do not establish an offence.
    relevant_ids = None if laws is None else {law['source_id'] for law in laws if law['support'] != 'unsupported'}
    relevant_sources = [source for source in sources if relevant_ids is None or source['id'] in relevant_ids]
    domains = {domain for source in relevant_sources for domain in source.get('domains', [])}
    descriptions = ' '.join(event['description'] for event in record['events']).lower()
    sexual = bool(domains & {'sexual', 'child'} or re.search(
        r'\b(?:rape|raped|sexual assault|molested|forced sex|child sexual abuse)\b|बलात्कार', descriptions))
    physical = bool(re.search(r'\b(?:assaulted|punched|stabbed|attacked|hit me|collision|robbed|robbery|snatched)\b', descriptions))
    theft = bool('theft' in domains or re.search(r'\b(?:stole|stolen|theft|snatched)\b|चोरी', descriptions))
    # Consumer provisions are shared with the food category. Require a
    # food-specific source or a direct cue before suggesting food evidence.
    food = bool(any(source['id'].startswith('fssa-') for source in relevant_sources)
                or re.search(r'\b(?:food|meal|restaurant|food poisoning|adulterated milk)\b|खाना|भोजन', descriptions))
    topics = (['sexual_safety'] if sexual else
              [name for name, applies in [('theft', theft), ('physical_incident', physical),
                                           ('food', food), ('property', 'property' in domains),
                                           ('consumer', 'consumer' in domains and not food)] if applies])
    scene = sexual or theft or physical
    suggestions = [PAPERWORK[procedure['stage']]] if procedure and procedure['stage'] in PAPERWORK else []
    for topic in topics:
        for suggestion in TOPIC_ITEMS[topic]:
            if suggestion not in suggestions:
                suggestions.append(suggestion)
    if theft and not sexual and re.search(r'\b(?:home|house|bedroom|flat|office|shop|door|lock|window|garage)\b', descriptions):
        suggestions.append(item(
            'Doors, locks and disturbed objects',
            'Note damage or changes you actually saw. If you know, record who used a key or moved or cleaned something afterward.',
            'This helps distinguish what changed from a guess about how someone entered.',
            'Describe it from a safe, permitted position. Leave damaged locks, tools and objects in place for the investigating officer.',
        ))
    if not sexual and re.search(r'\b(?:snatched|snatching|grabbed|robbed|robbery)\b', descriptions):
        suggestions.append(item(
            'Movement and viewing position',
            'Record the last direction you personally saw, nearby landmarks, and anything that limited your view. Separate what you saw from what others reported.',
            'It helps police identify which witnesses or time windows may be relevant.',
            'Write down your recollection while it is fresh. Do not follow or confront anyone.',
        ))
    suggestions.append(item(
        'Original records and an evidence log',
        'Keep records you lawfully have, with their surrounding context. For each item note the related event, who provided it, when you received it, and any transfer.',
        'The log distinguishes what you observed from what someone later told you and makes it easier to check the source.',
        'Keep an unchanged original and label working copies. Avoid editing originals, guessing gaps, or sharing evidence publicly.',
    ))
    if sexual:
        prompts = ['If you choose to record it, what approximate time and place do you remember?',
                   'What do you personally recall or already have that shows sequence? Leave out names and graphic details.']
    elif scene:
        prompts = ['Where did each event happen, and what was the last confirmed time before it?',
                   'What did you actually see or hear? Where were you, and what could you see from there?',
                   'What was already different when you arrived, and what changed afterward? Say if you are unsure.']
    else:
        prompts = ['Which part of the timeline needs independent support?',
                   'What already shows that event, and who may lawfully hold another record?']
    scene_points = []
    if scene and not sexual:
        scene_words = re.compile(
            r'\b(?:stole|stolen|theft|took|snatched|grabbed|robbed|robbery|bedroom|lock|door|'
            r'assaulted|attacked|punched|hit me|collision|witness)\b|चोरी', re.I)
        for event in record['events']:
            if not scene_words.search(event['description']):
                continue
            timing = ', '.join(part for part in (event['date'] or event.get('day'), event.get('time')) if part)
            description = event['description']
            if len(description) > 300:
                description = description[:297].rstrip() + '…'
            scene_points.append(f'{timing} · {description}' if timing else description)
            if len(scene_points) == 3:
                break
    return {
        'scene': scene,
        'heading': 'Scene and evidence review' if scene else 'Evidence plan',
        'safety': ('Get to safety and seek medical or police help if needed. Do not enter or alter a scene to gather evidence. '
                   'Leave physical collection to the authorities.' if scene else ''),
        'prompts': prompts,
        'scene_points': scene_points,
        'suggestions': suggestions,
    }
