# Sosmed Downloader

Website berbahasa Indonesia untuk mengambil **media dari URL postingan publik**, tanpa akun pengguna atau API berbayar. Frontend HTML/CSS/JavaScript statis, API Python di Vercel. Logo SVG dibuat khusus untuk proyek ini.

Domain canonical: **https://www.sosmed-downloader.web.id/**

## Status nyata — 27 November 2026

| Platform | Hasil uji lokal |
| --- | --- |
| Instagram | Dua carousel berhasil: 17 foto + 1 video. Semua 18 berkas diunduh penuh dari CDN; satu foto juga diuji melalui tombol unduh browser. |
| X / Twitter | Satu foto dan satu video berhasil diunduh penuh; unduhan video melalui browser berhasil. |
| Facebook | Satu video dan audio terpisah berhasil diunduh penuh. Foto belum diuji. |
| TikTok | Ekstraksi menghasilkan URL video, tetapi CDN mengembalikan HTTP 403. Belum dinyatakan didukung. |
| Threads | Dua contoh tidak menghasilkan media dari halaman publik. Eksperimental. |

Keberhasilan sampel **bukan jaminan semua postingan atau IP Vercel akan berhasil**. UI menampilkan status yang sama di `public/support.json`. Tidak ada hasil demo yang menyamar sebagai hasil unduhan.

“Kualitas tertinggi” adalah varian terbaik yang ditemukan dari sumber, tanpa re-encode. Bukan janji berkas asli sebelum kompresi platform. Instagram mempertahankan kandidat original-first saat sumber tidak menyertakan ukuran varian. Video/audio yang terpisah diberi label dan tidak digabungkan.

## Jalankan lokal

Python 3.12 atau lebih baru:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python dev.py
```

Buka http://127.0.0.1:8765. Tidak membutuhkan Node.js untuk menjalankan aplikasi; Node dipakai untuk pemeriksaan sintaks JavaScript di CI.

```sh
python -m unittest discover -s tests -v
node --check public/app.js
```

## Deploy ke Vercel

1. Import repository ini, branch `main`.
2. Framework preset **Other**, root directory repository, output directory **public**. Tidak perlu build command frontend atau API key.
3. Vercel memasang dependensi Python dari konfigurasi proyek. API ada di `api/resolve.py`; kode worker disertakan melalui `vercel.json`.
4. Deploy, lalu uji URL postingan dari deployment tersebut. IP pusat data dapat dibatasi platform meskipun uji lokal berhasil.
5. Tambahkan `www.sosmed-downloader.web.id` di **Settings → Domains**. Ikuti **nilai DNS yang ditampilkan Vercel untuk proyek Anda** di penyedia domain.
6. Tambahkan `sosmed-downloader.web.id` dan atur redirect permanen ke `https://www.sosmed-downloader.web.id/` di pengaturan Domains.
7. Pastikan HTTPS dan domain www valid sebelum mengirim sitemap ke mesin pencari.

Canonical, Open Graph URL, `robots.txt`, dan `sitemap.xml` memakai domain **www**. Sitemap hanya berisi halaman utama. `/api/` tidak diizinkan untuk crawler; hasil bersifat sementara di browser, tidak membuat halaman hasil terindeks.

Belum ada deployment atau perubahan DNS yang dilakukan oleh proyek ini. Hosting mengikuti kuota/paket Vercel Anda; kode tidak menjamin hosting tanpa biaya pada semua volume penggunaan.

## Cara kerja & batasan

- Satu URL postingan lengkap per permintaan, maksimal 20 media. URL profil, akun privat, story, shortlink dan unduhan seluruh akun tidak termasuk.
- Instagram memakai data **logged-out** publik, termasuk token sesi publik dari HTML, tanpa password/cookie login pengguna. Query ID situs dapat berubah.
- X memakai endpoint syndication/embed publik. Media kutipan dan tautan video eksternal tidak diambil.
- TikTok/Facebook memakai `gallery-dl`. Threads membaca data terstruktur pada halaman publik; tidak menembus login atau pembatasan akses.
- URL CDN dikirim ke browser. Browser mengunduh langsung dari sumber; server Vercel tidak mem-proxy berkas besar.
- CORS, URL kedaluwarsa, pembatasan wilayah/IP, dan syarat cookie sumber dapat menggagalkan pratinjau/unduhan. Tombol **Buka berkas** disediakan untuk penyimpanan manual bila browser mengizinkan.
- Unduhan melalui blob dibatasi 150 MB dan 90 detik agar memori browser tidak tak terbatas. Batas itu bukan ukuran maksimal file pada platform.
- Tombol batal menghentikan penantian browser; worker server tetap memiliki batas keras 23 detik.

## Keamanan & privasi

Validasi host/path postingan; HTTPS saja; tolak userinfo, port khusus, profil, URL lokal dan skema non-HTTP. Permintaan extractor, termasuk redirect, dibatasi ke domain layanan/CDN yang diketahui dan alamat IP publik. Respons sumber dibatasi 6 MiB, timeout jaringan 6 detik; proses anak dihentikan setelah 23 detik.

API menerima JSON maksimum 4 KiB; maksimal dua proses aktif dan 12 permintaan/menit **per instance hangat**. Ini bukan rate limit global. Untuk website publik dengan trafik besar, konfigurasi aturan rate limit di Vercel Firewall sesuai paket yang tersedia. Tidak ada Redis atau layanan berbayar yang diwajibkan oleh kode.

Tidak ada database, cookie autentikasi pengguna, telemetry aplikasi, atau penyimpanan berkas/riwayat di server. Hosting dan sumber media dapat mencatat metadata permintaan. Pesan kesalahan tidak mengekspos token atau stack trace. CSP dan header keamanan diatur di `vercel.json`; `dev.py` hanya server pengembangan lokal.

## Struktur

- `public/`: UI, logo SVG, robots, sitemap, status dukungan.
- `api/resolve.py`: batas permintaan dan worker terisolasi.
- `server/core.py`: validasi dan normalisasi hasil.
- `server/worker.py`: extractor publik.
- `tests/`: pengujian validasi, pemilihan media, batas API dan kegagalan sumber.
- `docs/testing.md`: hasil dan batas pengujian.
- `.github/workflows/test.yml`: pemeriksaan otomatis setiap push/PR.

Referensi implementasi: [yt-dlp Instagram extractor](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/instagram.py), [gallery-dl](https://github.com/mikf/gallery-dl), [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python). `gallery-dl` berlisensi GPL-2.0; Requests berlisensi Apache-2.0. Dependensi diinstal oleh pip, tidak disalin ke repository.
