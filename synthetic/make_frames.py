"""Синтетический набор для открытого сравнения библиотек чтения DataMatrix.

    python synthetic/make_frames.py <dmgen> [--trials 12] [--seed 20261010]

Символы — из генератора dmgen (данные — случайные цифры, у каждого кода свои,
60–85 % ёмкости, как у настоящих кодов; ось damage@nopad — символ под
завязку). Условия съёмки — по одной оси за раз, остальное номинал:
кадр 720×540, код на белой этикетке на сером фоне с неравномерным светом,
4 пикселя на модуль, случайный поворот 0…360°, контраст печати 0,85, шум σ=3.
На точку — trials кадров с символами 16×16, 22×22, 40×40 по очереди.

Пишет рядом:
  frames/NNNN.png      — кадры для публикации (JPEG-ось — уже с артефактами);
  gray/NNNN.pgm        — те же кадры для стенда (8-бит серый);
  frames.lst           — абсолютные пути к PGM в порядке номеров;
  expected.csv         — №;файл;ось;значение;размер;ожидаемая строка.
Зерно фиксировано: набор воспроизводится.
"""
import argparse
import csv
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render_limits as L  # noqa: E402

AXES = [
    # (ось в отчёте, имя оси в render_limits или особая, значения, поправки)
    ('module px', 'ppm', [1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.5, 3.0, 4.0, 6.0], {}),
    ('rotation deg', 'angle', [0, 5, 10, 15, 20, 25, 30, 35, 40, 45], {'ppm': 2.5}),
    ('defocus sigma px', 'blur', [0, 0.5, 0.8, 1.0, 1.2, 1.5, 1.8, 2.2, 2.6, 3.0], {}),
    ('motion blur px', 'motion', [0, 2, 3, 4, 5, 6, 8, 10], {}),
    ('noise sigma', 'noise', [0, 10, 20, 30, 45, 60, 80, 100], {}),
    ('print contrast', 'contrast', [0.85, 0.5, 0.3, 0.2, 0.12, 0.08, 0.05], {}),
    ('jpeg quality', 'jpeg', [95, 75, 50, 30, 20, 10, 5], {'ppm': 3.0}),
    ('tilt deg', 'tilt', [0, 15, 30, 40, 50, 60, 70], {}),
    ('dot gain', 'gain', [-0.55, -0.45, -0.3, -0.15, 0, 0.15, 0.3, 0.45, 0.55, 0.7], {}),
    ('damage share', 'damage', [0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30], {}),
    ('damage share, no padding', 'damage', [0, 0.03, 0.05, 0.10], {'fill': 1.0}),
    ('cylinder bend deg', 'bend', [0, 30, 60, 90, 120, 150, 180], {'surface': 'bend'}),
    ('wave modules', 'wave', [0, 0.25, 0.5, 0.75, 1.0, 1.5], {'surface': 'wave'}),
    ('crumpled paper modules', 'crumple', [0, 0.15, 0.3, 0.45, 0.6, 0.8], {'surface': 'crumple'}),
    ('plastic bag modules', 'bag', [0, 0.25, 0.5, 0.75, 1.0], {'surface': 'bag'}),
    ('inverted (light on dark)', 'invert', [0, 1], {}),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dmgen')
    ap.add_argument('--trials', type=int, default=12)
    ap.add_argument('--seed', type=int, default=20261010)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    for d in ('frames', 'gray'):
        shutil.rmtree(HERE / d, ignore_errors=True)
        (HERE / d).mkdir()
    tmp = Path(tempfile.mkdtemp(prefix='synth-'))
    syms = L.Symbols(a.dmgen, tmp, rng)
    rows, n = [], 0
    for label, key, values, over in AXES:
        for val in values:
            for t in range(a.trials):
                p = dict(L.BASE, **over)
                if key in ('bend', 'wave', 'crumple', 'bag'):
                    p['surf_amp'] = val
                elif key == 'invert':
                    p['invert'] = bool(val)
                else:
                    p[key] = val
                p['size'] = L.SIZES[t % len(L.SIZES)]
                p['angle'] = float(val + 90 * rng.integers(0, 4)) if key == 'angle' else float(rng.uniform(0, 360))
                p['tilt_axis'] = rng.uniform(0, 180)
                sym, data = syms.make(p['size'], p.get('fill'))
                frame = L.background(720, 540, rng)
                side_px = (p['size'] + 2 * L.QUIET + 6) * p['ppm']
                lim_x = max(0, 360 - side_px * 0.75)
                lim_y = max(0, 270 - side_px * 0.75)
                c = (360 + rng.uniform(-lim_x, lim_x) * 0.5, 270 + rng.uniform(-lim_y, lim_y) * 0.5)
                L.place(frame, sym, p, c, rng)
                img = L.to_gray8(frame, p.get('jpeg', 0), tmp)
                n += 1
                name = f'{n:04d}'
                img.save(HERE / 'frames' / f'{name}.png', optimize=True)
                img.save(HERE / 'gray' / f'{name}.pgm')
                rows.append([n, f'{name}.png', label, val, p['size'], data])
        print(f'{label}: всего {n}', flush=True)
    with open(HERE / 'expected.csv', 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh, delimiter=';')
        w.writerow(['№', 'file', 'axis', 'value', 'symbol size', 'expected'])
        w.writerows(rows)
    with open(HERE / 'frames.lst', 'w', encoding='utf-8') as fh:
        for r in rows:
            fh.write(str(HERE / 'gray' / f'{r[0]:04d}.pgm') + '\n')
    shutil.rmtree(tmp, ignore_errors=True)
    print('кадров', n)


if __name__ == '__main__':
    main()
