# Berkas Beres — AI Document Checker

Aplikasi web yang membantu mengecek kelengkapan berkas pendaftaran (PKM, beasiswa, dll)
berdasarkan buku panduan resmi, lalu membantu men-generate draft dokumen yang masih kurang.

**Stack:** Flask + LangChain + Mistral API (`langchain-mistralai`)

## Alur penggunaan

1. **Pilih peran** — Mahasiswa atau Pekerja/Profesional (menentukan syarat mana yang relevan).
2. **Upload buku panduan** — PDF/DOCX/gambar. AI membaca isinya dan mengekstrak checklist syarat.
3. **Upload berkas yang sudah dimiliki** — bisa banyak file sekaligus.
4. **Pengecekan otomatis** — AI membandingkan checklist vs berkas yang di-upload, menandai setiap
   syarat sebagai **Sudah ada** / **Belum lengkap** / **Belum ada**, lengkap dengan alasannya.
5. **Generate dokumen yang kurang** — user pilih mana saja yang ingin dibuatkan draft-nya.
   Data pribadi/sensitif yang tidak diketahui AI (nama, NIM, alamat, tanggal, dll) otomatis
   ditandai sebagai placeholder seperti `[NAMA_LENGKAP]`.
6. **Review & edit** — draft ditampilkan di textarea yang bisa diedit langsung, beserta daftar
   placeholder yang harus diisi.
7. **Download** — pilih format PDF atau DOCX.

## Instalasi

```bash
cd ai-doc-checker
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### OCR untuk gambar/scan (opsional tapi disarankan)

Untuk fitur upload gambar (scan dokumen), perlu binary `tesseract` terpasang di sistem:

```bash
# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-ind

# macOS (Homebrew)
brew install tesseract tesseract-lang
```

Kalau `tesseract` tidak terpasang, fitur lain tetap berjalan normal — hanya upload gambar yang
akan menampilkan pesan bahwa OCR tidak tersedia, bukannya error/crash.

## Konfigurasi

```bash
cp .env.example .env
```

Lalu isi `MISTRAL_API_KEY` dengan API key dari [console.mistral.ai](https://console.mistral.ai/).

## Menjalankan

```bash
python app.py
```

Buka `http://127.0.0.1:5000` di browser.

## Struktur proyek

```
ai-doc-checker/
├── app.py              # Routing Flask & state management
├── doc_extract.py       # Ekstraksi teks dari PDF/DOCX/gambar (OCR)
├── llm_utils.py         # Semua prompt & panggilan ke Mistral via LangChain
├── doc_export.py        # Generate file .docx / .pdf dari draft
├── templates/
│   └── index.html       # UI wizard (5 langkah)
├── static/
│   ├── style.css
│   └── script.js
├── requirements.txt
└── .env.example
```

## Catatan penting (batasan prototype)

- **State disimpan in-memory** (dict Python per session cookie). Cocok untuk demo/development.
  Kalau server restart, semua progres hilang. Untuk produksi, ganti dengan Redis/database
  dan jangan jalankan dengan banyak worker proses sekaligus (atau pakai shared store).
- **PDF hasil scan tanpa teks** (PDF dari foto yang di-export jadi PDF) tidak bisa diekstrak
  teksnya langsung — sebaiknya user upload dalam format gambar (PNG/JPG) agar diproses lewat OCR.
- **AI bisa salah baca/menyimpulkan.** Hasil pengecekan checklist dan draft yang dihasilkan AI
  tetap perlu direview manual oleh user sebelum dipakai untuk keperluan resmi — terutama soal
  ketepatan syarat administratif yang sering berubah-ubah antar instansi.
- **Jangan biarkan placeholder `[SEPERTI_INI]` tersisa** di dokumen final — selalu cek ulang
  sebelum submit ke pihak resmi.
- Belum ada autentikasi user — semua pakai session cookie browser biasa. Tambahkan login kalau
  mau dipakai multi-user di internet publik.
