"""Server-side example: pip install requests. Never embed the token in public JS."""
import os
from urllib.parse import quote, urlsplit
import requests


class CommunityClient:
    def __init__(self, base_url, layer_id, token):
        url = urlsplit(base_url)
        if url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in ('localhost', '127.0.0.1')):
            raise ValueError('Use HTTPS (HTTP only for loopback development).')
        self.base = base_url.rstrip('/') + '/api/layers/' + quote(layer_id, safe='') + '/community'
        self.session = requests.Session()
        self.session.headers['Authorization'] = 'Bearer ' + token

    def request(self, method, path, **kwargs):
        if not path.startswith('/') or path.startswith('//') or '?' in path or '..' in path:
            raise ValueError('Use a relative Community Intelligence API path.')
        response = self.session.request(method, self.base + path, timeout=(5, 30),
                                        allow_redirects=False, **kwargs)
        if 300 <= response.status_code < 400:
            raise RuntimeError('Unexpected redirect; check the configured API URL.')
        response.raise_for_status()
        return response.json()

    def ask(self, question):
        return self.request('POST', '/answer/', json={'question': question})

    def save_opportunity(self, suggestion):
        return self.request('POST', '/opportunities/', json={
            'claim_ids': [c['claim_id'] for c in suggestion['citations']],
            'evidence': suggestion['evidence'],
        })


if __name__ == '__main__':
    client = CommunityClient(os.environ['GOVHUB_BASE_URL'], os.environ['GOVHUB_LAYER_ID'],
                             os.environ['GOVHUB_COMMUNITY_TOKEN'])
    print(client.ask('Who offers training?'))
