"""zxing-cpp (Python bindings) in-process harness.

  python zxingcpp_bench.py <frames.lst> <out.tsv> [warmup_frames=20] [reps=3]

Options: formats=DataMatrix, try_rotate=True, try_invert=True,
try_downscale=True (all "best effort" switches on; the C++ tryHarder option
is not exposed by the Python binding and is on by default in the library),
binarizer = library default (LocalAverage), text_mode=Plain so that GS1
group separators come back as raw 0x1D bytes like in the other libraries.
zxing-cpp's reader is single-threaded.

Timed: only zxingcpp.read_barcodes() on an in-memory numpy uint8 gray array.
Output: idx \t rep \t ok \t hex(text) \t ms \t timedOut(always 0)
"""
import sys
import time

import numpy as np
import zxingcpp


def load_pgm(path):
    with open(path, "rb") as f:
        data = f.read()
    # header: P5 <ws> w <ws> h <ws> 255 <single ws>
    parts, pos = [], 0
    while len(parts) < 4:
        while data[pos:pos + 1].isspace():
            pos += 1
        if data[pos:pos + 1] == b"#":
            pos = data.index(b"\n", pos) + 1
            continue
        start = pos
        while not data[pos:pos + 1].isspace():
            pos += 1
        parts.append(data[start:pos])
    pos += 1
    w, h = int(parts[1]), int(parts[2])
    return np.frombuffer(data, dtype=np.uint8, count=w * h, offset=pos).reshape(h, w).copy()


def main():
    lst, out = sys.argv[1], sys.argv[2]
    warm = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    reps = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    paths = [l.strip() for l in open(lst, encoding="utf-8") if l.strip()]
    imgs = [load_pgm(p) for p in paths]
    kw = dict(formats=zxingcpp.BarcodeFormat.DataMatrix, try_rotate=True, try_invert=True,
              try_downscale=True, text_mode=zxingcpp.TextMode.Plain)
    for im in imgs[:warm]:
        zxingcpp.read_barcodes(im, **kw)
    with open(out, "w", encoding="ascii", newline="\n") as f:
        for r in range(1, reps + 1):
            for i, im in enumerate(imgs):
                t0 = time.perf_counter()
                res = zxingcpp.read_barcodes(im, **kw)
                ms = (time.perf_counter() - t0) * 1000.0
                ok = 1 if res else 0
                txt = res[0].text.encode("latin-1", "backslashreplace") if res else b""
                f.write("%d\t%d\t%d\t%s\t%.4f\t0\n" % (i, r, ok, txt.hex() if ok else "-", ms))
            f.flush()
            print("zxing-cpp rep %d done" % r, file=sys.stderr)


if __name__ == "__main__":
    main()
