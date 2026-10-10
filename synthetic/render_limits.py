# Копия tools/limits_experiment.py из репозитория dmr (коммит 1c20199) — только
# функции рисования кадров для синтетического сравнения (make_frames.py).
# Импорт dmr сделан необязательным; остальное не менялось.
#!/usr/bin/env python3
"""Пределы читаемости: развёртки по одной оси и кадры с сотнями кодов.

    python tools/limits_experiment.py <dmgen.exe> <каталог вывода> [--part sweeps|multi|all]
                                      [--trials N] [--save-fails]

Символы — свои, из генератора dmgen (сборка с -Dlicense=disabled), данные —
случайные цифры, у каждого кода свои (эталон для сверки). Условия съёмки
имитируются: размер модуля в пикселях, поворот, наклон плоскости
(перспектива), расфокус, смаз, шум, контраст печати, растискивание,
повреждения, JPEG и искажения поверхности — изгиб на цилиндре, волна,
мятая бумага, пакет со складками и бликами.

Части:
  sweeps  каждая ось отдельно при умеренных остальных (кадр 720×540, один
          код, Settings.single()); на точку — N кадров с разными символами и
          случайным поворотом;
  multi   кадры с 256 кодами, у каждого кода свои случайные условия
          (Settings.multi(0), max_candidates=600).

Пишет <вывод>/sweeps.csv, multi.csv, multi-frame-*.png|jpg и summary.txt.
Библиотека — dmr_c сборки разработчика (DMR_C_LIBRARY, см. angle_sweep.py).
"""
import argparse
import csv
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
try:  # рисованию кадров ридер не нужен
    sys.path.insert(0, str(ROOT / 'python' / 'src'))
    import dmr  # noqa: E402
except Exception:
    dmr = None

SRC_PX = 8          # пикселей на модуль у символа из генератора
QUIET = 2           # свободная зона генератора, модулей
# Данные ASCII-кодовых слов у квадратных символов: цифры кодируются парами,
# поэтому 2*cw цифр дают ровно этот размер.
DATA_CW = {10: 3, 12: 5, 14: 8, 16: 12, 18: 18, 20: 22, 22: 30, 24: 36, 26: 44,
           32: 62, 36: 86, 40: 114, 44: 144, 48: 174, 52: 204, 64: 280,
           72: 368, 80: 456, 88: 576, 96: 696, 104: 816, 120: 1050, 132: 1304, 144: 1558}


# ── Символы ────────────────────────────────────────────────────────────────

class Symbols:
    def __init__(self, dmgen, tmp, rng):
        self.dmgen, self.tmp, self.rng = dmgen, Path(tmp), rng
        self.used = set()
        self.env = dict(os.environ)
        self.env.setdefault('DMGEN_LICENSE_DIR', str(self.tmp / 'lic'))

    def make(self, size, fill=None):
        """(картинка float32 0..1, 8 px/модуль, с зоной 2 модуля; данные).

        fill — доля ёмкости под данные. Ридер исправляет ошибки только у
        символа с дополнением (PAD, Acceptance.cpp: paddingValid — защита от
        ложной сходимости), поэтому по умолчанию данные занимают 60–85 %
        ёмкости, как у настоящих кодов; fill=1 — символ под завязку."""
        if fill is None:
            fill = self.rng.uniform(0.6, 0.85)
        n = max(2, int(2 * DATA_CW[size] * fill))
        if fill < 1 and n >= 2 * DATA_CW[size]:
            n = 2 * DATA_CW[size] - 2
        while True:
            data = ''.join(self.rng.choice(list('0123456789'), n))
            if data not in self.used:
                self.used.add(data)
                break
        p = self.tmp / 'sym.png'
        r = subprocess.run([self.dmgen, f'--px={SRC_PX}', f'--quiet={QUIET}', f'--size={size}',
                            '--no-verify', '-o', str(p), '--', data],
                           env=self.env, capture_output=True)
        if r.returncode != 0:
            raise SystemExit(f'dmgen {size}: {r.stderr.decode("utf-8", "replace")}')
        img = np.asarray(Image.open(p).convert('L'), dtype=np.float32) / 255.0
        return img, data


# ── Искажения в плоскости этикетки (единицы — пиксели источника) ───────────

def dot_gain(sym, gain):
    """Растискивание: насколько тёмный модуль шире (+) или уже (−) номинала,
    в долях модуля; каждый край сдвигается на половину. Сдвиг — по карте
    расстояний до краски (рост) или до бумаги (усадка), на сетке вчетверо
    мельче, чтобы доли пикселя не терялись."""
    if gain == 0:
        return sym
    up = 4
    ink = np.kron(sym < 0.5, np.ones((up, up), bool))
    shift = abs(gain) / 2 * SRC_PX * up
    if gain > 0:
        ink = ndimage.distance_transform_edt(~ink) <= shift
    else:
        ink = ndimage.distance_transform_edt(ink) > shift
    paper = (~ink).astype(np.float32)
    return paper.reshape(sym.shape[0], up, sym.shape[1], up).mean(axis=(1, 3))


def damage(sym, frac, rng, size):
    """Повреждения: пятна (царапины, грязь) на доле frac области данных.
    Половина пятен тёмная, половина светлая; рамку не трогают специально —
    повреждение рамки отдельный разговор."""
    if frac <= 0:
        return sym
    out = sym.copy()
    q = QUIET * SRC_PX
    inner = (q + SRC_PX, q + (size - 1) * SRC_PX)
    area = (inner[1] - inner[0]) ** 2
    covered = 0
    while covered < frac * area:
        r = rng.uniform(0.7, 2.0) * SRC_PX
        cx, cy = rng.uniform(*inner), rng.uniform(*inner)
        yy, xx = np.ogrid[:sym.shape[0], :sym.shape[1]]
        m = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
        m[:inner[0], :] = m[inner[1]:, :] = False
        m[:, :inner[0]] = m[:, inner[1]:] = False
        out[m] = 1.0 if rng.random() < 0.5 else 0.0
        covered += math.pi * r * r
    return out


def surface_field(kind, amp, shape, rng, sym_px):
    """Смещение (dx, dy) и множитель яркости в координатах этикетки.

    bend    — этикетка на цилиндре: amp — дуга, которую занимает этикетка, °;
              видимая координата u -> координата печати R*asin(u/R).
    wave    — волна поперёк: amp — размах в модулях, длина ~0.6 символа.
    crumple — мятая бумага: гладкое случайное поле смещений (корреляция ~2.5
              модуля), amp — СКО в модулях, плюс затенение по рельефу.
    bag     — пакет: складки по случайным прямым (сжатие поперёк складки,
              amp — модулей) и блики вдоль складок.
    """
    h, w = shape
    dx = np.zeros(shape, np.float32)
    dy = np.zeros(shape, np.float32)
    shade = np.ones(shape, np.float32)
    inside = np.ones(shape, bool)
    if kind == 'none' or amp <= 0:
        return dx, dy, shade, inside
    yy, xx = np.mgrid[:h, :w].astype(np.float32)
    if kind == 'bend':
        alpha = math.radians(amp)
        R = w / alpha
        c = w / 2
        u = xx - c
        half = R * math.sin(alpha / 2)
        inside = np.abs(u) <= half
        # Видимая этикетка уже печатной: растягиваем видимую полосу на всю
        # ширину, чтобы символ остался в кадре того же размера по середине.
        uu = np.clip(u * (half / c), -R * 0.999999, R * 0.999999)
        dx = (R * np.arcsin(uu / R) - u).astype(np.float32)
        inside = np.ones(shape, bool)
        cosn = np.sqrt(1 - (uu / R) ** 2)
        shade = (0.55 + 0.45 * cosn).astype(np.float32)
    elif kind == 'wave':
        lam = 0.6 * sym_px
        dy = (amp * SRC_PX * np.sin(2 * np.pi * xx / lam + rng.uniform(0, 6.3))).astype(np.float32)
        slope = np.cos(2 * np.pi * xx / lam)
        shade = (1 - 0.12 * min(1.0, amp) * slope).astype(np.float32)
    elif kind == 'crumple':
        corr = 2.5 * SRC_PX
        def field():
            f = ndimage.gaussian_filter(rng.standard_normal(shape).astype(np.float32), corr)
            return f / (f.std() + 1e-9)
        dx = field() * amp * SRC_PX
        dy = field() * amp * SRC_PX
        hgt = ndimage.gaussian_filter(rng.standard_normal(shape).astype(np.float32), corr * 0.8)
        gy, gx = np.gradient(hgt / (hgt.std() + 1e-9))
        light = gx * 0.7 + gy * 0.7
        shade = np.clip(1 + 0.18 * min(1.0, amp) * light / (light.std() + 1e-9), 0.6, 1.2).astype(np.float32)
    elif kind == 'bag':
        k = rng.integers(2, 5)
        for _ in range(k):
            th = rng.uniform(0, np.pi)
            nx, ny = math.cos(th), math.sin(th)
            off = rng.uniform(0.25, 0.75) * w
            d = (xx * nx + yy * ny) - off
            width = rng.uniform(0.6, 1.5) * SRC_PX
            step = amp * SRC_PX * np.tanh(d / width)
            dx += (step * nx).astype(np.float32)
            dy += (step * ny).astype(np.float32)
            glare = np.exp(-(d / (width * 1.2)) ** 2) * rng.uniform(0.25, 0.6) * min(1.0, amp + 0.3)
            shade = shade + glare.astype(np.float32) * 2.0   # блик > 1: высветляет краску
    return dx, dy, shade, inside


# ── Проекция этикетки в кадр ───────────────────────────────────────────────

def homography(src, dst):
    a = []
    for (x, y), (u, v) in zip(src, dst):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    _, _, vt = np.linalg.svd(np.asarray(a, np.float64))
    H = vt[-1].reshape(3, 3)
    return H / H[2, 2]


def label_corners(side, ppm, angle, tilt, tilt_axis, focal):
    """Углы этикетки (сторона side пикселей источника) на кадре относительно
    центра: масштаб, поворот в плоскости, наклон плоскости на tilt° вокруг
    оси tilt_axis° и центральная проекция с фокусом focal пикселей."""
    s = ppm / SRC_PX
    half = side * s / 2
    pts = np.array([[-half, -half, 0], [half, -half, 0], [half, half, 0], [-half, half, 0]], np.float64)
    a = math.radians(angle)
    rz = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    pts = pts @ rz.T
    if tilt:
        t, ax = math.radians(tilt), math.radians(tilt_axis)
        k = np.array([math.cos(ax), math.sin(ax), 0])
        K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
        R = np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K
        pts = pts @ R.T
        # Наклон уменьшает видимую площадь; расстояние подбирается так,
        # чтобы ближайший к камере край сохранял масштаб ppm (иначе наклон
        # подменялся бы уменьшением модуля).
    z = pts[:, 2]
    zmin = z.min()
    proj = pts[:, :2] * (focal / (focal + (z - zmin)))[:, None]
    return proj


def dpm_dots(img, size, quiet, diam):
    """Точечная маркировка (DPM): каждый тёмный модуль — круглая точка
    диаметром diam модуля, модули не сливаются в сплошные области."""
    out = np.ones_like(img)
    yy, xx = np.mgrid[:SRC_PX, :SRC_PX].astype(np.float32)
    r = diam * SRC_PX / 2
    dot = ((xx - (SRC_PX - 1) / 2) ** 2 + (yy - (SRC_PX - 1) / 2) ** 2 <= r * r)
    q = int(round(quiet * SRC_PX))
    for row in range(size):
        for col in range(size):
            y, x = q + row * SRC_PX, q + col * SRC_PX
            if img[y + SRC_PX // 2, x + SRC_PX // 2] < 0.5:
                out[y:y + SRC_PX, x:x + SRC_PX][dot] = 0.0
    return out


_FONT = {}


def text_block(width_px, height_px, rng):
    """Строки мелкого текста этикетки (ярлык, состав, дата) — картинка 0..1."""
    from PIL import ImageDraw, ImageFont
    h = max(6, int(height_px))
    if h not in _FONT:
        try:
            _FONT[h] = ImageFont.truetype('arial.ttf', h)
        except OSError:
            _FONT[h] = ImageFont.load_default()
    alpha = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -/.:'
    img = Image.new('L', (max(1, int(width_px)), h + 2), 255)
    d = ImageDraw.Draw(img)
    s = ''.join(rng.choice(list(alpha), 60))
    d.text((0, -h // 8), s, fill=0, font=_FONT[h])
    return np.asarray(img, np.float32) / 255.0


def render_label(sym, p, rng, label_margin=3):
    """Символ на белой этикетке с искажениями печати и поверхности.
    Возвращает яркость 0..1 в пикселях источника.

    Ключи p сверх основных:
      quiet      — сколько модулей свободной зоны оставить (≤ QUIET); вместе
                   с margin=0 край этикетки встаёт на это расстояние от кода;
      margin     — поле этикетки за свободной зоной, модулей (умолчание 3);
      text_gap   — строка текста под символом на этом расстоянии, модулей;
      text_sides — 2: текст и под символом, и справа;
      dpm        — точечная маркировка, диаметр точки в долях модуля;
      invert     — светлые модули на тёмной этикетке."""
    size = p['size']
    img = dot_gain(sym, p.get('gain', 0.0))
    img = damage(img, p.get('damage', 0.0), rng, size)
    quiet = QUIET
    if p.get('quiet') is not None and p['quiet'] < QUIET:
        c = int(round((QUIET - p['quiet']) * SRC_PX))
        img = img[c:img.shape[0] - c, c:img.shape[1] - c]
        quiet = p['quiet']
    if p.get('dpm'):
        img = dpm_dots(img, size, quiet, p['dpm'])
    m = int(round(p.get('margin', label_margin) * SRC_PX))
    extra_b = extra_r = 0
    gap = p.get('text_gap')
    th = 1.6 * SRC_PX     # высота строки текста — 1,6 модуля
    if gap is not None:
        extra_b = int(gap * SRC_PX + 2 * th + SRC_PX)
        if p.get('text_sides', 1) == 2:
            extra_r = int(gap * SRC_PX + 14 * th)
    H, W = img.shape[0] + 2 * m + extra_b, img.shape[1] + 2 * m + extra_r
    side = max(H, W)
    lab = np.ones((side, side), np.float32)
    lab[m:m + img.shape[0], m:m + img.shape[1]] = img
    if gap is not None:
        sym_edge = m + int(round(quiet * SRC_PX))
        sym_side = size * SRC_PX
        y0 = sym_edge + sym_side + int(round(gap * SRC_PX))
        for k in range(2):
            t = text_block(sym_side + (extra_r if extra_r else 0), th, rng)
            y = y0 + int(k * th * 1.2)
            if y + t.shape[0] <= side:
                w = min(t.shape[1], side - sym_edge)
                lab[y:y + t.shape[0], sym_edge:sym_edge + w] = np.minimum(
                    lab[y:y + t.shape[0], sym_edge:sym_edge + w], t[:, :w])
        if p.get('text_sides', 1) == 2:
            x0 = sym_edge + sym_side + int(round(gap * SRC_PX))
            for k in range(int(sym_side // (th * 1.2))):
                t = text_block(side - x0, th, rng)
                y = sym_edge + int(k * th * 1.2)
                if y + t.shape[0] <= side and x0 < side:
                    w = min(t.shape[1], side - x0)
                    lab[y:y + t.shape[0], x0:x0 + w] = np.minimum(lab[y:y + t.shape[0], x0:x0 + w], t[:, :w])
    if p.get('invert'):
        lab = 1.0 - lab
    return lab


def place(frame, sym, p, center, rng, focal=2500.0):
    """Нарисовать код с условиями p на кадре (float32, 0..255) вокруг center.
    Условия кадра (размытие, шум) применяются к области вокруг этикетки."""
    lab = render_label(sym, p, rng)
    side = lab.shape[0]
    sym_px = (p['size'] + 2 * QUIET) * SRC_PX
    dx, dy, shade, inside = surface_field(p.get('surface', 'none'), p.get('surf_amp', 0.0),
                                          lab.shape, rng, sym_px)
    # Печать: чернила ink, бумага paper; контраст = (paper - ink) / paper.
    paper = p.get('paper', 245.0)
    ink = paper * (1 - p.get('contrast', 0.9))
    # Пиксель кадра интегрирует квадрат со стороной SRC_PX/ppm пикселей
    # источника: предфильтр против наложения частот.
    pre = 0.3 * SRC_PX / p['ppm']
    lab_f = ndimage.gaussian_filter(lab, pre) if pre > 0.3 else lab

    corners = label_corners(side, p['ppm'], p['angle'], p.get('tilt', 0.0), p.get('tilt_axis', 0.0), focal)
    corners = corners + np.asarray(center)
    src = [(0, 0), (side, 0), (side, side), (0, side)]
    H = homography(src, corners)
    Hi = np.linalg.inv(H)
    pad = 4 + 3 * (p.get('blur', 0.0) + p.get('motion', 0.0))
    x0 = int(max(0, math.floor(corners[:, 0].min() - pad)))
    y0 = int(max(0, math.floor(corners[:, 1].min() - pad)))
    x1 = int(min(frame.shape[1], math.ceil(corners[:, 0].max() + pad)))
    y1 = int(min(frame.shape[0], math.ceil(corners[:, 1].max() + pad)))
    if x1 <= x0 or y1 <= y0:
        return None
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float64)
    den = Hi[2, 0] * xx + Hi[2, 1] * yy + Hi[2, 2]
    u = (Hi[0, 0] * xx + Hi[0, 1] * yy + Hi[0, 2]) / den
    v = (Hi[1, 0] * xx + Hi[1, 1] * yy + Hi[1, 2]) / den
    on = (u >= 0) & (u < side - 1) & (v >= 0) & (v < side - 1)
    ui, vi = np.clip(u, 0, side - 1), np.clip(v, 0, side - 1)
    sdx = ndimage.map_coordinates(dx, [vi, ui], order=1)
    sdy = ndimage.map_coordinates(dy, [vi, ui], order=1)
    ssh = ndimage.map_coordinates(shade, [vi, ui], order=1)
    sin_ = ndimage.map_coordinates(inside.astype(np.float32), [vi, ui], order=1) > 0.5
    val = ndimage.map_coordinates(lab_f, [vi + sdy, ui + sdx], order=1, mode='constant', cval=1.0)
    lum = ink + (paper - ink) * val
    lum = lum * np.where(ssh > 1, 1, ssh) + np.where(ssh > 1, (ssh - 1) * (255 - lum) * 0.5, 0)
    if p.get('glare', 0.0) > 0:
        # Блик: полоса поперёк этикетки, высветляет и краску, и бумагу.
        th = rng.uniform(0, np.pi)
        d = (ui - side / 2) * math.cos(th) + (vi - side / 2) * math.sin(th)
        w = p.get('glare_w', 2.0) * SRC_PX
        lum = lum + p['glare'] * (255 - lum) * np.exp(-(d / w) ** 2)
    region = frame[y0:y1, x0:x1]
    mask = on & sin_
    region[mask] = lum[mask]

    # Условия съёмки — на области кода.
    pad_i = int(pad)
    patch = region
    if p.get('blur', 0.0) > 0:
        patch[:] = ndimage.gaussian_filter(patch, p['blur'])
    if p.get('motion', 0.0) > 0:
        L = max(1, int(round(p['motion'])))
        k = np.zeros((L, L), np.float32)
        ang = rng.uniform(0, np.pi)
        for t in np.linspace(-0.5, 0.5, 4 * L):
            cx = int(round((L - 1) / 2 + t * (L - 1) * math.cos(ang)))
            cy = int(round((L - 1) / 2 + t * (L - 1) * math.sin(ang)))
            k[cy, cx] = 1
        patch[:] = ndimage.convolve(patch, k / k.sum(), mode='nearest')
    if p.get('noise', 0.0) > 0:
        patch += rng.normal(0, p['noise'], patch.shape).astype(np.float32)
    np.clip(patch, 0, 255, out=patch)
    return (x0, y0, x1, y1), corners


def background(w, h, rng):
    g = np.linspace(0, 1, w, dtype=np.float32)[None, :] * 25 + np.linspace(0, 1, h, dtype=np.float32)[:, None] * 15
    tex = ndimage.gaussian_filter(rng.standard_normal((h, w)).astype(np.float32), 12) * 40
    return np.clip(135 + g + tex, 0, 255).astype(np.float32)


def to_gray8(frame, jpeg, tmp):
    img = Image.fromarray(np.clip(frame + 0.5, 0, 255).astype(np.uint8))
    if jpeg:
        p = Path(tmp) / 'f.jpg'
        img.save(p, quality=int(jpeg))
        img = Image.open(p).convert('L')
    return img


def scan_gray(scanner, img):
    a = np.ascontiguousarray(np.asarray(img, dtype=np.uint8))
    buf = bytearray(a.tobytes())
    h, w = a.shape
    return scanner.scan(dmr.ImageView(buf, w, h, w, dmr.PixelFormat.GRAY8))


# ── Развёртки ──────────────────────────────────────────────────────────────

BASE = dict(ppm=4.0, blur=0.0, motion=0.0, noise=3.0, contrast=0.85, jpeg=0, tilt=0.0,
            gain=0.0, damage=0.0, surface='none', surf_amp=0.0)
SIZES = (16, 22, 40)

SWEEPS = [
    # ось, значения, поправки к базе
    ('ppm', [1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.5, 3.0, 4.0, 6.0], {}),
    ('angle', [0, 5, 10, 15, 20, 25, 30, 35, 40, 45], {'ppm': 2.5}),
    ('blur', [0, 0.5, 0.8, 1.0, 1.2, 1.5, 1.8, 2.2, 2.6, 3.0], {}),
    ('blur@ppm2.5', [0, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5], {'ppm': 2.5}),
    ('motion', [0, 2, 3, 4, 5, 6, 8, 10], {}),
    ('noise', [0, 10, 20, 30, 45, 60, 80, 100], {}),
    ('contrast', [0.85, 0.5, 0.3, 0.2, 0.12, 0.08, 0.05, 0.03], {}),
    ('contrast+noise10', [0.85, 0.5, 0.3, 0.2, 0.12, 0.08, 0.05], {'noise': 10.0}),
    ('jpeg', [95, 75, 50, 30, 20, 10, 5], {'ppm': 3.0}),
    ('tilt', [0, 15, 30, 40, 50, 60, 70, 75], {}),
    ('gain', [-0.7, -0.55, -0.45, -0.3, -0.15, 0, 0.15, 0.3, 0.45, 0.55, 0.7], {}),
    ('damage', [0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40], {}),
    ('bend', [0, 30, 60, 90, 120, 150, 180], {'surface': 'bend'}),
    ('wave', [0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0], {'surface': 'wave'}),
    ('crumple', [0, 0.15, 0.3, 0.45, 0.6, 0.8, 1.0, 1.3], {'surface': 'crumple'}),
    ('bag', [0, 0.25, 0.5, 0.75, 1.0, 1.5], {'surface': 'bag'}),
    ('crumple@ppm2.5', [0, 0.15, 0.3, 0.45, 0.6, 0.8], {'surface': 'crumple', 'ppm': 2.5}),
    # Символ под завязку, без дополнения: ридер такой не исправляет вовсе.
    ('damage@nopad', [0, 0.03, 0.05, 0.10], {'fill': 1.0}),
    ('blur@nopad', [0, 1.0, 1.5, 1.8], {'fill': 1.0}),
    ('noise@nopad', [0, 30, 45, 60], {'fill': 1.0}),
]
SIZE_SWEEP = [10, 12, 14, 18, 22, 26, 32, 40, 52, 64, 80, 104, 144]
GRID_PPM = [1.6, 1.8, 2.0, 2.5, 3.0, 4.0]
GRID_BLUR = [0.0, 0.5, 1.0, 1.5]


def sweep_points(trials):
    pts = []
    for axis, values, over in SWEEPS:
        key = axis.split('@')[0].split('+')[0]
        for val in values:
            for t in range(trials):
                p = dict(BASE, **over)
                if key in ('bend', 'wave', 'crumple', 'bag'):
                    p['surf_amp'] = val
                else:
                    p[key] = val
                p['size'] = SIZES[t % len(SIZES)]
                pts.append((axis, val, p))
    for size in SIZE_SWEEP:
        for t in range(trials):
            pts.append(('size@ppm2.5', size, dict(BASE, ppm=2.5, size=size)))
    for ppm in GRID_PPM:
        for blur in GRID_BLUR:
            for t in range(trials):
                pts.append((f'ppm×blur {blur:g}', ppm, dict(BASE, ppm=ppm, blur=blur, size=SIZES[t % len(SIZES)])))
    return pts


def run_sweeps(syms, out, rng, trials, save_fails, tmp, axes=None):
    scanner = dmr.Scanner(dmr.Settings.single())
    rows = []
    pts = [x for x in sweep_points(trials) if not axes or x[0] in axes]
    t0 = time.time()
    fails_dir = out / 'sweep-fails'
    for i, (axis, val, p) in enumerate(pts):
        # Поворот — случайный везде, кроме своей оси: там угол задан, а
        # четверть оборота случайна (символ симметричен по ним, см.
        # SYNTHETIC_FAILURES.md).
        p['angle'] = float(val + 90 * rng.integers(0, 4)) if axis == 'angle' else float(rng.uniform(0, 360))
        p['tilt_axis'] = rng.uniform(0, 180)
        sym, data = syms.make(p['size'], p.get('fill'))
        frame = background(720, 540, rng)
        side_px = (p['size'] + 2 * QUIET + 6) * p['ppm']
        lim_x = max(0, 360 - side_px * 0.75)
        lim_y = max(0, 270 - side_px * 0.75)
        c = (360 + rng.uniform(-lim_x, lim_x) * 0.5, 270 + rng.uniform(-lim_y, lim_y) * 0.5)
        place(frame, sym, p, c, rng)
        img = to_gray8(frame, p.get('jpeg', 0), tmp)
        r = scan_gray(scanner, img)
        got = r.codes[0].text.decode('latin-1') if r.codes else ''
        ok = got == data
        wrong = bool(got) and not ok
        rows.append(dict(axis=axis, value=val, size=p['size'], ok=int(ok), wrong=int(wrong),
                         ms=round(r.elapsed_ms, 1), angle=round(p['angle'], 1),
                         status=r.status.name))
        if save_fails and not ok:
            fails_dir.mkdir(parents=True, exist_ok=True)
            img.save(fails_dir / f'{axis.replace("×", "x").replace(" ", "_")}_{val}_{p["size"]}_{i}.png')
        if i % 200 == 0:
            print(f'  {i}/{len(pts)}  {time.time() - t0:.0f} с', flush=True)
    with open(out / 'sweeps.csv', 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return rows


# ── Кадры с сотнями кодов ──────────────────────────────────────────────────

SURFACES = ['bend', 'wave', 'crumple', 'bag']

# Нагрузки многокодового кадра: (имя, ключ, от, до). Верхняя граница чуть
# за пределом, найденным развёрткой, нижняя — заметно внутри.
STRESSORS = [
    ('ppm', 'ppm', 1.3, 2.5),
    ('blur', 'blur', 0.6, 2.2),
    ('motion', 'motion', 2.0, 9.0),
    ('noise', 'noise', 15.0, 70.0),
    ('contrast', 'contrast', 0.08, 0.4),
    ('tilt', 'tilt', 20.0, 65.0),
    ('gain', 'gain', -0.6, 0.6),
    ('damage', 'damage', 0.03, 0.25),
    ('bend', 'surf_amp', 40.0, 180.0),
    ('wave', 'surf_amp', 0.2, 1.0),
    ('crumple', 'surf_amp', 0.1, 0.5),
    ('bag', 'surf_amp', 0.2, 1.0),
]


def random_conditions(rng, cell):
    """Условия одного кода на многокодовом кадре. Поворот случайный у всех;
    кроме него у кода от нуля до трёх «нагрузок» случайной силы, остальное —
    номинально (BASE). Так по каждой нагрузке видно, где она ломает чтение,
    и не всё решает сочетание нескольких сразу."""
    p = dict(BASE, ppm=float(rng.uniform(2.5, 5.0)), blur=0.3)
    k = int(rng.choice([0, 1, 1, 2, 2, 3]))
    names = []
    surf_taken = False
    for i in rng.permutation(len(STRESSORS))[:k]:
        name, key, lo, hi = STRESSORS[i]
        if name in SURFACES:
            if surf_taken:
                continue
            surf_taken = True
            p['surface'] = name
        p[key] = float(rng.uniform(lo, hi))
        names.append(name)
    p['stress'] = '+'.join(sorted(names)) or 'none'
    # Этикетка с поворотом обязана уместиться в клетку, иначе коды налезают
    # на соседей. Размер — только из помещающихся; не помещается и 10×10 —
    # уменьшается модуль.
    fits = lambda s: (s + 2 * QUIET + 6) * p['ppm'] * 1.45 <= cell
    sizes = [s for s in (10, 12, 14, 16, 18, 20, 22, 24, 26, 32) if fits(s)]
    if not sizes:
        p['ppm'] = cell / ((10 + 2 * QUIET + 6) * 1.45)
        sizes = [10]
    p['size'] = int(rng.choice(sizes))
    p['angle'] = float(rng.uniform(0, 360))
    p['tilt_axis'] = float(rng.uniform(0, 180))
    return p


def run_multi(syms, out, rng, tmp, frames):
    rows = []
    for fi, (W, H, cols, rows_n, jpeg) in enumerate(frames):
        cell_w, cell_h = W // cols, H // rows_n
        cell = min(cell_w, cell_h)
        frame = background(W, H, rng)
        truth = {}
        for r_ in range(rows_n):
            for c_ in range(cols):
                p = random_conditions(rng, cell)
                sym, data = syms.make(p['size'])
                ctr = (c_ * cell_w + cell_w / 2 + rng.uniform(-3, 3), r_ * cell_h + cell_h / 2 + rng.uniform(-3, 3))
                place(frame, sym, p, ctr, rng)
                p['cx'], p['cy'] = round(ctr[0]), round(ctr[1])
                truth[data] = p
        img = to_gray8(frame, jpeg, tmp)
        name = f'multi-frame-{fi + 1}-{W}x{H}-{len(truth)}codes' + ('-jpeg%d.jpg' % jpeg if jpeg else '.png')
        img.save(out / name, quality=95) if jpeg else img.save(out / name)
        s = dmr.Settings.multi(0)
        s.max_candidates = 2 * len(truth) + 100
        s.timeout_ms = 0.0
        t0 = time.time()
        res = scan_gray(dmr.Scanner(s), img)
        dt = time.time() - t0
        got = {}
        for c in res.codes:
            got.setdefault(c.text.decode('latin-1'), c)
        wrong = [(t, c) for t, c in got.items() if t not in truth]
        for data, p in truth.items():
            rows.append(dict(frame=fi + 1, read=int(data in got), data=data,
                             **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in p.items()}))
        nread = sum(1 for d in truth if d in got)
        print(f'  кадр {fi + 1}: {W}x{H}, кодов {len(truth)}, прочитано {nread}, ложных {len(wrong)}, {dt:.1f} с',
              flush=True)
        with open(out / 'multi-frames.txt', 'a', encoding='utf-8') as fh:
            fh.write(f'{name}\t{len(truth)}\t{nread}\t{len(wrong)}\t{dt:.1f}\n')
            for t, c in wrong:
                fh.write(f'  ЛОЖНОЕ: {t!r} box={c.box}\n')
    with open(out / 'multi.csv', 'w', newline='', encoding='utf-8') as fh:
        keys = []
        for r in rows:
            for k in r:
                if k not in keys:
                    keys.append(k)
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dmgen')
    ap.add_argument('out')
    ap.add_argument('--part', default='all', choices=['sweeps', 'multi', 'all'])
    ap.add_argument('--trials', type=int, default=12)
    ap.add_argument('--save-fails', action='store_true')
    ap.add_argument('--seed', type=int, default=20261008)
    ap.add_argument('--axes', help='только эти оси развёртки, через запятую')
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    tmp = tempfile.mkdtemp(prefix='limits-')
    syms = Symbols(a.dmgen, tmp, rng)
    print('dmr', dmr.version())
    if a.part in ('sweeps', 'all'):
        run_sweeps(syms, out, rng, a.trials, a.save_fails, tmp, a.axes.split(',') if a.axes else None)
    if a.part in ('multi', 'all'):
        (out / 'multi-frames.txt').unlink(missing_ok=True)
        run_multi(syms, out, rng, tmp, [
            (2000, 2000, 16, 16, 0),     # 4 Мп: детекция без уменьшения
            (2000, 2000, 16, 16, 75),    # то же, JPEG q=75
            (3200, 3200, 16, 16, 0),     # 10 Мп: детекция на уменьшенном вдвое
        ])


if __name__ == '__main__':
    main()
