# Feed-Exporter Refactoring Guide
## Migration from Shopify API to MySQL Data Source

**Document Version:** 1.0
**Date:** 2026-02-02
**Author:** IT Infrastructure Analysis
**Target Audience:** Feed-Exporter Developer

---

## Executive Summary

This guide provides step-by-step instructions to refactor Feed-Exporter from fetching data directly via Shopify API to reading from the existing MySQL `online_products` table populated by `shopify-mysql-sync`.

### Current State Problems

1. **API Call Duplication**: Feed-Exporter makes ~1,500 API calls per generation while shopify-mysql-sync makes ~30 calls for the same data
2. **N+1 Query Pattern**: REST API calls made individually per product (inefficient)
3. **Rate Limiting Risk**: High volume of API calls risks hitting Shopify limits (40 calls/sec)
4. **Slow Generation**: 20-30 minutes per feed generation
5. **Daily API Waste**: ~4,500+ redundant Shopify API calls per day

### Target State Benefits

1. **0 Shopify API calls** for feed generation (reads from MySQL)
2. **2-5 minute** feed generation time (vs 20-30 minutes)
3. **No rate limiting issues**
4. **98% reduction** in Shopify API usage
5. **Decoupled architecture** (data sync independent from feed generation)

---

## Architecture Overview

### Current Architecture (Inefficient)

```
Feed-Exporter
    ↓
    ↓ [1,500+ API calls per run]
    ↓ REST API (N+1 pattern)
    ↓ - get_all_products() → 2 calls
    ↓ - get_product_metafields() → 500 calls
    ↓ - get_product_collections() → 1,000 calls
    ↓
Shopify API
    ↓
Google Shopping Feed + Meta Feed
```

**Problems:**
- Direct Shopify dependency
- Slow (20-30 min)
- Rate limit risk
- Duplicate calls with shopify-mysql-sync

---

### Target Architecture (Efficient)

```
shopify-mysql-sync (runs every 30-60 min)
    ↓
    ↓ [30-60 GraphQL API calls per run]
    ↓
MySQL online_products table
    ↓
    ↓ [SQL query - 0 API calls]
    ↓
Feed-Exporter
    ↓
    ↓ [2-5 minutes generation]
    ↓
Google Shopping Feed + Meta Feed
```

**Benefits:**
- Zero Shopify API calls
- Fast (2-5 min)
- No rate limits
- Fresh data (MySQL synced every 30-60 min)

---

## MySQL Database Schema

### Table: `online_products`

**Location:** Database configured in `shopify-mysql-sync`
**Schema Definition:** `/Users/alesap/DATI/Racoon-LAB/IT/SVILUPPO/shopify-mysql-sync/src/db.py` (lines 21-67)

```sql
CREATE TABLE IF NOT EXISTS online_products (
    -- Variant identifiers
    Variant_id        BIGINT PRIMARY KEY,
    Variant_Title     TEXT,
    SKU               VARCHAR(255),
    Barcode           VARCHAR(255),

    -- Product identifiers
    Product_id        BIGINT,
    Product_title     TEXT,
    Product_handle    VARCHAR(255),
    Vendor            VARCHAR(255),
    Product_Type      VARCHAR(255) DEFAULT NULL,

    -- Pricing
    Price             DECIMAL(10,2),
    Compare_AT_Price  DECIMAL(10,2),

    -- Inventory
    Inventory_Item_ID BIGINT,
    Stock_Magazzino   INT DEFAULT NULL,

    -- Categorization
    Tags              TEXT,              -- Comma-separated
    Collections       TEXT,              -- Comma-separated

    -- Content
    Body_HTML         LONGTEXT DEFAULT NULL,
    Product_Images    JSON DEFAULT NULL,  -- Array of image objects

    -- Product-level Metafields
    MF_Customization_Description TEXT DEFAULT NULL,
    MF_Shoe_Details              TEXT DEFAULT NULL,
    MF_Customization_Details     TEXT DEFAULT NULL,
    MF_O_Description             TEXT DEFAULT NULL,
    MF_Handling                  INT DEFAULT NULL,
    MF_Google_Custom_Product     BOOLEAN DEFAULT NULL,

    -- Variant-level Google Shopping Metafields
    MF_Google_Age_Group      VARCHAR(100) DEFAULT NULL,
    MF_Google_Condition      VARCHAR(100) DEFAULT NULL,
    MF_Google_Gender         VARCHAR(100) DEFAULT NULL,
    MF_Google_MPN            VARCHAR(255) DEFAULT NULL,
    MF_Google_Custom_Label_0 VARCHAR(255) DEFAULT NULL,
    MF_Google_Custom_Label_1 VARCHAR(255) DEFAULT NULL,
    MF_Google_Custom_Label_2 VARCHAR(255) DEFAULT NULL,
    MF_Google_Custom_Label_3 VARCHAR(255) DEFAULT NULL,
    MF_Google_Custom_Label_4 VARCHAR(255) DEFAULT NULL,
    MF_Google_Size_System    VARCHAR(100) DEFAULT NULL,
    MF_Google_Size_Type      VARCHAR(100) DEFAULT NULL,
    MF_Google_Color          VARCHAR(255) DEFAULT NULL,
    MF_Google_Size           VARCHAR(100) DEFAULT NULL,
    MF_Google_Material       VARCHAR(255) DEFAULT NULL,
    MF_Google_Product_Category VARCHAR(500) DEFAULT NULL
)
```

---

## Data Field Mapping

### Feed Requirements vs MySQL Coverage

| Feed Requirement | Current Source | MySQL Field | Status |
|-----------------|----------------|-------------|--------|
| **Product ID** | Shopify API | `Product_id` | ✅ Available |
| **Product Title** | Shopify API | `Product_title` | ✅ Available |
| **Product Handle** | Shopify API | `Product_handle` | ✅ Available |
| **Vendor/Brand** | Shopify API | `Vendor` | ✅ Available |
| **Product Type** | Shopify API | `Product_Type` | ✅ Available |
| **Description** | `body_html` | `Body_HTML` | ✅ Available |
| **Tags** | Shopify API | `Tags` (comma-separated) | ✅ Available |
| **Collections** | API (N calls) | `Collections` (comma-separated) | ✅ Available |
| **Images** | Shopify API | `Product_Images` (JSON array) | ✅ Available |
| **Variant ID** | Shopify API | `Variant_id` | ✅ Available |
| **Variant Title** | Shopify API | `Variant_Title` | ✅ Available |
| **SKU** | Shopify API | `SKU` | ✅ Available |
| **Barcode/GTIN** | Shopify API | `Barcode` | ✅ Available |
| **Price** | Shopify API | `Price` | ✅ Available |
| **Compare Price** | Shopify API | `Compare_AT_Price` | ✅ Available |
| **Stock/Availability** | Shopify API | `Stock_Magazzino` | ✅ Available |
| **Google: Gender** | Metafield API | `MF_Google_Gender` | ✅ Available |
| **Google: Age Group** | Metafield API | `MF_Google_Age_Group` | ✅ Available |
| **Google: Condition** | Metafield API | `MF_Google_Condition` | ✅ Available |
| **Google: Color** | Metafield API | `MF_Google_Color` | ✅ Available |
| **Google: Size** | Metafield API | `MF_Google_Size` | ✅ Available |
| **Google: Material** | Metafield API | `MF_Google_Material` | ✅ Available |
| **Google: MPN** | Metafield API | `MF_Google_MPN` | ✅ Available |
| **Google: Category** | Metafield API | `MF_Google_Product_Category` | ✅ Available |
| **Google: Custom Labels** | Metafield API | `MF_Google_Custom_Label_0-4` | ✅ Available |
| **Google: Size System** | Metafield API | `MF_Google_Size_System` | ✅ Available |
| **Google: Size Type** | Metafield API | `MF_Google_Size_Type` | ✅ Available |
| **Custom Fields** | Metafield API | `MF_Customization_*`, `MF_Shoe_*` | ✅ Available |

**Result: 100% field coverage** ✅

---

## Refactoring Steps

### Step 1: Create MySQL Data Loader Module

**File to create:** `src/mysql_client.py`

```python
"""
MySQL Data Loader for Feed Generation
Replaces Shopify API calls with MySQL queries
"""

import mysql.connector
import json
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class MySQLDataLoader:
    """
    Load product data from MySQL online_products table
    Provides same interface as ShopifyClient for minimal code changes
    """

    def __init__(self, config: Dict):
        """
        Initialize MySQL connection

        Args:
            config: Dict with keys 'host', 'user', 'password', 'database'
        """
        self.config = config
        self.connection = None
        self.cursor = None

    def connect(self):
        """Establish MySQL connection"""
        try:
            self.connection = mysql.connector.connect(
                host=self.config['host'],
                user=self.config['user'],
                password=self.config['password'],
                database=self.config['database'],
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci'
            )
            self.cursor = self.connection.cursor(dictionary=True)
            logger.info(f"✅ Connected to MySQL: {self.config['database']}")
        except Exception as e:
            logger.error(f"❌ MySQL connection failed: {e}")
            raise

    def disconnect(self):
        """Close MySQL connection"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("MySQL connection closed")

    def get_all_products(self) -> List[Dict]:
        """
        Fetch all products with stock > 0

        Returns:
            List of product dictionaries (one per variant)
            Each dict contains all fields from online_products table
        """
        query = """
            SELECT
                Variant_id, Variant_Title, SKU, Barcode,
                Product_id, Product_title, Product_handle,
                Vendor, Product_Type,
                Price, Compare_AT_Price,
                Inventory_Item_ID, Stock_Magazzino,
                Tags, Collections,
                Body_HTML,
                Product_Images,
                MF_Customization_Description, MF_Shoe_Details,
                MF_Customization_Details, MF_O_Description,
                MF_Handling, MF_Google_Custom_Product,
                MF_Google_Age_Group, MF_Google_Condition, MF_Google_Gender,
                MF_Google_MPN,
                MF_Google_Custom_Label_0, MF_Google_Custom_Label_1,
                MF_Google_Custom_Label_2, MF_Google_Custom_Label_3,
                MF_Google_Custom_Label_4,
                MF_Google_Size_System, MF_Google_Size_Type,
                MF_Google_Color, MF_Google_Size,
                MF_Google_Material, MF_Google_Product_Category
            FROM online_products
            WHERE Stock_Magazzino > 0
            ORDER BY Product_id, Variant_id
        """

        try:
            self.cursor.execute(query)
            results = self.cursor.fetchall()

            logger.info(f"📊 Loaded {len(results)} variants from MySQL")

            # Transform to match Shopify API format
            products = self._transform_to_shopify_format(results)

            return products

        except Exception as e:
            logger.error(f"❌ MySQL query failed: {e}")
            raise

    def _transform_to_shopify_format(self, rows: List[Dict]) -> List[Dict]:
        """
        Transform MySQL rows to match Shopify API product structure
        Groups variants by product_id

        Args:
            rows: Raw MySQL rows

        Returns:
            List of products with nested variants (Shopify-like structure)
        """
        products_map = {}

        for row in rows:
            product_id = row['Product_id']

            # Create product entry if not exists
            if product_id not in products_map:
                products_map[product_id] = {
                    'id': product_id,
                    'title': row['Product_title'],
                    'handle': row['Product_handle'],
                    'vendor': row['Vendor'],
                    'product_type': row['Product_Type'],
                    'tags': row['Tags'].split(',') if row['Tags'] else [],
                    'body_html': row['Body_HTML'],
                    'images': json.loads(row['Product_Images']) if row['Product_Images'] else [],
                    'variants': [],
                    'collections': row['Collections'].split(',') if row['Collections'] else [],
                    # Product-level metafields
                    'metafields': {
                        'customization_description': row['MF_Customization_Description'],
                        'shoe_details': row['MF_Shoe_Details'],
                        'customization_details': row['MF_Customization_Details'],
                        'o_description': row['MF_O_Description'],
                        'handling': row['MF_Handling'],
                        'google_custom_product': row['MF_Google_Custom_Product']
                    }
                }

            # Add variant
            variant = {
                'id': row['Variant_id'],
                'title': row['Variant_Title'],
                'sku': row['SKU'],
                'barcode': row['Barcode'],
                'price': float(row['Price']) if row['Price'] else 0.0,
                'compare_at_price': float(row['Compare_AT_Price']) if row['Compare_AT_Price'] else None,
                'inventory_item_id': row['Inventory_Item_ID'],
                'inventory_quantity': row['Stock_Magazzino'],
                # Variant-level Google Shopping metafields
                'metafields': {
                    'age_group': row['MF_Google_Age_Group'],
                    'condition': row['MF_Google_Condition'],
                    'gender': row['MF_Google_Gender'],
                    'mpn': row['MF_Google_MPN'],
                    'custom_label_0': row['MF_Google_Custom_Label_0'],
                    'custom_label_1': row['MF_Google_Custom_Label_1'],
                    'custom_label_2': row['MF_Google_Custom_Label_2'],
                    'custom_label_3': row['MF_Google_Custom_Label_3'],
                    'custom_label_4': row['MF_Google_Custom_Label_4'],
                    'size_system': row['MF_Google_Size_System'],
                    'size_type': row['MF_Google_Size_Type'],
                    'color': row['MF_Google_Color'],
                    'size': row['MF_Google_Size'],
                    'material': row['MF_Google_Material'],
                    'product_category': row['MF_Google_Product_Category']
                }
            }

            products_map[product_id]['variants'].append(variant)

        # Convert map to list
        products = list(products_map.values())

        logger.info(f"📦 Grouped into {len(products)} products")

        return products
```

---

### Step 2: Update Configuration

**File to modify:** `src/config_loader.py` or create `config.json`

Add MySQL configuration section:

```json
{
  "mysql": {
    "host": "your-mysql-host.com",
    "user": "your-mysql-user",
    "password": "your-mysql-password",
    "database": "your-database-name"
  },
  "shopify": {
    "shop_url": "racoon-lab.myshopify.com",
    "access_token": "your-access-token"
  },
  "platforms": {
    "google": {
      "enabled": true
    },
    "meta": {
      "enabled": true
    }
  }
}
```

**Environment Variables (recommended for secrets):**

```bash
# .env file
MYSQL_HOST=your-mysql-host.com
MYSQL_USER=your-mysql-user
MYSQL_PASSWORD=your-mysql-password
MYSQL_DATABASE=your-database-name

# Shopify (keep for fallback/testing)
SHOPIFY_SHOP_URL=racoon-lab.myshopify.com
SHOPIFY_ACCESS_TOKEN=your-access-token
```

---

### Step 3: Modify Orchestrator

**File to modify:** `orchestrator.py`

**Current code (lines 36-37):**
```python
from src.shopify_client import ShopifyClient
from src.config_loader import ConfigLoader
```

**Add import:**
```python
from src.mysql_client import MySQLDataLoader
```

**Current initialization (lines 62-81):**
```python
def __init__(self):
    # Load config
    self.config = ConfigLoader.load_config()

    # Initialize Shopify client
    shop_url = os.getenv('SHOPIFY_SHOP_URL') or self.config.get('shopify', {}).get('shop_url')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN') or self.config.get('shopify', {}).get('access_token')

    if not shop_url or not access_token:
        raise ValueError("Missing Shopify credentials")

    self.shopify_client = ShopifyClient(shop_url, access_token)
```

**Replace with:**
```python
def __init__(self, use_mysql: bool = True):
    """
    Initialize Feed Orchestrator

    Args:
        use_mysql: If True, use MySQL data loader. If False, use Shopify API (fallback)
    """
    # Load config
    self.config = ConfigLoader.load_config()
    self.use_mysql = use_mysql

    # Initialize data source (MySQL or Shopify)
    if use_mysql:
        logger.info("🔄 Using MySQL data source")
        mysql_config = {
            'host': os.getenv('MYSQL_HOST') or self.config.get('mysql', {}).get('host'),
            'user': os.getenv('MYSQL_USER') or self.config.get('mysql', {}).get('user'),
            'password': os.getenv('MYSQL_PASSWORD') or self.config.get('mysql', {}).get('password'),
            'database': os.getenv('MYSQL_DATABASE') or self.config.get('mysql', {}).get('database')
        }

        if not all(mysql_config.values()):
            raise ValueError("Missing MySQL credentials")

        self.data_loader = MySQLDataLoader(mysql_config)
        self.data_loader.connect()
    else:
        logger.info("🔄 Using Shopify API data source (fallback mode)")
        shop_url = os.getenv('SHOPIFY_SHOP_URL') or self.config.get('shopify', {}).get('shop_url')
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN') or self.config.get('shopify', {}).get('access_token')

        if not shop_url or not access_token:
            raise ValueError("Missing Shopify credentials")

        self.data_loader = ShopifyClient(shop_url, access_token)
```

**Current product fetching (lines 206-270):**
```python
# Fetch products from Shopify
logger.info("📡 Fetching products from Shopify...")
products = self.shopify_client.get_all_products(limit=250)
```

**Replace with:**
```python
# Fetch products from data source
if self.use_mysql:
    logger.info("📡 Fetching products from MySQL...")
else:
    logger.info("📡 Fetching products from Shopify API...")

products = self.data_loader.get_all_products()
```

**Add cleanup in generate_all_feeds() at the end:**
```python
def generate_all_feeds(self) -> bool:
    try:
        # ... existing code ...

        return overall_success

    finally:
        # Cleanup MySQL connection
        if self.use_mysql and hasattr(self.data_loader, 'disconnect'):
            self.data_loader.disconnect()
```

---

### Step 4: Update Dependencies

**File to modify:** `requirements.txt`

Add MySQL connector:

```
flask==3.0.0
requests==2.31.0
gunicorn==21.2.0
-e .
APScheduler==3.10.4
mysql-connector-python==8.2.0
```

---

### Step 5: Update Mapper Classes (Optional Improvements)

**Files to review:**
- `platforms/google/mapper.py`
- `platforms/meta/mapper.py`

**Current mappers expect Shopify API format**, which the MySQL loader now provides via `_transform_to_shopify_format()`.

**No changes required** if using the transformation function above.

**Optional optimization:** Remove Shopify API-specific handling code (e.g., collections fetching logic) since MySQL already provides collections as comma-separated string.

---

### Step 6: Testing Strategy

#### 6.1 Unit Tests

Create `tests/test_mysql_loader.py`:

```python
import unittest
from src.mysql_client import MySQLDataLoader

class TestMySQLLoader(unittest.TestCase):
    def setUp(self):
        self.config = {
            'host': 'localhost',
            'user': 'test_user',
            'password': 'test_pass',
            'database': 'test_db'
        }
        self.loader = MySQLDataLoader(self.config)

    def test_connection(self):
        """Test MySQL connection"""
        self.loader.connect()
        self.assertIsNotNone(self.loader.connection)
        self.loader.disconnect()

    def test_get_all_products(self):
        """Test product fetching"""
        self.loader.connect()
        products = self.loader.get_all_products()
        self.assertIsInstance(products, list)
        self.assertGreater(len(products), 0)
        self.loader.disconnect()

    def test_product_structure(self):
        """Test product data structure matches Shopify format"""
        self.loader.connect()
        products = self.loader.get_all_products()

        # Check first product has required fields
        product = products[0]
        self.assertIn('id', product)
        self.assertIn('title', product)
        self.assertIn('variants', product)
        self.assertIn('images', product)
        self.assertIn('metafields', product)

        # Check first variant
        variant = product['variants'][0]
        self.assertIn('id', variant)
        self.assertIn('sku', variant)
        self.assertIn('price', variant)
        self.assertIn('metafields', variant)

        self.loader.disconnect()
```

#### 6.2 Integration Tests

**Test 1: Generate feeds from MySQL**

```bash
# Set MySQL credentials
export MYSQL_HOST=your-host
export MYSQL_USER=your-user
export MYSQL_PASSWORD=your-password
export MYSQL_DATABASE=your-database

# Run orchestrator
python -c "from orchestrator import FeedOrchestrator; o = FeedOrchestrator(use_mysql=True); o.generate_all_feeds()"
```

**Test 2: Compare MySQL vs Shopify feeds**

Generate feeds from both sources and compare:

```python
# Generate from MySQL
orchestrator_mysql = FeedOrchestrator(use_mysql=True)
orchestrator_mysql.generate_all_feeds()
# Saves to: public/google_shopping_feed.xml, public/meta_catalog_feed.xml

# Rename files
os.rename('public/google_shopping_feed.xml', 'public/google_mysql.xml')
os.rename('public/meta_catalog_feed.xml', 'public/meta_mysql.xml')

# Generate from Shopify API
orchestrator_api = FeedOrchestrator(use_mysql=False)
orchestrator_api.generate_all_feeds()
# Saves to: public/google_shopping_feed.xml, public/meta_catalog_feed.xml

# Compare files
import difflib
with open('public/google_mysql.xml') as f1, open('public/google_shopping_feed.xml') as f2:
    diff = difflib.unified_diff(f1.readlines(), f2.readlines())
    print('\n'.join(diff))
```

**Expected result:** Feeds should be identical or have minimal differences (e.g., timestamp, order)

#### 6.3 Performance Testing

```python
import time

# MySQL version
start = time.time()
orchestrator = FeedOrchestrator(use_mysql=True)
orchestrator.generate_all_feeds()
mysql_time = time.time() - start

print(f"MySQL feed generation: {mysql_time:.2f} seconds")
# Expected: 120-300 seconds (2-5 minutes)

# Shopify API version (for comparison)
start = time.time()
orchestrator = FeedOrchestrator(use_mysql=False)
orchestrator.generate_all_feeds()
api_time = time.time() - start

print(f"Shopify API feed generation: {api_time:.2f} seconds")
# Expected: 1200-1800 seconds (20-30 minutes)

print(f"Speedup: {api_time / mysql_time:.2f}x faster")
```

---

### Step 7: Deployment Checklist

#### Pre-Deployment

- [ ] MySQL credentials configured in environment variables
- [ ] `mysql-connector-python==8.2.0` added to `requirements.txt`
- [ ] `src/mysql_client.py` created and tested
- [ ] `orchestrator.py` modified with MySQL support
- [ ] Unit tests passing
- [ ] Integration tests passing (MySQL vs Shopify comparison)
- [ ] Performance tests show expected speedup

#### Deployment

- [ ] Update environment variables on Render:
  ```
  MYSQL_HOST=your-host
  MYSQL_USER=your-user
  MYSQL_PASSWORD=your-password
  MYSQL_DATABASE=your-database
  ```

- [ ] Deploy to staging environment first
- [ ] Run test feed generation on staging
- [ ] Verify feed quality (compare with production)
- [ ] Deploy to production
- [ ] Monitor first scheduled run (6:00 AM UTC)

#### Post-Deployment Monitoring

- [ ] Check feed generation time (should be 2-5 minutes)
- [ ] Verify feed file sizes match previous versions
- [ ] Check Shopify API usage (should drop to ~0 calls)
- [ ] Monitor MySQL query performance
- [ ] Verify Google Merchant Center accepts feeds
- [ ] Verify Meta Catalog accepts feeds

---

### Step 8: Rollback Plan

If issues occur, revert to Shopify API mode:

**Option 1: Environment variable override**

```bash
# Add to Render environment variables
USE_MYSQL=false
```

**Modify orchestrator.py:**
```python
def __init__(self):
    use_mysql = os.getenv('USE_MYSQL', 'true').lower() == 'true'
    # ... rest of init code
```

**Option 2: Code rollback**

```bash
git revert HEAD
git push
# Render auto-deploys previous version
```

---

## Expected Impact

### Performance Metrics

| Metric | Before (Shopify API) | After (MySQL) | Improvement |
|--------|---------------------|---------------|-------------|
| **Generation Time** | 20-30 minutes | 2-5 minutes | **80% faster** |
| **API Calls per Run** | ~1,500 | 0 | **100% reduction** |
| **Daily API Calls** | ~4,500 | 0 | **100% reduction** |
| **Rate Limit Risk** | High | None | **Risk eliminated** |
| **Memory Usage** | Moderate | Low | Streaming from MySQL |
| **Reliability** | Moderate (API dependent) | High | MySQL always available |

### Cost Savings

- **Shopify API costs**: Potentially reduced if on metered plan
- **Render compute**: Reduced from ~25 min to ~3 min per run = 88% compute savings
- **Developer time**: Fewer rate limit issues = less debugging

---

## Troubleshooting

### Issue: MySQL connection timeout

**Symptoms:**
```
ERROR: MySQL connection failed: Can't connect to MySQL server
```

**Solutions:**
1. Verify MySQL host is accessible from Render (check firewall rules)
2. Add Render IP ranges to MySQL allowlist
3. Increase connection timeout:
   ```python
   self.connection = mysql.connector.connect(
       ...,
       connection_timeout=30
   )
   ```

---

### Issue: Missing data in feeds

**Symptoms:**
- Feeds generated but products missing
- Metafields empty

**Solutions:**
1. Check `shopify-mysql-sync` is running and syncing data
2. Verify MySQL table has recent data:
   ```sql
   SELECT COUNT(*), MAX(Variant_id), MAX(Product_id) FROM online_products;
   ```
3. Check stock filter:
   ```sql
   SELECT COUNT(*) FROM online_products WHERE Stock_Magazzino > 0;
   ```

---

### Issue: Feed validation errors

**Symptoms:**
- Google Merchant Center rejects feeds
- Meta Catalog rejects feeds

**Solutions:**
1. Compare MySQL-generated feed with Shopify API-generated feed (side-by-side)
2. Check for NULL values in required fields:
   ```sql
   SELECT COUNT(*) FROM online_products
   WHERE Product_title IS NULL OR Price IS NULL;
   ```
3. Validate JSON image format:
   ```python
   images = json.loads(row['Product_Images'])
   print(images)  # Should be array of objects with 'src', 'alt', etc.
   ```

---

### Issue: Slow MySQL queries

**Symptoms:**
- Feed generation still takes 10+ minutes
- MySQL query timeout

**Solutions:**
1. Add index on `Stock_Magazzino`:
   ```sql
   CREATE INDEX idx_stock ON online_products(Stock_Magazzino);
   ```
2. Add index on `Product_id` for grouping:
   ```sql
   CREATE INDEX idx_product ON online_products(Product_id);
   ```
3. Optimize query with LIMIT (if testing):
   ```sql
   SELECT * FROM online_products WHERE Stock_Magazzino > 0 LIMIT 100;
   ```

---

## Maintenance

### Weekly Tasks

- [ ] Monitor feed generation time (should stay under 5 minutes)
- [ ] Check feed file sizes (should be consistent)
- [ ] Verify Shopify API call count (should be near 0)

### Monthly Tasks

- [ ] Review MySQL query performance
- [ ] Check for MySQL table bloat (run `OPTIMIZE TABLE online_products`)
- [ ] Verify `shopify-mysql-sync` is running on schedule
- [ ] Compare feed product counts vs Shopify product count

---

## Additional Resources

### Documentation References

- **Shopify API:** https://shopify.dev/api/admin-rest
- **MySQL Connector:** https://dev.mysql.com/doc/connector-python/en/
- **Google Merchant Center:** https://support.google.com/merchants/answer/7052112
- **Meta Catalog:** https://www.facebook.com/business/help/125074381480892

### Contact

For questions about this refactoring:
- **IT Infrastructure Team:** [contact info]
- **shopify-mysql-sync Maintainer:** [contact info]

---

## Appendix A: SQL Queries for Validation

### Check MySQL data freshness

```sql
-- Check when data was last updated (requires timestamp column)
-- Note: online_products table doesn't have timestamp, check shopify-mysql-sync logs instead
```

### Verify all required fields populated

```sql
-- Check for NULL values in critical fields
SELECT
    COUNT(*) AS total_variants,
    SUM(CASE WHEN Product_title IS NULL THEN 1 ELSE 0 END) AS missing_title,
    SUM(CASE WHEN Price IS NULL THEN 1 ELSE 0 END) AS missing_price,
    SUM(CASE WHEN Stock_Magazzino IS NULL THEN 1 ELSE 0 END) AS missing_stock,
    SUM(CASE WHEN Product_Images IS NULL THEN 1 ELSE 0 END) AS missing_images,
    SUM(CASE WHEN MF_Google_Gender IS NULL THEN 1 ELSE 0 END) AS missing_gender
FROM online_products
WHERE Stock_Magazzino > 0;
```

### Compare product counts

```sql
-- Count variants by product
SELECT
    Product_id,
    Product_title,
    COUNT(*) AS variant_count
FROM online_products
WHERE Stock_Magazzino > 0
GROUP BY Product_id, Product_title
ORDER BY variant_count DESC
LIMIT 20;
```

---

## Appendix B: Example MySQL Query Output

```
mysql> SELECT Variant_id, Product_title, SKU, Price, Stock_Magazzino, MF_Google_Color
    -> FROM online_products
    -> WHERE Stock_Magazzino > 0
    -> LIMIT 3;

+-------------+---------------------------+----------+--------+-----------------+-----------------+
| Variant_id  | Product_title             | SKU      | Price  | Stock_Magazzino | MF_Google_Color |
+-------------+---------------------------+----------+--------+-----------------+-----------------+
| 44234567890 | Nike Air Max 90           | NIKE-001 | 129.99 |              15 | White           |
| 44234567891 | Nike Air Max 90           | NIKE-002 | 129.99 |              8  | Black           |
| 44234567892 | Adidas Superstar Original | ADID-101 |  89.99 |              22 | White/Black     |
+-------------+---------------------------+----------+--------+-----------------+-----------------+
```

---

**End of Refactoring Guide**
