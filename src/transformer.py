"""
Product Transformer - Converts Shopify products to Google Shopping format
Version: 3.0 - With Star Rating & Multiple Images
"""

import re
from datetime import datetime
from typing import Dict, List, Any, Optional


class ProductTransformer:
    def __init__(self, config_loader, base_url: str):
        self.config = config_loader
        self.base_url = base_url
        self.field_mapping = config_loader.field_mapping
        self.tag_categories = config_loader.tag_categories
        self.static_values = config_loader.static_values
        
    def transform_product(self, product: Dict, metafields: Optional[Dict] = None) -> List[Dict]:
        """Transform a Shopify product into Google Shopping items (one per variant)"""
        items = []
        tags = product.get('tags', '').split(', ') if isinstance(product.get('tags'), str) else product.get('tags', [])
        
        for variant in product.get('variants', []):
            item = self.transform_variant(product, variant, tags, metafields)
            items.append(item)
            
        return items
    
    def transform_variant(self, product: Dict, variant: Dict, tags: List[str], metafields: Optional[Dict] = None) -> Dict:
        """Transform a single variant into a Google Shopping item"""
        item = {}
        
        # Priority: Metafields > Tag extraction > Static values
        metafield_data = self._extract_metafields(metafields) if metafields else {}
        
        # Core fields
        item['g:id'] = str(variant['id'])
        item['g:title'] = self._build_title(product, variant)
        item['g:description'] = self._clean_html(product.get('body_html', ''))
        item['g:link'] = f"{self.base_url}/products/{product['handle']}?variant={variant['id']}"
        
        # Images - MULTIPLE IMAGES SUPPORT
        images = product.get('images', [])
        if images:
            item['g:image_link'] = images[0].get('src', '')
            # Add up to 10 additional images
            additional_images = [img.get('src', '') for img in images[1:11]]
            if additional_images:
                item['g:additional_image_link'] = additional_images
        
        # Pricing
        item['g:price'] = f"{float(variant['price']):.2f} EUR"
        if variant.get('compare_at_price'):
            item['g:sale_price'] = f"{float(variant['price']):.2f} EUR"
            
        # Basic attributes
        item['g:condition'] = self.static_values.get('condition', 'new')
        item['g:availability'] = 'in stock' if variant.get('inventory_quantity', 0) > 0 else 'out of stock'
        item['g:brand'] = product.get('vendor', 'Racoon Lab')
        
        # Fashion-specific fields
        item['g:gender'] = self._get_gender(tags, metafield_data)
        item['g:age_group'] = self.static_values.get('age_group', 'adult')
        item['g:color'] = self._get_color(product, tags, metafield_data)
        
        # Grouping
        item['g:item_group_id'] = str(product['id'])
        
        # Identifiers
        item['g:gtin'] = variant.get('barcode', '')
        item['g:mpn'] = variant.get('sku', '')
        
        # Category
        item['g:google_product_category'] = self.static_values.get('google_product_category', '187')
        item['g:product_type'] = product.get('product_type', '')
        
        # Size
        item['g:size'] = variant.get('option1', '')
        
        # Material & Pattern
        item['g:material'] = self._get_material(product, tags, metafield_data)
        item['g:pattern'] = self._get_pattern(product, tags, metafield_data)
        
        # Product Details (structured attributes)
        product_details = self._get_product_details(tags)
        if product_details:
            item['g:product_detail'] = product_details
        
        # Custom Labels
        item['g:custom_label_0'] = self._get_custom_label_0(tags)
        item['g:custom_label_1'] = self._get_custom_label_1(product, tags, variant)
        item['g:custom_label_2'] = self.static_values.get('custom_label_2', '')
        item['g:custom_label_3'] = self.static_values.get('custom_label_3', '')
        item['g:custom_label_4'] = self.static_values.get('custom_label_4', '')
        
        # Size system
        item['g:size_system'] = self.static_values.get('size_system', 'IT')
        
        # Bundle (shoes are always sold as pairs)
        item['g:is_bundle'] = 'TRUE'
        
        # Product Highlight
        item['g:product_highlight'] = self._get_product_highlight(product, tags)
        
        # Shipping
        shipping_cost = self._calculate_shipping(float(variant['price']))
        item['g:shipping'] = f"IT:::{shipping_cost:.2f} EUR"
        
        # Tax
        item['g:tax'] = "IT::22.00:yes"
        
        # TAGS (for internal tracking)
        item['g:TAGS'] = ', '.join(tags)
        
        # ⭐ STAR RATING - NEW in v3.0
        rating_data = self._get_product_rating(metafield_data)
        if rating_data:
            item['g:product_rating'] = rating_data['rating']
            item['g:product_review_count'] = rating_data['count']
        
        return item
    
    def _extract_metafields(self, metafields: Dict) -> Dict:
        """Extract metafields into a flat dictionary"""
        data = {}
        for mf in metafields.get('metafields', []):
            namespace = mf.get('namespace', '')
            key = mf.get('key', '')
            value = mf.get('value', '')
            
            # Google Shopping metafields
            if namespace == 'mm-google-shopping':
                data[key] = value
            
            # Stamped.io review metafields
            elif namespace == 'stamped':
                if key in ['reviews_average', 'reviews_count', 'rating', 'count']:
                    data[key] = value
            
            # Other review app namespaces
            elif namespace == 'reviews':
                data[key] = value
                
        return data
    
    def _build_title(self, product: Dict, variant: Dict) -> str:
        """Build optimized title"""
        title = product.get('title', '')
        size = variant.get('option1', '')
        
        if size:
            title = f"{title} - Taglia {size}"
            
        return title[:150]
    
    def _clean_html(self, html: str) -> str:
        """Remove HTML tags and clean text"""
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text)
        text = text.replace('&quot;', '"').replace('&amp;', '&')
        text = text.replace('&#39;', "'").replace('&lt;', '<').replace('&gt;', '>')
        return text.strip()[:5000]
    
    def _get_gender(self, tags: List[str], metafield_data: Dict) -> str:
        """Extract gender from metafields or tags"""
        # Priority 1: Metafield
        if 'gender' in metafield_data:
            return metafield_data['gender'].lower()
        
        # Priority 2: Tags
        gender_mapping = {
            'donna': 'female',
            'donne': 'female',
            'female': 'female',
            'uomo': 'male',
            'uomini': 'male',
            'male': 'male',
            'unisex': 'unisex'
        }
        
        for tag in tags:
            tag_lower = tag.lower().strip()
            if tag_lower in gender_mapping:
                return gender_mapping[tag_lower]
        
        # Default: female (based on store data)
        return 'female'
    
    def _get_color(self, product: Dict, tags: List[str], metafield_data: Dict) -> str:
        """Extract color from metafields, tags, or product title"""
        # Priority 1: Metafield
        if 'color' in metafield_data:
            return metafield_data['color']
        
        # Priority 2: Color keywords in tags
        color_keywords = {
            'nero': 'Nero',
            'bianco': 'Bianco',
            'rosso': 'Rosso',
            'blu': 'Blu',
            'azzurro': 'Azzurro',
            'verde': 'Verde',
            'giallo': 'Giallo',
            'arancione': 'Arancione',
            'rosa': 'Rosa',
            'viola': 'Viola',
            'marrone': 'Marrone',
            'grigio': 'Grigio',
            'beige': 'Beige',
            'bordeaux': 'Bordeaux',
            'burgundy': 'Bordeaux',
            'oro': 'Oro',
            'argento': 'Argento'
        }
        
        colors_found = []
        for tag in tags:
            tag_lower = tag.lower().strip()
            for keyword, color_name in color_keywords.items():
                if keyword in tag_lower:
                    colors_found.append(color_name)
        
        # Priority 3: Extract from title
        if not colors_found:
            title_lower = product.get('title', '').lower()
            for keyword, color_name in color_keywords.items():
                if keyword in title_lower:
                    colors_found.append(color_name)
        
        return '/'.join(colors_found[:3]) if colors_found else 'Multicolore'
    
    def _get_material(self, product: Dict, tags: List[str], metafield_data: Dict) -> str:
        """Extract material from metafields, tags, or description"""
        # Priority 1: Metafield
        if 'material' in metafield_data:
            return metafield_data['material']
        
        # Priority 2: Tags
        material_mapping = {
            'pelle': 'Vera pelle',
            'leather': 'Vera pelle',
            'scamosciata': 'Pelle scamosciata',
            'suede': 'Pelle scamosciata',
            'tela': 'Tela',
            'canvas': 'Tela',
            'tessuto': 'Tessuto',
            'sintetico': 'Materiale sintetico',
            'denim': 'Denim',
            'jeans': 'Denim'
        }
        
        for tag in tags:
            tag_lower = tag.lower().strip()
            for keyword, material in material_mapping.items():
                if keyword in tag_lower:
                    return material
        
        # Priority 3: Check description
        description = product.get('body_html', '').lower()
        for keyword, material in material_mapping.items():
            if keyword in description:
                return material
        
        return 'Vera pelle'
    
    def _get_pattern(self, product: Dict, tags: List[str], metafield_data: Dict) -> str:
        """Extract pattern from metafields, tags, title or description"""
        # Priority 1: Metafield
        if 'pattern' in metafield_data:
            return metafield_data['pattern']
        
        # Priority 2: Tags
        pattern_keywords = {
            'mimetico': 'Mimetico',
            'camouflage': 'Mimetico',
            'floreale': 'Floreale',
            'fiori': 'Floreale',
            'righe': 'A righe',
            'strisce': 'A righe',
            'pois': 'A pois',
            'animalier': 'Animalier',
            'leopardato': 'Leopardato',
            'zebrato': 'Zebrato',
            'geometrico': 'Geometrico',
            'tinta unita': 'Tinta unita',
            'solid': 'Tinta unita'
        }
        
        for tag in tags:
            tag_lower = tag.lower().strip()
            for keyword, pattern in pattern_keywords.items():
                if keyword in tag_lower:
                    return pattern
        
        # Priority 3: Check title and description
        text = (product.get('title', '') + ' ' + product.get('body_html', '')).lower()
        for keyword, pattern in pattern_keywords.items():
            if keyword in text:
                return pattern
        
        return ''
    
    def _get_product_details(self, tags: List[str]) -> List[Dict[str, str]]:
        """Extract structured product details from tags"""
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
        
        return details[:3]  # Max 3 details
    
    def _get_custom_label_0(self, tags: List[str]) -> str:
        """Build custom_label_0 from categories/collections"""
        labels = []
        
        # Brand categories
        brand_tags = ['Nike', 'Adidas', 'nike', 'adidas']
        for tag in tags:
            if tag in brand_tags:
                labels.append(tag.upper())
        
        # Product lines
        product_lines = {
            'Air Force 1': 'Nike Air Force 1',
            'Air Force': 'Nike Air Force 1',
            'Gazelle': 'Adidas Gazelle',
            'Campus': 'Adidas Campus',
            'Samba': 'Adidas Samba'
        }
        
        for tag in tags:
            if tag in product_lines:
                labels.append(product_lines[tag])
        
        # Special collections
        collection_keywords = [
            'Sneakers Personalizzate',
            'Nike Personalizzate',
            'Adidas Personalizzate',
            'Denim',
            'Effetto Vintage'
        ]
        
        for tag in tags:
            for keyword in collection_keywords:
                if keyword.lower() in tag.lower():
                    labels.append(tag)
        
        # Seasons
        seasons = ['Autunno', 'Inverno', 'Primavera', 'Estate']
        for tag in tags:
            if tag in seasons:
                labels.append(tag)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_labels = []
        for label in labels:
            label_upper = label.upper()
            if label_upper not in seen:
                seen.add(label_upper)
                unique_labels.append(label)
        
        return ', '.join(unique_labels[:10])
    
    def _get_custom_label_1(self, product: Dict, tags: List[str], variant: Dict) -> str:
        """Build enhanced custom_label_1 with 8 marketing elements"""
        labels = []
        price = float(variant.get('price', 0))
        
        # 1. Edizione Limitata (sempre)
        labels.append("Adidas Personalizzate a mano in Edizione Limitata")
        
        # 2. Seasonal tags
        seasonal_tags = ['Autunno', 'Inverno', 'Primavera', 'Estate']
        for tag in tags:
            if tag in seasonal_tags:
                labels.append(tag)
        
        # 3. Price-based gift category
        if price >= 170:
            labels.append("Idee regalo oltre i 170€")
        elif price >= 120:
            labels.append("Idee regalo tra 120€ e 170€")
        
        # 4. New Collection
        if 'NEW' in tags or 'Nuova Collezione' in tags:
            labels.append("NUOVA COLLEZIONE 2025")
        
        # 5. Special materials/features
        special_features = {
            'Denim': 'Scarpe in Jeans Denim',
            'Jeans': 'Scarpe in Jeans Denim',
            'Effetto Vintage': 'Stile Vintage',
            'Platform': 'Suola Platform Alta'
        }
        
        for tag in tags:
            for keyword, label in special_features.items():
                if keyword in tag:
                    labels.append(label)
        
        # 6. Sales
        if variant.get('compare_at_price'):
            labels.append("Sneaker in super saldo")
            labels.append("SALDI")
        
        # 7. Trending
        if any(word in tags for word in ['Trending', 'Top', 'Più vendute']):
            labels.append("Scarpe personalizzate più di tendenza e alla moda")
        
        # 8. Best sellers indicator
        if 'Best Seller' in tags or 'Più vendute' in tags:
            labels.append("Sneakers personalizzate più vendute")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_labels = []
        for label in labels:
            if label not in seen:
                seen.add(label)
                unique_labels.append(label)
        
        return ', '.join(unique_labels[:8])
    
    def _get_product_highlight(self, product: Dict, tags: List[str]) -> str:
        """Extract key product highlights from title and description"""
        title = product.get('title', '')
        description = self._clean_html(product.get('body_html', ''))
        
        # Extract first sentence or up to 150 chars from description
        first_part = description.split('.')[0] if '.' in description else description
        highlight = f"{title} {first_part[:150]}"
        
        return highlight.strip()[:500]
    
    def _calculate_shipping(self, price: float) -> float:
        """Calculate dynamic shipping cost based on price tiers (Italy)"""
        if price >= 89:
            return 0.00  # Free shipping
        elif price > 30:
            return 10.00
        else:
            return 6.00
    
    def _get_product_rating(self, metafield_data: Dict) -> Optional[Dict[str, str]]:
        """
        Extract product rating and review count from metafields
        
        Supported review apps:
        - Stamped.io: stamped.reviews_average, stamped.reviews_count
        - Judge.me: judgeme.rating, judgeme.review_count
        - Loox: loox.avg_rating, loox.num_reviews
        - Generic: reviews.rating, reviews.count
        """
        rating = None
        count = None
        
        # Check multiple possible metafield keys (order matters - most specific first)
        rating_keys = [
            'reviews_average',    # Stamped.io
            'rating',             # Generic/Judge.me
            'reviews_rating',     # Generic
            'avg_rating',         # Loox
            'product_rating',     # Custom
            'average_rating',     # Alternative
        ]
        
        count_keys = [
            'reviews_count',      # Stamped.io
            'count',              # Generic
            'review_count',       # Judge.me
            'num_reviews',        # Loox
            'number_of_reviews',  # Alternative
            'total_reviews',      # Alternative
        ]
        
        for key in rating_keys:
            if key in metafield_data:
                try:
                    value_str = str(metafield_data[key])
                    rating_value = float(value_str)
                    
                    # Validate rating is in correct range
                    if 0.0 <= rating_value <= 5.0:
                        rating = f"{rating_value:.1f}"
                        break
                except (ValueError, TypeError) as e:
                    continue
        
        for key in count_keys:
            if key in metafield_data:
                try:
                    value_str = str(metafield_data[key])
                    # Handle possible string numbers
                    count_value = int(float(value_str))
                    
                    # Only show if we have actual reviews
                    if count_value > 0:
                        count = str(count_value)
                        break
                except (ValueError, TypeError) as e:
                    continue
        
        # Return rating data only if both values are present and valid
        if rating and count:
            return {'rating': rating, 'count': count}
        
        return None
