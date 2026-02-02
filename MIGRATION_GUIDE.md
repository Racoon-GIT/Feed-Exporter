# 🔄 GUIDA MIGRAZIONE: Web Service → Cron Job Dormiente

Questa guida documenta la migrazione di Feed-Exporter da **Web Service Render ($7-21/mese)** a **Cron Job Free ($0/mese)**.

---

## 📊 COSA CAMBIA

| Aspetto | Prima (Web Service) | Dopo (Cron Job) |
|---------|---------------------|-----------------|
| **Tipo servizio** | Web Service (always-on) | Cron Job (on-demand) |
| **Costo** | $7-21/mese | **$0/mese** ✅ |
| **Trigger** | HTTP POST /api/trigger | Deploy Hook POST |
| **Dashboard** | Flask UI (localhost:10000) | Scheduler UI |
| **Schedule** | APScheduler interno | Scheduler esterno |
| **Uptime** | 24/7 | Solo durante esecuzione (~25 min/giorno) |
| **Consumo ore** | ~730 ore/mese | ~12.5 ore/mese |

---

## 🗑️ COSA VIENE RIMOSSO

### File/Dipendenze Non Più Necessarie

- ❌ `app_multiplatform.py` (Flask server) → **Mantieni per backup, ma non usato**
- ❌ `flask==3.0.0` (requirements.txt) → **Rimosso**
- ❌ `gunicorn==21.2.0` (requirements.txt) → **Rimosso**
- ❌ `APScheduler==3.10.4` (requirements.txt) → **Rimosso**

### Endpoint HTTP Deprecati

- ❌ `GET /` (homepage dashboard)
- ❌ `GET /feed/google` (serve feed XML)
- ❌ `GET /feed/meta` (serve feed XML)
- ❌ `GET /api/health` (health check)
- ❌ `POST /api/trigger` (trigger manuale)

**Nuovo trigger:** Deploy Hook URL da Render

---

## ✅ COSA VIENE AGGIUNTO

### Nuovi File

1. **render.yaml** ✨ (NUOVO)
   - Configurazione Blueprint Render
   - Cron Job con schedule impossibile (31 feb)
   - ENV vars template

2. **README.md** ✨ (NUOVO)
   - Documentazione completa architettura Cron
   - Istruzioni deploy e configurazione
   - Troubleshooting

3. **.env.example** ✨ (NUOVO)
   - Template environment variables
   - Note deployment

4. **MIGRATION_GUIDE.md** ✨ (questo file)

### File Modificati

1. **requirements.txt** (UPDATED)
   - Rimossi: flask, gunicorn, APScheduler
   - Mantenuti: requests, -e .

2. **orchestrator.py** (UNCHANGED)
   - Entry point già perfetto per Cron Job
   - Nessuna modifica necessaria

---

## 🚀 PROCEDURA MIGRAZIONE (Step-by-Step)

### FASE 1: Backup e Preparazione (5 minuti)

#### 1.1 Salva Configurazione Attuale

```bash
# Render Dashboard → racoon-lab-feed-server → Environment
# Copia tutte le ENV vars in un file locale:
```

**ENV vars da salvare:**
```bash
SHOPIFY_SHOP_URL=racoon-lab.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_xxxxxxxxxxxxxxxxxxxxxxxx
SHOP_BASE_URL=https://racoon-lab.it
SHOPIFY_API_VERSION=2024-10
```

#### 1.2 Test Locale con Nuova Configurazione

```bash
cd Feed-Exporter

# Installa dipendenze aggiornate
pip install -r requirements.txt

# Testa esecuzione locale
export SHOPIFY_SHOP_URL=racoon-lab.myshopify.com
export SHOPIFY_ACCESS_TOKEN=shpat_xxx
python orchestrator.py

# Verifica output:
ls -lh public/
# Dovresti vedere:
# - google_shopping_feed.xml
# - meta_catalog_feed.xml
# - feed_metrics.json
```

✅ **Checkpoint:** Se test locale OK, procedi. Altrimenti debug prima di continuare.

---

### FASE 2: Deploy Cron Job su Render (10 minuti)

#### 2.1 Commit e Push Modifiche

```bash
cd Feed-Exporter

git add .
git commit -m "feat: migrazione Web Service → Cron Job dormiente

- Aggiunti: render.yaml, README.md, .env.example, MIGRATION_GUIDE.md
- Modificati: requirements.txt (rimossi flask, gunicorn, APScheduler)
- Costo: $7-21/mese → $0/mese
- Trigger: Deploy Hook da Scheduler"

git push origin main
```

#### 2.2 Crea Cron Job su Render

**Opzione A: Via Blueprint (CONSIGLIATO)**

```bash
# Render Dashboard
1. Click "New +" → "Blueprint"
2. Connect Repository: Racoon-GIT/Feed-Exporter
3. Branch: main
4. Render legge render.yaml automaticamente
5. Review configurazione:
   ✓ Name: feed-exporter
   ✓ Type: cron
   ✓ Schedule: 0 0 31 2 * (dormiente)
   ✓ Plan: free
6. Click "Apply"
7. Attendi build (~2-3 minuti)
```

**Opzione B: Manuale**

```bash
# Render Dashboard
1. New + → Cron Job
2. Configurazione:
   - Name: feed-exporter
   - Repository: Racoon-GIT/Feed-Exporter
   - Branch: main
   - Runtime: Python 3
   - Build Command: pip install -r requirements.txt
   - Start Command: python orchestrator.py
   - Schedule: 0 0 31 2 *  ⭐ IMPORTANTE!
   - Region: Frankfurt
   - Plan: Free
3. Create Cron Job
```

#### 2.3 Configura Environment Variables

```bash
# Render Dashboard → feed-exporter → Environment
1. Add Environment Variable (per ciascuna):

   Key: SHOPIFY_SHOP_URL
   Value: racoon-lab.myshopify.com

   Key: SHOPIFY_ACCESS_TOKEN
   Value: shpat_xxxxxxxxxxxxxxxxxxxxxxxx

   Key: SHOP_BASE_URL
   Value: https://racoon-lab.it

   Key: SHOPIFY_API_VERSION
   Value: 2024-10

2. Save Changes
3. Servizio farà re-deploy automaticamente
```

#### 2.4 Ottieni Deploy Hook

```bash
# Render Dashboard → feed-exporter → Settings
1. Scroll to "Deploy Hook"
2. Click "Create Deploy Hook" (se non esiste già)
3. Copy URL: https://api.render.com/deploy/srv_xxxxx?key=yyyyy
4. Salva in un file temporaneo (serve per Fase 3)
```

**Esempio Deploy Hook:**
```
https://api.render.com/deploy/srv_cq1abc2def3g4h5i6j7k?key=A1B2C3D4E5F6G7H8I9J0
```

✅ **Checkpoint:** Cron Job creato, ENV configurate, Deploy Hook copiato.

---

### FASE 3: Configurare Scheduler (5 minuti)

#### 3.1 Crea Job in Scheduler App

```bash
# Vai su: https://<your-scheduler-url>.vercel.app
# Oppure: localhost:3000 se sviluppo

1. Click "New Job"
2. Compila form:
```

**Configurazione Job:**
```json
{
  "name": "Feed-Exporter Daily 6 AM",
  "description": "Genera feed Google Shopping e Meta Catalog",
  "type": "webhook",

  "url": "https://api.render.com/deploy/srv_xxxxx?key=yyyyy",
  "method": "POST",

  "schedule": "0 6 * * *",
  "timezone": "Europe/Rome",

  "enabled": true,

  "timeout": 60000,
  "retry_count": 2,
  "retry_delay": 30000,

  "notifications": {
    "on_success": false,
    "on_failure": true,
    "email": "your-email@example.com"  // Opzionale
  }
}
```

```bash
3. Save Job
4. Verifica job appare nella dashboard
```

#### 3.2 Test Trigger Manuale

```bash
# Da Scheduler UI
1. Trova job "Feed-Exporter Daily 6 AM"
2. Click "Run Now" / "▶ Trigger"
3. Attendi conferma "Job triggered successfully"
```

**Verifica esecuzione:**
```bash
# Render Dashboard → feed-exporter → Logs
# Dovresti vedere:
# - "🚀 Feed-Exporter Started at ..."
# - "Processing products for google..."
# - "✅ GOOGLE feed generated successfully"
# - "✅ META feed generated successfully"
# - "🎉 All feeds generated successfully!"

# Durata attesa: ~25-30 minuti
```

✅ **Checkpoint:** Job eseguito con successo, feed generati.

---

### FASE 4: Elimina Vecchio Web Service (2 minuti)

⚠️ **ATTENZIONE:** Esegui SOLO dopo aver verificato che Cron Job funziona correttamente.

```bash
# Render Dashboard
1. Trova "racoon-lab-feed-server" (vecchio Web Service)
2. Settings → Delete Service
3. Conferma eliminazione
```

**Cosa succede:**
- ✅ Service fermato immediatamente
- ✅ Billing interrotto (risparmi $7-21/mese da subito)
- ✅ Deployment history mantenuto per 90 giorni
- ❌ Service NON recuperabile (ma repository intatto)

✅ **Checkpoint:** Vecchio servizio eliminato, risparmio attivato.

---

### FASE 5: Configurare Cronmaster (Opzionale, 5 minuti)

Se vuoi trigger manuale anche da Cronmaster:

#### 5.1 Aggiungi Servizio a Cronmaster

```typescript
// In Cronmaster app - servizi configurati

const renderServices = [
  // ... altri servizi ...

  {
    id: 'srv_xxxxx',  // ID dal Deploy Hook
    name: 'feed-exporter',
    type: 'cron',
    status: 'dormiente',
    deploy_hook: 'https://api.render.com/deploy/srv_xxxxx?key=yyyyy',
    description: 'Generazione feed Google Shopping e Meta',
    last_run: null,  // Popolato dopo primo trigger
  }
];
```

#### 5.2 Test Trigger da Cronmaster

```bash
# Cronmaster UI
1. Trova "feed-exporter" nella lista servizi
2. Status: "Dormiente" (badge giallo)
3. Click "Wake Up" / "Trigger"
4. Popup conferma: "Feed generation started"
5. Controlla Render logs per verifica
```

---

## 📊 VERIFICA POST-MIGRAZIONE

### Checklist Finale

- [ ] Cron Job `feed-exporter` creato su Render
- [ ] ENV vars configurate correttamente
- [ ] Deploy Hook ottenuto e salvato
- [ ] Job Scheduler configurato e testato
- [ ] Test manuale trigger eseguito con successo
- [ ] Feed XML generati correttamente (verifica file size)
- [ ] Vecchio Web Service eliminato
- [ ] Cronmaster configurato (opzionale)
- [ ] Billing Render aggiornato ($0/mese per feed-exporter)

### Test Automatico Daily

```bash
# Attendi domani mattina alle 6:00 AM (Europe/Rome)
# Verifica automaticamente:
1. Scheduler triggera Deploy Hook alle 6:00
2. Render avvia Cron Job
3. Feed generati (~25-30 min)
4. Logs puliti senza errori
5. Metriche salvate in feed_metrics.json
```

---

## 🐛 Troubleshooting

### Problema: Job non parte quando triggerato

**Causa:** Schedule errato (non dormiente)

**Soluzione:**
```bash
# Render Dashboard → feed-exporter → Settings
# Verifica Schedule: DEVE essere "0 0 31 2 *"
# Se diverso, modifica e salva
```

### Problema: Job parte ma fallisce subito

**Causa:** ENV vars mancanti o errate

**Soluzione:**
```bash
# Render Dashboard → feed-exporter → Environment
# Verifica TUTTE le ENV vars siano presenti
# Test locale con stesse ENV:
export SHOPIFY_SHOP_URL=...
export SHOPIFY_ACCESS_TOKEN=...
python orchestrator.py
```

### Problema: Scheduler non triggera il job

**Causa:** Deploy Hook URL errato

**Soluzione:**
```bash
# Verifica Deploy Hook:
curl -X POST "https://api.render.com/deploy/srv_xxxxx?key=yyyyy"
# Risposta attesa: {"ok": true}

# Aggiorna URL in Scheduler se errato
```

### Problema: Feed generati ma vuoti/incompleti

**Causa:** Permessi Shopify token insufficienti

**Soluzione:**
```bash
# Shopify Admin → Apps → Custom Apps → feed-exporter
# Verifica permessi:
# ✓ read_products
# ✓ read_product_listings
# Re-genera token se necessario
```

---

## 💰 RISPARMIO REALIZZATO

```
PRIMA (Web Service Starter):
- Costo fisso: $7/mese
- Uptime: 24/7 (730 ore/mese)
- Utilizzo effettivo: ~25 min/giorno = 12.5 ore/mese
- Spreco: 717.5 ore/mese (98.3% inutilizzato)

DOPO (Cron Job Free):
- Costo: $0/mese ✅
- Uptime: on-demand (solo quando esegue)
- Utilizzo: 12.5 ore/mese (su 750 free)
- Spreco: 0 ore

RISPARMIO ANNUALE: $84/anno
ROI migrazione: ♾️ (costo setup $0, benefit $84/anno perpetuo)
```

---

## 📞 Supporto

**Problemi durante migrazione?**
- GitHub Issues: https://github.com/Racoon-GIT/Feed-Exporter/issues
- Email: support@racoon-lab.it

**Rollback necessario?**
- Vecchio Web Service eliminato = NON recuperabile
- Ma puoi ri-creare in <10 minuti:
  1. Checkout branch `legacy-web-service` (se esiste)
  2. Deploy come Web Service su Render
  3. Configura ENV vars
  4. Done

---

## ✅ MIGRAZIONE COMPLETATA

Se sei arrivato qui, congratulazioni! 🎉

Hai migrato con successo Feed-Exporter a un'architettura **serverless, cost-free, e 100% automatizzata**.

**Prossimi passi:**
- Monitora esecuzioni daily per 1 settimana
- Verifica metriche in feed_metrics.json
- Considera estendere pattern ad altri servizi simili

**Happy feeding! 🚀**
