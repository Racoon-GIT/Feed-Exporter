"""
Product Transformer - Converts Shopify products to Google Shopping format
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
        
        # Excluded product type keywords (case-insensitive)
        self.excluded_product_types = ['buon', 'gift', 'pacco', 'berretti', 'shirt', 'felp', 'stringhe', 'outlet']
        """Check if product should be excluded based on various criteria"""
    def _should_exclude_product(self, product: Dict) -> bool:
        """Check if product should be excluded based on various criteria"""
        
        # FILTER 1: Only active products
        status = product.get('status', '').lower()
        if status != 'active':
            return True
        
        # FILTER 2: Exclude products with "Outlet" in title (case-insensitive)
        title = product.get('title', '').lower()
        if 'outlet' in title:
            return True
        
        # FILTER 3: Exclude specific product types (case-insensitive)
        product_type = product.get('product_type', '').lower()
        
        for excluded in self.excluded_product_types:
            if excluded in product_type:
                return True
        
        return False
    
    def _has_available_stock(self, product: Dict) -> bool:
        """Check if at least one variant has stock > 0"""
        variants = product.get('variants', [])
        
        for variant in variants:
            if variant.get('inventory_quantity', 0) > 0:
                return True
        
        return False
    
    def _should_exclude_variant(self, variant: Dict, product: Dict) -> bool:
        """Check if variant should be excluded (personalizzazione in variant options only)"""
        # Check ONLY variant options (option1, option2, option3), NOT product title
        # This allows products with "Personalizzazione" in the title to still be sold
        # but excludes specific variants like "Solo Personalizzazione"
        
        # Handle None values properly - Shopify can return None for options
        option1 = (variant.get('option1') or '').lower()
        option2 = (variant.get('option2') or '').lower()
        option3 = (variant.get('option3') or '').lower()
        
        # Exclude if ANY option contains "personalizzazione"
        if 'personalizzazione' in option1 or 'personalizzazione' in option2 or 'personalizzazione' in option3:
            return True
        
        return False
        
    def transform_product(self, product: Dict, metafields: Optional[Dict] = None, collections: Optional[List[str]] = None) -> List[Dict]:
        """Transform a Shopify product into Google Shopping items (one per variant)"""
        
        # FILTER 1: Check if product_type should be excluded
        if self._should_exclude_product(product):
            return []  # Skip this product entirely
        
        # FILTER 2: Check if product has at least one variant with stock
        if not self._has_available_stock(product):
            return []  # Skip product if all variants are out of stock
        
        items = []
        tags = product.get('tags', '').split(', ') if isinstance(product.get('tags'), str) else product.get('tags', [])
        collections = collections or []
        
        for variant in product.get('variants', []):
            # FILTER 3: Skip variants with "personalizzazione" in title
            if self._should_exclude_variant(variant, product):
                continue
            
            item = self.transform_variant(product, variant, tags, metafields, collections)
            items.append(item)
            
        return items
    
    def transform_variant(self, product: Dict, variant: Dict, tags: List[str], metafields: Optional[Dict] = None, collections: Optional[List[str]] = None) -> Dict:
        """Transform a single variant into a Google Shopping item"""
        item = {}
        
        # Priority: Metafields > Tag extraction > Static values
        metafield_data = self._extract_metafields(metafields) if metafields else {}
        collections = collections or []
        
        # Core fields
        item['g:id'] = str(variant['id'])
        item['g:title'] = self._build_title(product, variant)
        item['g:description'] = self._clean_html(product.get('body_html', ''))
        item['g:link'] = f"{self.base_url}/products/{product['handle']}?variant={variant['id']}"
        
        # Images - MULTIPLE IMAGES SUPPORT + Converse _INT logic
        images = product.get('images', [])
        brand = product.get('vendor', '').lower()
        
        if images:
            # Special handling for Converse: prioritize _INT images
            if 'converse' in brand:
                # Find _INT image
                int_image = None
                other_images = []
                
                for img in images:
                    img_src = img.get('src', '')
                    if '_INT' in img_src or '_int' in img_src:
                        int_image = img_src
                    else:
                        other_images.append(img_src)
                
                # Use _INT as main image if found
                if int_image:
                    item['g:image_link'] = int_image
                    # Add other images as additional (up to 10 total)
                    if other_images:
                        item['g:additional_image_link'] = other_images[:10]
                else:
                    # Fallback if no _INT found
                    item['g:image_link'] = images[0].get('src', '')
                    additional_images = [img.get('src', '') for img in images[1:11]]
                    if additional_images:
                        item['g:additional_image_link'] = additional_images
            else:
                # Standard image handling for non-Converse products
                item['g:image_link'] = images[0].get('src', '')
                # Add up to 10 additional images
                additional_images = [img.get('src', '') for img in images[1:11]]
                if additional_images:
                    item['g:additional_image_link'] = additional_images
        
        # Pricing - FIXED LOGIC
        compare_at = variant.get('compare_at_price')
        price = float(variant['price'])
        
        if compare_at and float(compare_at) > 0:
            # Product is on sale
            item['g:price'] = f"{float(compare_at):.2f} EUR"
            item['g:sale_price'] = f"{price:.2f} EUR"
        else:
            # Regular price, no sale
            item['g:price'] = f"{price:.2f} EUR"
            # Omit sale_price field when not on sale (Google best practice)
            
        # Basic attributes
        item['g:condition'] = self.static_values.get('condition', 'new')
        item['g:availability'] = 'in stock' if variant.get('inventory_quantity', 0) > 0 else 'out of stock'
        item['g:brand'] = product.get('vendor', 'Racoon Lab')
        
        # Fashion-specific fields
        item['g:gender'] = self._get_gender(metafield_data)
        item['g:age_group'] = self._get_age_group(metafield_data)
        
        # Color - skip field if not in metafield
        color = self._get_color(metafield_data)
        if color:
            item['g:color'] = color
        
        # Grouping
        item['g:item_group_id'] = str(product['id'])
        
        # Identifiers
        # GTIN from barcode - omit field if empty (Google best practice)
        barcode = variant.get('barcode', '')
        if barcode and str(barcode).strip():
            item['g:gtin'] = str(barcode).strip()
        # If no barcode, omit g:gtin field entirely
        
        item['g:mpn'] = variant.get('sku', '')
        
        # Category
        item['g:google_product_category'] = self.static_values.get('google_product_category', '187')
        item['g:product_type'] = product.get('product_type', '')
        
        # Size
        item['g:size'] = variant.get('option1', '')
        
        # Material & Pattern - skip if not in metafield
        material = self._get_material(metafield_data)
        if material:
            item['g:material'] = material
            
        pattern = self._get_pattern(tags, metafield_data)
        if pattern:
            item['g:pattern'] = pattern
        
        # Product Details (structured attributes)
        product_details = self._get_product_details(tags)
        if product_details:
            item['g:product_detail'] = product_details
        
        # Custom Labels - Use Shopify collections with smart split
        item['g:custom_label_0'] = self._get_custom_label_0(tags)
        
        # Split collections across custom_label_1 and custom_label_2
        label_1, label_2 = self._split_collections_across_labels(collections)
        item['g:custom_label_1'] = label_1
        item['g:custom_label_2'] = label_2
        
        item['g:custom_label_3'] = self.static_values.get('custom_label_3', '')
        item['g:custom_label_4'] = self.static_values.get('custom_label_4', '')
        
        # Size system
        item['g:size_system'] = self.static_values.get('size_system', 'IT')
        
        # Bundle (shoes are always sold as pairs)
        item['g:is_bundle'] = 'TRUE'
        
        # Product Highlight
        item['g:product_highlight'] = self._get_product_highlight(product, tags)
        
        # TAGS (for internal tracking)
        item['g:TAGS'] = ', '.join(tags)
        
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
            title = f"{title} - {size}"
            
        return title[:150]
    
    def _clean_html(self, html: str) -> str:
        """Remove HTML tags and clean text"""
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text)
        text = text.replace('&quot;', '"').replace('&amp;', '&')
        text = text.replace('&#39;', "'").replace('&lt;', '<').replace('&gt;', '>')
        return text.strip()[:5000]
    
    def _get_gender(self, metafield_data: Dict) -> str:
        """Extract gender from Shopify metafield"""
        # Priority 1: Metafield from Shopify
        if 'gender' in metafield_data:
            gender_value = metafield_data['gender'].lower()
            # Normalize to Google Shopping values
            if gender_value in ['female', 'male', 'unisex']:
                return gender_value
        
        # Default: female (as per user instruction)
        return 'female'
    
    def _get_age_group(self, metafield_data: Dict) -> str:
        """Extract age_group from Shopify metafield"""
        # Priority 1: Metafield from Shopify
        if 'age_group' in metafield_data:
            age_value = metafield_data['age_group'].lower()
            # Normalize to Google Shopping values
            if age_value in ['adult', 'kids', 'toddler', 'infant', 'newborn']:
                return age_value
        
        # Default: adult (as per user instruction)
        return 'adult'
    
    def _get_color(self, metafield_data: Dict) -> str:
        """Extract color from Shopify metafield - skip field if not present"""
        # Use ONLY metafield from Shopify
        if 'color' in metafield_data and metafield_data['color']:
            return metafield_data['color']
        
        # Return empty string to skip field (caller will omit it)
        return ''
    
    def _get_material(self, metafield_data: Dict) -> str:
        """Extract material from Shopify metafield - skip field if not present"""
        # Use ONLY metafield from Shopify
        if 'material' in metafield_data and metafield_data['material']:
            return metafield_data['material']
        
        # Return empty string to skip field (caller will omit it)
        return ''
    
    def _get_pattern(self, tags: List[str], metafield_data: Dict) -> str:
        """Extract pattern from Shopify using DFW mapping table"""
        # Priority 1: Metafield
        if 'pattern' in metafield_data and metafield_data['pattern']:
            return metafield_data['pattern']
        
        # Priority 2: DFW Pattern mapping table from tags
        pattern_mapping = {
            'animalier': 'Animalier',
            'azulejos': 'Azulejos C',
            'bandane': 'Bandane',
            'cartoon': 'Cartoon',
            'catene': 'Catene',
            'coccodrillo': 'Animalier Co',
            'colori pastello': 'Colori Past',
            'comix': 'Design artis',
            'con borchie': 'Con Borchie',
            'country': 'Country',
            'crochet': 'UNCINETTO',
            'cuori': 'Cuori',
            'farfalle': 'Farfalle',
            'fiamme': 'Fiamme',
            'fiori': 'Fiori',
            'fumetti': 'Fumetti',
            'gioielli': 'Con gioielli',
            'goth': 'Gotico',
            'leopardate': 'Leopardato',
            'matelassè': 'Matelassè',
            'mimetico camo militare': 'Mimetico',
            'mimetico': 'Mimetico',
            'camo': 'Mimetico',
            'militare': 'Mimetico',
            'muccato': 'Muccato',
            'paisley': 'Paisley',
            'paillettes': 'Paillettes',
            'pelo': 'Pelo furry',
            'peluche': 'Peluche',
            'perle': 'Con Perle',
            'perline': 'Perline',
            'pied de poule': 'Pied de poule',
            'pietre': 'Con pietre pr',
            'pitonato': 'Pitonato',
            'pitonate': 'Pitonato',
            'pizzo': 'Pizzo',
            'pizzo bianco': 'Pizzo',
            'pizzo nero': 'Pizzo',
            'pois': 'Pois',
            'principe di galles': 'Principe di',
            'ricamate a mano': 'Rciama a ma',
            'rope': 'Rope',
            'specchio': 'Specchio',
            'spille': 'Con spille',
            'strass': 'Con strass e la',
            'sughero': 'Sughero',
            'tartan scozzese': 'Tartan',
            'tartan': 'Tartan',
            'teddy': 'pelo Teddy',
            'teschi': 'Con teschi',
            'tiedye': 'Tie dye',
            'tie dye': 'Tie dye',
            'tulle': 'Tulle',
            'uncinetto': 'UNCINETTO'
        }
        
        # Search tags for pattern keywords (case-insensitive)
        for tag in tags:
            tag_lower = tag.lower().strip()
            for pattern_key, pattern_value in pattern_mapping.items():
                if pattern_key in tag_lower:
                    return pattern_value
        
        # Return empty string to skip field if not found
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
        """Return all Shopify tags as-is"""
        # Use ALL tags from Shopify, joined by comma
        return ', '.join(tags) if tags else ''
    
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
