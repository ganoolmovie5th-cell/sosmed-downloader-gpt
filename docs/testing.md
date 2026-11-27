# Pengujian — 27 November 2026

## Otomatis

`python -m unittest discover -s tests -v`: 14 kasus, mencakup URL sah, penghapusan tracking, host palsu, URL privat, port/userinfo, DNS privat, pemilihan varian terbesar, kandidat original-first, deduplikasi, batas 20 media, payload gated Instagram, batas body/origin/content type, budget permintaan, timeout, serta redaksi error.

`node --check public/app.js`: sintaks valid.

## Pengujian sumber nyata (lokal, bukan Vercel)

| Sampel | Hasil |
| --- | --- |
| Instagram `DgM8G2gH3gz` | 8 foto; seluruh berkas HTTP 200, diunduh penuh. |
| Instagram `DfPUSJdnxaP` | 9 foto + 1 video; seluruh berkas HTTP 200, diunduh penuh. Foto pertama 3075×4096 terlihat di browser; tombol unduh berhasil. |
| X `BarackObama/status/896523232098078720` | Foto HTTP 200, 94.820 byte. |
| X `captainamerica/status/719944021058060289` | Video HTTP 200, 537.709 byte. Tombol unduh browser berhasil. |
| Facebook `watch/?v=647537299265662` | Video 15.561.291 byte + audio 775.999 byte, HTTP 200. Audio dipisahkan dan diberi peringatan. |
| TikTok `@tiktok/video/7012606652008402182` | Metadata/URL tersedia; GET media HTTP 403. Status terbatas. |
| Threads `@zuck/post/CuVafQTvquB` dan `@zuck/post/DMF6uUgx9f9` | Tidak menghasilkan media publik yang dapat diproses. Status eksperimental. |

File media dan respons sumber lengkap tidak dimasukkan ke repository. Data uji lokal hanya dipakai untuk pemeriksaan; endpoint CDN bertoken tidak dipublikasikan.

## Browser

Chrome: layout desktop 1440×1000 dan mobile emulation 390×844. Form, hasil nyata Instagram/X, filter video, keadaan kosong, error URL profil, loading, cancel, clipboard failure, dan hasil parsial diperiksa. Tidak ada overflow horizontal. Label form, fokus keyboard, area tombol, dan fallback unduhan diperiksa. Screenshot/evidence disimpan lokal di workspace pengerjaan, bukan berkas media pengguna di repository.

## Belum diuji / risiko

- Belum deploy; belum ada pengujian dari IP Vercel, DNS, HTTPS domain produksi, atau eksekusi CI GitHub sampai push selesai.
- Belum menguji Safari/iOS, semua format postingan, file >150 MB, semua wilayah, atau beban paralel antar-instance.
- Pembatasan Instagram/TikTok/X/Meta bisa berubah kapan saja. Tidak ada jaminan seluruh postingan tersedia.
- Foto Facebook dan unduhan Threads belum lolos uji nyata. TikTok belum lolos unduhan.
- Worker tidak menggabungkan stream audio/video. Rate limit hanya per instance, bukan global.
