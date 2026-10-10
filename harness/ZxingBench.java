// ZXing (Java, original) in-process harness.
//
//   java -cp core-3.5.4.jar;. ZxingBench <frames.lst> <out.tsv> [warmup_frames=20] [reps=3] [upscale=1]
//
// upscale>1 (SUPPLEMENTARY run only, not the headline number): bilinear integer
// upscaling of the gray frame before decoding, inside the timed region. ZXing's
// DataMatrix detector does not find symbols below ~5 px/module (ZxingSanity.java).
//
// Hints: POSSIBLE_FORMATS=[DATA_MATRIX], TRY_HARDER=true, ALSO_INVERTED=true
// (the same switches CommandLineRunner --try_harder --possible_formats=DATA_MATRIX
// sets, plus inverted symbols). Binarizer: HybridBinarizer (ZXing's default,
// also what CommandLineRunner uses). Luminance: the 8-bit gray plane is passed
// as-is via PlanarYUVLuminanceSource (Y plane == gray), no conversion.
//
// Timed: source + binarizer + BinaryBitmap construction + decodeWithState(),
// all on the calling thread. JIT is warmed by the warm-up pass.
// Output: idx \t rep \t ok \t hex(text) \t ms \t timedOut(always 0)
import com.google.zxing.*;
import com.google.zxing.common.HybridBinarizer;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

public class ZxingBench {
    static final class Gray { int w, h; byte[] px; }

    static Gray loadPgm(String path) throws IOException {
        byte[] d = Files.readAllBytes(Paths.get(path));
        int pos = 0; String[] tok = new String[4]; int nt = 0;
        while (nt < 4) {
            while (Character.isWhitespace(d[pos])) pos++;
            if (d[pos] == '#') { while (d[pos] != '\n') pos++; continue; }
            int s = pos;
            while (!Character.isWhitespace(d[pos])) pos++;
            tok[nt++] = new String(d, s, pos - s, StandardCharsets.US_ASCII);
        }
        pos++;
        Gray g = new Gray();
        g.w = Integer.parseInt(tok[1]); g.h = Integer.parseInt(tok[2]);
        g.px = Arrays.copyOfRange(d, pos, pos + g.w * g.h);
        return g;
    }

    static String hex(String s) {
        if (s == null || s.isEmpty()) return "-";
        // ZXing returns DataMatrix ASCII/byte data as ISO-8859-1 chars
        byte[] b = s.getBytes(StandardCharsets.ISO_8859_1);
        StringBuilder sb = new StringBuilder();
        for (byte x : b) sb.append(String.format("%02x", x & 0xff));
        return sb.toString();
    }

    public static void main(String[] a) throws Exception {
        int warm = a.length > 2 ? Integer.parseInt(a[2]) : 20;
        int reps = a.length > 3 ? Integer.parseInt(a[3]) : 3;
        scale = a.length > 4 ? Integer.parseInt(a[4]) : 1;
        List<String> paths = new ArrayList<>();
        for (String l : Files.readAllLines(Paths.get(a[0]), StandardCharsets.UTF_8))
            if (!l.trim().isEmpty()) paths.add(l.trim());
        List<Gray> imgs = new ArrayList<>();
        for (String p : paths) imgs.add(loadPgm(p));

        Map<DecodeHintType, Object> hints = new EnumMap<>(DecodeHintType.class);
        hints.put(DecodeHintType.POSSIBLE_FORMATS, EnumSet.of(BarcodeFormat.DATA_MATRIX));
        hints.put(DecodeHintType.TRY_HARDER, Boolean.TRUE);
        hints.put(DecodeHintType.ALSO_INVERTED, Boolean.TRUE);
        MultiFormatReader reader = new MultiFormatReader();
        reader.setHints(hints);

        for (int i = 0; i < warm && i < imgs.size(); i++) decode(reader, imgs.get(i));

        try (PrintWriter out = new PrintWriter(new BufferedWriter(new OutputStreamWriter(
                new FileOutputStream(a[1]), StandardCharsets.US_ASCII)))) {
            for (int r = 1; r <= reps; r++) {
                for (int i = 0; i < imgs.size(); i++) {
                    long t0 = System.nanoTime();
                    String txt = decode(reader, imgs.get(i));
                    double ms = (System.nanoTime() - t0) / 1e6;
                    out.printf(Locale.ROOT, "%d\t%d\t%d\t%s\t%.4f\t0%n", i, r, txt != null ? 1 : 0, hex(txt), ms);
                }
                out.flush();
                System.err.println("zxing-java rep " + r + " done");
            }
        }
    }

    static int scale = 1;

    static Gray upscale(Gray g, int k) {
        Gray o = new Gray(); o.w = g.w * k; o.h = g.h * k; o.px = new byte[o.w * o.h];
        for (int y = 0; y < o.h; y++) {
            double fy = Math.max(0, (y + 0.5) / k - 0.5); int y0 = Math.min((int) fy, g.h - 1), y1 = Math.min(y0 + 1, g.h - 1); double wy = fy - y0;
            for (int x = 0; x < o.w; x++) {
                double fx = Math.max(0, (x + 0.5) / k - 0.5); int x0 = Math.min((int) fx, g.w - 1), x1 = Math.min(x0 + 1, g.w - 1); double wx = fx - x0;
                double v = (1 - wy) * ((1 - wx) * (g.px[y0 * g.w + x0] & 255) + wx * (g.px[y0 * g.w + x1] & 255))
                         + wy * ((1 - wx) * (g.px[y1 * g.w + x0] & 255) + wx * (g.px[y1 * g.w + x1] & 255));
                o.px[y * o.w + x] = (byte) (int) Math.round(v);
            }
        }
        return o;
    }

    static String decode(MultiFormatReader reader, Gray g) {
        try {
            if (scale > 1) g = upscale(g, scale);
            LuminanceSource src = new PlanarYUVLuminanceSource(g.px, g.w, g.h, 0, 0, g.w, g.h, false);
            BinaryBitmap bmp = new BinaryBitmap(new HybridBinarizer(src));
            Result res = reader.decodeWithState(bmp);
            return res.getText();
        } catch (ReaderException e) {
            return null;
        }
    }
}
