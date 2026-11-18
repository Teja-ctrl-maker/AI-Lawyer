"""Conservative comparisons and evidence links for the case workspace."""
from difflib import SequenceMatcher
import hashlib
import re


PAGE_REF = re.compile(r'\[D\d{1,3} p\.\d{1,2}\]')
STOP = set('the and was were with from that this they their some then later about before after said told into have what when which event user'.split())
ANCHORS = {
    'cpa-2-7': [('(i) buys any goods', 185), ('(ii) hires or avails', 170)],
    'cpa-2-10': [('(10) "defect"', 220)],
    'cpa-2-11': [('(11) "deficiency"', 240)],
    'cpa-35': [('35. (1)', 235), ('may be filed electronically', 120)],
    'cpa-39': [('Where the District Commission is satisfied', 240), ('(c) to return', 170)],
    'bns-303': [('Whoever, intending to take dishonestly', 220)],
    'bns-304': [('Theft is snatching if', 198)],
    'bns-305': [('in any building, tent or vessel', 215)],
    'bns-309': [('In all robbery', 75), ('the offender, for that end voluntarily', 195)],
}


def words(text):
    return set(re.findall(r'[\w]{3,}', text.casefold())) - STOP


def normalized(text):
    return ' '.join(text.casefold().split())


def catalogue_excerpts(source, claim):
    text = ' '.join(source['text'].split())
    passages = []
    for marker, width in ANCHORS.get(source['id'], ()):
        start = text.find(marker)
        if start < 0:
            continue
        excerpt = text[start:start + width]
        if start + width < len(text):
            excerpt = excerpt.rsplit(' ', 1)[0]
        passages.append({'claim': claim, 'quote': excerpt, 'partial': True})
    return passages


def page_excerpt(text, fact_words):
    passages = [line.strip() for line in re.split(r'(?<=[.!?])\s+|\n+', text) if line.strip()]
    best = max(passages, key=lambda part: len(words(part) & fact_words), default='')
    return best[:420]


def fact_map(record, documents):
    pages = {row['ref']: row for row in documents}
    notes = [(note, words(note)) for note in record['evidence']]
    rows = []
    for index, event in enumerate(record['events'], 1):
        fact = event['description']
        fact_words = words(fact)
        direct_refs = set(PAGE_REF.findall(event['basis']))
        links = []
        for ref, page in pages.items():
            overlap = len(fact_words & words(page['text']))
            if ref in direct_refs or overlap >= 3:
                links.append((ref in direct_refs, overlap, {
                    'ref': ref,
                    'label': 'Cited in the timeline' if ref in direct_refs else 'Possible text match',
                    'excerpt': page_excerpt(page['text'], fact_words),
                }))
        links.sort(key=lambda row: (row[0], row[1]), reverse=True)
        conflicts = [
            conflict for conflict in record['contradictions']
            if len(fact_words & words(conflict)) >= 3
        ][:2]
        related_notes = [note for note, note_words in notes
                         if len(fact_words & note_words) >= 3 or
                         (re.search(r'\b(?:bought|purchased|paid|ordered)\b', fact, re.I)
                          and re.search(r'\b(?:receipt|invoice|order confirmation)\b', note, re.I))][:2]
        rows.append({
            'event': index, 'fact': fact, 'basis': event['basis'],
            'materials': [row[2] for row in links[:2]], 'conflicts': conflicts,
            'related_notes': related_notes,
            'gap': ('Check whether the passage supports this specific detail. The app has not authenticated the document.'
                    if links else 'No matching PDF passage is linked to this event. Add a record or explain how you know it, if available.'),
        })
    return {'rows': rows, 'reported_material': record['evidence'], 'reported_conflicts': record['contradictions']}


def next_question(record, sources, used):
    text = ' '.join(event['description'] for event in record['events']).casefold()
    domains = {domain for source in sources for domain in source.get('domains', [])}
    suggestions = []
    if domains & {'sexual', 'child'}:
        return None  # The intake already carries the account-specific safeguards.
    if 'theft' in domains:
        if not re.search(r'\b(?:last saw|last seen|last had|last used|last remember|last noticed)\b', text):
            suggestions.append(('last-seen', 'When and where did you last see or use the missing item?',
                                'This narrows the time and place to check for records or witnesses.'))
        if not re.search(r'\b(?:serial number|imei|receipt|invoice|older photo)\b', text + ' ' + ' '.join(record['evidence']).casefold()):
            suggestions.append(('item-id', 'Do you have a serial number, receipt, or earlier photo that identifies the item?',
                                'It can help identify the item if it is found.'))
    if 'consumer' in domains and not re.search(r'\b(?:refused|denied|declined|replied|responded|offered|no reply|no response)\b', text):
        suggestions.append(('seller-reply', 'What did the seller say when you asked for a resolution?',
                            'The response can show what the seller disputes or offered.'))
    if 'property' in domains and not re.search(r'\b(?:lives?|living|occup(?:ies|ied|ying)|possess(?:es|ion)|locked out)\b', text):
        suggestions.append(('property-possession', 'Who was using the property just before the dispute?',
                            'Actual possession and claimed ownership are different questions.'))
    for question in record['questions']:
        if not question.strip().endswith('?') or len(question) > 300 or '\n' in question:
            continue
        question_words = words(question)
        if any(len(question_words & words(text)) >= max(3, len(question_words) - 1)
               for text in [event['description'] for event in record['events']]):
            continue
        key = 'q-' + hashlib.sha256(normalized(question).encode()).hexdigest()[:16]
        suggestions.append((key, question, 'This can help clarify an open point in your timeline.'))
    for key, question, why in suggestions:
        if key not in used:
            return {'key': key, 'question': question, 'why': why}
    return None


def compare_record(before, after, before_docs, after_docs):
    prior = before['events']
    revised = after['events']
    unmatched = set(range(len(prior)))
    added, removed, updated = [], [], []
    remaining = []
    matched_order = []
    for event in revised:
        match = next((i for i in sorted(unmatched) if prior[i] == event), None)
        if match is not None:
            unmatched.remove(match)
            matched_order.append(match)
        else:
            remaining.append(event)
    for event in remaining:
        description = normalized(event['description'])
        best, score = None, 0
        for i in sorted(unmatched):
            old = normalized(prior[i]['description'])
            shared = words(old) & words(description)
            similarity = (1 if old == description else SequenceMatcher(None, old, description).ratio()
                          if len(shared) >= 3 and max(len(old), len(description)) <= 800 else 0)
            if similarity > score:
                best, score = i, similarity
        if best is not None and score >= .78:
            updated.append({'before': prior[best], 'after': event})
            unmatched.remove(best)
        else:
            added.append(event)
    removed = [prior[i] for i in sorted(unmatched)]
    previous = {page['ref']: page['text'] for page in before_docs}
    current = {page['ref']: page['text'] for page in after_docs}
    return {
        'added': added, 'removed': removed, 'updated': updated,
        'order_changed': matched_order != sorted(matched_order),
        'changed_fields': [key for key in ('goal', 'location', 'evidence', 'contradictions') if before[key] != after[key]],
        'added_pages': sorted(current.keys() - previous.keys()),
        'removed_pages': sorted(previous.keys() - current.keys()),
        'changed_pages': sorted(ref for ref in previous.keys() & current.keys() if previous[ref] != current[ref]),
    }


def review_snapshot(analysis):
    if not analysis:
        return None
    return {'laws': {law['source_id']: law['support'] for law in analysis['laws']},
            'next_steps': analysis['next_steps'], 'stage': (analysis.get('procedure') or {}).get('stage')}


def compare_review(before, after, source_index, revision=None):
    if not before:
        return None
    previous, current = before['laws'], after['laws']
    ids = list(dict.fromkeys([*previous, *current]))
    labels = {'supported': 'Matches reported facts', 'conditional': 'Conditional',
              'unsupported': 'Less likely', None: 'Outside this review'}
    changes = []
    for key in ids:
        old, new = previous.get(key), current.get(key)
        if old == new or key not in source_index:
            continue
        source = source_index[key]
        changes.append({'title': source['title'] + ' · ' + source['section'],
                        'before': labels[old], 'after': labels[new]})
    stage_changed = before['stage'] != after['stage']
    context = []
    if revision:
        if revision['order_changed'] or any(revision[key] for key in ('added', 'removed', 'updated')):
            context.append('the revised timeline')
        if any(revision[key] for key in ('added_pages', 'removed_pages', 'changed_pages')) or 'evidence' in revision['changed_fields']:
            context.append('the updated evidence list')
        if 'goal' in revision['changed_fields']:
            context.append('the revised outcome you want')
    if stage_changed:
        context.append('the newly selected case stage')
    return {'law_changes': changes, 'stage_changed': stage_changed, 'revised_inputs': context,
            'new_next_steps': [step for step in after['next_steps'] if step not in before['next_steps']],
            'removed_next_steps': [step for step in before['next_steps'] if step not in after['next_steps']]}
