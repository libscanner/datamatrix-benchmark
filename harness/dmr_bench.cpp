// dmr (our library) in-process harness.
//
//   dmr_bench <frames.lst> <out.tsv> [warmup_frames=20] [reps=3] [mode=independent]
//
// mode:
//   independent (default, used for the published numbers) — library defaults
//       (Settings::stream()) with the cross-frame size hint switched OFF
//       (mcHintRun=0), i.e. every frame is decoded on its own, exactly as the
//       `dmr --serve` CLI does for unrelated requests. No size sweep.
//   single — Settings::single() preset: as above plus the symbol-size sweep
//       (maxSizeTries=24) on frames where nothing was read. Slower on failures.
// In both modes rowParallel=false, and the library is built with
// -Dthreading=serial, so the whole scan runs on the calling thread. Default
// 10 s safety limit (Settings::timeoutMs) is kept.
//
// Timed: only Scanner::scan() on an in-memory 8-bit gray buffer.
// Output: idx \t rep \t ok \t hex(text) \t ms \t timedOut
#include <dmr/Dmr.h>
#include <chrono>
#include <cstdio>
#include <string>
#include <vector>
#include "pgm.h"

int main(int argc, char** argv) {
    if (argc < 3) { std::fprintf(stderr, "usage: dmr_bench list out.tsv [warmup] [reps]\n"); return 2; }
    const int warm = argc > 3 ? std::atoi(argv[3]) : 20;
    const int reps = argc > 4 ? std::atoi(argv[4]) : 3;
    char** paths = nullptr;
    const int n = read_list(argv[1], &paths);
    std::vector<PgmImage> imgs(n);
    for (int i = 0; i < n; ++i)
        if (!pgm_load(paths[i], &imgs[i])) { std::fprintf(stderr, "cannot load %s\n", paths[i]); return 1; }

    const std::string mode = argc > 5 ? argv[5] : "independent";
    dmr::Settings s;
    if (mode == "single") s = dmr::Settings::single();
    else if (mode == "independent") { s = dmr::Settings::stream(); s.mcHintRun = 0; }
    else { std::fprintf(stderr, "unknown mode %s\n", mode.c_str()); return 2; }
    s.rowParallel = false;
    const dmr::Scanner scanner(s);
    auto view = [&](int i) {
        return dmr::ImageView{ imgs[i].data, imgs[i].w, imgs[i].h, imgs[i].w, dmr::PixelFormat::Gray8 };
    };
    for (int i = 0; i < warm && i < n; ++i) (void)scanner.scan(view(i));

    FILE* out = std::fopen(argv[2], "wb");
    for (int r = 1; r <= reps; ++r) {
        for (int i = 0; i < n; ++i) {
            const auto t0 = std::chrono::steady_clock::now();
            const dmr::ScanResult res = scanner.scan(view(i));
            const auto t1 = std::chrono::steady_clock::now();
            const double ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
            const std::string& t = res.text();
            std::fprintf(out, "%d\t%d\t%d\t", i, r, res.ok() ? 1 : 0);
            put_hex(out, reinterpret_cast<const unsigned char*>(t.data()), res.ok() ? t.size() : 0);
            std::fprintf(out, "\t%.4f\t%d\n", ms, res.timedOut ? 1 : 0);
        }
        std::fflush(out);
        std::fprintf(stderr, "dmr rep %d done\n", r);
    }
    std::fclose(out);
    return 0;
}
