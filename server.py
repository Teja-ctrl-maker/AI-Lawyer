"""Local-only HTTP app. Case data stays in memory; never logged to disk."""
import base64
from collections import deque
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
import urllib.parse
import core
import accounts
from case_intelligence import catalogue_excerpts, compare_record, compare_review, fact_map, next_question, review_snapshot
from evidence_plan import build_evidence_plan
from court_guidance import build_court_guidance
from legal_documents import FORMATS
from research import extract_pdf

SESSIONS = {}
@dataclass
class Session:
    deadline: float
    username: str | None
    live_calls: int = 0


GUESTS = {}
AUTH_ATTEMPTS = deque()
AUTH_SLOTS = threading.BoundedSemaphore(2)
LOCK = threading.RLock()
GUEST_IDLE_SECONDS = 30 * 60
MAX_REQUEST_BYTES = 3_000_000
PORT = int(os.getenv('PORT','8765'))
STATIC = Path(__file__).parent / 'static'


def drop_guest(guest):
    """Call with LOCK held. Remove every case owned by this guest."""
    GUESTS.pop(guest, None)
    for sid in [sid for sid, case in SESSIONS.items() if case['guest'] == guest]:
        del SESSIONS[sid]


def expire_guests():
    with LOCK:
        now = time.monotonic()
        for guest in [token for token, session in GUESTS.items() if session.deadline <= now]:
            drop_guest(guest)


def session_active(token):
    session = GUESTS.get(token)
    return session is not None and session.deadline > time.monotonic()


def sweep_guests():
    while True:
        time.sleep(15)
        expire_guests()


def case_insights(case):
    record = case['record']
    seen = case.get('seen_questions', [])
    return {
        'fact_map': fact_map(record, case['documents']),
        'follow_up': next_question(record, core.retrieve(record), seen),
        'seen_questions': seen,
    }


def mark_question(case, key):
    seen = case.setdefault('seen_questions', [])
    if key not in seen:
        seen.append(key)
        del seen[:-120]


def imported_history(payload):
    seen = core.strings(payload.get('seen_questions', []), 'question history', 120)
    if any(len(key) > 40 for key in seen):
        raise ValueError('Invalid question history.')
    snapshot = payload.get('review_snapshot')
    if snapshot is None:
        return seen, None
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get('laws'), dict):
        raise ValueError('Invalid previous review.')
    allowed = {s['id'] for s in core.sources()}
    laws = snapshot['laws']
    if len(laws) > 12 or any(key not in allowed or value not in ('supported', 'conditional', 'unsupported')
                             for key, value in laws.items()):
        raise ValueError('Invalid previous review.')
    stage = snapshot.get('stage')
    if stage is not None and stage not in core.PROCEDURE_STAGES:
        raise ValueError('Invalid previous case stage.')
    return seen, {'laws': laws, 'stage': stage, 'next_steps': core.strings(snapshot.get('next_steps'), 'previous steps')}


def attach_scope_checks(result, candidates, record, procedure):
    sources = {source['id']: source for source in candidates}
    dates = {event['date'] for event in record['events']}
    for law in result['laws']:
        source = sources[law['source_id']]
        check = law.setdefault('source_check', {'status': 'Source excerpt available', 'passages': []})
        if not check['passages']:
            check['passages'] = catalogue_excerpts(source, law['explanation'])
        notes = []
        first_date = source.get('effective_from')
        if first_date:
            if None in dates or any(date < first_date for date in dates if date):
                notes.append('The timeline has an unknown or earlier date. Confirm the relevant incident or proceeding date before relying on this provision.')
            notes.append('This catalogue records a start date of ' + first_date + ' for this provision.')
        if source.get('case_stage') == 'follow_up':
            notes.append('Review this as a procedural or later option. Check whether the specific conditions have been reached.')
        if procedure['stage'] in ('notice', 'hearing', 'decision'):
            notes.append('Check the actual notice or order for dates and directions that apply to your case.')
        check['scope'] = notes


class Handler(BaseHTTPRequestHandler):
    server_version = 'CaseCompanion'
    sys_version = ''
    timeout = 10
    accounts_enabled = True
    guest_limit = 200

    def live_enabled(self):
        return core.configured()

    def reserve_live_calls(self, guest, count):
        pass

    def request_origin(self):
        return f"http://{self.headers['Host']}"

    def log_message(self, *_):
        pass  # Do not log user material or session IDs.

    def respond(self, body, status=200, content_type='application/json; charset=utf-8', filename=None):
        if not isinstance(body, bytes):
            body = json.dumps(body,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'; form-action 'self'")
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Cross-Origin-Resource-Policy','same-origin')
        self.send_header('Permissions-Policy','camera=(), microphone=(), geolocation=()')
        if filename:
            self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True

    def safe_host(self):
        return self.headers.get_all('Host') in ([f'127.0.0.1:{PORT}'], [f'localhost:{PORT}'])

    def start_session(self, username=None):
        with LOCK:
            if len(GUESTS) >= self.guest_limit:
                return self.respond({'error':'Too many sessions. Try again shortly.'}, 503)
            token = secrets.token_urlsafe(32)
            GUESTS[token] = Session(time.monotonic() + GUEST_IDLE_SECONDS, username)
        return self.respond({'guest':token, 'username':username})

    def account_session(self, payload, creating):
        with LOCK:
            now = time.monotonic()
            while AUTH_ATTEMPTS and now - AUTH_ATTEMPTS[0] >= 60:
                AUTH_ATTEMPTS.popleft()
            if len(AUTH_ATTEMPTS) >= 12:
                return self.respond({'error':'Too many sign-in attempts. Try again in a minute.'}, 429)
            AUTH_ATTEMPTS.append(now)
        creds = accounts.credentials(payload, creating)
        if not creds:
            error = ('Use a 3–32 character username (letters, numbers, dots, underscores or hyphens) '
                     'and a 15–128 character password.' if creating else 'Username or password is incorrect.')
            return self.respond({'error':error}, 400 if creating else 401)
        if not AUTH_SLOTS.acquire(blocking=False):
            return self.respond({'error':'Sign-in is busy. Try again shortly.'}, 503)
        try:
            accepted = (accounts.register if creating else accounts.authenticate)(*creds)
        except (OSError, sqlite3.Error):
            return self.respond({'error':'The local account database is unavailable.'}, 503)
        finally:
            AUTH_SLOTS.release()
        if not accepted:
            error = 'That username is already taken.' if creating else 'Username or password is incorrect.'
            return self.respond({'error':error}, 409 if creating else 401)
        return self.start_session(creds[0])

    def read_json(self, size):
        deadline = time.monotonic() + 10
        body = bytearray()
        while len(body) < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            self.connection.settimeout(remaining)
            block = self.rfile.read1(min(64_000, size - len(body)))
            if not block:
                raise ValueError('The request body was incomplete.')
            body.extend(block)
        return json.loads(body)

    def do_GET(self):
        if not self.safe_host():
            return self.respond({'error':'Invalid host'},403)
        path=urllib.parse.urlsplit(self.path).path
        if path=='/api/config':
            return self.respond({'live':self.live_enabled(),'accounts':self.accounts_enabled,'guest_idle_seconds':GUEST_IDLE_SECONDS,
                'model':os.getenv('LAWYER_MODEL','Not configured'),
                'sample':core.DEMO_STORY,'source_count':len(core.sources()),'document_formats':FORMATS})
        files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
        if path not in files:
            return self.respond({'error':'Not found'},404)
        filename,typ=files[path]
        self.respond((STATIC/filename).read_bytes(),content_type=typ)

    def do_POST(self):
        if not self.safe_host():
            return self.respond({'error':'Invalid host'},403)
        origin=self.headers.get('Origin')
        if ((origin and origin != self.request_origin())
                or self.headers.get('Sec-Fetch-Site') in ('cross-site', 'same-site')):
            # Drain a bounded request before closing so Windows can deliver the 403
            # rather than resetting a connection with unread input.
            try:
                rejected_size=int(self.headers.get('Content-Length','0'))
                if 0<rejected_size<=4096:
                    self.rfile.read(rejected_size)
            except (ValueError, OSError):
                pass
            return self.respond({'error':'Cross-origin requests are not accepted'},403)
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':
            return self.respond({'error':'JSON required'},415)
        try:
            lengths = self.headers.get_all('Content-Length', [])
            if self.headers.get_all('Transfer-Encoding') or len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdecimal():
                raise ValueError('A single valid Content-Length is required.')
            size = int(lengths[0])
            if size<=0 or size>MAX_REQUEST_BYTES:
                raise ValueError('Request too large or empty.')
            payload=self.read_json(size)
            if not isinstance(payload,dict):
                raise ValueError('Expected a JSON object.')
            expire_guests()
            if self.path == '/api/guest':
                return self.start_session()
            if self.path in ('/api/register', '/api/login'):
                if not self.accounts_enabled:
                    return self.respond({'error':'This demo is guest-only.'}, 404)
                return self.account_session(payload, self.path == '/api/register')
            guest = payload.get('guest')
            with LOCK:
                if not isinstance(guest, str) or not session_active(guest):
                    return self.respond({'error':'Your session ended. Sign in or continue as a guest.'}, 401)
                if self.path == '/api/guest-end':
                    drop_guest(guest)
                    return self.respond({'ok': True})
                GUESTS[guest].deadline = time.monotonic() + GUEST_IDLE_SECONDS
            if self.path == '/api/pdf-preview':
                return self.respond(extract_pdf(payload.get('pdf')))
            if self.path == '/api/import':
                record = core.validate_record(payload.get('record'))
                documents = core.document_passages(payload.get('documents', []))
                seen, previous_review = imported_history(payload)
                language = payload.get('language', 'English')
                if language not in ('English', 'Hindi', 'Hinglish'):
                    raise ValueError('The saved file has an unsupported language.')
                with LOCK:
                    if not session_active(guest):
                        return self.respond({'error':'Your guest session ended.'}, 401)
                    for old in [sid for sid, case in SESSIONS.items() if case['guest'] == guest]:
                        del SESSIONS[old]
                    sid = secrets.token_urlsafe(32)
                    SESSIONS[sid] = {
                        'record': record, 'documents': documents, 'language': language,
                        'guest': guest, 'confirmed': False, 'demo': False, 'live': False,
                        'lock': threading.RLock(), 'seen_questions': seen, 'previous_review': previous_review,
                    }
                    case = SESSIONS[sid]
                return self.respond({'id':sid, 'record':record, 'documents':documents,
                                     'insights':case_insights(case), 'review_snapshot':previous_review})
            if self.path=='/api/intake':
                language=payload.get('language','English')
                if language not in ('English','Hindi','Hinglish'):
                    raise ValueError('Choose a supported language.')
                demo=payload.get('demo') is True
                live = payload.get('live_consent') is True and self.live_enabled() and not demo
                if not demo and not live and language!='English':
                    raise ValueError('Hindi and Hinglish need a live model. Offline extraction only recognises English dates.')
                documents = core.document_passages(payload.get('documents', []))
                if demo and documents:
                    raise ValueError('Switch to your own case to use PDF passages.')
                if live:
                    self.reserve_live_calls(guest, 1)
                record=core.intake(payload.get('story',''),payload.get('evidence',''),language,demo,documents,use_live=live)
                with LOCK:
                    if not session_active(guest):
                        return self.respond({'error':'Your guest session ended.'}, 401)
                    for old in [sid for sid, case in SESSIONS.items() if case['guest'] == guest]:
                        del SESSIONS[old]
                    sid=secrets.token_urlsafe(32)
                    SESSIONS[sid]={'record':record,'confirmed':False,'demo':demo,'language':language,'documents':documents,'guest':guest,'live':live,'lock':threading.RLock()}
                    case = SESSIONS[sid]
                return self.respond({'id':sid,'record':record,'mode':'Scripted sample' if demo else 'Live AI' if live else 'Offline extraction',
                                     'insights':case_insights(case)})
            sid=payload.get('id')
            if not isinstance(sid, str):
                return self.respond({'error':'Case expired or missing. Start with your story again.'},404)
            with LOCK:
                case=SESSIONS.get(sid)
            if not case or case['guest'] != guest:
                return self.respond({'error':'Case expired or missing. Start with your story again.'},404)
            if self.path=='/api/clear':
                with LOCK:
                    if SESSIONS.get(sid) is case:
                        del SESSIONS[sid]
                return self.respond({'ok':True})
            with case['lock']:
                with LOCK:
                    if SESSIONS.get(sid) is not case or not session_active(guest):
                        return self.respond({'error':'Case expired or missing.'},404)
                if self.path == '/api/skip-question':
                    current = case_insights(case)['follow_up']
                    if not current or payload.get('key') != current['key']:
                        raise ValueError('This follow-up question has changed. Refresh the case summary.')
                    mark_question(case, current['key'])
                    return self.respond({'insights': case_insights(case)})
                if self.path == '/api/follow-up':
                    live = payload.get('live_consent') is True and self.live_enabled()
                    update = core.textfield(payload.get('story'), 'case update', 12000).strip()
                    documents = core.document_passages(payload.get('documents', case['documents']))
                    question = None
                    if payload.get('question_key'):
                        question = case_insights(case)['follow_up']
                        if not question or question['key'] != payload['question_key']:
                            raise ValueError('This follow-up question has changed. Refresh the case summary.')
                    old_record, old_documents = case['record'], case['documents']
                    if live:
                        self.reserve_live_calls(guest, 1)
                    record = core.intake(update, payload.get('evidence', ''), case['language'],
                                         documents=documents, use_live=live, previous_record=old_record,
                                         focus_question=question['question'] if question else None)
                    changes = compare_record(old_record, record, old_documents, documents)
                    with LOCK:
                        if SESSIONS.get(sid) is not case:
                            return self.respond({'error':'Case expired or missing.'},404)
                        case.update(record=record, documents=documents, confirmed=False, demo=False, live=live)
                        case['last_revision'] = changes
                        if question:
                            mark_question(case, question['key'])
                        if case.get('analysis'):
                            case['previous_review'] = review_snapshot(case['analysis'])
                        for key in ('analysis', 'draft', 'procedure', 'sources'):
                            case.pop(key, None)
                    return self.respond({'id':sid, 'record':record,
                                         'mode':'Live AI' if live else 'Offline extraction',
                                         'insights':case_insights(case), 'changes':changes})
                if self.path=='/api/confirm':
                    record=core.validate_record(payload.get('record'))
                    # Editing the scripted sample turns it into a real case; never reuse sample legal conclusions.
                    if record!=case['record']:
                        case['demo']=False
                        case['last_revision'] = compare_record(case['record'], record, case['documents'], case['documents'])
                    if case.get('analysis'):
                        case['previous_review'] = review_snapshot(case['analysis'])
                    case.update(record=record,confirmed=True)
                    case.pop('analysis',None); case.pop('draft',None)
                    case.pop('procedure', None); case.pop('sources', None)
                    candidates = core.retrieve(record)
                    return self.respond({'confirmed':True,'record':record,'demo':case['demo'], 'insights':case_insights(case),
                                         'evidence_plan':build_evidence_plan(record, candidates),
                                         'court_guidance':build_court_guidance(record, candidates)})
                if not case['confirmed']:
                    raise ValueError('Confirm the case before continuing.')
                live = case['live'] and payload.get('live_consent') is True and self.live_enabled()
                if self.path=='/api/analyse':
                    procedure = core.procedure_context(payload)
                    if live and not case['demo']:
                        self.reserve_live_calls(guest, 2)
                    result, candidates = core.analyse(case['record'], case['demo'], case['language'],
                                                      procedure, case['documents'], use_live=live)
                    with LOCK:
                        if SESSIONS.get(sid) is not case:
                            return self.respond({'error':'Case expired or missing.'},404)
                    result['procedure'] = procedure | {
                        'label': core.PROCEDURE_STAGES[procedure['stage']],
                        'guidance': core.PROCEDURE_GUIDANCE[procedure['stage']],
                    }
                    result['evidence_plan'] = build_evidence_plan(case['record'], candidates, procedure, result['laws'])
                    result['court_guidance'] = build_court_guidance(case['record'], candidates, procedure)
                    attach_scope_checks(result, candidates, case['record'], procedure)
                    current_review = review_snapshot(result)
                    previous_review = review_snapshot(case.get('analysis')) or case.pop('previous_review', None)
                    case.pop('previous_review', None)
                    result['changes'] = compare_review(previous_review, current_review,
                                                       {s['id']: s for s in core.sources()}, case.pop('last_revision', None))
                    case.update(analysis=result, sources=candidates, procedure=procedure)
                    case.pop('draft', None)
                    return self.respond({'analysis':result,'sources':candidates,'review_snapshot':current_review})
                if self.path=='/api/rehearse':
                    if 'analysis' not in case:
                        raise ValueError('Explore the legal issues before practising.')
                    result = core.prepare_rehearsal(
                        case['record'], case['analysis'], payload.get('scenario'),
                        payload.get('answer'), case['demo'], case['language'], use_live=live)
                    with LOCK:
                        if SESSIONS.get(sid) is not case:
                            return self.respond({'error':'Case expired or missing.'},404)
                    return self.respond(result)
                if self.path=='/api/draft':
                    if 'analysis' not in case:
                        raise ValueError('Review the legal analysis before drafting.')
                    case['draft']=core.draft(case['record'],case['analysis'],payload.get('options',{}))
                    return self.respond({'draft':case['draft']})
                if self.path=='/api/export':
                    if 'draft' not in case:
                        raise ValueError('Create a draft before exporting.')
                    text=core.textfield(payload.get('text',case['draft']),'draft',60000)
                    template=payload.get('template')
                    template=base64.b64decode(template,validate=True) if template else None
                    body=core.docx_bytes(text,payload.get('font','Times New Roman'),int(payload.get('size',12)),template)
                    return self.respond(body,content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',filename='case-draft.docx')
                return self.respond({'error':'Not found'},404)
        except TimeoutError:
            self.respond({'error': 'The request timed out.'}, 408)
        except (json.JSONDecodeError, UnicodeError, RecursionError):
            self.respond({'error': 'The request contains invalid or overly nested data.'}, 400)
        except ValueError as exc:
            self.respond({'error':str(exc)},400)
        except (TypeError, KeyError, AttributeError):
            self.respond({'error': 'The request contains invalid fields.'}, 400)
        except Exception:
            self.respond({'error':'The operation could not finish. Check the input or DOCX template and retry. No document was sent or filed.'},500)


class LocalServer(ThreadingHTTPServer):
    request_queue_size = 24
    _slots = threading.BoundedSemaphore(24)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def handle_error(self, request, client_address):
        # Suppress request-linked tracebacks and error objects in process logs.
        return


if __name__=='__main__':
    print(f'Case Companion is running at http://127.0.0.1:{PORT}')
    print('Mode: '+('Live model enabled' if core.configured() else 'Offline extraction + labelled sample; configure .env for live AI'))
    threading.Thread(target=sweep_guests, daemon=True).start()
    LocalServer(('127.0.0.1',PORT),Handler).serve_forever()
