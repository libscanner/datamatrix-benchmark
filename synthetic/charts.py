"""Графики для статьи: доля прочитанного по четырём условиям (per_point.csv -> article/img/*.png).

Малые множества 2×2, одна ось Y (0–100 %) на панель, одна линия на библиотеку.
Цвета — категориальная палитра в фиксированном порядке (проверена валидатором),
у каждой линии своя форма маркера: цвет не единственный носитель различия.
По оси X условие идёт от лёгкого к трудному.
"""
import csv
import os
from collections import defaultdict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'img')
os.makedirs(OUT, exist_ok=True)

SURFACE, INK, INK2, MUTED, GRID, AXIS = '#fcfcfb', '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#c3c2b7'
SERIES = [  # (имя в per_point.csv, подпись, цвет, маркер)
    ('dmr (ours)', 'dmr', '#2a78d6', 'o'),
    ('zxing-cpp', 'zxing-cpp', '#eb6834', 's'),
    ('libdmtx', 'libdmtx', '#1baf7a', '^'),
    ('ZXing (Java)', 'ZXing (Java)', '#eda100', 'D'),
]
PANELS = [  # (ось, заголовок, подпись X, обратить порядок значений: True — «меньше = труднее»)
    ('module px', 'Размер модуля', 'пикселей на модуль', True),
    ('defocus sigma px', 'Расфокус', 'σ гауссова размытия, пикселей (модуль 4 px)', False),
    ('tilt deg', 'Наклон этикетки к камере', 'градусов', False),
    ('damage share', 'Повреждение области данных', 'доля площади', False),
]

pts = defaultdict(dict)
order = defaultdict(list)
for r in csv.DictReader(open(os.path.join(HERE, 'results', 'per_point.csv'), encoding='utf-8')):
    key = (r['axis'], r['library'])
    pts[key][r['value']] = 100.0 * int(r['read']) / int(r['frames'])
    if r['value'] not in order[r['axis']]:
        order[r['axis']].append(r['value'])

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'axes.edgecolor': AXIS,
                     'axes.labelcolor': INK2, 'xtick.color': MUTED, 'ytick.color': MUTED,
                     'text.color': INK})
fig, axes = plt.subplots(2, 2, figsize=(11, 8), dpi=150, facecolor=SURFACE)
for ax, (axis, title, xlabel, rev) in zip(axes.flat, PANELS):
    vals = order[axis][::-1] if rev else order[axis]
    xs = list(range(len(vals)))
    ax.set_facecolor(SURFACE)
    for name, label, color, marker in SERIES:
        ys = [pts[(axis, name)].get(v, 0) for v in vals]
        ax.plot(xs, ys, color=color, linewidth=2, marker=marker, markersize=7,
                markeredgecolor=SURFACE, markeredgewidth=1.5, label=label, zorder=6 if name == 'dmr (ours)' else 3)
    ax.set_title(title, loc='left', fontsize=13, color=INK, pad=8)
    ax.set_xticks(xs)
    ax.set_xticklabels([v.replace('.', ',') for v in vals])
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylim(-3, 103)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels(['0', '25', '50', '75', '100 %'])
    ax.grid(axis='y', color=GRID, linewidth=0.8, zorder=0)
    ax.tick_params(length=0)
    for side in ('top', 'right', 'left'):
        ax.spines[side].set_visible(False)
    ax.spines['bottom'].set_color(AXIS)
handles, labels = axes.flat[0].get_legend_handles_labels()
fig.legend(handles, labels, loc='upper left', ncol=4, frameon=False, bbox_to_anchor=(0.06, 0.965),
           fontsize=11, handlelength=2.2)
fig.suptitle('Доля прочитанных кадров: одно условие меняется, остальные номинальные (12 кадров на точку)',
             x=0.06, y=0.995, ha='left', fontsize=12, color=INK2)
fig.tight_layout(rect=(0, 0, 1, 0.93))
p = os.path.join(OUT, 'synthetic-4-conditions.png')
fig.savefig(p, facecolor=SURFACE)
print('wrote', p)
