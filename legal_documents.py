"""Deterministic document layouts and the facts each layout needs."""
CONSUMER = 'https://e-jagriti.gov.in/static/media/CC_Filing.34e0fc5dd03b1d864cab.pdf'
POLICE = 'https://www.ncrb.mha.gov.in/uploads/SankalanPortal/ChaptersBNSS.html#173'
FOOD = 'https://foscos.fssai.gov.in/consumergrievance/faqs'
CPC = 'https://www.indiacode.nic.in/bitstream/123456789/2191/1/eng.pdf'

# Each field has the same label in the form and in the generated document.
FORMATS = {
    'Legal notice': {
        'title': 'GENERAL LEGAL NOTICE', 'help': 'For a private demand or request to correct a problem. Statutory notices require a separate review.',
        'parties': ['Sender’s name and service address', 'Addressee’s name and service address'],
        'action': 'Demand or corrective action', 'fields': {
            'basis': 'Agreement, transaction or prior dealings', 'prior': 'Earlier requests and responses',
            'service': 'Proposed service method', 'response': 'Requested response date or period, if reviewed',
        },
    },
    'Payment demand notice': {
        'title': 'PAYMENT DEMAND NOTICE', 'help': 'For an ordinary outstanding invoice or loan payment. A dishonoured-cheque notice requires a statutory format.',
        'parties': ['Creditor’s name and service address', 'Debtor’s name and service address'],
        'action': 'Payment requested and method', 'fields': {
            'basis': 'Agreement, invoice or loan reference and payment due date',
            'amount': 'Amount due and calculation, including credits or part payments',
            'prior': 'Earlier demands and responses', 'service': 'Proposed service method',
            'response': 'Requested response date or period, if reviewed',
        },
    },
    'Reply to notice': {
        'title': 'REPLY TO NOTICE', 'help': 'For responding to a private notice. Address each numbered allegation and have admissions reviewed before sending.',
        'parties': ['Respondent’s name and service address', 'Notice sender or advocate and service address'],
        'action': 'Requested outcome or proposed resolution', 'fields': {
            'received': 'Date the notice was received and mode of service',
            'reply': 'Paragraph-wise reply, including any admissions, denials and reasons',
        },
    },
    'Consumer commission complaint': {
        'title': 'CONSUMER COMPLAINT', 'help': 'For a confirmed consumer commission. The e-Jagriti filing guide lists separate uploads including the index, synopsis, memo of parties, complaint with notarised affidavit and annexures.',
        'parties': ['Complainant’s name, address and contact details', 'Opposite party names, roles and service addresses'],
        'action': 'Relief sought and calculation', 'source': CONSUMER, 'fields': {
            'forum': 'Name and place of the consumer commission',
            'transaction': 'Goods or services, order or invoice, purchase date and amount actually paid',
            'cause': 'What went wrong and when the cause of action arose',
            'prior': 'Earlier complaints and each opposite party’s response',
            'jurisdiction': 'Facts supporting territorial and monetary jurisdiction',
            'limitation': 'Dates relevant to limitation and any delay application requiring review',
        },
    },
    'Written police complaint': {
        'title': 'WRITTEN COMPLAINT TO POLICE', 'help': 'A factual account signed by the person reporting. The police determine how to record and act on it.',
        'parties': ['Informant’s name, address and safe contact details', 'Police station and address'],
        'action': 'Action requested from police', 'source': POLICE, 'fields': {
            'incident': 'Incident date, time and exact location',
            'witnesses': 'People involved or witnesses, where known and safe to include',
            'impact': 'Injury, loss or property identifiers, if relevant',
            'prior': 'Any prior police report or acknowledgement',
        },
    },
    'Food safety grievance': {
        'title': 'FOOD SAFETY GRIEVANCE', 'help': 'For reporting a food-safety concern to the appropriate authority. A compensation claim uses a separate route.',
        'parties': ['Complainant’s name, address and safe contact details', 'Food safety authority or grievance recipient'],
        'action': 'Investigation, inspection or other action requested', 'source': FOOD, 'fields': {
            'transaction': 'Food business, outlet or platform and purchase or order details',
            'product': 'Food item, batch or lot, expiry, and licence details if known',
            'impact': 'Symptoms, when they began and supporting medical records if relevant',
            'prior': 'Earlier complaint and food business response',
        },
    },
    'Civil plaint for advocate review': {
        'title': 'DRAFT PLAINT FOR ADVOCATE REVIEW', 'help': 'For discussing a potential civil suit. Have an advocate verify the forum, pleadings and local filing rules.',
        'parties': ['Plaintiff’s name, description and address', 'Defendant names, descriptions and addresses'],
        'action': 'Specific relief sought', 'source': CPC, 'fields': {
            'forum': 'Name and place of the proposed court', 'cause': 'Cause of action and dates',
            'jurisdiction': 'Facts supporting the court’s jurisdiction', 'valuation': 'Suit valuation and court fee for verification',
            'limitation': 'Limitation dates and any grounds requiring review', 'property': 'Property schedule, boundaries or survey details if applicable',
        },
    },
    'Case brief': {
        'title': 'CONFIDENTIAL CASE BRIEF FOR LEGAL REVIEW', 'help': 'For a consultation when the correct court, remedy, or specialist document is uncertain.',
        'parties': ['Person seeking advice and safe contact details', 'Other parties or organisations involved'],
        'action': 'Outcome sought and questions for counsel', 'fields': {
            'prior': 'Procedural status and earlier steps', 'response': 'Known notice, hearing or response dates',
            'issues': 'Disputed facts, missing information and urgency',
        },
    },
}

FORMAT_ALIASES = {'Complaint draft': 'Consumer commission complaint'}
PLEADINGS = {'Consumer commission complaint', 'Civil plaint for advocate review'}
NOTICES = {'Legal notice', 'Payment demand notice', 'Reply to notice'}


def document_draft(record, options):
    if not isinstance(options, dict):
        raise ValueError('Choose a document format and provide its fields.')
    kind = options.get('kind', 'Legal notice')
    if not isinstance(kind, str):
        raise ValueError('Unsupported document type.')
    kind = FORMAT_ALIASES.get(kind, kind)
    if kind not in FORMATS:
        raise ValueError('Unsupported document type.')
    spec = FORMATS[kind]

    def value(key, fallback='', limit=3000):
        text = options.get(key, '')
        if not isinstance(text, str) or len(text) > limit:
            raise ValueError('Invalid document field: ' + key)
        return text.strip() or fallback

    sender = value('sender', '[SENDER NAME AND ADDRESS]', 2000)
    recipient = value('recipient', '[RECIPIENT NAME AND ADDRESS]', 2000)
    reference = value('reference', limit=500)
    subject = value('subject', '[State the specific matter and relevant reference]', 400)
    action = value('demand', '[Specify the requested action or relief]')
    facts = value('facts', limit=26000)
    if 'facts' not in options and kind == 'Case brief':
        facts = '\n'.join(event['description'] for event in record.get('events', []))
    if facts:
        facts = '\n\n'.join(f'{index}. {line.strip()}' for index, line in enumerate(
            (line for line in facts.splitlines() if line.strip()), 1))
    else:
        facts = '[Add the material facts in sequence. Identify disputed facts and the source of each allegation.]'
    enclosures = value('enclosures', '[List only the documents actually attached, or state None.]', 4000)
    if not enclosures.startswith('[') and enclosures.casefold() != 'none':
        enclosures = '\n'.join(f'{index}. {item.strip()}' for index, item in enumerate(
            (line for line in enclosures.splitlines() if line.strip()), 1))
    fields = {key: value(key) for key in spec['fields']}

    def section(key):
        label = spec['fields'][key]
        return f'{label}\n{fields[key] or "[Complete if applicable]"}'

    paragraphs = ['DRAFT FOR REVIEW', spec['title']]
    if kind in NOTICES:
        paragraphs.append('Date: [date of issue]')
        if fields.get('service'):
            paragraphs.append(f'Proposed service method: {fields["service"]}')
    if kind in PLEADINGS:
        paragraphs += [f'BEFORE {fields["forum"] or "[NAME AND PLACE OF THE COURT OR COMMISSION]"}',
                       f'{sender}\n… {"Complainant" if kind.startswith("Consumer") else "Plaintiff"}',
                       'VERSUS',
                       f'{recipient}\n… {"Opposite party or parties" if kind.startswith("Consumer") else "Defendant or defendants"}']
    else:
        if kind == 'Written police complaint':
            recipient = f'The Officer-in-Charge\n{recipient}'
        paragraphs += [f'From: {sender}\nTo: {recipient}']
    paragraphs += [f'Subject: {subject}']
    if reference or kind == 'Reply to notice':
        paragraphs.append(f'Reference: {reference or "[Notice date and reference]"}')
    if kind in NOTICES:
        paragraphs.append('Sir / Madam,')
    if kind == 'Reply to notice':
        paragraphs += [section('received'), section('reply')]
    if kind in ('Written police complaint', 'Food safety grievance'):
        paragraphs += [section(key) for key in ('incident', 'transaction', 'product') if key in fields]
    paragraphs += ['MATERIAL FACTS', facts]
    presented = {'forum', 'received', 'reply', 'incident', 'product', 'service'}
    if kind == 'Food safety grievance':
        presented.add('transaction')
    for key in fields:
        if key not in presented and (fields[key] or kind in PLEADINGS or key in {'basis', 'amount'}):
            paragraphs.append(section(key))
    paragraphs += [spec['action'].upper(), action, 'ENCLOSURES', enclosures]
    if kind in PLEADINGS:
        paragraphs += ['VERIFICATION',
                       'I, [name], verify that paragraphs [identify] are true to my personal knowledge and that paragraphs [identify] are based on [identify the information and its source], which I believe to be true.']
    elif kind in NOTICES:
        paragraphs.append('Yours faithfully,')
    paragraphs += ['Place: [place]\nDate: [date of signing]\nSignature: ____________________']
    draft = '\n\n'.join(paragraphs)
    if len(draft) > 60000:
        raise ValueError('The draft is too long. Shorten the facts or the attachment descriptions.')
    return draft
