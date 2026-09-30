"""Read-only re-score of retained PHerc0139 public-control evidence.

Uses histogram pair counting for AUC and grouped precision for AP. Writes only
the new verification JSON beside this script; original receipts stay unchanged.
"""
import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone

import os
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['OPENBLAS_NUM_THREADS'] = '2'
import numpy as np
import numcodecs
from PIL import Image

import argparse
parser = argparse.ArgumentParser(description='Rescore the retained PHerc0139 w016 public control; no inference or download.')
parser.add_argument('--root', required=True, type=pathlib.Path)
parser.add_argument('--output', required=True, type=pathlib.Path)
args = parser.parse_args()
ROOT = args.root.resolve()
DEST = args.output.resolve()
if DEST.exists():
    raise SystemExit('Refusing to overwrite an existing verification receipt.')
script_hash = hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
hashes = {}
missing = []

def read(path):
    data = path.read_bytes()
    hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(data).hexdigest()
    return data

def decode_plane(name):
    folder = ROOT / 'labels' / name
    meta = json.loads(read(folder / '.zarray'))
    cz, cy, cx = meta['chunks']
    assert meta['order'] == 'C' and np.dtype(meta['dtype']) == np.dtype('uint8')
    assert not meta.get('filters')
    codec = numcodecs.get_codec(meta['compressor'])
    y0, y1, x0, x1, plane = 4736, 5632, 1664, 2304, 10
    result = np.full((y1-y0, x1-x0), meta.get('fill_value') or 0, dtype=np.uint8)
    for yi in range(y0//cy, (y1-1)//cy+1):
        for xi in range(x0//cx, (x1-1)//cx+1):
            path = folder / f'{plane//cz}.{yi}.{xi}'
            if not path.exists():
                missing.append(path.relative_to(ROOT).as_posix())
                continue
            tile = np.frombuffer(codec.decode(read(path)), dtype=np.uint8).reshape(cz, cy, cx)[plane % cz]
            sy, sx = yi*cy, xi*cx
            ya, yb, xa, xb = max(y0, sy), min(y1, sy+cy), max(x0, sx), min(x1, sx+cx)
            result[ya-y0:yb-y0, xa-x0:xb-x0] = tile[ya-sy:yb-sy, xa-sx:xb-sx]
    return result

ink, supervision, validation = [decode_plane(name) for name in ('ink', 'supervision', 'validation')]
read(ROOT / 'prediction.tif')
prediction = np.asarray(Image.open(ROOT / 'prediction.tif'))
assert prediction.shape == ink.shape and prediction.dtype == np.uint8
mask = validation > 0
truth = ink[mask] > 0
scores = prediction[mask]
pos = np.bincount(scores[truth], minlength=256).astype(np.float64)
neg = np.bincount(scores[~truth], minlength=256).astype(np.float64)
npos, nneg = pos.sum(), neg.sum()
auc = float(np.sum(pos * (np.cumsum(neg)-neg+0.5*neg)) / (npos*nneg))
tp, fp = np.cumsum(pos[::-1]), np.cumsum(neg[::-1])
precision = np.divide(tp, tp+fp, out=np.zeros_like(tp), where=(tp+fp)>0)
ap = float(np.sum((pos[::-1]/npos)*precision))
receipt = json.loads(read(ROOT / 'PIPELINE_RUN_RECEIPT.json'))
metric = next(stage['detail']['metric'] for stage in receipt['stages'] if stage['stage'] == 'score')
result = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(), script_sha256=script_hash,
              python_version=sys.version.split()[0], method='uint8 histogram pair-count AUC and grouped AP',
              n=int(mask.sum()), n_positive=int(npos), auc=auc, ap=ap,
              auc_difference=auc-metric['auc'], ap_difference=ap-metric['ap'],
              validation_pixels_also_supervised=int(np.sum(mask & (supervision > 0))),
              missing_chunks_using_declared_fill=missing, input_sha256=hashes)
result['pass'] = (not missing and result['validation_pixels_also_supervised'] == 0 and result['n'] == metric['n'] and result['n_positive'] == metric['n_positive']
                  and abs(result['auc_difference']) < 1e-12 and abs(result['ap_difference']) < 1e-12
                  and hashes['prediction.tif'] == receipt['outputs']['prediction.tif']['sha256'])
with DEST.open('x', encoding='utf-8') as f:
    f.write(json.dumps(result, indent=2))
print(json.dumps({k:v for k,v in result.items() if k != 'input_sha256'}, indent=2))
raise SystemExit(0 if result['pass'] else 1)
