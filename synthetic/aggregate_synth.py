"""Сводка синтетического сравнения: synthetic/raw/*.tsv + expected.csv -> summary_synth.md, per_point.csv.

Верно прочитан — строка совпала с закодированной. Ложное чтение — выдана
непустая строка, отличная от закодированной. Предел оси — последнее значение
(от номинала в сторону ухудшения), при котором прочитано не меньше 90 % кадров
точки; для осей, где «хуже» — меньшее значение (контраст, качество JPEG),
порядок значений в expected.csv уже от лучшего к худшему.
"""
import csv
import json
import os
import statistics
from collections import OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, 'results')
RAW = os.path.join(RES, 'raw')
LIBS = [('dmr', 'dmr (ours)'), ('zxingcpp', 'zxing-cpp'), ('zxingjava', 'ZXing (Java)'),
        ('libdmtx', 'libdmtx'), ('dmr_single', 'dmr, Settings::single()')]
THRESH = 0.9

exp = list(csv.reader(open(os.path.join(HERE, 'expected.csv'), encoding='utf-8'), delimiter=';'))[1:]
frames = [dict(no=int(r[0]), file=r[1], axis=r[2], value=r[3], size=int(r[4]), data=r[5]) for r in exp]


def load(lib):
    p = os.path.join(RAW, lib + '.tsv')
    if not os.path.exists(p):
        return None
    res = {}
    for row in csv.reader(open(p, encoding='utf-8', errors='replace'), delimiter='\t'):
        if len(row) < 5:
            continue
        idx, ok, hx, ms = int(row[0]), row[2] == '1', row[3], float(row[4])
        text = bytes.fromhex(hx).decode('latin-1') if hx and hx != '-' else ''
        r = res.setdefault(idx, {'text': text if ok else '', 'ms': []})
        r['ms'].append(ms)
    return res


def cpu(lib):
    p = os.path.join(RAW, lib + '.cpuperf')
    if not os.path.exists(p):
        return None
    a, m, n = open(p).read().strip().replace(',', '.').split(';')
    return float(a), float(m), int(n)


data = OrderedDict((k, load(k)) for k, _ in LIBS)
data = OrderedDict((k, v) for k, v in data.items() if v is not None)
names = dict(LIBS)

axes = OrderedDict()
for f in frames:
    axes.setdefault(f['axis'], OrderedDict()).setdefault(f['value'], []).append(f)

out = []
P = out.append
P('# DataMatrix readers on synthetic frames')
P('')
P(f'{len(frames)} frames, 720×540, one code per frame on a white label on a grey background with uneven light. '
  'One condition is varied at a time; the rest stay nominal (4 px per module, random rotation 0–360°, print contrast 0.85, '
  'noise σ = 3). 12 frames per point: symbols 16×16, 22×22 and 40×40 in turn, random digits filling 60–85 % of capacity '
  '(the "no padding" axis: 100 %). Frames, expected strings and the generator are published with this report.')
P('')
P('**Read** = decoded string equals the encoded one. **Wrong** = a non-empty string that differs from the encoded one.')
P('')

# Итог
P('## Overall')
P('')
P('| library | read | read % | wrong | median ms (all frames) | median ms (read frames) | CPU mean / min % |')
P('|---|---:|---:|---:|---:|---:|---:|')
summary = {}
for lib, res in data.items():
    read = wrong = 0
    ms_all, ms_read = [], []
    for f in frames:
        r = res.get(f['no'] - 1)
        if r is None:
            continue
        m = statistics.median(r['ms'])
        ms_all.append(m)
        if r['text'] == f['data']:
            read += 1
            ms_read.append(m)
        elif r['text']:
            wrong += 1
    c = cpu(lib)
    summary[lib] = dict(read=read, wrong=wrong, n=len(frames))
    P(f'| {names[lib]} | {read}/{len(frames)} | {100 * read / len(frames):.1f} % | {wrong} | '
      f'{statistics.median(ms_all):.1f} | {statistics.median(ms_read) if ms_read else float("nan"):.1f} | '
      f'{f"{c[0]:.0f} / {c[1]:.0f}" if c else "–"} |')
P('')

# Номинал — проверка, что символы стандартные
nominal = [f for f in frames if (f['axis'], f['value']) in
           {('module px', '4.0'), ('defocus sigma px', '0'), ('noise sigma', '0'), ('print contrast', '0.85'),
            ('damage share', '0'), ('tilt deg', '0'), ('dot gain', '0'), ('inverted (light on dark)', '0')}]
P(f'**Sanity check — nominal frames** ({len(nominal)} frames with no added distortion, taken from the nominal point of '
  'several axes): ' + ', '.join(
      f'{names[lib]} {sum(1 for f in nominal if res.get(f["no"] - 1, {}).get("text") == f["data"])}/{len(nominal)}'
      for lib, res in data.items()) + '. The symbols are standard ECC 200 that other readers decode.')
P('')

# Пределы
P('## Limit per condition')
P('')
P(f'Worst value, moving away from the nominal one, at which a library still reads ≥ {THRESH:.0%} of the frames of the point '
  '(module size: smallest; dot gain: range both ways); "—" = not even at the nominal value.')
P('')
P('| condition | ' + ' | '.join(names[l] for l in data) + ' |')
P('|---|' + '---:|' * len(data))
rows_csv = []
# Номинал оси: от него предел отсчитывается в сторону ухудшения; у двусторонних
# осей (растискивание) — в обе стороны, предел — диапазон.
NOMINAL = {'module px': '4.0', 'rotation deg': '0', 'defocus sigma px': '0', 'motion blur px': '0',
           'noise sigma': '0', 'print contrast': '0.85', 'jpeg quality': '95', 'tilt deg': '0',
           'dot gain': '0', 'damage share': '0', 'damage share, no padding': '0', 'cylinder bend deg': '0',
           'wave modules': '0', 'crumpled paper modules': '0', 'plastic bag modules': '0',
           'inverted (light on dark)': '0'}
TWO_SIDED = {'dot gain'}
UP_IS_BETTER = {'module px'}   # ниже номинала — хуже; выше номинала не предел


def share(res, fs):
    return sum(1 for f in fs if res.get(f['no'] - 1, {}).get('text') == f['data']) / len(fs)


def walk(res, vals, pts):
    last = None
    for v in vals:
        if share(res, pts[v]) >= THRESH:
            last = v
        else:
            break
    return last


for axis, pts in axes.items():
    vals = list(pts.keys())
    nom = NOMINAL.get(axis, vals[0])
    i = vals.index(nom) if nom in vals else 0
    cells = []
    for lib, res in data.items():
        if axis in TWO_SIDED:
            lo = walk(res, vals[i::-1], pts)
            hi = walk(res, vals[i:], pts)
            cells.append('—' if lo is None or hi is None else f'{lo} … +{hi}' if float(hi) > 0 else f'{lo} … {hi}')
        elif axis in UP_IS_BETTER:
            last = walk(res, vals[i::-1], pts)
            cells.append('—' if last is None else last)
        else:
            last = walk(res, vals[i:], pts)
            cells.append('—' if last is None else last)
    P(f'| {axis} | ' + ' | '.join(cells) + ' |')
P('')

# По точкам
P('## Read share per point, %')
P('')
for axis, pts in axes.items():
    P(f'### {axis}')
    P('')
    P('| value | ' + ' | '.join(names[l] for l in data) + ' |')
    P('|---:|' + '---:|' * len(data))
    for val, fs in pts.items():
        cells = []
        for lib, res in data.items():
            ok = sum(1 for f in fs if res.get(f['no'] - 1, {}).get('text') == f['data'])
            wr = sum(1 for f in fs if res.get(f['no'] - 1, {}).get('text') not in ('', None, f['data']))
            cells.append(f'{100 * ok / len(fs):.0f}' + (f' ({wr} wrong)' if wr else ''))
            rows_csv.append(dict(axis=axis, value=val, library=names[lib], frames=len(fs), read=ok, wrong=wr))
        P(f'| {val} | ' + ' | '.join(cells) + ' |')
    P('')

with open(os.path.join(RES, 'summary_synth.md'), 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out) + '\n')
with open(os.path.join(RES, 'per_point.csv'), 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=['axis', 'value', 'library', 'frames', 'read', 'wrong'])
    w.writeheader()
    w.writerows(rows_csv)
print('wrote synthetic/results/summary_synth.md and per_point.csv;', json.dumps(summary))
