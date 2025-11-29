"""
Meta (Facebook/Instagram) Catalog Mapper
Transforms Shopify products to Meta catalog format

MAPPING SOURCE: Excel file "mapping_meta.xlsx"
Follows exact specifications from mapping document
"""

import logging
from typing import Dict, List, Optional
from core.base_mapper import BaseMapper

logger = logging.getLogger(__name__)


class MetaMapper(BaseMapper):
    """Meta (Facebook & Instagram) specific mapper"""
    
    def get_platform_name(self) -> str:
        """Return platform name"""
        return 'meta'
    
    def transform_product(self, product: Dict, metafields: Optional[Dict] = None, collections: Optional[List[str]] = None) -> List[Dict]:
        """Transform Shopify product into Meta catalog items"""
        
        # Apply same filters as Google
        if self._should_exclude_product(product):
            return []
        
        if not self._has_available_stock(product):
            return []
        
        items = []
        tags = product.get('tags', '').split(', ') if isinstance(product.get('tags'), str) else product.get('tags', [])
        collections = collections or []
        
        for variant in product.get('variants', []):
            if self._should_exclude_variant(variant):
                continue
            
            item = self._transform_variant_meta(product, variant, tags, metafields, collections)
            items.append(item)
        
        return items
    
    def _transform_variant_meta(self, product: Dict, variant: Dict, tags: List[str],
                                 metafields: Optional[Dict], collections: List[str]) -> Dict:
        """
        Transform single variant to Meta catalog format
        
        MAPPING AREAS:
        Each field is documented with its mapping source from Excel
        """
        item = {}
        
        # Extract metafields
        metafield_data = self._extract_metafields(metafields) if metafields else {}
        
        # ========== REQUIRED FIELDS ==========
        
        # ID (Excel: "replica quanto già fatto per il feed google")
        item['g:id'] = str(variant['id'])
        
        # TITLE (Excel: "Titolo leggibile e descrittivo: Brand + modello + tips + genere + colore/feature principale")
        item['g:title'] = self._build_title_meta(product, variant, tags, metafield_data)
        
        # DESCRIPTION (Excel: "Prendi il campo descrizione e togli i tag html")
        item['g:description'] = self._clean_html(product.get('body_html', ''))
        
        # LINK (Excel: "replica quanto già fatto per il feed google")
        item['g:link'] = f"{self.base_url}/products/{product['handle']}?variant={variant['id']}"
        
        # IMAGE_LINK (Excel: "replica quanto già fatto per il feed google")
        item['g:image_link'] = self._get_main_image_meta(product)
        
        # AVAILABILITY (Excel: "replica quanto già fatto per il feed google")
        item['g:availability'] = 'in stock' if variant.get('inventory_quantity', 0) > 0 else 'out of stock'
        
        # PRICE (Excel: "replica quanto già fatto per il feed google")
        compare_at = variant.get('compare_at_price')
        price = float(variant['price'])
        
        if compare_at and float(compare_at) > 0:
            item['g:price'] = f"{float(compare_at):.2f} EUR"
            item['g:sale_price'] = f"{price:.2f} EUR"
        else:
            item['g:price'] = f"{price:.2f} EUR"
        
        # BRAND (Excel: "replica quanto già fatto per il feed google")
        item['g:brand'] = product.get('vendor', 'Racoon Lab')
        
        # CONDITION (Excel: "Sempre 'NEW'")
        item['g:condition'] = 'new'
        
        # ========== ADDITIONAL REQUIRED/RECOMMENDED FIELDS ==========
        
        # ADDITIONAL_IMAGE_LINK (Excel: "ha a disposizione diverse immagini per prodotto...")
        additional_images = self._get_additional_images_meta(product)
        if additional_images:
            item['g:additional_image_link'] = additional_images
        
        # AGE_GROUP (Excel: "replica quanto già fatto per il feed google")
        item['g:age_group'] = self._get_age_group_meta(metafield_data)
        
        # GENDER (Excel: "replica quanto già fatto per il feed google")
        item['g:gender'] = self._get_gender_meta(metafield_data)
        
        # COLOR (Excel: "replica quanto già fatto per il feed google")
        color = self._get_color_meta(metafield_data)
        if color:
            item['g:color'] = color
        
        # SIZE (Excel: "replica quanto già fatto per il feed google")
        item['g:size'] = variant.get('option1', '')
        
        # SIZE_SYSTEM (Excel: "Sempre EU")
        item['g:size_system'] = 'EU'
        
        # MATERIAL (Excel: "replica quanto già fatto per il feed google")
        material = self._get_material_meta(metafield_data)
        if material:
            item['g:material'] = material
        
        # PATTERN (Excel: "replica quanto già fatto per il feed google")
        pattern = self._get_pattern(tags)
        if pattern:
            item['g:pattern'] = pattern
        
        # GOOGLE_PRODUCT_CATEGORY (Excel: "replica quanto già fatto per il feed google")
        item['g:google_product_category'] = self.static_values.get('google_product_category', '187')
        
        # PRODUCT_TYPE (Excel: "informativa intelligente basata su macro cateria, brand, modello")
        item['g:product_type'] = self._build_hierarchical_product_type(product)
        
        # ITEM_GROUP_ID (Excel: "replica quanto già fatto per il feed google")
        item['g:item_group_id'] = str(product['id'])
        
        # GTIN (Excel: "replica quanto già fatto per il feed google")
        barcode = variant.get('barcode', '')
        if barcode and str(barcode).strip():
            item['g:gtin'] = str(barcode).strip()
        
        # MPN (Excel: "replica quanto già fatto per il feed google")
        item['g:mpn'] = variant.get('sku', '')
        
        # SHIPPING (Excel: "in Italia sempre gratis sopra la 89€, nel dubio leggi le policy da shopify")
        # Uses same logic as Google
        shipping_cost = self._calculate_shipping_meta(price)
        if shipping_cost is not None:
            item['g:shipping'] = f"IT:::{ shipping_cost:.2f} EUR"
        
        # STATUS (Excel: "Sempre Active")
        item['g:status'] = 'active'
        
        # INVENTORY (Excel: "sempre a 1")
        item['g:inventory'] = '1'
        
        # ========== CUSTOM LABELS (Excel: "per ora saltalo") ==========
        # Implementing these for future use, but can be disabled via config
        
        item['g:custom_label_0'] = ''  # Excel: "per ora saltalo"
        item['g:custom_label_1'] = ''  # Excel: "per ora saltalo"
        item['g:custom_label_2'] = ''  # Excel: "per ora saltalo"
        item['g:custom_label_3'] = ''  # Excel: "per ora saltalo"
        item['g:custom_label_4'] = ''  # Excel: "per ora saltalo"
        
        # ========== INTERNAL_LABEL (Excel: "concatena i campi Shopify tags e collections") ==========
        # This field uses MULTIPLE XML tags (one per value)
        internal_labels = self._build_internal_labels_meta(tags, collections)
        if internal_labels:
            item['g:internal_label'] = internal_labels  # Will be handled specially by XML generator
        
        # ========== OPTIONAL FIELDS ==========
        
        # RICH_TEXT_DESCRIPTION (Excel: "Prendi il campo descrizione")
        item['g:rich_text_description'] = product.get('body_html', '')
        
        # SALE_PRICE_EFFECTIVE_DATE (Excel: "per ora saltalo")
        # Skipped as per mapping
        
        return item
    
    # ========== META-SPECIFIC HELPER METHODS ==========
    
    def _build_title_meta(self, product: Dict, variant: Dict, tags: List[str], metafield_data: Dict) -> str:
        """
        Build Meta-optimized title
        
        Formula (Excel): Brand + modello + tips + genere + colore/feature principale
        Target: 65 characters max for optimal Meta display
        
        Args:
            product: Shopify product
            variant: Shopify variant
            tags: Product tags
            metafield_data: Extracted metafields
        
        Returns:
            Optimized title string (max 65 chars)
        """
        parts = []
        
        # 1. Brand
        brand = product.get('vendor', '')
        if brand:
            parts.append(brand)
        
        # 2. Modello (product_type)
        model = product.get('product_type', '')
        if model:
            parts.append(model)
        
        # 3. Genere (gender from metafields)
        gender = metafield_data.get('gender', '')
        if gender:
            gender_map = {
                'female': 'Donna',
                'male': 'Uomo',
                'unisex': 'Unisex'
            }
            gender_it = gender_map.get(gender.lower(), gender)
            parts.append(gender_it)
        
        # 4. Taglia (size)
        size = variant.get('option1', '')
        if size:
            parts.append(f"Taglia {size}")
        
        # Build title
        title = ' '.join(parts)
        
        # Truncate to 65 characters if needed
        if len(title) > 65:
            title = title[:62] + '...'
        
        return title
    
    def _get_main_image_meta(self, product: Dict) -> str:
        """
        Get main image for Meta
        
        Special logic (Excel): For Converse, use _INT image as main
        For others, use first image
        """
        images = product.get('images', [])
        if not images:
            return ''
        
        brand = product.get('vendor', '').lower()
        
        # Special handling for Converse
        if 'converse' in brand:
            # Find _INT image
            for img in images:
                img_src = img.get('src', '')
                if '_INT' in img_src or '_int' in img_src:
                    return img_src
        
        # Default: first image
        return images[0].get('src', '')
    
    def _get_additional_images_meta(self, product: Dict) -> List[str]:
        """
        Get additional images for Meta
        
        Excel: "ha a disposizione diverse immagini per prodotto; quelle che terminano con
        _IND, _INDS o _INDH sono con elementi umani; quelle che terminano con _DETT sono
        dei closeup. Se non ritieni che ci siano logiche da seguire in base alle tue
        conoscenze sulle logiche e algoritmi meta, lascia l'ordine che trovi."
        
        Strategy: Keep natural order from Shopify (no special sorting needed)
        """
        images = product.get('images', [])
        if not images:
            return []
        
        brand = product.get('vendor', '').lower()
        
        # For Converse: main is _INT, others are additional
        if 'converse' in brand:
            additional = []
            for img in images:
                img_src = img.get('src', '')
                # Skip _INT as it's already the main image
                if '_INT' not in img_src and '_int' not in img_src:
                    additional.append(img_src)
            return additional[:19]  # Meta allows up to 20 images total (1 main + 19 additional)
        
        # For others: first is main, rest are additional (up to 19)
        return [img.get('src', '') for img in images[1:20]]
    
    def _get_gender_meta(self, metafield_data: Dict) -> str:
        """Get gender for Meta (same as Google)"""
        return metafield_data.get('gender', self.static_values.get('default_gender', 'female'))
    
    def _get_age_group_meta(self, metafield_data: Dict) -> str:
        """Get age_group for Meta (same as Google)"""
        return metafield_data.get('age_group', self.static_values.get('default_age_group', 'adult'))
    
    def _get_color_meta(self, metafield_data: Dict) -> str:
        """Get color for Meta (same as Google)"""
        return metafield_data.get('color', '')
    
    def _get_material_meta(self, metafield_data: Dict) -> str:
        """Get material for Meta (same as Google)"""
        return metafield_data.get('material', '')
    
    def _calculate_shipping_meta(self, price: float) -> Optional[float]:
        """
        Calculate shipping cost for Meta
        
        Excel: "in Italia sempre gratis sopra la 89€, nel dubio leggi le policy da shopify"
        
        Returns:
            Shipping cost in EUR or None if free
        """
        if price >= 89:
            return 0.00  # Free shipping
        elif price > 30:
            return 10.00
        else:
            return 6.00
    
    def _build_internal_labels_meta(self, tags: List[str], collections: List[str]) -> List[str]:
        """
        Build internal_label values for Meta
        
        Excel: "concatena i campi Shopify tags e collections; usa un tag <internal_label>
        per ogni voce sempre a 1"
        
        This means:
        - One <g:internal_label> XML tag for each tag
        - One <g:internal_label> XML tag for each collection
        
        Returns:
            List of internal label values (will be written as multiple XML tags)
        """
        labels = []
        
        # Add all tags
        for tag in tags:
            if tag.strip():
                labels.append(tag.strip())
        
        # Add all collections
        for collection in collections:
            if collection.strip():
                labels.append(collection.strip())
        
        return labels
