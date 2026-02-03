"""
MySQL Data Loader for Feed Generation
Replaces Shopify API calls with MySQL queries from online_products table

Data source: shopify-mysql-sync (populates online_products table)
"""

import json
import logging
from typing import List, Dict, Optional
from decimal import Decimal

import mysql.connector
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursor

logger = logging.getLogger(__name__)


class MySQLDataLoader:
    """
    Load product data from MySQL online_products table.

    Provides same data structure as ShopifyClient for minimal code changes
    in mappers and orchestrator.
    """

    def __init__(self, config: Dict):
        """
        Initialize MySQL connection configuration.

        Args:
            config: Dict with keys 'host', 'user', 'password', 'database'
        """
        self.config = config
        self._connection: Optional[MySQLConnection] = None
        self._cursor: Optional[MySQLCursor] = None

    def connect(self) -> 'MySQLDataLoader':
        """
        Establish MySQL connection.

        Returns:
            MySQLDataLoader: Self for method chaining
        """
        try:
            self._connection = mysql.connector.connect(
                host=self.config['host'],
                user=self.config['user'],
                password=self.config['password'],
                database=self.config['database'],
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci',
                connection_timeout=30
            )
            self._cursor = self._connection.cursor(dictionary=True)
            logger.info(f"✅ Connected to MySQL: {self.config['database']}")
            return self
        except Exception as e:
            logger.error(f"❌ MySQL connection failed: {e}")
            raise

    def disconnect(self) -> None:
        """Close MySQL connection."""
        if self._cursor:
            self._cursor.close()
        if self._connection:
            self._connection.close()
        logger.info("🔌 MySQL connection closed")

    def get_all_products(self) -> List[Dict]:
        """
        Fetch all products from MySQL online_products table.

        Note: shopify-mysql-sync already filters for:
        - status: active
        - tags: sneakers/scarpe/ciabatte/stivali personalizzat*

        Additional filter here: Stock_Magazzino > 0

        Returns:
            List of product dictionaries in Shopify-compatible format
        """
        query = """
            SELECT
                Variant_id, Variant_Title, SKU, Barcode,
                Product_id, Product_title, Product_handle,
                Vendor, Product_Type,
                Price, Compare_AT_Price,
                Inventory_Item_ID, Stock_Magazzino,
                Tags, Collections,
                Body_HTML, Product_Images,
                MF_Customization_Description, MF_Shoe_Details,
                MF_Customization_Details, MF_O_Description,
                MF_Handling, MF_Google_Custom_Product,
                MF_Google_Age_Group, MF_Google_Condition,
                MF_Google_Gender, MF_Google_MPN,
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
            self._cursor.execute(query)
            rows = self._cursor.fetchall()

            logger.info(f"📊 Loaded {len(rows)} variants from MySQL")

            # Transform to Shopify-compatible format
            products = self._transform_to_shopify_format(rows)

            logger.info(f"📦 Grouped into {len(products)} products")

            return products

        except Exception as e:
            logger.error(f"❌ MySQL query failed: {e}")
            raise

    def _transform_to_shopify_format(self, rows: List[Dict]) -> List[Dict]:
        """
        Transform MySQL rows to match Shopify API product structure.

        Groups variants by product_id and reconstructs nested structure
        expected by mappers.

        Args:
            rows: Raw MySQL rows (one per variant)

        Returns:
            List of products with nested variants (Shopify-like structure)
        """
        products_map: Dict[int, Dict] = {}

        for row in rows:
            product_id = row['Product_id']

            # Create product entry if not exists
            if product_id not in products_map:
                # Parse images JSON
                images = self._parse_images(row['Product_Images'])

                products_map[product_id] = {
                    'id': product_id,
                    'title': row['Product_title'],
                    'handle': row['Product_handle'],
                    'vendor': row['Vendor'],
                    'product_type': row['Product_Type'],
                    'status': 'active',  # Already filtered by shopify-mysql-sync
                    'tags': row['Tags'] or '',  # String format: "tag1, tag2, tag3"
                    'body_html': row['Body_HTML'],
                    'images': images,
                    'variants': [],
                    'collections': self._parse_collections(row['Collections']),
                    # Metafields reconstructed in Shopify format
                    # Will be populated per-variant and passed to mapper
                    'metafields': {}
                }

            # Build variant
            variant = {
                'id': row['Variant_id'],
                'title': row['Variant_Title'],
                'option1': row['Variant_Title'],  # Taglia (es. "42")
                'option2': None,
                'option3': None,
                'sku': row['SKU'] or '',
                'barcode': row['Barcode'] or '',
                'price': self._decimal_to_str(row['Price']),
                'compare_at_price': self._decimal_to_str(row['Compare_AT_Price']),
                'inventory_item_id': row['Inventory_Item_ID'],
                'inventory_quantity': row['Stock_Magazzino'] or 0,
            }

            products_map[product_id]['variants'].append(variant)

        # Convert map to list
        return list(products_map.values())

    def _parse_images(self, images_json: Optional[str]) -> List[Dict]:
        """
        Parse Product_Images JSON into list of image dicts.

        MySQL format: {"count": N, "images": [{...}], "featured": "url"}
        Shopify format: [{"src": "url", "alt": "", ...}]

        Args:
            images_json: JSON string from MySQL

        Returns:
            List of image dicts in Shopify format
        """
        if not images_json:
            return []

        try:
            data = json.loads(images_json)
            images = data.get('images', [])

            # Convert to Shopify format (ensure 'src' key exists)
            result = []
            for img in images:
                result.append({
                    'id': img.get('id'),
                    'position': img.get('position'),
                    'src': img.get('src', ''),
                    'alt': img.get('alt', ''),
                    'width': img.get('width'),
                    'height': img.get('height')
                })

            return result

        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Could not parse images JSON: {e}")
            return []

    def _parse_collections(self, collections_str: Optional[str]) -> List[str]:
        """
        Parse Collections string into list.

        Args:
            collections_str: Comma-separated collection titles

        Returns:
            List of collection titles
        """
        if not collections_str:
            return []

        # Split and clean
        return [c.strip() for c in collections_str.split(',') if c.strip()]

    def _decimal_to_str(self, value: Optional[Decimal]) -> Optional[str]:
        """
        Convert Decimal to string for price fields.

        Args:
            value: Decimal value or None

        Returns:
            String representation or None
        """
        if value is None:
            return None
        return str(value)

    def get_product_metafields_from_row(self, row: Dict) -> Dict:
        """
        Reconstruct metafields structure from MySQL row.

        Builds the nested dict format that _extract_metafields() expects:
        {'mm-google-shopping': {'gender': 'female', 'color': 'red', ...}}

        Args:
            row: MySQL row dict

        Returns:
            Dict with metafields in Shopify namespace format
        """
        google_shopping = {}

        # Map MySQL columns to metafield keys
        field_mapping = {
            'MF_Google_Gender': 'gender',
            'MF_Google_Age_Group': 'age_group',
            'MF_Google_Condition': 'condition',
            'MF_Google_Color': 'color',
            'MF_Google_Size': 'size',
            'MF_Google_Material': 'material',
            'MF_Google_MPN': 'mpn',
            'MF_Google_Size_System': 'size_system',
            'MF_Google_Size_Type': 'size_type',
            'MF_Google_Custom_Label_0': 'custom_label_0',
            'MF_Google_Custom_Label_1': 'custom_label_1',
            'MF_Google_Custom_Label_2': 'custom_label_2',
            'MF_Google_Custom_Label_3': 'custom_label_3',
            'MF_Google_Custom_Label_4': 'custom_label_4',
            'MF_Google_Product_Category': 'google_product_category',
        }

        for mysql_col, metafield_key in field_mapping.items():
            value = row.get(mysql_col)
            if value is not None:
                google_shopping[metafield_key] = value

        return {
            'mm-google-shopping': google_shopping
        }

    def get_products_with_metafields(self) -> List[Dict]:
        """
        Fetch all products with metafields pre-loaded.

        This is the main method to use for feed generation.
        Returns products in exact format expected by orchestrator.

        Returns:
            List of products with 'metafields' and 'collections' already populated
        """
        query = """
            SELECT
                Variant_id, Variant_Title, SKU, Barcode,
                Product_id, Product_title, Product_handle,
                Vendor, Product_Type,
                Price, Compare_AT_Price,
                Inventory_Item_ID, Stock_Magazzino,
                Tags, Collections,
                Body_HTML, Product_Images,
                MF_Google_Age_Group, MF_Google_Condition,
                MF_Google_Gender, MF_Google_MPN,
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
            self._cursor.execute(query)
            rows = self._cursor.fetchall()

            logger.info(f"📊 Loaded {len(rows)} variants from MySQL")

            # Group by product and build structure
            products_map: Dict[int, Dict] = {}
            variant_metafields: Dict[int, Dict] = {}  # variant_id -> metafields

            for row in rows:
                product_id = row['Product_id']
                variant_id = row['Variant_id']

                # Store metafields per variant
                variant_metafields[variant_id] = self.get_product_metafields_from_row(row)

                if product_id not in products_map:
                    images = self._parse_images(row['Product_Images'])
                    collections = self._parse_collections(row['Collections'])

                    products_map[product_id] = {
                        'id': product_id,
                        'title': row['Product_title'],
                        'handle': row['Product_handle'],
                        'vendor': row['Vendor'],
                        'product_type': row['Product_Type'],
                        'status': 'active',
                        'tags': row['Tags'] or '',
                        'body_html': row['Body_HTML'],
                        'images': images,
                        'variants': [],
                        'collections': collections,
                        # Use first variant's metafields as product-level
                        # (will be overridden per-variant in orchestrator)
                        'metafields': variant_metafields[variant_id],
                        '_variant_metafields': {}  # Store per-variant metafields
                    }

                # Build variant
                variant = {
                    'id': variant_id,
                    'title': row['Variant_Title'],
                    'option1': row['Variant_Title'],
                    'option2': None,
                    'option3': None,
                    'sku': row['SKU'] or '',
                    'barcode': row['Barcode'] or '',
                    'price': self._decimal_to_str(row['Price']),
                    'compare_at_price': self._decimal_to_str(row['Compare_AT_Price']),
                    'inventory_item_id': row['Inventory_Item_ID'],
                    'inventory_quantity': row['Stock_Magazzino'] or 0,
                }

                products_map[product_id]['variants'].append(variant)
                products_map[product_id]['_variant_metafields'][variant_id] = variant_metafields[variant_id]

            products = list(products_map.values())
            logger.info(f"📦 Grouped into {len(products)} products")

            return products

        except Exception as e:
            logger.error(f"❌ MySQL query failed: {e}")
            raise

    def get_variant_metafields(self, product: Dict, variant_id: int) -> Dict:
        """
        Get metafields for a specific variant from pre-loaded data.

        Args:
            product: Product dict with '_variant_metafields'
            variant_id: Variant ID

        Returns:
            Metafields dict for this variant
        """
        return product.get('_variant_metafields', {}).get(variant_id, {})
