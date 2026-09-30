import importlib.util
import json
from pathlib import Path
import sys

import pytest

from synthetic_engine.config import Config
from synthetic_engine.outputs.parquet import write_json

folder = Path(__file__).parents[1] / 'deploy/gcp'
spec = importlib.util.spec_from_file_location('run_pilot', folder/'run_pilot.py')
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
sys.modules['run_pilot'] = pilot
spec = importlib.util.spec_from_file_location('run_bulk', folder/'run_bulk.py')
bulk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bulk)


def config():
    return Config(domain='banking', rows=100, parameters={'accounts':40,'banks':5,'days':2,
                    'scenarios':{'aml':{'enabled':True}}})


def fake_generate(c, root):
    root.mkdir()
    (root/'transactions').mkdir()
    (root/'transactions/a.parquet').write_bytes(b'x'*100)
    (root/'labels.parquet').write_bytes(b'x'*1000)
    manifest={'status':'complete','files':[{'path':'transactions/a.parquet','bytes':100},
                                         {'path':'labels.parquet','bytes':1000}]}
    write_json(root/'manifest.json',manifest)
    return manifest


def test_target_uses_only_transactions_and_cleans_scratch(tmp_path):
    uploaded=[]
    def upload(bucket, name, path):
        assert path.exists()
        uploaded.append(name)
    result=bulk.run(config(),'bucket','test-run',tmp_path,target_bytes=201,max_shards=3,
                    generate_fn=fake_generate,upload_fn=upload)
    assert result['rows']==300
    assert result['transaction_bytes']==300
    assert result['all_parquet_bytes']==3300
    assert len(result['shards'])==3
    assert len({s['seed'] for s in result['shards']})==3
    assert uploaded[-1]=='datasets/test-run/dataset.json'
    assert not list(tmp_path.iterdir())


def test_limit_or_upload_failure_never_publishes_dataset(tmp_path):
    uploaded=[]
    with pytest.raises(RuntimeError, match='limit'):
        bulk.run(config(),'bucket','test-run',tmp_path,target_bytes=101,max_shards=1,
                 generate_fn=fake_generate,upload_fn=lambda b,n,p:uploaded.append(n))
    assert not any(n.endswith('/dataset.json') for n in uploaded)
    def fail(*args):
        raise OSError('upload failure')
    with pytest.raises(OSError):
        bulk.run(config(),'bucket','test-run',tmp_path,target_bytes=1,
                 generate_fn=fake_generate,upload_fn=fail)
    assert not list(tmp_path.iterdir())


def test_real_small_aml_shard_validates_before_publication(tmp_path):
    published=[]
    def upload(bucket,name,path):
        if path.name in {'manifest.json','validation.json','dataset.json'}:
            published.append((name,json.loads(path.read_text())))
    result=bulk.run(config(),'bucket','real-test',tmp_path,target_bytes=1,upload_fn=upload)
    assert result['status']=='complete'
    assert any(data.get('passed') for name,data in published if name.endswith('/validation.json'))
    assert published[-1][0].endswith('/dataset.json')
