"""frames/NNNN.png -> gray/NNNN.pgm and frames.lst (absolute paths, in expected.csv order).

    python synthetic/png_to_pgm.py

Every reader in the harness loads these PGM files, so all of them get the
byte-identical 8-bit gray buffer. The PNGs are already 8-bit gray.
"""
import csv
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
rows = list(csv.reader(open(HERE / 'expected.csv', encoding='utf-8'), delimiter=';'))[1:]
(HERE / 'gray').mkdir(exist_ok=True)
with open(HERE / 'frames.lst', 'w', encoding='utf-8') as lst:
    for r in rows:
        src = HERE / 'frames' / r[1]
        dst = HERE / 'gray' / (Path(r[1]).stem + '.pgm')
        Image.open(src).convert('L').save(dst)
        lst.write(str(dst) + '\n')
print(f'{len(rows)} frames -> {HERE / "gray"}, list {HERE / "frames.lst"}')
