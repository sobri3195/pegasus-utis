# Pegasus-UTIS

Pegasus-UTIS adalah framework Python modular untuk tracking dan intelligence berbasis consent, data milik sendiri, dan sumber publik legal. Framework ini dibangun dengan clean architecture, audit trail, dan integritas data (hash chain).

## Arsitektur & Alasan Desain

- **Core (Clean Architecture)**: Model event, hashing, storage engine, query, dan audit log dipisahkan agar mudah diuji serta diganti storage-nya.
- **Event-driven + Immutable**: Setiap output modul disimpan sebagai event immutable (`hash` + `prev_hash`).
- **Pluggable Storage**: SQLite default untuk konsistensi dan query, JSONL opsional untuk portability.
- **Modular Modules**: Location, Email, WhatsApp, dan OSINT adalah modul terpisah yang memakai core event processor.

## Struktur Proyek

```
utis/
  core/                 # models, storage, hashing, query, audit
  modules/
    location/           # FastAPI + halaman web
    email/              # email analyzer
    whatsapp/           # WhatsApp chat analyzer
    osint/              # OSINT provider + service
  cli.py
sample_data/
outputs/
```

## Modul A — Consent Location Check-in

### Menjalankan API

```bash
uvicorn utis.modules.location.api:app --reload --port 8000
```

### Endpoint

- `GET /links` → generate token check-in per entity
- `GET /c/{token}` → halaman web consent check-in
- `POST /checkin/{token}` → simpan event lokasi
- `GET /events` → query event check-in

## Modul B — Email Security & Deliverability Analyzer

```bash
utis email analyze sample_data/sample.eml --out outputs/email_report.json
```

Output disimpan sebagai event `email_analysis` dan report JSON di `outputs/email_report.json`.

## Modul C — WhatsApp Chat Export Analyzer

```bash
utis wa analyze sample_data/whatsapp_chat.txt --entity user123 --export outputs/wa
```

Output:
- `outputs/wa/report.json`
- `outputs/wa/messages_per_day.csv`
- `outputs/wa/activity.png`

Event disimpan sebagai `whatsapp_export_analysis`.

## Modul D — OSINT Public Footprint Checker

```bash
utis osint search "email@example.com" --dataset sample_data/osint_dataset.txt
```

Modul OSINT menggunakan provider modular (contoh: `LocalFileProvider`) + rate limiting + caching.
Event disimpan sebagai `osint_footprint`.

## Core System

- **EventProcessor** membuat hash chain (SHA-256) dengan `prev_hash`.
- **QueryEngine** mendukung filter `entity_id`, `event_type`, range waktu, pagination.
- **Audit Log** tersedia di tabel `audit_log` untuk tindakan storage (siap diperluas).

## Contoh Output

Contoh laporan tersedia di folder `outputs/`:
- `outputs/sample_email_report.json`
- `outputs/sample_osint_report.json`
- `outputs/sample_wa_report.json`

## Sample Data

File contoh tersedia di folder `sample_data/`:
- `sample.eml`
- `whatsapp_chat.txt`
- `osint_dataset.txt`
