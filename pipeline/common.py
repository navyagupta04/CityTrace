from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import subprocess
import yaml

ROOT = Path(__file__).resolve().parent.parent

def digest(path):
    h = sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def read(path, default=None):
    path = Path(path)
    if not path.exists(): return default
    return yaml.safe_load(path.read_text(encoding='utf-8-sig'))

def write(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    temporary.replace(path)

def now(): return datetime.now(timezone.utc).isoformat()
def expiry(days=90): return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
def config(path='configs/demo.yaml'):
    cfg = read(ROOT / path)
    cfg['privacy_settings'] = read(ROOT / cfg['privacy'])
    cfg['config_hash'] = sha256(json.dumps({**cfg, 'placements_data':read(ROOT/cfg['placements']), 'lines_data':read(ROOT/cfg['counting_lines']), 'watchlist_data':read(ROOT/cfg['watchlist'])}, sort_keys=True).encode()).hexdigest()
    try: cfg['commit'] = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError): cfg['commit'] = 'unversioned-workspace'
    return cfg
