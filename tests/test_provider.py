import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch
import core


class ProviderTests(unittest.TestCase):
    def settings(self):
        return patch.dict(os.environ,{'LAWYER_API_BASE':'https://generativelanguage.googleapis.com/v1beta/openai',
                                    'LAWYER_MODEL':'gemini-flash-latest','LAWYER_API_KEY':'test-only-not-a-real-key'})

    def test_compatible_endpoint_and_json_response(self):
        response=io.BytesIO(json.dumps({'choices':[{'message':{'content':'{"ok":true}'}}]}).encode())
        with self.settings(),patch('core.MODEL_OPENER.open',return_value=response) as send:
            self.assertEqual(core.model_json('Return {"ok":true}',{}),{'ok':True})
            request=send.call_args.args[0]
            self.assertEqual(request.full_url,'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions')
            self.assertEqual(json.loads(request.data)['model'],'gemini-flash-latest')
            self.assertIn('Authorization',request.headers)
            self.assertEqual(request.get_header('User-agent'),'CaseCompanion/0.1')

    def test_openrouter_uses_gpt4o_and_application_attribution_headers(self):
        response=io.BytesIO(json.dumps({'choices':[{'message':{'content':'{"ok":true}'}}]}).encode())
        with patch.dict(os.environ, {'LAWYER_API_BASE':'https://openrouter.ai/api/v1',
                                     'LAWYER_MODEL':'openai/gpt-4o',
                                     'LAWYER_API_KEY':'test-only-not-a-real-key',
                                     'CASE_COMPANION_ORIGIN':'https://example.test'}), \
             patch('core.MODEL_OPENER.open', return_value=response) as send:
            self.assertEqual(core.model_json('Return JSON',{}),{'ok':True})
            request=send.call_args.args[0]
            self.assertEqual(request.full_url,'https://openrouter.ai/api/v1/chat/completions')
            self.assertEqual(json.loads(request.data)['model'],'openai/gpt-4o')
            self.assertEqual(request.get_header('Http-referer'),'https://example.test')
            self.assertEqual(request.get_header('X-title'),'Case Companion — AI Lawyer')
            self.assertEqual(json.loads(request.data)['provider'],{'zdr':True,'data_collection':'deny'})
            self.assertNotIn('response_format', json.loads(request.data))

    def test_provider_accepts_a_fenced_json_object(self):
        response=io.BytesIO(json.dumps({'choices':[{'message':{'content':'```json\n{"ok":true}\n```'}}]}).encode())
        with self.settings(),patch('core.MODEL_OPENER.open',return_value=response):
            self.assertEqual(core.model_json('Return JSON',{}),{'ok':True})

    def test_provider_accepts_segmented_content_with_a_json_prefix(self):
        response=io.BytesIO(json.dumps({'choices':[{'message':{'content':[
            {'type':'text','text':'Structured response: {"ok":true}'}]}}]}).encode())
        with self.settings(),patch('core.MODEL_OPENER.open',return_value=response):
            self.assertEqual(core.model_json('Return JSON',{}),{'ok':True})

    def test_key_rejection_has_safe_message(self):
        error=urllib.error.HTTPError('https://provider.invalid',403,'Forbidden',{},io.BytesIO(b'secret provider body'))
        with self.settings(),patch('core.MODEL_OPENER.open',side_effect=error):
            with self.assertRaisesRegex(ValueError,'HTTP 403') as failure:
                core.model_json('',{})
            self.assertNotIn('secret provider body',str(failure.exception))
            self.assertNotIn('test-only-not-a-real-key',str(failure.exception))

    def test_model_redirects_are_disabled(self):
        handler = next(h for h in core.MODEL_OPENER.handlers if isinstance(h, core.NoProviderRedirects))
        self.assertIsNone(handler.redirect_request(None, None, 302, '', {}, 'https://example.com'))

    def test_quota_error_is_distinct(self):
        error=urllib.error.HTTPError('https://provider.invalid',429,'Limit',{},io.BytesIO())
        with self.settings(),patch('core.MODEL_OPENER.open',side_effect=error):
            with self.assertRaisesRegex(ValueError,'quota or rate limit'):
                core.model_json('',{})

    def test_service_unavailable_is_distinct(self):
        error=urllib.error.HTTPError('https://provider.invalid',503,'Unavailable',{},io.BytesIO())
        with self.settings(),patch('core.MODEL_OPENER.open',side_effect=error):
            with self.assertRaisesRegex(ValueError,'HTTP 503'):
                core.model_json('',{})

    def test_exhausted_quota_does_not_suggest_temporary_retry(self):
        body=json.dumps({'error':{'type':'insufficient_quota','message':'private provider detail'}}).encode()
        error=urllib.error.HTTPError('https://provider.invalid',429,'Limit',{},io.BytesIO(body))
        with self.settings(),patch('core.MODEL_OPENER.open',side_effect=error):
            with self.assertRaisesRegex(ValueError,'API account has insufficient quota') as failure:
                core.model_json('',{})
            self.assertNotIn('private provider detail',str(failure.exception))

    def test_live_source_review_keeps_description_match_separate_from_proof(self):
        record=core.intake(core.DEMO_STORY,demo=True)
        candidate,_=core.analyse(record,True)
        candidate['laws'][0]['support']='supported'
        with self.settings(),patch('core.model_json',return_value=candidate):
            result,_=core.analyse(record)
            self.assertEqual(result['laws'][0]['support'],'supported')
            self.assertEqual(result['laws'][0]['relevance'],'Matches the reported description')
            self.assertIn('not been independently verified',result['laws'][0]['evidence_status'])

    def test_source_check_keeps_only_literal_passages_for_displayed_wording(self):
        record = core.intake(core.DEMO_STORY, demo=True)
        candidate, _ = core.analyse(record, True)
        law = candidate['laws'][0]
        sid = law['source_id']
        real_passage = 'buys any goods for a consideration which has been paid or promised'
        candidate['source_checks'] = {sid: [
            {'claim': law['explanation'], 'quote': real_passage},
            {'claim': law['explanation'], 'quote': 'A refund is always guaranteed within a year.'},
            {'claim': 'Some unrelated legal claim.', 'quote': real_passage},
        ]}
        with self.settings(), patch('core.model_json', return_value=candidate):
            result, _ = core.analyse(record)
        pairs = result['laws'][0]['source_check']['passages']
        self.assertEqual(pairs, [{'claim': law['explanation'], 'quote': real_passage}])

    def test_live_source_review_blocks_unsourced_deadline(self):
        record=core.intake(core.DEMO_STORY,demo=True)
        candidate,_=core.analyse(record,True)
        candidate['next_steps']=['Send a notice requiring a response within 7 days.']
        with self.settings(),patch('core.model_json',return_value=candidate):
            with self.assertRaisesRegex(ValueError,'unsupported procedural time period'):
                core.analyse(record)

    def test_live_review_cannot_show_fabricated_legal_text_with_valid_source_id(self):
        record = core.intake(core.DEMO_STORY, demo=True)
        candidate, _ = core.analyse(record, True)
        invented = 'Section 999 of the Invented Refund Act grants an automatic refund.'
        candidate['overview'] = invented
        candidate['laws'][0]['connection'] = invented
        candidate['scenarios'][0]['effect'] = invented
        with self.settings(), patch('core.model_json', return_value=candidate):
            result, _ = core.analyse(record)
            self.assertNotIn(invented, json.dumps(result))
            candidate['laws'][0]['source_id'] = 'invented-999'
            with self.assertRaisesRegex(ValueError, 'unavailable or duplicated source'):
                core.analyse(record)

    def test_short_retry_after_is_honoured_once(self):
        error=urllib.error.HTTPError('https://provider.invalid',429,'Rate',{'retry-after':'3'},io.BytesIO(b'{}'))
        response=io.BytesIO(json.dumps({'choices':[{'message':{'content':'{"ok":true}'}}]}).encode())
        with self.settings(),patch('core.MODEL_OPENER.open',side_effect=[error,response]) as send,patch('core.time.sleep') as pause:
            self.assertEqual(core.model_json('',{}),{'ok':True})
            self.assertEqual(send.call_count,2)
            pause.assert_called_once_with(3.2)
