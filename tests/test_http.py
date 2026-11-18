"""Integration checks; local sockets require network permission in restricted sandboxes."""
import json
import base64
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import server
import core


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http=server.LocalServer(('127.0.0.1',0),server.Handler)
        server.PORT=cls.http.server_port
        cls.base=f'http://127.0.0.1:{server.PORT}'
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close()

    def setUp(self):
        self.guest = None
        status, body, _ = self.post('guest', {})
        self.assertEqual(status, 200)
        self.guest = json.loads(body)['guest']

    def tearDown(self):
        if self.guest:
            self.post('guest-end', {})

    def post(self,path,data,origin=None):
        if self.guest and path != 'guest':
            data = {'guest': self.guest, **data}
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        req=urllib.request.Request(self.base+'/api/'+path,json.dumps(data).encode(),headers)
        try:
            with urllib.request.urlopen(req,timeout=10) as r:return r.status,r.read(),r.headers
        except urllib.error.HTTPError as e:
            try:return e.code,e.read(),e.headers
            finally:e.close()

    def start_case(self):
        status,body,_=self.post('intake',{'story':core.DEMO_STORY,'demo':True})
        self.assertEqual(status,200)
        return json.loads(body)

    def test_full_sample_export(self):
        case=self.start_case();sid=case['id']
        self.assertEqual(self.post('analyse',{'id':sid})[0],400)
        self.assertEqual(self.post('draft',{'id':sid})[0],400)
        self.assertEqual(self.post('confirm',{'id':sid,'record':case['record']})[0],200)
        self.assertEqual(self.post('draft',{'id':sid})[0],400)
        status,body,_=self.post('analyse',{'id':sid});self.assertEqual(status,200)
        self.assertEqual(len(json.loads(body)['analysis']['laws']),3)
        self.assertEqual(self.post('draft',{'id':sid,'options':{}})[0],200)
        status,body,headers=self.post('export',{'id':sid})
        self.assertEqual(status,200);self.assertTrue(body.startswith(b'PK'))
        self.assertIn('wordprocessingml',headers['Content-Type'])
        self.assertEqual(self.post('clear',{'id':sid})[0],200)
        self.assertEqual(self.post('confirm',{'id':sid, 'record':case['record']})[0],404)

    def test_cross_origin_blocked(self):
        self.assertEqual(self.post('intake',{'story':'hello'},'https://untrusted.example')[0],403)

    def test_reconfirmation_removes_prior_analysis_and_draft(self):
        case=self.start_case();sid=case['id']
        self.post('confirm',{'id':sid,'record':case['record']});self.post('analyse',{'id':sid});self.post('draft',{'id':sid})
        case['record']['goal']='A different requested outcome'
        self.post('confirm',{'id':sid,'record':case['record']})
        self.assertEqual(self.post('export',{'id':sid})[0],400)
        with server.LOCK:
            self.assertFalse(server.SESSIONS[sid]['demo'])
            self.assertNotIn('analysis', server.SESSIONS[sid])

    def test_resubmit_invalidates_old_case(self):
        case=self.start_case()
        status,body,_=self.post('intake',{'id':case['id'],'story':core.DEMO_STORY,'demo':True})
        self.assertEqual(status,200)
        self.assertEqual(self.post('confirm',{'id':case['id'], 'record':case['record']})[0],404)

    def test_unknown_session_rejected(self):
        self.assertEqual(self.post('analyse',{'id':'unknown'})[0],404)

    def test_fictional_evidence_map_and_follow_up_changes(self):
        story = 'On 12 November 2026 someone stole my phone from my bedroom.'
        documents = [{'document': 'D1', 'page': 1,
                      'text': 'Phone stolen from the bedroom on 12 November 2026.'}]
        status, body, _ = self.post('intake', {'story': story, 'documents': documents})
        self.assertEqual(status, 200, body)
        case = json.loads(body)
        sid = case['id']
        insights = case['insights']
        self.assertEqual(insights['follow_up']['key'], 'last-seen')
        self.assertEqual(insights['fact_map']['rows'][0]['materials'][0]['ref'], '[D1 p.1]')
        self.assertEqual(self.post('confirm', {'id': sid, 'record': case['record']})[0], 200)
        self.assertEqual(self.post('analyse', {'id': sid, 'stage': 'starting'})[0], 200)
        status, body, _ = self.post('follow-up', {
            'id': sid, 'story': 'I last saw my phone in the bedroom at 9 am.', 'question_key': 'last-seen',
        })
        self.assertEqual(status, 200, body)
        revised = json.loads(body)
        self.assertIn('last-seen', revised['insights']['seen_questions'])
        self.assertNotEqual(revised['insights']['follow_up']['key'], 'last-seen')
        self.assertTrue(revised['changes']['added'])
        self.assertEqual(self.post('analyse', {'id': sid})[0], 400)
        self.assertEqual(self.post('confirm', {'id': sid, 'record': revised['record']})[0], 200)
        status, body, _ = self.post('analyse', {'id': sid, 'stage': 'reported'})
        self.assertEqual(status, 200, body)
        changes = json.loads(body)['analysis']['changes']
        self.assertTrue(changes['stage_changed'])
        self.assertIn('the revised timeline', changes['revised_inputs'])

    def test_confirm_and_review_include_case_specific_court_guidance(self):
        for story, demo, judgement, route, excluded in (
            ('On 12 November 2026 someone stole my phone from my bedroom.', False,
             'Imran Pratapgadhi', 'BNSS section 173', 'Pioneer Urban'),
            (core.DEMO_STORY, True, 'Maruti Udyog', 'Section 35', 'Pioneer Urban'),
            ('On 12 November 2023 someone stole my phone from my bedroom.', False,
             None, None, 'Imran Pratapgadhi'),
        ):
            with self.subTest(story=story):
                status, body, _ = self.post('intake', {'story': story, 'demo': demo})
                self.assertEqual(status, 200, body)
                case = json.loads(body)
                status, body, _ = self.post('confirm', {'id': case['id'], 'record': case['record']})
                self.assertEqual(status, 200, body)
                confirmed = json.loads(body)['court_guidance']
                status, body, _ = self.post('analyse', {'id': case['id'], 'stage': 'hearing'})
                self.assertEqual(status, 200, body)
                reviewed = json.loads(body)['analysis']['court_guidance']
                for guidance in (confirmed, reviewed):
                    titles = ' '.join(item['title'] for item in guidance['suggestions'])
                    self.assertNotIn(excluded, titles)
                    if judgement:
                        self.assertIn(judgement, titles)
                        self.assertIn(route, guidance['route']['title'])
                        self.assertTrue(all(item['url'].startswith('https://api.sci.gov.in/')
                                            for item in guidance['suggestions']))
                    else:
                        self.assertIsNone(guidance['route'])

    def test_same_day_product_dispute_and_seller_reply_stage(self):
        story = ('The seller refused my refund at 7 pm on 16 November 2026. '
                 'Earlier that day, around 9 am, I bought a mixer for home use in Pune. '
                 'At 1 pm that same day, the mixer stopped working. '
                 'On 17 November 2026, the seller offered to inspect it.')
        status, body, _ = self.post('intake', {'story': story})
        self.assertEqual(status, 200, body)
        case = json.loads(body)
        events = case['record']['events']
        self.assertEqual([(event['date'], event.get('time')) for event in events], [
            ('2026-11-16', 'Around 9 am'), ('2026-11-16', '1 pm'),
            ('2026-11-16', '7 pm'), ('2026-11-17', None),
        ])
        ctx = {'id': case['id']}
        self.assertEqual(self.post('confirm', {**ctx, 'record': case['record']})[0], 200)
        status, body, _ = self.post('analyse', {**ctx, 'stage': 'notice', 'details': 'The seller replied.'})
        self.assertEqual(status, 200, body)
        result = json.loads(body)['analysis']
        ids = {law['source_id'] for law in result['laws']}
        self.assertIn('cpa-2-10', ids)
        self.assertNotIn('cpa-38', ids)
        self.assertIn('seller says you caused the fault', result['scenarios'][0]['question'])
        status, body, _ = self.post('analyse', {**ctx, 'stage': 'hearing',
                                              'details': 'The consumer commission admitted my complaint.'})
        self.assertEqual(status, 200, body)
        self.assertIn('cpa-38', {law['source_id'] for law in json.loads(body)['analysis']['laws']})

        status, body, _ = self.post('intake', {
            'story': 'The seller refused the refund that evening. Earlier that day, I bought the mixer.',
        })
        self.assertEqual(status, 200, body)
        undated = json.loads(body)['record']['events']
        self.assertTrue(undated[0]['description'].startswith('Earlier that day'))
        self.assertTrue(all(event['date'] is None and event['day'] == 'Same day' for event in undated))

    def test_guest_isolation_and_end(self):
        case = self.start_case()
        sid = case['id']
        other = json.loads(self.post('guest', {})[1])['guest']
        self.assertEqual(self.post('confirm', {'id': sid, 'record': case['record'], 'guest': other})[0], 404)
        self.post('guest-end', {'guest': other})
        self.assertEqual(self.post('guest-end', {})[0], 200)
        self.assertEqual(self.post('confirm', {'id': sid, 'record':case['record']})[0], 401)
        with server.LOCK:
            self.assertNotIn(sid, server.SESSIONS)
            self.assertNotIn(self.guest, server.GUESTS)

    def test_idle_expiry_removes_case(self):
        case = self.start_case()
        with server.LOCK:
            server.GUESTS[self.guest].deadline = 0
        server.expire_guests()
        with server.LOCK:
            self.assertNotIn(case['id'], server.SESSIONS)
        self.assertEqual(self.post('clear', {'id': case['id']})[0], 401)

    def test_guest_default_uses_no_remote_model(self):
        with patch('core.configured', return_value=True), patch('core.model_json') as model:
            status, body, _ = self.post('intake', {'story': 'Someone stole my phone.'})
            self.assertEqual(status, 200)
            case = json.loads(body)
            self.assertEqual(case['mode'], 'Offline extraction')
            self.assertEqual(self.post('confirm', {'id': case['id'], 'record': case['record']})[0], 200)
            self.assertEqual(self.post('analyse', {'id': case['id'], 'live_consent': True})[0], 200)
            model.assert_not_called()

    def test_registered_user_can_sign_in_after_sign_out(self):
        with TemporaryDirectory() as directory, patch('accounts.ACCOUNT_DB', Path(directory) / 'users.sqlite3'):
            payload = {'username': 'Fictional.User', 'password': 'fictional login phrase'}
            status, body, _ = self.post('register', payload)
            self.assertEqual(status, 200, body)
            account = json.loads(body)
            self.assertEqual(account['username'], 'fictional.user')
            self.assertNotEqual(self.guest, account['guest'])
            self.assertEqual(self.post('register', payload)[0], 409)
            self.assertEqual(self.post('guest-end', {'guest': account['guest']})[0], 200)
            self.assertEqual(self.post('login', payload | {'password':'wrong password'})[0], 401)
            status, body, _ = self.post('login', payload)
            self.assertEqual(status, 200, body)
            self.assertNotEqual(account['guest'], json.loads(body)['guest'])
            self.assertEqual(self.post('guest-end', {'guest': json.loads(body)['guest']})[0], 200)

    def test_import_and_follow_up_in_new_guest(self):
        original = self.start_case()
        self.post('guest-end', {})
        self.guest = json.loads(self.post('guest', {})[1])['guest']
        with patch('core.configured', return_value=True), patch('core.model_json') as model:
            status, body, _ = self.post('import', {
                'record': original['record'], 'language': 'English', 'documents': [],
            })
            self.assertEqual(status, 200, body)
            imported = json.loads(body)
            self.assertNotEqual(imported['id'], original['id'])
            self.assertEqual(self.post('analyse', {'id': imported['id']})[0], 400)
            status, body, _ = self.post('follow-up', {
                'id': imported['id'], 'story': 'On 21 October 2026 the seller called.',
            })
            self.assertEqual(status, 200, body)
            updated = json.loads(body)['record']
            self.assertEqual(len(updated['events']), 5)
            self.assertEqual(updated['events'][-1]['date'], '2026-10-21')
            self.assertEqual(self.post('confirm', {'id': imported['id'], 'record': updated})[0], 200)
            model.assert_not_called()

    def test_pdf_preview_then_selected_page_in_case(self):
        try:
            from pypdf import PdfReader, PdfWriter
        except ImportError:
            self.skipTest('PDF support requires pypdf')
        original = PdfReader(core.ROOT / 'data' / 'consumer.pdf')
        pdf = PdfWriter()
        pdf.add_page(original.pages[0])
        pdf.add_page(original.pages[1])
        stream = io.BytesIO()
        pdf.write(stream)
        status, body, _ = self.post('pdf-preview', {'pdf': base64.b64encode(stream.getvalue()).decode('ascii')})
        self.assertEqual(status, 200, body)
        pages = json.loads(body)['pages']
        second_page = next(page for page in pages if page['page'] == 2)
        with patch('core.configured', return_value=False):
            status, body, _ = self.post('intake', {
                'story': 'I bought a faulty product and want a refund.',
                'documents': [{'document': 'D1', 'page': 2, 'text': second_page['text']}],
            })
        self.assertEqual(status, 200, body)
        case = json.loads(body)
        sid = case['id']
        self.assertIn('[D1 p.2]', '\n'.join(case['record']['evidence']))
        self.assertNotIn('[D1 p.1]', '\n'.join(case['record']['evidence']))
        self.assertEqual(self.post('confirm', {'id': sid, 'record': case['record']})[0], 200)
        self.assertEqual(self.post('raw', {'id': sid})[0], 404)
        with server.LOCK:
            self.assertEqual([p['ref'] for p in server.SESSIONS[sid]['documents']], ['[D1 p.2]'])
        self.assertEqual(self.post('clear', {'id': sid})[0], 200)


if __name__=='__main__':unittest.main()
