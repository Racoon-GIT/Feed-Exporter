"""
Base Mapper - Abstract class for platform-specific mappers
All platform mappers (Google, Meta, etc.) inherit from this
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class BaseMapper(ABC):
    """
    Abstract base class for platform-specific product mappers
    
    Each platform (Google, Meta, etc.) implements its own mapper
    that transforms Shopify product data into platform-specific format.
    """
    
    def __init__(self, config_loader, base_url: str):
        """
        Initialize mapper
        
        Args:
            config_loader: ConfigLoader instance with static values
            base_url: Base URL for product links (e.g., 'https://racoon-lab.it')
        """
        self.config = config_loader
        self.base_url = base_url
        self.static_values = config_loader.static_values
        
        # Load common configurations
        self.product_type_mapping = self._load_product_type_mapping()
        self.product_mappings = self._load_product_mappings()
        
        # Pattern mapping (common across platforms)
        self.pattern_mapping = self._get_pattern_mapping()
    
    def _load_product_type_mapping(self) -> Dict:
        """Load product type → macro category mapping"""
        mapping_file = Path('config/product_type_mapping.json')
        
        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.warning(f"Could not load product_type_mapping.json: {e}")
            return {"mappings": {}, "default": "Sneakers"}
    
    def _load_product_mappings(self) -> Dict:
        """Load product highlight/detail mappings"""
        mappings_file = Path('config/product_mappings.json')
        
        if not mappings_file.exists():
            mappings_file = Path('product_mappings.json')
        
        if not mappings_file.exists():
            logger.warning("Product mappings file not found")
            return {}
        
        try:
            with open(mappings_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Build lookup: (handle, sku) → data
            lookup = {}
            for item in data:
                handle = item.get('handle', '')
                sku = item.get('variant_sku', '')
                if handle and sku:
                    lookup[(handle, sku)] = {
                        'product_highlight': item.get('product_highlight', []),
                        'product_detail': item.get('product_detail', [])
                    }
            
            return lookup
        except Exception as e:
            logger.error(f"Error loading product mappings: {e}")
            return {}
    
    def _get_pattern_mapping(self) -> Dict:
        """Get pattern mapping (common across platforms)"""
        return {
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
            'pois': 'Pois',
            'principe di galles': 'Principe di',
            'ricamate a mano': 'Rciama a ma',
            'rope': 'Rope',
            'specchio': 'Specchio',
            'spille': 'Con spille',
            'strass': 'Con strass e la',
            'sughero': 'Sughero',
            'tartan': 'Tartan',
            'teddy': 'pelo Teddy',
            'teschi': 'Con teschi',
            'tiedye': 'Tie dye',
            'tie dye': 'Tie dye',
            'tulle': 'Tulle',
            'uncinetto': 'UNCINETTO'
        }
    
    # ========== ABSTRACT METHODS (must be implemented by subclasses) ==========
    
    @abstractmethod
    def transform_product(self, product: Dict, metafields: Optional[Dict], collections: Optional[List[str]]) -> List[Dict]:
        """Transform Shopify product into platform-specific items"""
        pass
    
    @abstractmethod
    def get_platform_name(self) -> str:
        """Return platform name (e.g., 'google', 'meta')"""
        pass
    
    # ========== COMMON HELPER METHODS ==========
    
    def _should_exclude_product(self, product: Dict) -> bool:
        """Check if product should be excluded"""
        status = product.get('status', '').lower()
        if status != 'active':
            return True
        
        title = product.get('title', '').lower()
        if 'outlet' in title:
            return True
        
        product_type = product.get('product_type', '').lower()
        excluded_types = ['buon', 'gift', 'pacco', 'berretti', 'calze', 'calzi', 'shirt', 'felp', 'stringhe', 'outlet']
        
        for excluded in excluded_types:
            if excluded in product_type:
                return True
        
        return False
    
    def _has_available_stock(self, product: Dict) -> bool:
        """Check if at least one variant has stock"""
        variants = product.get('variants', [])
        for variant in variants:
            if variant.get('inventory_quantity', 0) > 0:
                return True
        return False
    
    def _should_exclude_variant(self, variant: Dict) -> bool:
        """Check if variant should be excluded (personalizzazione)"""
        option1 = (variant.get('option1') or '').lower()
        option2 = (variant.get('option2') or '').lower()
        option3 = (variant.get('option3') or '').lower()
        
        if 'personalizzazione' in option1 or 'personalizzazione' in option2 or 'personalizzazione' in option3:
            return True
        
        return False
    
    def _clean_html(self, html: str) -> str:
        """Remove HTML tags from description"""
        if not html:
            return ""
        
        import re
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html)
        # Remove extra whitespace
        text = ' '.join(text.split())
        # Truncate to 5000 characters (Google Shopping limit)
        if len(text) > 5000:
            text = text[:4997] + '...'
        
        return text.strip()
    
    def _extract_metafields(self, metafields: Dict) -> Dict:
        """Extract metafields into flat dictionary"""
        data = {}
        
        if 'mm-google-shopping' in metafields:
            for key, value in metafields['mm-google-shopping'].items():
                data[key] = value
        
        # Star rating from Stamped.io
        if 'stamped' in metafields:
            for key, value in metafields['stamped'].items():
                if 'rating' in key.lower():
                    try:
                        data['star_rating'] = float(value)
                    except:
                        pass
        
        return data
    
    def _get_pattern(self, tags: List[str]) -> str:
        """Extract pattern from tags"""
        for tag in tags:
            tag_lower = tag.lower().strip()
            for pattern_key, pattern_value in self.pattern_mapping.items():
                if pattern_key in tag_lower:
                    return pattern_value
        return ''
    
    def _build_hierarchical_product_type(self, product: Dict) -> str:
        """
        Build hierarchical product_type: Macro Category > Brand > Model
        
        Example: "Sneakers > Adidas > Stan Smith"
        
        Args:
            product: Shopify product dict
        
        Returns:
            Hierarchical product_type string
        """
        brand = product.get('vendor', '')
        model = product.get('product_type', '')
        
        # Get macro category from mapping
        macro_category = self.product_type_mapping.get('mappings', {}).get(
            model,
            self.product_type_mapping.get('default', 'Sneakers')
        )
        
        # Build hierarchy
        parts = [macro_category]
        
        if brand:
            parts.append(brand)
        
        if model and model != macro_category:
            parts.append(model)
        
        return ' > '.join(parts)
