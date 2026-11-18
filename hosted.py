"""Serve the guest demo behind a managed HTTPS ingress using WSGI."""
from email.message import Message
from http import HTTPStatus
from io import BytesIO
import json
import os
import re
import threading
from urllib.parse import urlsplit

from server import Handler, MAX_REQUEST_BYTES, sweep_guests


def configured_origin():
    origin = os.getenv('CASE_COMPANION_ORIGIN', '')
    hostname = os.getenv('RENDER_EXTERNAL_HOSTNAME') or os.getenv('RAILWAY_PUBLIC_DOMAIN')
    if not origin and hostname:
        origin = f'https://{hostname}'
    if not origin:
        return 'http://127.0.0.1:' + os.getenv('PORT', '8766')
    parsed = urlsplit(origin)
    if (parsed.scheme != 'https' or parsed.geturl() != origin or parsed.path or parsed.query
            or parsed.fragment or not re.fullmatch(r'[a-z0-9.-]+', parsed.netloc)):
        raise ValueError('Configure CASE_COMPANION_ORIGIN as an exact HTTPS origin, with no path or port.')
    return origin


class HostedRequest(Handler):
    accounts_enabled = False
    guest_limit = 32

    def __init__(self, environ, origin):
        self.origin = origin
        self.path = environ.get('PATH_INFO', '/')
        self.rfile = environ['wsgi.input']
        self.wfile = BytesIO()
        self.headers = Message()
        self.response_headers = []
        for field, value in environ.items():
            if field.startswith('HTTP_'):
                self.headers[field[5:].replace('_', '-')] = value
        for field, header in (('CONTENT_TYPE', 'Content-Type'), ('CONTENT_LENGTH', 'Content-Length')):
            if environ.get(field):
                self.headers[header] = environ[field]

    def safe_host(self):
        return self.headers.get_all('Host') == [urlsplit(self.origin).netloc]

    def request_origin(self):
        return self.origin

    def live_enabled(self):
        return False

    def read_json(self, size):
        # Waitress buffers and bounds the complete request before dispatch.
        raw = self.rfile.read(size)
        if len(raw) != size:
            raise ValueError('The request body was incomplete.')
        return json.loads(raw)

    def send_response(self, code):
        self.status = f'{code} {HTTPStatus(code).phrase}'

    def send_header(self, key, value):
        self.response_headers.append((key, value))

    def end_headers(self):
        pass


def create_app(origin):
    def app(environ, start_response):
        request = HostedRequest(environ, origin)
        method = environ['REQUEST_METHOD']
        if request.path == '/healthz' and method == 'GET':
            request.respond({'status': 'ok'})
        elif method == 'GET':
            request.do_GET()
        elif method == 'POST':
            request.do_POST()
        else:
            request.respond({'error': 'Method not allowed.'}, 405)
        start_response(request.status, request.response_headers)
        return [request.wfile.getvalue()]

    return app


def main():
    from waitress import serve

    origin = configured_origin()
    port = int(os.getenv('PORT', '8766'))
    bind = '0.0.0.0' if origin.startswith('https://') else '127.0.0.1'
    print(f'Case Companion guest demo listening on {bind}:{port}', flush=True)
    threading.Thread(target=sweep_guests, daemon=True).start()
    serve(create_app(origin), host=bind, port=port, threads=4, connection_limit=64,
          max_request_body_size=MAX_REQUEST_BYTES, max_request_header_size=16384,
          inbuf_overflow=MAX_REQUEST_BYTES + 65536, channel_timeout=30,
          log_socket_errors=False)


if __name__ == '__main__':
    main()
