"""
Google Shopping Mapper - Transforms Shopify products to Google Shopping format
Inherits from BaseMapper with Google-specific logic
"""

import logging
from typing import Dict, List, Optional
from core.base_mapper import BaseMapper

logger = logging.getLogger(__name__)


class GoogleMapper(BaseMapper):
    """Google Shopping specific mapper"""
    
    def get_platform_name(self) -> str:
        """Return platform name"""
        return 'google'
    
    def transform_product(self, product: Dict, metafields: Optional[Dict] = None, collections: Optional[List[str]] = None) -> List[Dict]:
        """Transform Shopify product into Google Shopping items"""
        
        # Apply filters
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
            
            item = self._transform_variant_google(product, variant, tags, metafields, collections)
            items.append(item)
        
        return items
    
    def _transform_variant_google(self, product: Dict, variant: Dict, tags: List[str], 
                                   metafields: Optional[Dict], collections: List[str]) -> Dict:
        """
        Transform single variant to Google Shopping format
        
        IMPORTANT: This preserves ALL existing Google feed logic without modifications
        """
        item = {}
        
        # Extract metafields
        metafield_data = self._extract_metafields(metafields) if metafields else {}
        
        # ========== CORE FIELDS (MAPPING AREA 1) ==========
        item['g:id'] = str(variant['id'])
        item['g:title'] = self._build_title_google(product, variant, metafield_data, tags)
        item['g:description'] = self._clean_html(product.get('body_html', ''))
        item['g:link'] = f"{self.base_url}/products/{product['handle']}?variant={variant['id']}"
        
        # ========== IMAGES (MAPPING AREA 2) ==========
        images = product.get('images', [])
        brand = product.get('vendor', '').lower()
        
        if images:
            if 'converse' in brand:
                # Special Converse logic: _INT as main image
                int_image = None
                other_images = []
                
                for img in images:
                    img_src = img.get('src', '')
                    if '_INT' in img_src or '_int' in img_src:
                        int_image = img_src
                    else:
                        other_images.append(img_src)
                
                if int_image:
                    item['g:image_link'] = int_image
                    if other_images:
                        item['g:additional_image_link'] = other_images[:10]
                else:
                    item['g:image_link'] = images[0].get('src', '')
                    additional_images = [img.get('src', '') for img in images[1:11]]
                    if additional_images:
                        item['g:additional_image_link'] = additional_images
            else:
                # Standard image handling
                item['g:image_link'] = images[0].get('src', '')
                additional_images = [img.get('src', '') for img in images[1:11]]
                if additional_images:
                    item['g:additional_image_link'] = additional_images
        
        # ========== PRICING (MAPPING AREA 3) ==========
        compare_at = variant.get('compare_at_price')
        price = float(variant['price'])
        
        if compare_at and float(compare_at) > 0:
            item['g:price'] = f"{float(compare_at):.2f} EUR"
            item['g:sale_price'] = f"{price:.2f} EUR"
        else:
            item['g:price'] = f"{price:.2f} EUR"
        
        # ========== BASIC ATTRIBUTES (MAPPING AREA 4) ==========
        item['g:condition'] = self.static_values.get('condition', 'new')
        item['g:availability'] = 'in stock' if variant.get('inventory_quantity', 0) > 0 else 'out of stock'
        item['g:brand'] = product.get('vendor', 'Racoon Lab')
        
        # ========== FASHION-SPECIFIC FIELDS (MAPPING AREA 5) ==========
        item['g:gender'] = self._get_gender_google(metafield_data)
        item['g:age_group'] = self._get_age_group_google(metafield_data)
        
        # Color - skip if not in metafield
        color = self._get_color_google(metafield_data)
        if color:
            item['g:color'] = color
        
        # ========== GROUPING & IDENTIFIERS (MAPPING AREA 6) ==========
        item['g:item_group_id'] = str(product['id'])
        
        # GTIN from barcode - omit if empty
        barcode = variant.get('barcode', '')
        if barcode and str(barcode).strip():
            item['g:gtin'] = str(barcode).strip()
        
        item['g:mpn'] = variant.get('sku', '')
        
        # ========== CATEGORY & TYPE (MAPPING AREA 7) ==========
        item['g:google_product_category'] = self.static_values.get('google_product_category', '187')
        # Use hierarchical product type: "Calzature > Sneakers > Adidas > Samba"
        item['g:product_type'] = self._build_hierarchical_product_type(product)
        
        # ========== SIZE & MATERIAL & PATTERN (MAPPING AREA 8) ==========
        item['g:size'] = variant.get('option1', '')
        
        # Material - skip if not in metafield
        material = self._get_material_google(metafield_data)
        if material:
            item['g:material'] = material
        
        # Pattern - skip if not found
        pattern = self._get_pattern(tags)
        if pattern:
            item['g:pattern'] = pattern
        
        # ========== PRODUCT DETAILS (MAPPING AREA 9) ==========
        product_details = self._get_product_details_google(product, variant, tags)
        if product_details:
            item['g:product_detail'] = product_details
        
        # ========== CUSTOM LABELS (MAPPING AREA 10) ==========
        # Split collections across custom_label_0 and custom_label_1
        label_0, label_1 = self._split_collections_across_labels(collections)
        item['g:custom_label_0'] = label_0
        item['g:custom_label_1'] = label_1
        item['g:custom_label_2'] = self.static_values.get('custom_label_2', '')
        item['g:custom_label_3'] = self.static_values.get('custom_label_3', '')
        item['g:custom_label_4'] = self.static_values.get('custom_label_4', '')
        
        # ========== ADDITIONAL FIELDS (MAPPING AREA 11) ==========
        item['g:size_system'] = self.static_values.get('size_system', 'IT')
        item['g:is_bundle'] = 'TRUE'  # Shoes sold as pairs
        item['g:product_highlight'] = self._get_product_highlight_google(product, variant, tags)
        item['g:TAGS'] = ', '.join(tags)
        
        # ========== STAR RATING (MAPPING AREA 12) ==========
        star_rating = metafield_data.get('star_rating')
        if star_rating:
            item['g:product_rating'] = str(star_rating)
        
        return item
    
    # ========== GOOGLE-SPECIFIC HELPER METHODS ==========
    
    def _build_title_google(self, product: Dict, variant: Dict, metafield_data: Dict, tags: List[str]) -> str:
        """
        Build optimized Google Shopping title with color and key features
        
        Format: Brand + Model + Color/Features + Taglia
        Example: "Adidas Samba Burgundy Pizzo Nero Taglia 39"
        """
        title_parts = []
        
        # Brand
        brand = product.get('vendor', '')
        if brand:
            title_parts.append(brand)
        
        # Product type/model
        product_type = product.get('product_type', '')
        if product_type:
            title_parts.append(product_type)
        
        # Color from metafields (if available)
        color = metafield_data.get('color', '')
        if color:
            title_parts.append(color)
        
        # Try to extract key features from tags (Burgundy, Pizzo, Kawaii, etc)
        # Look for distinctive color/style keywords in tags
        feature_keywords = ['burgundy', 'bordeaux', 'pizzo', 'kawaii', 'glitter', 
                           'charms', 'fiocco', 'metallizzato', 'vintage', 'patent',
                           'nero', 'bianco', 'rosa', 'blu', 'verde', 'rosso']
        
        features_found = []
        for tag in tags:
            tag_lower = tag.lower().strip()
            # Check if tag contains a feature keyword
            for keyword in feature_keywords:
                if keyword in tag_lower and keyword not in [t.lower() for t in title_parts]:
                    # Add the original tag (capitalized properly)
                    features_found.append(tag.strip())
                    break
        
        # Add max 2 feature tags to avoid too long title
        if features_found:
            title_parts.extend(features_found[:2])
        
        # Size
        size = variant.get('option1', '')
        if size:
            title_parts.append(f"Taglia {size}")
        
        title = ' '.join(title_parts)
        
        # Limit to 150 characters (Google Shopping limit)
        if len(title) > 150:
            title = title[:147] + '...'
        
        return title
    
    def _get_gender_google(self, metafield_data: Dict) -> str:
        """Get gender from metafields with fallback"""
        return metafield_data.get('gender', self.static_values.get('default_gender', 'female'))
    
    def _get_age_group_google(self, metafield_data: Dict) -> str:
        """Get age_group from metafields with fallback"""
        return metafield_data.get('age_group', self.static_values.get('default_age_group', 'adult'))
    
    def _get_color_google(self, metafield_data: Dict) -> str:
        """Get color from metafields"""
        return metafield_data.get('color', '')
    
    def _get_material_google(self, metafield_data: Dict) -> str:
        """Get material from metafields"""
        return metafield_data.get('material', '')
    
    def _get_product_details_google(self, product: Dict, variant: Dict, tags: List[str]) -> List[Dict[str, str]]:
        """Extract structured product details for Google Shopping"""
        handle = product.get('handle', '')
        sku = variant.get('sku', '')
        
        # Try JSON lookup first
        if handle and sku:
            key = (handle, sku)
            if key in self.product_mappings:
                json_details = self.product_mappings[key].get('product_detail', [])
                if json_details:
                    cleaned_details = []
                    for detail in json_details:
                        cleaned_details.append({
                            'attribute_name': detail.get('attribute_name', ''),
                            'attribute_value': detail.get('attribute_value', '')
                        })
                    return cleaned_details
        
        # Fallback: Tag-based extraction
        details = []
        detail_mapping = {
            'suola vintage': {'attribute_name': 'Tipo di Suola', 'attribute_value': 'Vintage'},
            'suola bianca': {'attribute_name': 'Tipo di Suola', 'attribute_value': 'Bianca'},
            'suola nera': {'attribute_name': 'Tipo di Suola', 'attribute_value': 'Nera'},
            'platform': {'attribute_name': 'Tipo di Suola', 'attribute_value': 'Platform'},
            'effetto vintage': {'attribute_name': 'Stile', 'attribute_value': 'Effetto Vintage'},
            'memory foam': {'attribute_name': 'Comfort', 'attribute_value': 'Memory Foam'},
            'impermeabile': {'attribute_name': 'Caratteristiche', 'attribute_value': 'Impermeabile'},
            'traspirante': {'attribute_name': 'Caratteristiche', 'attribute_value': 'Traspirante'}
        }
        
        for tag in tags:
            tag_lower = tag.lower().strip()
            if tag_lower in detail_mapping:
                details.append(detail_mapping[tag_lower])
        
        return details[:3]
    
    def _deduplicate_collections(self, collections: List[str]) -> List[str]:
        """Remove duplicate collections while preserving order"""
        if not collections:
            return []
        
        seen = set()
        unique = []
        
        for collection in collections:
            collection_lower = collection.lower().strip()
            if collection_lower and collection_lower not in seen:
                seen.add(collection_lower)
                unique.append(collection.strip())
        
        return unique
    
    def _split_collections_across_labels(self, collections: List[str], 
                                         label_0_limit: int = 100, 
                                         label_1_limit: int = 500) -> tuple:
        """
        Split Shopify collections across custom_label_0 and custom_label_1
        without cutting or repeating words
        """
        if not collections:
            return ('', '')
        
        unique_collections = self._deduplicate_collections(collections)
        full_text = ', '.join(unique_collections)
        
        if len(full_text) <= label_0_limit:
            return (full_text, '')
        
        label_0_parts = []
        label_1_parts = []
        current_length = 0
        overflow = False
        
        for collection in unique_collections:
            item_length = len(collection) + (2 if current_length > 0 else 0)
            
            if not overflow and current_length + item_length <= label_0_limit:
                label_0_parts.append(collection)
                current_length += item_length
            else:
                overflow = True
                label_1_parts.append(collection)
        
        label_0 = ', '.join(label_0_parts)
        label_1 = ', '.join(label_1_parts)
        
        # Trim label_1 if exceeds limit
        if len(label_1) > label_1_limit:
            label_1_trimmed = []
            current = 0
            for part in label_1_parts:
                part_len = len(part) + (2 if current > 0 else 0)
                if current + part_len <= label_1_limit:
                    label_1_trimmed.append(part)
                    current += part_len
                else:
                    break
            label_1 = ', '.join(label_1_trimmed)
        
        return (label_0, label_1)
    
    def _get_product_highlight_google(self, product: Dict, variant: Dict, tags: List[str]) -> str:
        """Extract key product highlights for Google Shopping"""
        handle = product.get('handle', '')
        sku = variant.get('sku', '')
        
        # Try JSON lookup first
        if handle and sku:
            key = (handle, sku)
            if key in self.product_mappings:
                highlights = self.product_mappings[key].get('product_highlight', [])
                if highlights:
                    return ', '.join(highlights)
        
        # Fallback: Generic highlights
        highlights = []
        brand = product.get('vendor', '')
        if brand:
            highlights.append(f"{brand} Original")
        
        highlights.append("100% Personalizzabili")
        highlights.append("Fatto a mano in Italia")
        
        return ', '.join(highlights)
