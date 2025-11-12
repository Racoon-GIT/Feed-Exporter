"""
Product Transformer - Memory Optimized with All Fixes Applied
Transforms Shopify products to Google Shopping feed format
"""

import logging
from typing import Dict, List, Optional
import re
import html

logger = logging.getLogger(__name__)


class ProductTransformer:
    def __init__(self, config_loader, base_url: str):
        self.config = config_loader
        self.base_url = base_url.rstrip('/')
        
        # Load configuration
        self.shipping_config = self.config.get_shipping_config()
        self.category_mapping = self.config.get_category_mapping()
        self.static_values = self.config.get_static_values()
        
        # Pattern mapping from DFW
        self.pattern_mapping = {
            # Original DFW patterns
            'animalier': 'animal print',
            'a pois': 'polka dots',
            'righe': 'striped',
            'a quadri': 'checkered',
            'camouflage': 'camouflage',
            'floreale': 'floral',
            'paisley': 'paisley',
            'geometrico': 'geometric',
            'astratto': 'abstract',
            'tie-dye': 'tie-dye',
            'stampa digitale': 'graphic print',
            'patchwork': 'patchwork',
            'ricamato': 'embroidered',
            'jacquard': 'jacquard',
            'damasco': 'damask',
            'chevron': 'chevron',
            'houndstooth': 'houndstooth',
            'vichy': 'gingham',
            'pied de poule': 'houndstooth',
            'batik': 'batik',
            'ombre': 'ombre',
            'marmorizzato': 'marbled',
            'splash': 'splatter',
            'logo': 'logo',
            'testo': 'text print',
            'glitter': 'glitter',
            'metalizzato': 'metallic',
            'olografico': 'holographic',
            'paillettes': 'sequined',
            'perle': 'pearl',
            'strass': 'rhinestone',
            'lacci': 'lace',
            'pizzo': 'lace',
            'tulle': 'tulle',
            'velluto': 'velvet',
            'pelliccia': 'fur',
            'pelle di serpente': 'snakeskin',
            'coccodrillo': 'crocodile',
            'denim': 'denim',
            'jeans': 'denim',
            'tartan': 'tartan',
            'militare': 'military',
            'nautical': 'nautical',
            'tropicale': 'tropical',
            'vintage': 'vintage',
            'retrò': 'retro',
            'boho': 'bohemian',
            'etnico': 'ethnic',
            'tribale': 'tribal',
            'orientale': 'oriental',
            'gotico': 'gothic',
            'punk': 'punk',
            'grunge': 'grunge',
            'street': 'street art',
            'pop art': 'pop art',
            'minimal': 'minimalist',
            'color block': 'color block'
        }
    
    def transform_product(self, product: Dict, metafields: Dict) -> List[Dict]:
        """
        Transform ONE Shopify product with metafields into Google Shopping items
        Returns list of items (one per variant)
        """
        # FILTER 1: Check if product is active
        if product.get('status') != 'active':
            return []  # Skip this product entirely
        
        # FILTER 2: Check if product has at least one variant with stock
        if not self._has_available_stock(product):
            return []  # Skip product if all variants are out of stock
        
        items = []
        tags = product.get('tags', '').split(', ') if isinstance(product.get('tags'), str) else product.get('tags', [])
        collections = product.get('collections', [])  # Added: collections from main.py
        
        for variant in product.get('variants', []):
            # FILTER 3: Skip variants with "personalizzazione" in title
            if self._should_exclude_variant(variant, product):
                continue
            
            item = self.transform_variant(product, variant, tags, metafields, collections)
            items.append(item)
            
        return items
    
    def transform_variant(self, product: Dict, variant: Dict, tags: List[str], 
                         metafields: Dict, collections: List[str]) -> Dict:
        """Transform single variant to Google Shopping item with all fixes applied"""
        
        # Extract metafields once
        metafields_dict = self._extract_metafields(metafields.get('metafields', []))
        
        # Build item
        item = {}
        
        # Required fields
        item['g:id'] = str(variant['id'])
        item['g:title'] = self._build_title(product, variant)
        item['g:description'] = self._get_description(product)
        item['g:link'] = self._build_product_url(product, variant)
        item['g:image_link'] = self._get_main_image(product, variant)
        
        # Additional images
        additional_images = self._get_additional_images(product, variant)
        for i, img_url in enumerate(additional_images[:10], 1):
            item[f'g:additional_image_link_{i}'] = img_url
        
        # Price and availability
        item['g:price'] = f"{variant['price']} EUR"
        if variant.get('compare_at_price'):
            item['g:sale_price'] = f"{variant['price']} EUR"
        
        item['g:availability'] = self._get_availability(variant)
        
        # Identifiers
        item['g:condition'] = 'new'
        item['g:brand'] = self._get_metafield_value(metafields_dict, 'brand') or product.get('vendor', 'Racoon Lab')
        if variant.get('gtin'):
            item['g:gtin'] = variant['gtin']
        item['g:mpn'] = str(variant.get('sku', variant['id']))
        
        # Categorization - Use metafield or category mapping
        item['g:google_product_category'] = self._get_google_category(product, tags, metafields_dict)
        item['g:product_type'] = self._get_product_type(product, tags, metafields_dict)
        
        # Gender - FIXED: Use metafield, default 'female'
        item['g:gender'] = self._get_metafield_value(metafields_dict, 'gender') or 'female'
        
        # Age group - FIXED: Use metafield, default 'adult'
        item['g:age_group'] = self._get_metafield_value(metafields_dict, 'age_group') or 'adult'
        
        # Color - FIXED: Use metafield or OMIT
        color = self._get_metafield_value(metafields_dict, 'color') or self._extract_color_from_tags(tags)
        if color:
            item['g:color'] = color
        
        # Material - FIXED: Use metafield or OMIT
        material = self._get_metafield_value(metafields_dict, 'material')
        if material:
            item['g:material'] = material
        
        # Pattern - FIXED: Use DFW table
        pattern = self._get_pattern_from_metafield_or_tags(metafields_dict, tags)
        if pattern:
            item['g:pattern'] = pattern
        
        # Size
        if variant.get('option1') and 'Taglia' not in variant['option1']:
            item['g:size'] = variant['option1']
        elif variant.get('option2'):
            item['g:size'] = variant['option2']
        
        # Shipping
        item['g:shipping_weight'] = f"{variant.get('weight', 1)} {variant.get('weight_unit', 'kg')}"
        
        # Custom Labels - FIXED: Use collections with smart split
        item['g:custom_label_0'] = self._get_custom_label_0(tags)
        
        # Split collections across custom_label_1 and custom_label_2
        label_1, label_2 = self._split_collections_across_labels(collections)
        item['g:custom_label_1'] = label_1
        item['g:custom_label_2'] = label_2
        
        item['g:custom_label_3'] = self.static_values.get('custom_label_3', '')
        item['g:custom_label_4'] = self.static_values.get('custom_label_4', '')
        
        # Product highlights
        item['g:product_highlight'] = self._get_product_highlight(product, tags)
        
        # Reviews/Ratings - Extract from Stamped.io metafields
        rating_data = self._extract_rating_from_metafields(metafields_dict)
        if rating_data:
            item['g:product_rating'] = rating_data['rating']
            item['g:product_review_count'] = rating_data['count']
        
        # Additional details
        item['g:item_group_id'] = str(product['id'])
        
        return item
    
    def _split_collections_across_labels(self, collections: List[str], max_length: int = 500) -> tuple:
        """
        Split Shopify collections across custom_label_1 and custom_label_2
        without cutting or repeating words
        
        Args:
            collections: List of collection names from Shopify
            max_length: Max characters per label (Google Shopping limit is 500)
        
        Returns:
            (label_1, label_2) tuple
        """
        if not collections:
            return ('', '')
        
        # Join all collections with delimiter
        full_text = ', '.join(collections)
        
        # If everything fits in label_1, done
        if len(full_text) <= max_length:
            return (full_text, '')
        
        # Otherwise, split smartly without cutting words
        label_1_parts = []
        label_2_parts = []
        current_length = 0
        overflow = False
        
        for collection in collections:
            # Calculate length with delimiter (", ")
            # +2 for ", " delimiter, but not for the first item
            item_length = len(collection) + (2 if current_length > 0 else 0)
            
            if not overflow and current_length + item_length <= max_length:
                # Fits in label_1
                label_1_parts.append(collection)
                current_length += item_length
            else:
                # Goes to label_2
                overflow = True
                label_2_parts.append(collection)
        
        label_1 = ', '.join(label_1_parts)
        label_2 = ', '.join(label_2_parts)
        
        # Trim label_2 if it exceeds max_length (rare case with very long collection names)
        if len(label_2) > max_length:
            # Find last complete collection that fits
            label_2_trimmed = []
            current = 0
            for part in label_2_parts:
                part_len = len(part) + (2 if current > 0 else 0)
                if current + part_len <= max_length:
                    label_2_trimmed.append(part)
                    current += part_len
                else:
                    break
            label_2 = ', '.join(label_2_trimmed)
        
        return (label_1, label_2)
    
    def _get_custom_label_0(self, tags: List[str]) -> str:
        """Return ALL Shopify tags, comma separated - FIXED"""
        return ', '.join(tags) if tags else ''
    
    def _get_pattern_from_metafield_or_tags(self, metafields_dict: Dict, tags: List[str]) -> str:
        """Get pattern using DFW mapping table - FIXED"""
        # Priority 1: Metafield
        metafield_pattern = self._get_metafield_value(metafields_dict, 'pattern')
        if metafield_pattern:
            # Check if it's in Italian, translate it
            pattern_lower = metafield_pattern.lower()
            return self.pattern_mapping.get(pattern_lower, metafield_pattern)
        
        # Priority 2: Extract from tags using DFW mapping
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower in self.pattern_mapping:
                return self.pattern_mapping[tag_lower]
        
        # Priority 3: Omit field
        return ''
    
    def _extract_metafields(self, metafields_list: List[Dict]) -> Dict:
        """Convert metafields list to easy-access dict"""
        result = {}
        
        for mf in metafields_list:
            namespace = mf.get('namespace', '')
            key = mf.get('key', '')
            value = mf.get('value', '')
            
            # Google Shopping metafields
            if namespace == 'mm-google-shopping':
                result[key] = value
            
            # Reviews metafields (Stamped.io, Judge.me, Loox)
            elif namespace in ['stamped', 'reviews', 'judgeme', 'loox']:
                if key in ['reviews_average', 'rating', 'avg_rating']:
                    result['reviews_average'] = value
                elif key in ['reviews_count', 'count', 'review_count']:
                    result['reviews_count'] = value
        
        return result
    
    def _get_metafield_value(self, metafields_dict: Dict, key: str) -> Optional[str]:
        """Get metafield value by key"""
        return metafields_dict.get(key)
    
    def _build_title(self, product: Dict, variant: Dict) -> str:
        """Build product title - OPTIMIZED: Remove 'Taglia' word"""
        base_title = product.get('title', 'Prodotto')
        
        # Add variant option if exists and is not 'Default Title'
        if variant.get('option1') and variant['option1'] != 'Default Title':
            option = variant['option1']
            # Remove "Taglia" word (case insensitive)
            option = re.sub(r'\bTaglia\b\s*', '', option, flags=re.IGNORECASE).strip()
            if option:
                return f"{base_title} - {option}"
        
        return base_title
    
    def _get_description(self, product: Dict) -> str:
        """Get clean product description"""
        desc = product.get('body_html', '')
        # Remove HTML tags
        clean_desc = self._clean_html(desc)
        # Limit to 5000 chars (Google Shopping limit)
        return clean_desc[:5000] if clean_desc else product.get('title', '')
    
    def _clean_html(self, html_text: str) -> str:
        """Remove HTML tags and decode entities"""
        if not html_text:
            return ''
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html_text)
        # Decode HTML entities
        text = html.unescape(text)
        # Remove extra whitespace
        text = ' '.join(text.split())
        return text.strip()
    
    def _build_product_url(self, product: Dict, variant: Dict) -> str:
        """Build product URL with variant"""
        handle = product.get('handle', '')
        variant_id = variant.get('id', '')
        return f"{self.base_url}/products/{handle}?variant={variant_id}"
    
    def _get_main_image(self, product: Dict, variant: Dict) -> str:
        """Get main product image"""
        # Try variant image first
        if variant.get('image_id'):
            for img in product.get('images', []):
                if img.get('id') == variant['image_id']:
                    return img.get('src', '')
        
        # Fallback to first product image
        images = product.get('images', [])
        if images:
            return images[0].get('src', '')
        
        return ''
    
    def _get_additional_images(self, product: Dict, variant: Dict) -> List[str]:
        """Get additional product images (max 10)"""
        images = []
        main_image_id = variant.get('image_id') or (product.get('images', [{}])[0].get('id') if product.get('images') else None)
        
        for img in product.get('images', []):
            if img.get('id') != main_image_id:
                images.append(img.get('src', ''))
                if len(images) >= 10:
                    break
        
        return images
    
    def _get_availability(self, variant: Dict) -> str:
        """Determine product availability"""
        if not variant.get('available', True):
            return 'out of stock'
        
        inventory_quantity = variant.get('inventory_quantity', 0)
        inventory_policy = variant.get('inventory_policy', 'deny')
        
        if inventory_policy == 'continue':
            return 'in stock'
        
        if inventory_quantity and inventory_quantity > 0:
            return 'in stock'
        
        return 'out of stock'
    
    def _get_google_category(self, product: Dict, tags: List[str], metafields_dict: Dict) -> str:
        """Get Google product category"""
        # Priority 1: Metafield
        metafield_cat = self._get_metafield_value(metafields_dict, 'google_product_category')
        if metafield_cat:
            return metafield_cat
        
        # Priority 2: Category mapping from config
        product_type = product.get('product_type', '').lower()
        for category_key, category_id in self.category_mapping.items():
            if category_key.lower() in product_type:
                return category_id
        
        # Priority 3: Static value
        return self.static_values.get('google_product_category', '1856')
    
    def _get_product_type(self, product: Dict, tags: List[str], metafields_dict: Dict) -> str:
        """Get product type"""
        # Priority 1: Metafield
        metafield_type = self._get_metafield_value(metafields_dict, 'product_type')
        if metafield_type:
            return metafield_type
        
        # Priority 2: Shopify product_type
        return product.get('product_type', 'Sneakers')
    
    def _extract_color_from_tags(self, tags: List[str]) -> str:
        """Extract color from tags"""
        color_keywords = [
            'Nero', 'Bianco', 'Rosso', 'Blu', 'Verde', 'Giallo', 
            'Rosa', 'Viola', 'Arancione', 'Grigio', 'Marrone', 
            'Beige', 'Oro', 'Argento', 'Multicolore'
        ]
        
        for tag in tags:
            for color in color_keywords:
                if color.lower() in tag.lower():
                    return color
        
        return ''
    
    def _get_product_highlight(self, product: Dict, tags: List[str]) -> str:
        """Extract key product highlights"""
        highlights = []
        
        # Add from tags
        highlight_keywords = ['Personalizzate', 'Edizione Limitata', 'Made in Italy', 'Artigianale']
        for tag in tags:
            for keyword in highlight_keywords:
                if keyword.lower() in tag.lower():
                    highlights.append(tag)
                    break
        
        # Limit to first 3
        return ', '.join(highlights[:3]) if highlights else ''
    
    def _extract_rating_from_metafields(self, metafields_dict: Dict) -> Optional[Dict]:
        """Extract review rating and count from metafields"""
        rating = metafields_dict.get('reviews_average')
        count = metafields_dict.get('reviews_count')
        
        if rating and count:
            try:
                return {
                    'rating': str(float(rating)),
                    'count': str(int(count))
                }
            except (ValueError, TypeError):
                pass
        
        return None
    
    def _has_available_stock(self, product: Dict) -> bool:
        """Check if product has at least one variant with available stock"""
        for variant in product.get('variants', []):
            if variant.get('available', False):
                return True
            
            # Check inventory
            if variant.get('inventory_policy') == 'continue':
                return True
            
            if variant.get('inventory_quantity', 0) > 0:
                return True
        
        return False
    
    def _should_exclude_variant(self, variant: Dict, product: Dict) -> bool:
        """Check if variant should be excluded (contains 'personalizzazione')"""
        title = product.get('title', '').lower()
        variant_title = variant.get('title', '').lower()
        option1 = (variant.get('option1') or '').lower()
        
        exclude_keywords = ['personalizzazione', 'customization']
        
        for keyword in exclude_keywords:
            if keyword in title or keyword in variant_title or keyword in option1:
                return True
        
        return False
