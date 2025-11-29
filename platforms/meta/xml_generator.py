"""
Meta XML Generator - RSS Format with special handling for internal_label
Based on Google's StreamingXMLGenerator but with Meta-specific features
"""

import logging
from typing import Dict, List, Optional, TextIO

logger = logging.getLogger(__name__)


class MetaXMLGenerator:
    """
    Streaming XML generator for Meta catalog feed
    
    Format: RSS 2.0 with Google namespace (Meta supports this format)
    Special handling: internal_label as multiple XML tags
    """
    
    def __init__(self, output_file: str):
        """Initialize Meta XML generator"""
        self.output_file = output_file
        self.file: Optional[TextIO] = None
        self.item_count = 0
    
    def start_feed(self, title: str, link: str, description: str):
        """Start XML feed and write RSS header"""
        self.file = open(self.output_file, 'w', encoding='utf-8')
        
        # Write XML declaration and RSS opening
        self.file.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        self.file.write('<rss xmlns:g="http://base.google.com/ns/1.0" version="2.0">\n')
        self.file.write('  <channel>\n')
        
        # Write channel metadata
        self.file.write(f'    <title>{self._escape(title)}</title>\n')
        self.file.write(f'    <link>{self._escape(link)}</link>\n')
        self.file.write(f'    <description>{self._escape(description)}</description>\n')
        
        logger.info(f"✅ Started Meta XML feed: {self.output_file}")
    
    def add_item(self, item_data: Dict):
        """
        Add a single item to Meta feed
        
        Special handling for Meta-specific fields:
        - internal_label: Can be a list (generates multiple tags)
        - rich_text_description: Full HTML allowed
        """
        if not self.file:
            raise RuntimeError("Feed not started. Call start_feed() first.")
        
        # Helper to get value with or without g: prefix
        def get_field(key):
            return item_data.get(f'g:{key}') or item_data.get(key)
        
        self.file.write('    <item>\n')
        
        # ========== REQUIRED FIELDS ==========
        self._write_field('g:id', get_field('id'))
        self._write_field('g:title', get_field('title'))
        self._write_field('g:description', get_field('description'))
        self._write_field('g:link', get_field('link'))
        self._write_field('g:image_link', get_field('image_link'))
        self._write_field('g:availability', get_field('availability'))
        self._write_field('g:price', get_field('price'))
        self._write_field('g:brand', get_field('brand'))
        self._write_field('g:condition', get_field('condition'))
        
        # ========== ADDITIONAL IMAGES ==========
        additional_images = get_field('additional_image_link')
        if additional_images:
            if isinstance(additional_images, list):
                # Write each image as separate tag
                for img_url in additional_images:
                    self._write_field('g:additional_image_link', img_url)
            else:
                # Single value or comma-separated
                self._write_field('g:additional_image_link', additional_images)
        
        # ========== SALE PRICE (optional) ==========
        if get_field('sale_price'):
            self._write_field('g:sale_price', get_field('sale_price'))
        
        # ========== IDENTIFIERS ==========
        if get_field('gtin'):
            self._write_field('g:gtin', get_field('gtin'))
        
        if get_field('mpn'):
            self._write_field('g:mpn', get_field('mpn'))
        
        # ========== CATEGORIES ==========
        self._write_field('g:google_product_category', get_field('google_product_category'))
        
        if get_field('product_type'):
            self._write_field('g:product_type', get_field('product_type'))
        
        # ========== PRODUCT ATTRIBUTES ==========
        self._write_field('g:gender', get_field('gender'))
        self._write_field('g:age_group', get_field('age_group'))
        
        if get_field('color'):
            self._write_field('g:color', get_field('color'))
        
        if get_field('size'):
            self._write_field('g:size', get_field('size'))
        
        if get_field('size_system'):
            self._write_field('g:size_system', get_field('size_system'))
        
        if get_field('material'):
            self._write_field('g:material', get_field('material'))
        
        if get_field('pattern'):
            self._write_field('g:pattern', get_field('pattern'))
        
        # ========== GROUPING ==========
        if get_field('item_group_id'):
            self._write_field('g:item_group_id', get_field('item_group_id'))
        
        # ========== SHIPPING ==========
        if get_field('shipping'):
            self._write_field('g:shipping', get_field('shipping'))
        
        # ========== STATUS & INVENTORY ==========
        if get_field('status'):
            self._write_field('g:status', get_field('status'))
        
        if get_field('inventory'):
            self._write_field('g:inventory', get_field('inventory'))
        
        # ========== CUSTOM LABELS ==========
        if get_field('custom_label_0'):
            self._write_field('g:custom_label_0', get_field('custom_label_0'))
        
        if get_field('custom_label_1'):
            self._write_field('g:custom_label_1', get_field('custom_label_1'))
        
        if get_field('custom_label_2'):
            self._write_field('g:custom_label_2', get_field('custom_label_2'))
        
        if get_field('custom_label_3'):
            self._write_field('g:custom_label_3', get_field('custom_label_3'))
        
        if get_field('custom_label_4'):
            self._write_field('g:custom_label_4', get_field('custom_label_4'))
        
        # ========== INTERNAL_LABEL (SPECIAL HANDLING) ==========
        # Meta Excel mapping: "usa un tag <internal_label> per ogni voce"
        # This means multiple <g:internal_label> tags, one per value
        internal_labels = get_field('internal_label')
        if internal_labels:
            if isinstance(internal_labels, list):
                # Write one tag per label
                for label in internal_labels:
                    if label.strip():
                        self._write_field('g:internal_label', label.strip())
            else:
                # Single value
                self._write_field('g:internal_label', internal_labels)
        
        # ========== RICH TEXT DESCRIPTION ==========
        if get_field('rich_text_description'):
            # For HTML content, use CDATA
            self._write_field_cdata('g:rich_text_description', get_field('rich_text_description'))
        
        self.file.write('    </item>\n')
        self.item_count += 1
    
    def _write_field(self, name: str, value: Optional[str]):
        """Write a single XML field"""
        if value is not None and str(value).strip():
            escaped_value = self._escape(str(value))
            self.file.write(f'      <{name}>{escaped_value}</{name}>\n')
    
    def _write_field_cdata(self, name: str, value: Optional[str]):
        """Write a field with CDATA section (for HTML content)"""
        if value is not None and str(value).strip():
            self.file.write(f'      <{name}><![CDATA[{value}]]></{name}>\n')
    
    def _escape(self, text: str) -> str:
        """Escape XML special characters"""
        if not text:
            return ""
        
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))
    
    def end_feed(self):
        """Close the XML feed"""
        if not self.file:
            raise RuntimeError("Feed not started")
        
        self.file.write('  </channel>\n')
        self.file.write('</rss>\n')
        self.file.close()
        
        logger.info(f"✅ Closed Meta XML feed with {self.item_count} items")
