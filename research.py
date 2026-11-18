"""Search concepts and document passages used by the case workflow."""
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import unicodedata


# These are retrieval hints. They add candidates without deciding applicability.
CONCEPTS = {
    'taking': (('bns-303',), ('phone le gaya', 'phone chori', 'bina puche le gaya', 'took my phone', 'मेरा फोन ले गया')),
    'unsafe_food': (('fssa-26', 'fssa-59'), ('got sick after eating', 'khana khake ulti', 'khana khane ke baad', 'keeda nikla', 'खाने के बाद उल्टी')),
    'faulty_goods': (('cpa-2-7', 'cpa-2-10', 'cpa-35', 'cpa-39'), ('paise wapas', 'khareeda', 'chalna band', 'does not turn on', 'won’t switch on', 'won\'t switch on')),
    'failed_service': (('cpa-2-7', 'cpa-2-11', 'cpa-35', 'cpa-39'), ('paid for a repair', 'repair ke paise', 'never did the work', 'kaam nahi kiya')),
    'lost_possession': (('sra-5', 'sra-6'), ('changed the locks', 'locked me out', 'ghar se nikal diya', 'tala badal diya', 'घर से निकाल')),
    'ownership_dispute': (('sra-34', 'sra-38'), ('claims my plot', 'plot par kabza', 'zameen meri', 'boundary wall', 'जमीन पर कब्जा')),
    'sexual_assault': (('bns-63',), ('forced himself on me', 'zabardasti sex', 'sex without consent')),
    'child_sexual_contact': (('pocso-2-1-d', 'pocso-7', 'pocso-19'), ('child sexual touching', 'bachchi ko galat tareeke se chhua')),
    'police_record': (('bnss-173',), ('no acknowledgement from police', 'police gave me no acknowledgement', 'police would not register', 'fir nahi likhi', 'police ne complaint nahi li', 'एफआईआर दर्ज नहीं')),
    'digital_evidence': (('bsa-63',), ('submit screenshots', 'use whatsapp messages in court', 'electronic record certificate', 'screenshot court mein')),
}


def normalise(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def has_phrase(text, phrase):
    return bool(re.search(r'(?<!\w)' + re.escape(normalise(phrase)) + r'(?!\w)', text))


def concept_scores(query, model_concepts):
    scores = {}
    for name, (source_ids, phrases) in CONCEPTS.items():
        weight = 3 if any(has_phrase(query, phrase) for phrase in phrases) else int(name in model_concepts)
        if weight:
            for source_id in source_ids:
                scores[source_id] = max(weight, scores.get(source_id, 0))
    return scores


def relevant_passages(documents, query, limit=5):
    stopwords = {'the', 'and', 'for', 'you', 'your', 'that', 'what', 'when', 'with', 'have', 'from'}
    words = set(re.findall(r'[^\W_]{3,}', normalise(query))) - stopwords
    def rank(row):
        passage_words = set(re.findall(r'[^\W_]{3,}', normalise(row['text'])))
        return (row['ref'] not in query, -len(words & passage_words))
    ranked = sorted(documents, key=rank)
    return [row | {'text': row['text'][:1600]} for row in ranked[:limit]]


PDF_SLOTS = threading.BoundedSemaphore(2)


def extract_pdf(encoded):
    """Extract on the local server. The browser keeps the original PDF."""
    if not isinstance(encoded, str) or len(encoded) > 2_800_000:
        raise ValueError('Choose a PDF under 2 MB.')
    raw = base64.b64decode(encoded, validate=True)
    if len(raw) > 2_000_000 or not raw.startswith(b'%PDF-'):
        raise ValueError('Choose a valid PDF under 2 MB.')
    if not PDF_SLOTS.acquire(blocking=False):
        raise ValueError('PDF extraction is busy. Try again shortly.')
    try:
        worker = Path(__file__).with_name('pdf_worker.py')
        # Never inherit the model API key or pass case data in process arguments.
        worker_env = {key: value for key, value in os.environ.items()
                      if key.upper() in {'SYSTEMROOT', 'WINDIR', 'TMP', 'TEMP'}}
        result = subprocess.run([sys.executable, '-I', str(worker)], input=raw,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=12, env=worker_env,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise ValueError('The PDF could not be read. Try a smaller text PDF.')
        reply = json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        raise ValueError('PDF processing timed out. Try fewer pages or paste the relevant passage.') from None
    except (OSError, json.JSONDecodeError):
        raise ValueError('PDF processing failed. Paste the relevant passage or try another file.') from None
    finally:
        PDF_SLOTS.release()
    if 'error' in reply:
        raise ValueError(reply['error'])
    return reply
