import io
import json
import unittest
from unittest.mock import patch
from wsgiref.util import setup_testing_defaults
from zipfile import ZipFile

import core
import hosted


class HostedDemoTests(unittest.TestCase):
    origin = 'https://case-companion.onrender.com'

    def call(self, app, path, payload=None, *, host='case-companion.onrender.com', origin=None):
        environ = {}
        setup_testing_defaults(environ)
        environ.update(PATH_INFO=path, HTTP_HOST=host)
        if origin:
            environ['HTTP_ORIGIN'] = origin
        if payload is not None:
            body = json.dumps(payload).encode()
            environ.update(REQUEST_METHOD='POST', CONTENT_LENGTH=str(len(body)),
                           CONTENT_TYPE='application/json')
            environ['wsgi.input'] = io.BytesIO(body)
        response = []
        body = b''.join(app(environ, lambda status, headers: response.extend((status, dict(headers)))))
        return int(response[0].split()[0]), response[1], body

    def test_hosted_guest_workflow_without_account_or_model_service(self):
        app = hosted.create_app(self.origin)
        self.assertEqual(self.call(app, '/healthz')[0], 200)
        self.assertEqual(self.call(app, '/', host='unknown.example')[0], 403)
        self.assertEqual(self.call(app, '/api/guest', {}, origin='https://unknown.example')[0], 403)
        with patch('server.accounts.register') as register, patch('core.model_json') as model:
            self.assertEqual(self.call(app, '/api/register', {}, origin=self.origin)[0], 404)
            register.assert_not_called()
            status, _, raw = self.call(app, '/api/config')
            self.assertEqual(status, 200)
            self.assertIs(json.loads(raw)['accounts'], False)
            self.assertIs(json.loads(raw)['live'], False)

            def post(path, payload):
                status, headers, body = self.call(app, '/api/' + path, payload, origin=self.origin)
                self.assertEqual(status, 200, body)
                self.assertEqual(headers['Cache-Control'], 'no-store')
                return body

            guest = json.loads(post('guest', {}))['guest']
            try:
                payload = {'guest': guest}
                intake = json.loads(post('intake', {**payload, 'story': core.DEMO_STORY,
                                                    'live_consent': True}))
                self.assertEqual(intake['mode'], 'Offline extraction')
                payload['id'] = intake['id']
                post('confirm', {**payload, 'record': intake['record']})
                post('analyse', {**payload, 'live_consent': True})
                post('draft', {**payload, 'options': {'kind': 'Consumer commission complaint'}})
                with ZipFile(io.BytesIO(post('export', payload))) as docx:
                    self.assertIn(b'CONSUMER COMPLAINT', docx.read('word/document.xml'))
                model.assert_not_called()
            finally:
                post('guest-end', {'guest': guest})
