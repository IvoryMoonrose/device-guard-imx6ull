#!/usr/bin/env python3
import argparse
import json
import os
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

from guard.service import GuardService


class Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    parser = argparse.ArgumentParser(description='Device Guard embedded monitoring service')
    parser.add_argument('--data', default=os.path.join(os.path.dirname(__file__), 'data'))
    parser.add_argument('--port', type=int, default=18765)
    parser.add_argument('--replay', action='store_true', help='clearly labelled synthetic replay mode')
    parser.add_argument('--no-indicators', action='store_true')
    args = parser.parse_args()
    # POSIX TZ works even on minimal rootfs images without zoneinfo files.
    os.environ['TZ'] = 'CST-8'
    if hasattr(time, 'tzset'):
        time.tzset()
    service = GuardService(args.data, args.replay, not args.no_indicators)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def send(self, body, code=200, content='application/json; charset=utf-8'):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=True).encode('utf8')
            self.send_response(code)
            self.send_header('Content-Type', content)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path)
            if path.path == '/api/state':
                self.send(service.snapshot())
            elif path.path == '/api/events':
                self.send(service.store.list(200))
            elif path.path == '/api/event':
                try:
                    event = service.store.detail(int(parse_qs(path.query)['id'][0]))
                    self.send(event if event else {'error': '记录不存在'}, 200 if event else 404)
                except (ValueError, KeyError):
                    self.send({'error': '事件编号无效'}, 400)
            elif path.path == '/api/export.csv':
                self.send(service.store.export_csv(), content='text/csv; charset=utf-8')
            else:
                self.send({'error': '接口不存在'}, 404)

        def do_POST(self):
            try:
                size = int(self.headers.get('Content-Length', 0))
                if size < 0 or size > 65536:
                    raise ValueError('请求过大')
                payload = json.loads(self.rfile.read(size).decode('utf8'))
                if not isinstance(payload, dict):
                    raise ValueError('请求必须是JSON对象')
                if self.path == '/api/action':
                    self.send(service.action(payload.get('action')))
                elif self.path == '/api/config':
                    self.send(service.configure(payload))
                elif self.path == '/api/acknowledge':
                    self.send(service.acknowledge(payload.get('id')))
                elif self.path == '/api/replay':
                    self.send(service.replay_scenario(payload.get('scenario')))
                elif self.path == '/api/export':
                    export_dir = os.path.join(service.directory, 'exports')
                    os.makedirs(export_dir, exist_ok=True)
                    filename = 'events_'+time.strftime('%Y%m%d_%H%M%S')+'.csv'
                    with open(os.path.join(export_dir, filename), 'wb') as stream:
                        stream.write(service.store.export_csv())
                    self.send({'ok': True, 'filename': filename})
                elif self.path == '/api/shutdown':
                    self.send({'ok': True})
                    threading.Thread(target=server.shutdown).start()
                else:
                    self.send({'error': '接口不存在'}, 404)
            except (ValueError, TypeError) as exc:
                self.send({'error': str(exc)}, 400)

    server = Server(('127.0.0.1', args.port), Handler)
    def stop(signum, frame):
        threading.Thread(target=server.shutdown).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    service.start()
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        service.close()


if __name__ == '__main__':
    main()
