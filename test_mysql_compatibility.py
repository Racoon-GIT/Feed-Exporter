#!/usr/bin/env python3
"""
Test di compatibilità struttura dati MySQL vs Shopify API

Questo script:
1. Carica dati da MySQL
2. Verifica che la struttura sia compatibile con i mapper
3. Simula la trasformazione senza scrivere file
4. Report dettagliato di eventuali problemi

Eseguire con:
    python test_mysql_compatibility.py

Richiede variabili d'ambiente:
    MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
"""

import os
import sys
import json
import logging
from typing import Dict, List, Any, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Aggiungi path per import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_env_vars() -> bool:
    """Verifica variabili d'ambiente MySQL"""
    required = ['MYSQL_HOST', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE']
    missing = [var for var in required if not os.getenv(var)]

    if missing:
        logger.error(f"❌ Variabili d'ambiente mancanti: {', '.join(missing)}")
        return False
    return True


def test_mysql_connection() -> Tuple[bool, Any]:
    """Test connessione MySQL"""
    from src.mysql_client import MySQLDataLoader

    config = {
        'host': os.getenv('MYSQL_HOST'),
        'user': os.getenv('MYSQL_USER'),
        'password': os.getenv('MYSQL_PASSWORD'),
        'database': os.getenv('MYSQL_DATABASE')
    }

    try:
        loader = MySQLDataLoader(config)
        loader.connect()
        logger.info("✅ Connessione MySQL riuscita")
        return True, loader
    except Exception as e:
        logger.error(f"❌ Connessione MySQL fallita: {e}")
        return False, None


def test_data_fetch(loader) -> Tuple[bool, List[Dict]]:
    """Test fetch prodotti"""
    try:
        products = loader.get_products_with_metafields()
        logger.info(f"✅ Caricati {len(products)} prodotti da MySQL")
        return True, products
    except Exception as e:
        logger.error(f"❌ Fetch prodotti fallito: {e}")
        return False, []


def validate_product_structure(product: Dict, index: int) -> List[str]:
    """Valida struttura singolo prodotto"""
    errors = []
    product_id = product.get('id', f'index_{index}')

    # Campi obbligatori prodotto
    required_product_fields = ['id', 'title', 'handle', 'vendor', 'variants', 'images']
    for field in required_product_fields:
        if field not in product:
            errors.append(f"Product {product_id}: campo '{field}' mancante")
        elif product[field] is None:
            errors.append(f"Product {product_id}: campo '{field}' è None")

    # Tags deve essere stringa
    tags = product.get('tags')
    if tags is not None and not isinstance(tags, str):
        errors.append(f"Product {product_id}: 'tags' deve essere stringa, trovato {type(tags).__name__}")

    # Images deve essere lista
    images = product.get('images', [])
    if not isinstance(images, list):
        errors.append(f"Product {product_id}: 'images' deve essere lista, trovato {type(images).__name__}")
    else:
        for i, img in enumerate(images):
            if not isinstance(img, dict):
                errors.append(f"Product {product_id}: images[{i}] deve essere dict")
            elif 'src' not in img:
                errors.append(f"Product {product_id}: images[{i}] manca 'src'")
            elif not img.get('src'):
                errors.append(f"Product {product_id}: images[{i}]['src'] è vuoto")
            elif not img['src'].startswith('http'):
                errors.append(f"Product {product_id}: images[{i}]['src'] non è URL completo: {img['src'][:50]}...")

    # Collections deve essere lista
    collections = product.get('collections', [])
    if not isinstance(collections, list):
        errors.append(f"Product {product_id}: 'collections' deve essere lista, trovato {type(collections).__name__}")

    # Variants
    variants = product.get('variants', [])
    if not isinstance(variants, list):
        errors.append(f"Product {product_id}: 'variants' deve essere lista")
    elif len(variants) == 0:
        errors.append(f"Product {product_id}: nessuna variante")
    else:
        for v_idx, variant in enumerate(variants):
            var_errors = validate_variant_structure(variant, product_id, v_idx)
            errors.extend(var_errors)

    # Metafields
    metafields = product.get('metafields', {})
    if not isinstance(metafields, dict):
        errors.append(f"Product {product_id}: 'metafields' deve essere dict")

    # _variant_metafields (interno)
    variant_mf = product.get('_variant_metafields', {})
    if not isinstance(variant_mf, dict):
        errors.append(f"Product {product_id}: '_variant_metafields' deve essere dict")

    return errors


def validate_variant_structure(variant: Dict, product_id: Any, v_idx: int) -> List[str]:
    """Valida struttura singola variante"""
    errors = []
    variant_id = variant.get('id', f'v_index_{v_idx}')
    prefix = f"Product {product_id}, Variant {variant_id}"

    # Campi obbligatori variante
    required_variant_fields = ['id', 'sku', 'price', 'inventory_quantity']
    for field in required_variant_fields:
        if field not in variant:
            errors.append(f"{prefix}: campo '{field}' mancante")

    # option1 (taglia) - critico per g:size
    if 'option1' not in variant:
        errors.append(f"{prefix}: 'option1' mancante (usato per g:size)")
    elif not variant.get('option1'):
        errors.append(f"{prefix}: 'option1' è vuoto (g:size sarà vuoto)")

    # price deve essere stringa o convertibile
    price = variant.get('price')
    if price is not None:
        try:
            float(price)
        except (ValueError, TypeError):
            errors.append(f"{prefix}: 'price' non convertibile a float: {price}")

    # inventory_quantity deve essere int
    inv = variant.get('inventory_quantity')
    if inv is not None and not isinstance(inv, int):
        errors.append(f"{prefix}: 'inventory_quantity' deve essere int, trovato {type(inv).__name__}")

    return errors


def validate_metafield_structure(product: Dict) -> List[str]:
    """Valida struttura metafield per compatibilità con _extract_metafields()"""
    errors = []
    product_id = product.get('id', 'unknown')

    for variant in product.get('variants', []):
        variant_id = variant.get('id')

        # Recupera metafield per questa variante
        variant_mf = product.get('_variant_metafields', {}).get(variant_id, {})

        if not variant_mf:
            errors.append(f"Product {product_id}, Variant {variant_id}: metafields vuoti")
            continue

        # Verifica struttura mm-google-shopping
        google_mf = variant_mf.get('mm-google-shopping', {})
        if not isinstance(google_mf, dict):
            errors.append(f"Product {product_id}, Variant {variant_id}: 'mm-google-shopping' deve essere dict")
            continue

        # Campi attesi (non tutti obbligatori, ma almeno alcuni dovrebbero esistere)
        expected_fields = ['gender', 'age_group', 'color', 'material', 'size', 'condition']
        found_fields = [f for f in expected_fields if google_mf.get(f)]

        if len(found_fields) == 0:
            # Warning, non errore - potrebbero usare valori di default
            pass

    return errors


def test_mapper_compatibility(products: List[Dict]) -> Tuple[int, int, List[str]]:
    """Testa compatibilità con i mapper reali"""
    from src.config_loader import ConfigLoader
    from platforms.google.mapper import GoogleMapper
    from platforms.meta.mapper import MetaMapper

    config = ConfigLoader('config')
    base_url = os.getenv('SHOP_BASE_URL', 'https://racoon-lab.it')

    google_mapper = GoogleMapper(config, base_url)
    meta_mapper = MetaMapper(config, base_url)

    errors = []
    total_google_items = 0
    total_meta_items = 0

    for product in products:
        product_id = product.get('id')
        collections = product.get('collections', [])

        for variant in product.get('variants', []):
            variant_id = variant['id']

            # Simula ciò che fa l'orchestrator
            from src.mysql_client import MySQLDataLoader
            metafields = product.get('_variant_metafields', {}).get(variant_id, {})

            single_variant_product = product.copy()
            single_variant_product['variants'] = [variant]

            # Test Google mapper
            try:
                google_items = google_mapper.transform_product(single_variant_product, metafields, collections)
                total_google_items += len(google_items)

                # Valida output Google
                for item in google_items:
                    item_errors = validate_feed_item(item, 'google', product_id, variant_id)
                    errors.extend(item_errors)

            except Exception as e:
                errors.append(f"Google mapper error - Product {product_id}, Variant {variant_id}: {e}")

            # Test Meta mapper
            try:
                meta_items = meta_mapper.transform_product(single_variant_product, metafields, collections)
                total_meta_items += len(meta_items)

                # Valida output Meta
                for item in meta_items:
                    item_errors = validate_feed_item(item, 'meta', product_id, variant_id)
                    errors.extend(item_errors)

            except Exception as e:
                errors.append(f"Meta mapper error - Product {product_id}, Variant {variant_id}: {e}")

    return total_google_items, total_meta_items, errors


def validate_feed_item(item: Dict, platform: str, product_id: Any, variant_id: Any) -> List[str]:
    """Valida singolo item del feed"""
    errors = []
    prefix = f"{platform.upper()} - Product {product_id}, Variant {variant_id}"

    # Campi obbligatori per Google/Meta
    required_fields = [
        'g:id', 'g:title', 'g:link', 'g:image_link',
        'g:price', 'g:availability', 'g:brand', 'g:condition'
    ]

    for field in required_fields:
        value = item.get(field)
        if not value:
            errors.append(f"{prefix}: '{field}' mancante o vuoto")

    # Verifica URL immagine
    image_link = item.get('g:image_link', '')
    if image_link and not image_link.startswith('http'):
        errors.append(f"{prefix}: 'g:image_link' non è URL valido: {image_link[:50]}...")

    # Verifica link prodotto
    link = item.get('g:link', '')
    if link and not link.startswith('http'):
        errors.append(f"{prefix}: 'g:link' non è URL valido")

    # Verifica prezzo formato
    price = item.get('g:price', '')
    if price and 'EUR' not in price:
        errors.append(f"{prefix}: 'g:price' formato errato (manca EUR): {price}")

    return errors


def print_sample_data(products: List[Dict], num_samples: int = 2):
    """Stampa esempi di dati per verifica manuale"""
    logger.info("\n" + "="*80)
    logger.info("SAMPLE DATA (per verifica manuale)")
    logger.info("="*80)

    for i, product in enumerate(products[:num_samples]):
        logger.info(f"\n--- Prodotto {i+1} ---")
        logger.info(f"ID: {product.get('id')}")
        logger.info(f"Title: {product.get('title', '')[:60]}...")
        logger.info(f"Handle: {product.get('handle')}")
        logger.info(f"Vendor: {product.get('vendor')}")
        logger.info(f"Product Type: {product.get('product_type')}")
        logger.info(f"Status: {product.get('status')}")
        logger.info(f"Tags: {product.get('tags', '')[:80]}...")
        logger.info(f"Collections: {product.get('collections', [])[:3]}...")
        logger.info(f"Num Images: {len(product.get('images', []))}")

        if product.get('images'):
            first_img = product['images'][0]
            logger.info(f"First Image src: {first_img.get('src', '')[:80]}...")

        logger.info(f"Num Variants: {len(product.get('variants', []))}")

        if product.get('variants'):
            v = product['variants'][0]
            logger.info(f"  First Variant ID: {v.get('id')}")
            logger.info(f"  option1 (size): {v.get('option1')}")
            logger.info(f"  SKU: {v.get('sku')}")
            logger.info(f"  Price: {v.get('price')}")
            logger.info(f"  Inventory: {v.get('inventory_quantity')}")

            # Metafields
            variant_id = v.get('id')
            mf = product.get('_variant_metafields', {}).get(variant_id, {})
            google_mf = mf.get('mm-google-shopping', {})
            logger.info(f"  Metafields mm-google-shopping:")
            for key in ['gender', 'age_group', 'color', 'material']:
                logger.info(f"    {key}: {google_mf.get(key, '(not set)')}")


def main():
    """Main test runner"""
    logger.info("="*80)
    logger.info("TEST COMPATIBILITÀ MYSQL → FEED-EXPORTER")
    logger.info("="*80)

    all_errors = []

    # 1. Check env vars
    logger.info("\n[1/6] Verifica variabili d'ambiente...")
    if not check_env_vars():
        sys.exit(1)
    logger.info("✅ Variabili d'ambiente OK")

    # 2. Test MySQL connection
    logger.info("\n[2/6] Test connessione MySQL...")
    success, loader = test_mysql_connection()
    if not success:
        sys.exit(1)

    # 3. Fetch data
    logger.info("\n[3/6] Fetch prodotti da MySQL...")
    success, products = test_data_fetch(loader)
    if not success:
        loader.disconnect()
        sys.exit(1)

    if len(products) == 0:
        logger.error("❌ Nessun prodotto trovato in MySQL")
        loader.disconnect()
        sys.exit(1)

    # 4. Validate structure
    logger.info("\n[4/6] Validazione struttura dati...")
    structure_errors = []
    for i, product in enumerate(products):
        errors = validate_product_structure(product, i)
        structure_errors.extend(errors)

        mf_errors = validate_metafield_structure(product)
        structure_errors.extend(mf_errors)

    if structure_errors:
        logger.warning(f"⚠️ Trovati {len(structure_errors)} problemi di struttura")
        for err in structure_errors[:20]:  # Mostra solo primi 20
            logger.warning(f"  - {err}")
        if len(structure_errors) > 20:
            logger.warning(f"  ... e altri {len(structure_errors) - 20} errori")
        all_errors.extend(structure_errors)
    else:
        logger.info("✅ Struttura dati valida")

    # 5. Test mapper compatibility
    logger.info("\n[5/6] Test compatibilità con mapper...")
    try:
        google_items, meta_items, mapper_errors = test_mapper_compatibility(products)
        logger.info(f"  Google items generati: {google_items}")
        logger.info(f"  Meta items generati: {meta_items}")

        if mapper_errors:
            logger.warning(f"⚠️ Trovati {len(mapper_errors)} problemi con i mapper")
            for err in mapper_errors[:20]:
                logger.warning(f"  - {err}")
            if len(mapper_errors) > 20:
                logger.warning(f"  ... e altri {len(mapper_errors) - 20} errori")
            all_errors.extend(mapper_errors)
        else:
            logger.info("✅ Mapper compatibili")
    except Exception as e:
        logger.error(f"❌ Errore test mapper: {e}")
        all_errors.append(f"Mapper test failed: {e}")

    # 6. Print samples
    logger.info("\n[6/6] Sample data...")
    print_sample_data(products, num_samples=2)

    # Cleanup
    loader.disconnect()

    # Final report
    logger.info("\n" + "="*80)
    logger.info("REPORT FINALE")
    logger.info("="*80)
    logger.info(f"Prodotti analizzati: {len(products)}")
    logger.info(f"Errori totali: {len(all_errors)}")

    if all_errors:
        logger.warning("\n⚠️ TEST COMPLETATO CON WARNING")
        logger.warning("Verificare gli errori sopra prima del deploy")
        sys.exit(1)
    else:
        logger.info("\n✅ TEST COMPLETATO CON SUCCESSO")
        logger.info("La struttura MySQL è compatibile con Feed-Exporter")
        sys.exit(0)


if __name__ == '__main__':
    main()
