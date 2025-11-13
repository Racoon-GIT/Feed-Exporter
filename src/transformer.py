"""
Product Transformer - v3.5 STABLE
Trasforma prodotti Shopify in formato Google Shopping

FILTRI MINIMI:
- Solo products con status='active' (richiesto da Shopify API call)
- NESSUN altro filtro su product_type, tags, titolo, ecc.

FEATURES:
- ✅ Collections support (custom_label_1, custom_label_2)
- ✅ Metafields priority (gender, age_group, color, material)
- ✅ Pattern mapping da DataFeedWatch (55+ patterns)
- ✅ Star ratings da Stamped.io
- ✅ Multiple images (max 10)
- ✅ Shipping dinamico per zona
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
        
        # Load config files
        self.field_mapping = config_loader.field_mapping
        self.tag_categories = config_loader.tag_categories
        self.static_values = config_loader.static_values
        
        # Category mapping (hardcoded - sempre 1856 per footwear)
        self.google_product_category = '1856'  # Footwear
        
        # Pattern mapping completo da DataFeedWatch (55+ patterns)
        self.pattern_mapping = {
            # Italian → English patterns
            'animalier': 'animal print',
            'a pois': 'polka dots',
            'pois': 'polka dots',
            'righe': 'striped',
            'a righe': 'striped',
            'a quadri': 'checkered',
            'quadri': 'checkered',
            'camouflage': 'camouflage',
            'mimetico': 'camouflage',
            'floreale': 'floral',
            'fiori': 'floral',
            'denim': 'denim',
            'jeans': 'denim',
            'vintage': 'vintage',
            'retro': 'vintage',
            'leopardato': 'leopard',
            'zebrato': 'zebra',
            'geometrico': 'geometric',
            'astratto': 'abstract',
            'paisley': 'paisley',
            'tie-dye': 'tie-dye',
            'batik': 'batik',
            'ikat': 'ikat',
            'chevron': 'chevron',
            'zig zag': 'zigzag',
            'zigzag': 'zigzag',
            'damasco': 'damask',
            'medaglione': 'medallion',
            'tropicale': 'tropical',
            'hawaiano': 'hawaiian',
            'nautico': 'nautical',
            'militare': 'military',
            'pied de poule': 'houndstooth',
            'spina di pesce': 'herringbone',
            'tartan': 'tartan',
            'plaid': 'plaid',
            'vichy': 'gingham',
            'jacquard': 'jacquard',
            'broccato': 'brocade',
            'ricamato': 'embroidered',
            'intrecciato': 'woven',
            'matelassé': 'quilted',
            'patchwork': 'patchwork',
            'color block': 'color block',
            'gradient': 'ombre',
            'sfumato': 'ombre',
            'marmorizzato': 'marbled',
            'macchiato': 'spotted',
            'stelle': 'stars',
            'cuori': 'hearts',
            'lettere': 'letters',
            'numeri': 'numbers',
            'logo': 'logo',
            'grafico': 'graphic',
            'slogan': 'slogan',
            'cartoon': 'cartoon',
            'fumetti': 'comic',
        }
    
    def transform_product(self, product: Dict, metafields: Dict, collections: Optional[List[str]] = None) -> List[Dict]:
        """
        Transform ONE Shopify product into Google Shopping items (one per variant)
        
        FILTRO UNICO: status='active' (già applicato nella API call di Shopify)
        
        Args:
            product: Shopify product dict
            metafields: Product metafields dict
            collections: Optional list of collection titles (default: empty list)
        """
        items = []
        tags = product.get('tags', '').split(', ') if isinstance(product.get('tags'), str) else product.get('tags', [])
        
        # Default to empty list if not provided (backward compatibility)
        if collections is None:
            collections = []
        
        for variant in product.get('variants', []):
            item = self.transform_variant(product, variant, tags, metafields, collections)
            items.append(item)
            
        return items
    
    def transform_variant(self, product: Dict, variant: Dict, tags: List[str], 
                         metafields: Dict, collections: List[str]) -> Dict:
        """Transform single variant to Google Shopping item with all required fields"""
        
        # Extract metafields
        meta = self._extract_metafields(metafields)
        
        # Build item ID and link
        item_id = str(variant.get('id', ''))
        product_handle = product.get('handle', '')
        link = f"{self.base_url}/products/{product_handle}?variant={item_id}"
        
        # Get images
        images = self._get_images(product, variant)
        
        # Get title (remove "- Taglia X" for cleaner titles)
        title = self._clean_title(product.get('title', ''), variant)
        
        # Get brand
        brand = product.get('vendor', 'Racoon Lab')
        
        # Get price
        price = self._format_price(variant.get('price', '0'))
        
        # Get availability
        availability = self._get_availability(variant)
        
        # Get shipping
        shipping = self._get_shipping(price)
        
        # Get star rating from metafields
        product_rating = meta.get('product_rating', '')
        
        # Get gender (PRIORITY: metafield → default 'female')
        gender = meta.get('gender', self.static_values.get('default_gender', 'female'))
        
        # Get age_group (PRIORITY: metafield → default 'adult')
        age_group = meta.get('age_group', self.static_values.get('default_age_group', 'adult'))
        
        # Get color (PRIORITY: metafield → tag extraction → OMIT)
        color = meta.get('color') or self._extract_color(tags) or None
        
        # Get material (PRIORITY: metafield → OMIT)
        material = meta.get('material') or None
        
        # Get pattern (from tags using DataFeedWatch mapping)
        pattern = self._extract_pattern(tags)
        
        # Get product_detail (from tags or metafield)
        product_detail = self._extract_product_detail(tags, meta)
        
        # Get custom_label_0 (ALL tags)
        custom_label_0 = self._format_custom_label_0(tags)
        
        # Get custom_label_1 and custom_label_2 (Collections split)
        custom_label_1, custom_label_2 = self._split_collections(collections)
        
        # Get custom_label_3 (Gender + Category)
        custom_label_3 = f"{gender}|{self.google_product_category}"
        
        # Get custom_label_4 (Brand)
        custom_label_4 = brand
        
        # Build Google Shopping item
        item = {
            'id': item_id,
            'title': title,
            'description': self._clean_description(product.get('body_html', '')),
            'link': link,
            'image_link': images[0] if images else '',
            'additional_image_link': ','.join(images[1:11]) if len(images) > 1 else '',  # Max 10 additional
            'availability': availability,
            'price': price,
            'brand': brand,
            'condition': 'new',
            'google_product_category': self.google_product_category,
            'product_type': product.get('product_type', ''),
            'shipping': shipping,
            'gender': gender,
            'age_group': age_group,
            'item_group_id': str(product.get('id', '')),
        }
        
        # Add optional fields only if they exist
        if color:
            item['color'] = color
        if material:
            item['material'] = material
        if pattern:
            item['pattern'] = pattern
        if product_detail:
            item['product_detail'] = product_detail
        if product_rating:
            item['product_rating'] = product_rating
        
        # Add custom labels
        item['custom_label_0'] = custom_label_0
        if custom_label_1:
            item['custom_label_1'] = custom_label_1
        if custom_label_2:
            item['custom_label_2'] = custom_label_2
        item['custom_label_3'] = custom_label_3
        item['custom_label_4'] = custom_label_4
        
        # Add size if available
        size = variant.get('option1') or variant.get('option2') or variant.get('option3')
        if size and size != 'Default Title':
            item['size'] = size
        
        # Add GTIN if available
        if variant.get('barcode'):
            item['gtin'] = variant.get('barcode')
        
        # Add MPN (use SKU or variant ID)
        item['mpn'] = variant.get('sku') or item_id
        
        return item
    
    def _extract_metafields(self, metafields: Dict) -> Dict:
        """Extract relevant metafields from mm-google-shopping namespace"""
        meta = {}
        
        if not metafields:
            return meta
        
        # Extract from mm-google-shopping namespace
        mm_fields = metafields.get('mm-google-shopping', {})
        
        # Map metafield keys to our keys
        field_mapping = {
            'gender': 'gender',
            'age_group': 'age_group',
            'color': 'color',
            'material': 'material',
            'pattern': 'pattern',
            'product_detail': 'product_detail',
        }
        
        for our_key, mm_key in field_mapping.items():
            if mm_key in mm_fields:
                value = mm_fields[mm_key]
                if value and value.strip():
                    meta[our_key] = value.strip()
        
        # Extract star rating from stamped namespace
        stamped = metafields.get('stamped', {}) or metafields.get('reviews', {})
        if stamped:
            rating = stamped.get('rating') or stamped.get('average_rating')
            if rating:
                try:
                    rating_float = float(rating)
                    if 0 <= rating_float <= 5:
                        meta['product_rating'] = f"{rating_float:.1f}"
                except (ValueError, TypeError):
                    pass
        
        return meta
    
    def _clean_title(self, title: str, variant: Dict) -> str:
        """Clean product title by removing size suffix like '- Taglia 37'"""
        # Remove "- Taglia X" pattern
        title = re.sub(r'\s*-\s*Taglia\s+\d+(\.\d+)?', '', title, flags=re.IGNORECASE)
        
        # Limit to 150 characters for Google Shopping
        if len(title) > 150:
            title = title[:147] + '...'
        
        return title.strip()
    
    def _get_images(self, product: Dict, variant: Dict) -> List[str]:
        """Get all images for this product (product image + variant image + additional)"""
        images = []
        
        # 1. Add main product image
        if product.get('image', {}).get('src'):
            images.append(product['image']['src'])
        
        # 2. Add variant-specific image if different from main
        if variant.get('image_id') and variant.get('image_id') != product.get('image', {}).get('id'):
            # Find variant image in product images
            for img in product.get('images', []):
                if img.get('id') == variant.get('image_id'):
                    if img['src'] not in images:
                        images.append(img['src'])
                    break
        
        # 3. Add additional product images (up to 10 total)
        for img in product.get('images', []):
            if img.get('src') and img['src'] not in images:
                images.append(img['src'])
                if len(images) >= 11:  # 1 main + 10 additional
                    break
        
        return images
    
    def _format_price(self, price: str) -> str:
        """Format price for Italian market: 123.45 EUR"""
        try:
            price_float = float(price)
            return f"{price_float:.2f} EUR"
        except (ValueError, TypeError):
            return "0.00 EUR"
    
    def _get_availability(self, variant: Dict) -> str:
        """Get availability status"""
        inventory_quantity = variant.get('inventory_quantity', 0)
        
        if inventory_quantity > 0:
            return 'in stock'
        elif inventory_quantity == 0:
            return 'out of stock'
        else:
            return 'preorder'
    
    def _get_shipping(self, price: str) -> str:
        """Calculate shipping cost based on price (Italian market rules)"""
        try:
            price_float = float(price.split()[0])
            
            # Italian shipping rules
            if price_float >= 89:
                return "IT:::0.00 EUR"  # Free shipping
            elif price_float >= 30:
                return "IT:::10.00 EUR"
            else:
                return "IT:::6.00 EUR"
        except (ValueError, IndexError, AttributeError):
            return "IT:::10.00 EUR"  # Default
    
    def _extract_color(self, tags: List[str]) -> Optional[str]:
        """Extract color from tags using tag_categories mapping"""
        colors_map = self.tag_categories.get('colors', {})
        
        for tag in tags:
            tag_lower = tag.lower().strip()
            if tag_lower in colors_map:
                return colors_map[tag_lower]
        
        return None
    
    def _extract_pattern(self, tags: List[str]) -> Optional[str]:
        """Extract pattern from tags using DataFeedWatch mapping"""
        for tag in tags:
            tag_lower = tag.lower().strip()
            if tag_lower in self.pattern_mapping:
                return self.pattern_mapping[tag_lower]
        
        return None
    
    def _extract_product_detail(self, tags: List[str], meta: Dict) -> Optional[str]:
        """Extract product_detail from tags or metafield"""
        # Check metafield first
        if 'product_detail' in meta:
            return meta['product_detail']
        
        # Extract from tags (examples: "Platform", "High Top", "Slip-On")
        detail_keywords = ['platform', 'high top', 'slip-on', 'slip on', 'lace-up', 'lace up']
        
        for tag in tags:
            tag_lower = tag.lower().strip()
            for keyword in detail_keywords:
                if keyword in tag_lower:
                    return keyword.title()
        
        return None
    
    def _format_custom_label_0(self, tags: List[str]) -> str:
        """Format custom_label_0 with ALL Shopify tags (no filtering)"""
        if not tags:
            return ""
        
        # Join all tags with pipe separator
        label = '|'.join(tag.strip() for tag in tags if tag.strip())
        
        # Limit to 1000 characters (Google Shopping limit)
        if len(label) > 1000:
            label = label[:997] + '...'
        
        return label
    
    def _split_collections(self, collections: List[str]) -> tuple:
        """
        Split Shopify collections intelligently between custom_label_1 and custom_label_2
        
        Algorithm:
        1. Join collections with ' | ' separator
        2. Split at 500 chars without cutting words
        3. No repeated content between labels
        
        Args:
            collections: List of collection titles from Shopify
        
        Returns:
            tuple: (custom_label_1, custom_label_2)
        """
        if not collections:
            return ("", "")
        
        # Join all collections
        full_text = ' | '.join(collections)
        
        # If total length <= 500, all in label_1
        if len(full_text) <= 500:
            return (full_text, "")
        
        # Find split point without cutting words
        split_point = 500
        while split_point > 0 and full_text[split_point] not in (' ', '|'):
            split_point -= 1
        
        # If we can't find a good split point, just cut at 497
        if split_point < 400:
            split_point = 497
        
        label_1 = full_text[:split_point].rstrip(' |')
        label_2 = full_text[split_point:].lstrip(' |')
        
        # Limit label_2 to 1000 chars (Google limit)
        if len(label_2) > 1000:
            label_2 = label_2[:997] + '...'
        
        return (label_1, label_2)
    
    def _clean_description(self, html_text: str) -> str:
        """Clean HTML description for Google Shopping"""
        if not html_text:
            return ""
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html_text)
        
        # Decode HTML entities
        text = html.unescape(text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Limit to 5000 characters (Google Shopping limit)
        if len(text) > 5000:
            text = text[:4997] + '...'
        
        return text
