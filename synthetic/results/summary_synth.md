# DataMatrix readers on synthetic frames

1368 frames, 720×540, one code per frame on a white label on a grey background with uneven light. One condition is varied at a time; the rest stay nominal (4 px per module, random rotation 0–360°, print contrast 0.85, noise σ = 3). 12 frames per point: symbols 16×16, 22×22 and 40×40 in turn, random digits filling 60–85 % of capacity (the "no padding" axis: 100 %). Frames, expected strings and the generator are published with this report.

**Read** = decoded string equals the encoded one. **Wrong** = a non-empty string that differs from the encoded one.

## Overall

| library | read | read % | wrong | median ms (all frames) | median ms (read frames) | CPU mean / min % |
|---|---:|---:|---:|---:|---:|---:|
| dmr (ours) | 1126/1368 | 82.3 % | 0 | 5.7 | 5.0 | 125 / 59 |
| zxing-cpp | 955/1368 | 69.8 % | 0 | 1.9 | 1.9 | 114 / 114 |
| ZXing (Java) | 43/1368 | 3.1 % | 0 | 0.8 | 1.1 | 25 / 25 |
| libdmtx | 892/1368 | 65.2 % | 0 | 12.1 | 5.5 | 168 / 29 |
| dmr, Settings::single() | 1133/1368 | 82.8 % | 0 | 5.3 | 4.4 | 151 / 17 |

**Sanity check — nominal frames** (96 frames with no added distortion, taken from the nominal point of several axes): dmr (ours) 96/96, zxing-cpp 95/96, ZXing (Java) 8/96, libdmtx 96/96, dmr, Settings::single() 96/96. The symbols are standard ECC 200 that other readers decode.

## Limit per condition

Worst value, moving away from the nominal one, at which a library still reads ≥ 90% of the frames of the point (module size: smallest; dot gain: range both ways); "—" = not even at the nominal value.

| condition | dmr (ours) | zxing-cpp | ZXing (Java) | libdmtx | dmr, Settings::single() |
|---|---:|---:|---:|---:|---:|
| module px | 1.4 | 2.0 | — | 2.5 | 1.4 |
| rotation deg | 45 | 20 | — | 30 | 45 |
| defocus sigma px | 1.8 | 1.5 | — | 1.2 | 1.8 |
| motion blur px | 6 | 4 | — | 5 | 6 |
| noise sigma | 30 | 30 | — | 10 | 45 |
| print contrast | 0.05 | 0.12 | — | 0.12 | 0.05 |
| jpeg quality | 5 | 5 | — | 10 | 5 |
| tilt deg | 60 | 60 | — | 50 | 60 |
| dot gain | -0.55 … +0.7 | -0.3 … +0.3 | — | -0.3 … +0.3 | -0.55 … +0.7 |
| damage share | 0.1 | 0.05 | — | 0.05 | 0.1 |
| damage share, no padding | 0.05 | 0.05 | — | 0.05 | 0.05 |
| cylinder bend deg | 180 | 150 | — | 60 | 180 |
| wave modules | 0.5 | 0.25 | — | 0 | 0.5 |
| crumpled paper modules | 0.15 | 0.15 | — | 0 | 0.15 |
| plastic bag modules | 0.25 | 0.25 | — | 0.25 | 0.25 |
| inverted (light on dark) | 1 | 1 | — | 1 | 1 |

## Read share per point, %

### module px

| value | dmr (ours) | zxing-cpp | ZXing (Java) | libdmtx | dmr, Settings::single() |
|---:|---:|---:|---:|---:|---:|
| 1.2 | 67 | 0 | 0 | 0 | 67 |
| 1.4 | 100 | 0 | 0 | 8 | 100 |
| 1.6 | 100 | 17 | 0 | 25 | 100 |
| 1.8 | 100 | 50 | 0 | 33 | 100 |
| 2.0 | 100 | 100 | 0 | 58 | 100 |
| 2.2 | 100 | 92 | 0 | 75 | 100 |
| 2.5 | 100 | 100 | 0 | 92 | 100 |
| 3.0 | 100 | 100 | 0 | 92 | 100 |
| 4.0 | 100 | 100 | 8 | 100 | 100 |
| 6.0 | 100 | 100 | 0 | 100 | 100 |

### rotation deg

| value | dmr (ours) | zxing-cpp | ZXing (Java) | libdmtx | dmr, Settings::single() |
|---:|---:|---:|---:|---:|---:|
| 0 | 100 | 100 | 0 | 92 | 100 |
| 5 | 100 | 100 | 8 | 92 | 100 |
| 10 | 100 | 100 | 8 | 100 | 100 |
| 15 | 100 | 100 | 0 | 92 | 100 |
| 20 | 100 | 92 | 0 | 92 | 100 |
| 25 | 100 | 75 | 0 | 100 | 100 |
| 30 | 100 | 100 | 0 | 92 | 100 |
| 35 | 100 | 83 | 0 | 83 | 100 |
| 40 | 100 | 100 | 0 | 75 | 100 |
| 45 | 100 | 100 | 0 | 58 | 100 |

### defocus sigma px

| value | dmr (ours) | zxing-cpp | ZXing (Java) | libdmtx | dmr, Settings::single() |
|---:|---:|---:|---:|---:|---:|
| 0 | 100 | 100 | 0 | 100 | 100 |
| 0.5 | 100 | 100 | 8 | 100 | 100 |
| 0.8 | 100 | 100 | 8 | 92 | 100 |
| 1.0 | 100 | 100 | 0 | 100 | 100 |
| 1.2 | 100 | 92 | 25 | 100 | 100 |
| 1.5 | 100 | 100 | 8 | 83 | 100 |
| 1.8 | 100 | 75 | 0 | 67 | 100 |
| 2.2 | 25 | 0 | 0 | 0 | 25 |
| 2.6 | 0 | 0 | 0 | 0 | 0 |
| 3.0 | 0 | 0 | 0 | 0 | 0 |

### motion blur px

| value | dmr (ours) | zxing-cpp | ZXing (Java) | libdmtx | dmr, Settings::single() |
|---:|---:|---:|---:|---:|---:|
| 0 | 100 | 100 | 8 | 100 | 100 |
| 2 | 100 | 100 | 8 | 100 | 100 |
| 3 | 100 | 100 | 8 | 100 | 100 |
| 4 | 100 | 100 | 0 | 100 | 100 |
| 5 | 100 | 83 | 0 | 92 | 100 |
| 6 | 100 | 92 | 8 | 33 | 100 |
| 8 | 17 | 0 | 0 | 0 | 17 |
| 10 | 0 | 0 | 0 | 0 | 0 |

### noise sigma

| value | dmr (ours) | zxing-cpp | ZXing (Java) | libdmtx | dmr, Settings::single() |
|---:|---:|---:|---:|---:|---:|
| 0 | 100 | 100 | 17 | 100 | 100 |
| 10 | 100 | 100 | 8 | 100 | 100 |
| 20 | 100 | 100 | 0 | 83 | 100 |
| 30 | 100 | 92 | 0 | 100 | 100 |
| 45 | 75 | 58 | 0 | 42 | 92 |
| 60 | 25 | 0 | 0 | 50 | 50 |
| 80 | 0 | 0 | 0 | 0 | 0 |
| 100 | 0 | 0 | 0 | 0 | 0 |

### print contrast

| value | dmr (ours) | zxing-cpp | ZXing (Java) | libdmtx | dmr, Settings::single() |
|---:|---:|---:|---:|---:|---:|
| 0.85 | 100 | 100 | 0 | 100 | 100 |
| 0.5 | 100 | 92 | 8 | 100 | 100 |
| 0.3 | 100 | 100 | 8 | 100 | 100 |
| 0.2 | 100 | 100 | 0 | 92 | 100 |
| 0.12 | 100 | 100 | 0 | 100 | 100 |
| 0.08 | 100 | 58 | 0 | 58 | 100 |
| 0.05 | 92 | 0 | 0 | 0 | 100 |

### jpeg quality

| value | dmr (ours) | zxing-cpp | ZXing (Java) | libdmtx | dmr, Settings::single() |
|---:|---:|---:|---:|---:|---:|
| 95 | 100 | 100 | 0 | 100 | 100 |
| 75 | 100 | 100 | 0 | 100 | 100 |
| 50 | 100 | 100 | 0 | 100 | 100 |
| 30 | 100 | 92 | 8 | 100 | 100 |
| 20 | 100 | 92 | 8 | 100 | 100 |
| 10 | 100 | 92 | 0 | 92 | 100 |
| 5 | 100 | 100 | 8 | 75 | 100 |

### tilt deg

| value | dmr (ours) | zxing-cpp | ZXing (Java) | libdmtx | dmr, Settings::single() |
|---:|---:|---:|---:|---:|---:|
| 0 | 100 | 100 | 8 | 100 | 100 |
| 15 | 100 | 100 | 17 | 100 | 100 |
| 30 | 100 | 100 | 0 | 100 | 100 |
| 40 | 100 | 100 | 17 | 100 | 100 |
| 50 | 100 | 92 | 0 | 92 | 100 |
| 60 | 100 | 92 | 0 | 67 | 100 |
| 70 | 33 | 8 | 0 | 17 | 33 |

### dot gain

| value | dmr (ours) | zxing-cpp | ZXing (Java) | libdmtx | dmr, Settings::single() |
|---:|---:|---:|---:|---:|---:|
| -0.55 | 100 | 75 | 0 | 0 | 100 |
| -0.45 | 100 | 83 | 8 | 17 | 100 |
| -0.3 | 100 | 100 | 8 | 100 | 100 |
| -0.15 | 100 | 100 | 8 | 100 | 100 |
| 0 | 100 | 100 | 8 | 100 | 100 |
| 0.15 | 100 | 100 | 0 | 100 | 100 |
| 0.3 | 100 | 100 | 8 | 100 | 100 |
| 0.45 | 100 | 25 | 0 | 83 | 100 |
| 0.55 | 100 | 8 | 0 | 50 | 100 |
| 0.7 | 100 | 0 | 0 | 0 | 100 |

### damage share

| value | dmr (ours) | zxing-cpp | ZXing (Java) | libdmtx | dmr, Settings::single() |
|---:|---:|---:|---:|---:|---:|
| 0 | 100 | 92 | 17 | 100 | 100 |
| 0.05 | 100 | 100 | 0 | 92 | 100 |
| 0.1 | 92 | 58 | 8 | 58 | 92 |
| 0.15 | 67 | 17 | 0 | 0 | 67 |
| 0.2 | 25 | 0 | 0 | 0 | 25 |
| 0.25 | 0 | 0 | 0 | 0 | 0 |
| 0.3 | 0 | 0 | 0 | 0 | 0 |

### damage share, no padding

| value | dmr (ours) | zxing-cpp | ZXing (Java) | libdmtx | dmr, Settings::single() |
|---:|---:|---:|---:|---:|---:|
| 0 | 100 | 100 | 8 | 100 | 100 |
| 0.03 | 100 | 100 | 0 | 100 | 100 |
| 0.05 | 100 | 92 | 8 | 100 | 100 |
| 0.1 | 25 | 50 | 0 | 50 | 25 |

### cylinder bend deg

| value | dmr (ours) | zxing-cpp | ZXing (Java) | libdmtx | dmr, Settings::single() |
|---:|---:|---:|---:|---:|---:|
| 0 | 100 | 100 | 8 | 100 | 100 |
| 30 | 100 | 100 | 0 | 100 | 100 |
| 60 | 100 | 100 | 0 | 100 | 100 |
| 90 | 100 | 92 | 0 | 67 | 100 |
| 120 | 100 | 100 | 0 | 58 | 100 |
| 150 | 100 | 100 | 0 | 33 | 100 |
| 180 | 100 | 67 | 0 | 0 | 100 |

### wave modules

| value | dmr (ours) | zxing-cpp | ZXing (Java) | libdmtx | dmr, Settings::single() |
|---:|---:|---:|---:|---:|---:|
| 0 | 100 | 100 | 8 | 100 | 100 |
| 0.25 | 100 | 92 | 0 | 83 | 100 |
| 0.5 | 100 | 8 | 0 | 0 | 100 |
| 0.75 | 25 | 0 | 0 | 0 | 25 |
| 1.0 | 0 | 0 | 0 | 0 | 0 |
| 1.5 | 0 | 0 | 0 | 0 | 0 |

### crumpled paper modules

| value | dmr (ours) | zxing-cpp | ZXing (Java) | libdmtx | dmr, Settings::single() |
|---:|---:|---:|---:|---:|---:|
| 0 | 100 | 92 | 8 | 100 | 100 |
| 0.15 | 100 | 100 | 0 | 83 | 100 |
| 0.3 | 67 | 25 | 0 | 8 | 67 |
| 0.45 | 0 | 0 | 0 | 0 | 8 |
| 0.6 | 0 | 0 | 0 | 0 | 0 |
| 0.8 | 0 | 0 | 0 | 0 | 0 |

### plastic bag modules

| value | dmr (ours) | zxing-cpp | ZXing (Java) | libdmtx | dmr, Settings::single() |
|---:|---:|---:|---:|---:|---:|
| 0 | 100 | 100 | 0 | 100 | 100 |
| 0.25 | 100 | 92 | 17 | 100 | 100 |
| 0.5 | 83 | 50 | 0 | 42 | 83 |
| 0.75 | 17 | 17 | 0 | 8 | 17 |
| 1.0 | 50 | 8 | 0 | 8 | 50 |

### inverted (light on dark)

| value | dmr (ours) | zxing-cpp | ZXing (Java) | libdmtx | dmr, Settings::single() |
|---:|---:|---:|---:|---:|---:|
| 0 | 100 | 100 | 8 | 100 | 100 |
| 1 | 100 | 100 | 8 | 100 | 100 |

