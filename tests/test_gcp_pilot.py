import importlib.util
import io
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

spec = importlib.util.spec_from_file_location('gcp_pilot', Path(__file__).parents[1]/'deploy/gcp/run_pilot.py')
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


def test_create_only_upload_and_size_verification(tmp_path, monkeypatch):
    path = tmp_path/'data.parquet'
    path.write_bytes(b'abc')
    requests=[]
    monkeypatch.setattr(pilot, 'token', lambda: 'test-token')
    def request(req, timeout):
        requests.append(req)
        return io.BytesIO(json.dumps({'size':'3'}).encode())
    monkeypatch.setattr(pilot, 'urlopen', request)
    pilot.upload('test-bucket', 'pilots/test/a.parquet', path)
    req=requests[0]
    assert req.data == b'abc'
    assert parse_qs(urlparse(req.full_url).query)['ifGenerationMatch'] == ['0']
    monkeypatch.setattr(pilot, 'urlopen', lambda *a, **k: io.BytesIO(b'{"size":"4"}'))
    with pytest.raises(ValueError, match='size'):
        pilot.upload('test-bucket', 'x', path)


def test_publication_marker_last(tmp_path, monkeypatch):
    monkeypatch.setenv('OUTPUT_BUCKET', 'test-bucket')
    monkeypatch.setenv('CLOUD_RUN_EXECUTION', 'aml-pilot-abc')
    root=tmp_path/'dataset'
    config=type('Config', (), {'rows':100})()
    monkeypatch.setattr(pilot.Config, 'load', lambda _: config)
    original=Path
    monkeypatch.setattr(pilot, 'Path', lambda p: root if p == '/tmp/dataset' else original(p))
    def generate(c, path):
        path.mkdir()
        (path/'manifest.json').write_text('{}')
        (path/'transactions.parquet').write_bytes(b'abc')
        return {'metrics':{}}
    monkeypatch.setattr(pilot, 'generate', generate)
    uploaded=[]
    monkeypatch.setattr(pilot, 'upload', lambda b,n,p: uploaded.append(n))
    pilot.main()
    assert uploaded[-1] == 'pilots/aml-pilot-abc/manifest.json'
    assert len(uploaded) == 2
