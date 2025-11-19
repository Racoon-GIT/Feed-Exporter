# Racoon Lab Feed Manager - Multi-Platform Architecture v4.0

Sistema unificato per la generazione di feed prodotti per Google Shopping e Meta (Facebook & Instagram).

## 🏗️ Architettura Modulare

```
project/
├── core/                           # Componenti condivisi
│   ├── base_mapper.py              # Classe base per tutti i mapper
│   └── __init__.py
│
├── platforms/                      # Implementazioni platform-specific
│   ├── google/
│   │   ├── mapper.py               # GoogleMapper (refactoring transformer esistente)
│   │   └── __init__.py
│   │
│   └── meta/
│       ├── mapper.py               # MetaMapper (nuovo)
│       ├── xml_generator.py        # Meta XML generator con internal_label multipli
│       └── __init__.py
│
├── config/                         # File di configurazione JSON
│   ├── platforms.json              # Feature flags per abilitare/disabilitare feed
│   ├── product_type_mapping.json  # Mapping modelli → categorie (Sneakers, Stivali, etc)
│   └── product_mappings.json      # Highlight e dettagli prodotti (esistente)
│
├── src/                            # Componenti core esistenti
│   ├── shopify_client.py           # Client Shopify con rate limiting
│   ├── config_loader.py            # Loader configurazioni
│   ├── xml_generator.py            # Google XML generator (esistente)
│   └── __init__.py
│
├── public/                         # Output feeds (serviti da web server)
│   ├── google_shopping_feed.xml
│   ├── meta_catalog_feed.xml
│   ├── feed_metrics.json
│   └── *.backup                    # Backup automatici
│
├── orchestrator.py                 # Genera tutti i feed abilitati
├── app_multiplatform.py            # Web server multi-platform
├── main.py                         # Compatibilità backward (solo Google)
├── app.py                          # Compatibilità backward (solo Google)
├── requirements.txt
└── render.yaml
```

## 🚀 Quick Start

### Generazione Feed (Tutti)
```bash
python orchestrator.py
```

### Generazione Solo Google (Backward Compatibility)
```bash
python main.py
```

### Web Server Multi-Platform
```bash
python app_multiplatform.py
```

Poi visita: `http://localhost:10000`

## ⚙️ Configurazione

### 1. Feature Flags (`config/platforms.json`)

Abilita/disabilita feed per piattaforma:

```json
{
  "platforms": {
    "google": {
      "enabled": true,
      "feed_filename": "google_shopping_feed.xml",
      "title": "Racoon Lab - Google Shopping Feed"
    },
    "meta": {
      "enabled": true,
      "feed_filename": "meta_catalog_feed.xml",
      "title": "Racoon Lab - Meta Catalog Feed"
    }
  },
  "settings": {
    "backup_previous_feed": true,
    "validate_before_save": true,
    "collect_metrics": true
  }
}
```

**Per disabilitare un feed**, imposta `"enabled": false`.

### 2. Mapping Modelli → Categorie (`config/product_type_mapping.json`)

**⚠️ IMPORTANTE: Qui modifichi le associazioni modello → macro categoria**

```json
{
  "mappings": {
    "Stan Smith": "Sneakers",
    "Superstar": "Sneakers",
    "Campus": "Sneakers",
    "Timberland": "Stivali",
    "Birkenstock": "Sandali",
    "Boston": "Ciabatte"
  },
  "default": "Sneakers"
}
```

**Come modificare**:
1. Apri `config/product_type_mapping.json`
2. Aggiungi/modifica le voci nel dizionario `"mappings"`
3. Salva il file
4. Rigenera i feed

**Esempio**: Per aggiungere un nuovo modello:
```json
"Air Max": "Sneakers",
"Vans Old Skool": "Sneakers",
"UGG": "Stivali"
```

## 📋 Mapping Campi Meta

Il mapper Meta segue ESATTAMENTE le specifiche dall'Excel:

| Campo Meta | Fonte | Note |
|------------|-------|------|
| `id` | variant.id | Stesso di Google |
| `title` | Formula ottimizzata | Brand + Modello + Genere + Taglia (max 65 char) |
| `description` | body_html | HTML rimosso |
| `link` | product URL | Stesso di Google |
| `image_link` | Principale | _INT per Converse, altrimenti prima |
| `additional_image_link` | Tutte le altre | Ordine naturale, max 19 |
| `price` | variant.price | Formato "X.XX EUR" |
| `sale_price` | compare_at_price | Se presente |
| `brand` | vendor | Stesso di Google |
| `condition` | Sempre "new" | Statico |
| `google_product_category` | 187 | Footwear |
| `product_type` | Gerarchico | **"Sneakers > Adidas > Stan Smith"** |
| `gender` | metafields | Con fallback |
| `age_group` | metafields | Con fallback |
| `color` | metafields | Se presente |
| `size` | option1 | Taglia |
| `size_system` | Sempre "EU" | Statico |
| `material` | metafields | Se presente |
| `pattern` | tags | Via mapping DFW |
| `item_group_id` | product.id | Raggruppamento varianti |
| `gtin` | barcode | Se presente |
| `mpn` | sku | Identificatore |
| `shipping` | Calcolato | Gratis >89€, 10€ 30-89€, 6€ <30€ |
| `status` | Sempre "active" | Statico |
| `inventory` | Sempre "1" | Statico |
| `internal_label` | **Tag multipli XML** | Uno per ogni tag + collection |
| `custom_label_*` | Vuoti | Per ora saltati |

### Internal Label (Speciale)

Il campo `internal_label` è **unico** perché genera **tag XML multipli**:

```xml
<g:internal_label>nike</g:internal_label>
<g:internal_label>sneakers</g:internal_label>
<g:internal_label>donna</g:internal_label>
<g:internal_label>Summer Collection</g:internal_label>
<g:internal_label>Best Sellers</g:internal_label>
```

Questo permette a Meta di filtrare per tag e collection in modo granulare.

## 🔧 Modifiche e Manutenzione

### Dove Modificare i Campi di Output

Ogni campo è chiaramente documentato nel codice con commenti "MAPPING AREA X":

#### Google Mapper (`platforms/google/mapper.py`)
```python
# ========== CORE FIELDS (MAPPING AREA 1) ==========
item['g:id'] = str(variant['id'])
item['g:title'] = self._build_title_google(product, variant)
# ... etc

# ========== IMAGES (MAPPING AREA 2) ==========
# Logica immagini Converse

# ========== CUSTOM LABELS (MAPPING AREA 10) ==========
# Logica collections
```

#### Meta Mapper (`platforms/meta/mapper.py`)
```python
# ========== REQUIRED FIELDS ==========
# ID (Excel: "replica quanto già fatto per il feed google")
item['g:id'] = str(variant['id'])

# TITLE (Excel: "Titolo leggibile e descrittivo...")
item['g:title'] = self._build_title_meta(...)
```

### Aggiungere un Nuovo Campo

**Esempio**: Aggiungere `sale_price_effective_date` a Meta:

1. Apri `platforms/meta/mapper.py`
2. Aggiungi nel metodo `_transform_variant_meta`:
```python
# SALE_PRICE_EFFECTIVE_DATE
if get_field('sale_price'):
    # Calcola data fine saldi
    end_date = datetime.now() + timedelta(days=30)
    item['g:sale_price_effective_date'] = f"{datetime.now().isoformat()}/{end_date.isoformat()}"
```
3. Rigenera feed

### Modificare la Logica di un Campo Esistente

**Esempio**: Cambiare formula title Meta:

1. Apri `platforms/meta/mapper.py`
2. Trova `_build_title_meta()`
3. Modifica la logica:
```python
def _build_title_meta(self, product, variant, tags, metafield_data):
    # Nuova formula: Solo Brand + Modello
    parts = [
        product.get('vendor', ''),
        product.get('product_type', '')
    ]
    
    title = ' '.join(parts)
    
    if len(title) > 65:
        title = title[:62] + '...'
    
    return title
```

## 📊 Monitoring e Metriche

### Health Check Endpoint
```bash
curl http://localhost:10000/api/health
```

Risposta:
```json
{
  "status": "healthy",
  "timestamp": "2024-11-19T18:00:00Z",
  "google": {
    "exists": true,
    "file_size_mb": 24.5,
    "generated_at": "2024-11-19T06:00:00Z",
    "products": 1042,
    "items": 9500
  },
  "meta": {
    "exists": true,
    "file_size_mb": 26.1,
    "generated_at": "2024-11-19T06:00:00Z",
    "products": 1042,
    "items": 9500
  }
}
```

### Metriche Dettagliate (`public/feed_metrics.json`)
```json
{
  "google": {
    "platform": "google",
    "generated_at": "2024-11-19T06:00:00Z",
    "total_products": 1042,
    "total_items": 9500,
    "file_size_mb": 24.5,
    "duration_seconds": 720,
    "success": true
  },
  "meta": {
    "platform": "meta",
    "generated_at": "2024-11-19T06:00:00Z",
    "total_products": 1042,
    "total_items": 9500,
    "file_size_mb": 26.1,
    "duration_seconds": 680,
    "success": true
  }
}
```

## 🔄 Aggiungere una Nuova Piattaforma

Per aggiungere una terza piattaforma (es: Amazon):

1. **Crea mapper**: `platforms/amazon/mapper.py`
```python
from core.base_mapper import BaseMapper

class AmazonMapper(BaseMapper):
    def get_platform_name(self):
        return 'amazon'
    
    def transform_product(self, product, metafields, collections):
        # Logica specifica Amazon
        pass
```

2. **Crea XML generator**: `platforms/amazon/xml_generator.py`

3. **Aggiungi a configurazione**: `config/platforms.json`
```json
{
  "platforms": {
    "amazon": {
      "enabled": true,
      "feed_filename": "amazon_feed.xml",
      "title": "Racoon Lab - Amazon Feed"
    }
  }
}
```

4. **Aggiorna orchestrator**: `orchestrator.py`
```python
def _get_mapper(self, platform_name: str):
    if platform_name == 'amazon':
        from platforms.amazon.mapper import AmazonMapper
        return AmazonMapper(self.config, self.base_url)
```

## 🚢 Deploy su Render.com

### Opzione A: Usa Orchestrator (Raccomandato)

Modifica `render.yaml`:
```yaml
services:
  - type: cron
    name: racoon-lab-feed-generator
    schedule: "0 6 * * *"
    startCommand: "python orchestrator.py"  # ← Cambia qui
```

### Opzione B: Solo Google (Backward Compatible)

Mantieni il setup esistente con `python main.py`.

## 📝 Environment Variables

Necessarie per Render.com:

```env
SHOPIFY_SHOP_URL=racoon-lab.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_xxxxxxxxxxxxx
SHOP_BASE_URL=https://racoon-lab.it
```

## ✅ Vantaggi della Nuova Architettura

1. **Zero Regressioni**: Il feed Google funziona esattamente come prima
2. **Manutenibilità**: Ogni campo ha la sua "area" documentata
3. **Estensibilità**: Aggiungere piattaforme è semplice
4. **Feature Flags**: Abilita/disabilita feed senza modificare codice
5. **Metrics**: Monitoraggio granulare per piattaforma
6. **Backup Automatici**: Salva feed precedente prima di rigenerare
7. **Configurazione Esterna**: Modifica mapping senza toccare codice

## 🐛 Troubleshooting

### Feed Meta vuoto
- Verifica che `platforms.json` abbia `"meta": {"enabled": true}`
- Controlla i log: `tail -f feed_generation.log`

### Categorie sbagliate nel product_type
- Apri `config/product_type_mapping.json`
- Aggiungi/modifica i mapping
- Rigenera feed

### Internal_label non viene generato
- Verifica che MetaXMLGenerator generi tag multipli
- Controlla il campo in `platforms/meta/mapper.py`

## 📞 Supporto

Per domande o problemi:
- Controlla i log: `feed_generation.log`
- Verifica metriche: `/api/health`
- Controlla configurazione: `config/*.json`

---

**Racoon Lab Feed Manager v4.0**  
Architettura Multi-Platform con supporto Google Shopping e Meta Catalog
