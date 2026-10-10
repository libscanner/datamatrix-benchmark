// Minimal binary PGM (P5, maxval 255) loader shared by the C/C++ harnesses.
#pragma once
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

typedef struct { int w, h; unsigned char* data; } PgmImage;

static int pgm_token_(FILE* f) {
    int c, v = 0;
    for (;;) {                       /* skip whitespace and comments */
        c = fgetc(f);
        if (c == '#') { while (c != '\n' && c != EOF) c = fgetc(f); continue; }
        if (c == EOF) return -1;
        if (!isspace(c)) break;
    }
    while (c != EOF && isdigit(c)) { v = v * 10 + (c - '0'); c = fgetc(f); }
    return v;                        /* the single whitespace after maxval is consumed here */
}

static int pgm_load(const char* path, PgmImage* img) {
    FILE* f = fopen(path, "rb");
    if (!f) return 0;
    if (fgetc(f) != 'P' || fgetc(f) != '5') { fclose(f); return 0; }
    img->w = pgm_token_(f); img->h = pgm_token_(f);
    int maxv = pgm_token_(f);
    if (img->w <= 0 || img->h <= 0 || maxv != 255) { fclose(f); return 0; }
    size_t n = (size_t)img->w * img->h;
    img->data = (unsigned char*)malloc(n);
    size_t got = fread(img->data, 1, n, f);
    fclose(f);
    return got == n;
}

/* Read the list file: one path per line. Returns count; *out is malloc'ed. */
static int read_list(const char* path, char*** out) {
    FILE* f = fopen(path, "rb");
    if (!f) return 0;
    int cap = 512, n = 0;
    char** v = (char**)malloc(sizeof(char*) * cap);
    char line[4096];
    while (fgets(line, sizeof line, f)) {
        size_t L = strlen(line);
        while (L && (line[L - 1] == '\n' || line[L - 1] == '\r')) line[--L] = 0;
        if (!L) continue;
        if (n == cap) { cap *= 2; v = (char**)realloc(v, sizeof(char*) * cap); }
        v[n] = (char*)malloc(L + 1); memcpy(v[n], line, L + 1); ++n;
    }
    fclose(f);
    *out = v;
    return n;
}

/* Write bytes as lowercase hex (empty string -> "-"). */
static void put_hex(FILE* f, const unsigned char* s, size_t n) {
    if (!n) { fputc('-', f); return; }
    for (size_t i = 0; i < n; ++i) fprintf(f, "%02x", s[i]);
}
