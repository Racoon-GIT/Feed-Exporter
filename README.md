# Feed-Exporter

Sistema automatizzato per generazione feed XML prodotti e-commerce per Google Shopping e Meta Catalog.

## 🎯 Caratteristiche

- ✅ **Multi-piattaforma**: Google Shopping + Meta (Facebook/Instagram)
- ✅ **Memory-efficient**: Streaming XML generation
- ✅ **GraphQL + REST hybrid**: Ottimizzazione chiamate API Shopify
- ✅ **Cron Job dormiente**: Trigger on-demand via Scheduler
- ✅ **Backup automatico**: Feed precedenti salvati prima di sovrascrivere
- ✅ **Metriche dettagliate**: Tracking performance e dimensioni feed

## 🏗️ Architettura

### Modalità Cron Job (Attuale)

```
┌──────────────────┐
│  Scheduler App   │  ← Vercel (Free)
│  (Vercel)        │
└────────┬─────────┘
         │ Deploy Hook POST
         │ Daily 6 AM (Europe/Rome)
         ▼
┌──────────────────┐
│  Render Cron Job │  ← Sempre dormiente
│  feed-exporter   │
│                  │
│  orchestrator.py │  ← Esegue quando triggerato
│  └─ Google Feed  │     ~25 minuti totali
│  └─ Meta Feed    │
└──────────────────┘
         │
         ▼
┌──────────────────┐
│  Feed XML Output │
│  (public/)       │
│  - google_shopping_feed.xml
│  - meta_catalog_feed.xml
│  - feed_metrics.json
└──────────────────┘
```

### Vantaggi vs Web Service

| Aspetto | Web Service (Prima) | Cron Job (Ora) |
|---------|---------------------|----------------|
| **Costo** | $7-21/mese | **$0/mese** ✅ |
| **Uptime** | Always-on (24/7) | On-demand (25 min/giorno) |
| **Consumo** | ~730 ore/mese | ~12.5 ore/mese |
| **Trigger** | HTTP endpoint | Deploy Hook |
| **Dashboard** | Flask UI | Scheduler UI |
| **Cold Start** | N/A | N/A (cron sempre fresh) |

## 📦 Installazione

```bash
# Clone repository
git clone https://github.com/Racoon-GIT/Feed-Exporter.git
cd Feed-Exporter

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env con le tue credenziali
```

## ⚙️ Configurazione

### Environment Variables

```bash
# Shopify Configuration (REQUIRED)
SHOPIFY_SHOP_URL=racoon-lab.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_xxxxxxxxxxxxx

# Shop Configuration (OPTIONAL)
SHOP_BASE_URL=https://racoon-lab.it
SHOPIFY_API_VERSION=2024-10
```

### Platform Configuration

File: `config/platforms.json`

```json
{
  "platforms": {
    "google": {
      "enabled": true,
      "feed_filename": "google_shopping_feed.xml"
    },
    "meta": {
      "enabled": true,
      "feed_filename": "meta_catalog_feed.xml"
    }
  },
  "settings": {
    "backup_previous_feed": true,
    "validate_before_save": true,
    "collect_metrics": true
  }
}
```

## 🚀 Esecuzione

### Locale (Test)

```bash
# Genera tutti i feed abilitati
python orchestrator.py

# Output:
# public/google_shopping_feed.xml
# public/meta_catalog_feed.xml
# public/feed_metrics.json
# feed_generation.log
```

### Produzione (Render Cron Job)

#### 1. Deploy su Render

```bash
# Render Dashboard
1. New → Blueprint
2. Connect: Racoon-GIT/Feed-Exporter
3. Review render.yaml → Create
4. Configura ENV vars nel dashboard
```

#### 2. Ottieni Deploy Hook

```bash
# Render Dashboard
feed-exporter → Settings → Deploy Hook
Copy URL: https://api.render.com/deploy/srv_xxxxx?key=yyyyy
```

#### 3. Configura Scheduler

```json
{
  "name": "Feed-Exporter Daily 6 AM",
  "url": "https://api.render.com/deploy/srv_xxxxx?key=yyyyy",
  "method": "POST",
  "schedule": "0 6 * * *",
  "timezone": "Europe/Rome",
  "enabled": true,
  "timeout": 60000,
  "retry_count": 2
}
```

#### 4. Test Manuale

**Da Cronmaster:**
```
1. Trova "feed-exporter" nella lista servizi
2. Click "Trigger" → POST al Deploy Hook
3. Controlla logs in Render Dashboard
```

**Da Scheduler:**
```
1. Trova job "Feed-Exporter Daily 6 AM"
2. Click "Run Now"
3. Attendi ~25-30 minuti
4. Verifica output in Render logs
```

## 📊 Output e Metriche

### Feed XML

```
public/
├── google_shopping_feed.xml        # Feed Google Shopping
├── google_shopping_feed.xml.backup # Backup feed precedente
├── meta_catalog_feed.xml           # Feed Meta Catalog
├── meta_catalog_feed.xml.backup    # Backup feed precedente
└── feed_metrics.json               # Metriche esecuzione
```

### Metriche (feed_metrics.json)

```json
{
  "google": {
    "platform": "google",
    "generated_at": "2026-02-02T06:25:34Z",
    "total_products": 1250,
    "total_items": 8432,
    "file_size_mb": 45.23,
    "duration_seconds": 1420,
    "feed_filename": "google_shopping_feed.xml",
    "success": true
  },
  "meta": {
    "platform": "meta",
    "generated_at": "2026-02-02T06:32:18Z",
    "total_products": 1250,
    "total_items": 8432,
    "file_size_mb": 42.67,
    "duration_seconds": 950,
    "feed_filename": "meta_catalog_feed.xml",
    "success": true
  }
}
```

### Logs

File: `feed_generation.log`

```
2026-02-02 06:00:15 - INFO - START: Feed Orchestrator at 2026-02-02T06:00:15Z
2026-02-02 06:00:15 - INFO - Enabled platforms: google, meta
2026-02-02 06:00:16 - INFO - GENERATING GOOGLE FEED
2026-02-02 06:00:16 - INFO - Processing products for google...
2026-02-02 06:05:42 - INFO - Page 1: 250 active products
...
2026-02-02 06:25:34 - INFO - ✅ GOOGLE feed generated successfully
2026-02-02 06:25:35 - INFO - GENERATING META FEED
...
2026-02-02 06:32:18 - INFO - ✅ META feed generated successfully
2026-02-02 06:32:18 - INFO - FEED ORCHESTRATOR COMPLETED
2026-02-02 06:32:18 - INFO - Total duration: 1923s (32.1min)
2026-02-02 06:32:18 - INFO - Success: 2/2 platforms
```

## 🔧 Troubleshooting

### Job non parte

**Problema:** Deploy Hook chiamato ma job non si avvia

**Soluzione:**
```bash
# Verifica schedule
1. Render Dashboard → feed-exporter → Settings
2. Controlla Schedule: deve essere "0 0 31 2 *" (dormiente)
3. Se diverso, cambia in "0 0 31 2 *" e salva
```

### Errore "Missing environment variables"

**Problema:** Job parte ma fallisce subito

**Soluzione:**
```bash
# Render Dashboard → feed-exporter → Environment
1. Verifica SHOPIFY_SHOP_URL è impostata
2. Verifica SHOPIFY_ACCESS_TOKEN è impostata
3. Test localmente con stesse ENV vars
```

### Feed XML vuoto o incompleto

**Problema:** Feed generato ma con pochi prodotti

**Soluzione:**
```bash
# Controlla logs per errori API Shopify
# Verifica token ha permessi: read_products, read_product_listings
# Controlla filtri in platforms/*/mapper.py
```

### Timeout durante generazione

**Problema:** Job termina prima di completare

**Soluzione:**
```bash
# Render Free tier: NO timeout su Cron Jobs
# Se fallisce comunque:
# 1. Verifica RAM usage nei logs
# 2. Ottimizza batch size in orchestrator.py
# 3. Dividi in 2 job separati (Google + Meta)
```

## 📁 Struttura Progetto

```
Feed-Exporter/
├── orchestrator.py              # Entry point principale
├── requirements.txt             # Dipendenze Python
├── render.yaml                  # Configurazione Render Cron
├── setup.py                     # Package setup
│
├── config/
│   ├── platforms.json           # Feature flags piattaforme
│   ├── product_type_mapping.json
│   └── product_mappings.json
│
├── src/
│   ├── shopify_client.py        # Client Shopify API
│   ├── config_loader.py         # Caricatore configurazioni
│   └── xml_generator.py         # Generatore XML Google
│
├── platforms/
│   ├── google/
│   │   ├── mapper.py            # Trasformazione Google
│   │   └── __init__.py
│   └── meta/
│       ├── mapper.py            # Trasformazione Meta
│       ├── xml_generator.py     # Generatore XML Meta
│       └── __init__.py
│
└── public/                      # Output feed (git-ignored)
    ├── google_shopping_feed.xml
    ├── meta_catalog_feed.xml
    └── feed_metrics.json
```

## 📜 Changelog

### v4.1.0 (2026-02-02) - Cron Job Dormiente

**BREAKING CHANGES:**
- ❌ Rimosso Flask web server
- ❌ Rimosso APScheduler (scheduling interno)
- ❌ Rimossi endpoint HTTP `/api/*`

**NEW:**
- ✅ Cron Job dormiente (schedule impossibile)
- ✅ Trigger via Deploy Hook (Scheduler/Cronmaster)
- ✅ render.yaml configurazione Blueprint
- ✅ README aggiornato con nuova architettura

**MIGRATION:**
- Da Web Service → Cron Job
- Costo: $7-21/mese → $0/mese
- Trigger: HTTP endpoint → Deploy Hook

### v4.0.0 (2025-01-28) - Multi-Platform

- Sistema multi-piattaforma (Google + Meta)
- GraphQL optimization
- Streaming XML generation

## 🆘 Supporto

**Repository:** https://github.com/Racoon-GIT/Feed-Exporter

**Issues:** https://github.com/Racoon-GIT/Feed-Exporter/issues

**Maintainer:** Racoon s.r.l.

## 📄 License

ISC License - Copyright © 2026 Racoon s.r.l.
