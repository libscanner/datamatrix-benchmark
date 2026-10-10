/* libdmtx in-process harness.
 *
 *   dmtx_bench <frames.lst> <out.tsv> [warmup_frames=20] [reps=3] [timeout_ms=3000]
 *
 * Library defaults (same as `dmtxread` with no options: shrink 1, default
 * edge threshold / square deviation / scan gap), except:
 *   - DmtxPropFnc1 = 0x1D, so GS1 FNC1 separators are emitted as GS bytes
 *     (by default libdmtx silently drops FNC1, which only changes the string
 *     representation, not what is decoded);
 *   - a per-frame time limit (timeout_ms), like `dmtxread -m`.
 * Regions are tried in the order libdmtx finds them until the first one that
 * decodes (like dmtxread -N1).
 *
 * Timed: dmtxImageCreate .. dmtxDecodeDestroy around an in-memory 8-bit gray
 * buffer (DmtxPack8bppK). Output: idx \t rep \t ok \t hex(text) \t ms \t timedOut
 */
#include <dmtx.h>
#include <time.h>
#include <windows.h>
#include "pgm.h"

static double now_ms(void) {
    static LARGE_INTEGER fq; LARGE_INTEGER t;
    if (!fq.QuadPart) QueryPerformanceFrequency(&fq);
    QueryPerformanceCounter(&t);
    return (double)t.QuadPart * 1000.0 / (double)fq.QuadPart;
}

static int decode(const PgmImage* im, int timeout_ms, unsigned char* buf, size_t cap,
                  size_t* len, int* timed_out) {
    int ok = 0;
    *len = 0; *timed_out = 0;
    DmtxImage* img = dmtxImageCreate(im->data, im->w, im->h, DmtxPack8bppK);
    DmtxDecode* dec = dmtxDecodeCreate(img, 1);
    dmtxDecodeSetProp(dec, DmtxPropFnc1, 0x1D);
    DmtxTime timeout = dmtxTimeAdd(dmtxTimeNow(), timeout_ms);
    for (;;) {
        DmtxRegion* reg = dmtxRegionFindNext(dec, &timeout);
        if (!reg) { if (dmtxTimeExceeded(timeout)) *timed_out = 1; break; }
        DmtxMessage* msg = dmtxDecodeMatrixRegion(dec, reg, DmtxUndefined);
        if (msg) {
            size_t n = msg->outputIdx < cap ? (size_t)msg->outputIdx : cap;
            memcpy(buf, msg->output, n); *len = n; ok = 1;
            dmtxMessageDestroy(&msg);
        }
        dmtxRegionDestroy(&reg);
        if (ok) break;
        if (dmtxTimeExceeded(timeout)) { *timed_out = 1; break; }
    }
    dmtxDecodeDestroy(&dec);
    dmtxImageDestroy(&img);
    return ok;
}

int main(int argc, char** argv) {
    if (argc < 3) { fprintf(stderr, "usage: dmtx_bench list out.tsv [warmup] [reps] [timeout_ms]\n"); return 2; }
    int warm = argc > 3 ? atoi(argv[3]) : 20;
    int reps = argc > 4 ? atoi(argv[4]) : 3;
    int tmo  = argc > 5 ? atoi(argv[5]) : 3000;
    char** paths = NULL;
    int n = read_list(argv[1], &paths);
    PgmImage* imgs = (PgmImage*)calloc(n, sizeof(PgmImage));
    for (int i = 0; i < n; ++i)
        if (!pgm_load(paths[i], &imgs[i])) { fprintf(stderr, "cannot load %s\n", paths[i]); return 1; }
    static unsigned char buf[8192];
    size_t len; int to;
    for (int i = 0; i < warm && i < n; ++i) decode(&imgs[i], tmo, buf, sizeof buf, &len, &to);

    FILE* out = fopen(argv[2], "wb");
    for (int r = 1; r <= reps; ++r) {
        for (int i = 0; i < n; ++i) {
            double t0 = now_ms();
            int ok = decode(&imgs[i], tmo, buf, sizeof buf, &len, &to);
            double ms = now_ms() - t0;
            fprintf(out, "%d\t%d\t%d\t", i, r, ok);
            put_hex(out, buf, ok ? len : 0);
            fprintf(out, "\t%.4f\t%d\n", ms, to);
        }
        fflush(out);
        fprintf(stderr, "libdmtx rep %d done\n", r);
    }
    fclose(out);
    return 0;
}
