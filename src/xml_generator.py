"""
Streaming XML Generator - RSS Format
Compatible with DataFeedWatch format (rss/channel/item instead of feed/entry)

Writes items directly to file without storing in memory
"""

import logging
from typing import Dict, Optional, TextIO
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


class StreamingXMLGenerator:
    """
    Streaming XML generator that writes directly to file
    
    Format: RSS 2.0 (compatible with DataFeedWatch)
    <rss>
      <channel>
        <item>...</item>
        <item>...</item>
      </channel>
    </rss>
    """
    
    def __init__(self, output_file: str):
        """
        Initialize streaming XML generator
        
        Args:
            output_file: Path to output XML file
        """
        self.output_file = output_file
        self.file: Optional[TextIO] = None
        self.item_count = 0
    
    def start_feed(self, title: str, link: str, description: str):
        """
        Start XML feed and write RSS header
        
        Args:
            title: Feed title
            link: Feed link
            description: Feed description
        """
        self.file = open(self.output_file, 'w', encoding='utf-8')
        
        # Write XML declaration and RSS opening
        self.file.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        self.file.write('<rss xmlns:g="http://base.google.com/ns/1.0" version="2.0">\n')
        self.file.write('  <channel>\n')
        
        # Write channel metadata
        self.file.write(f'    <title>{self._escape(title)}</title>\n')
        self.file.write(f'    <link>{self._escape(link)}</link>\n')
        self.file.write(f'    <description>{self._escape(description)}</description>\n')
        
        logger.info(f"✅ Started streaming XML feed: {self.output_file}")
    
    def add_item(self, item_data: Dict):
        """
        Add a single item to the feed (writes immediately to file)
        
        Args:
            item_data: Dictionary with Google Shopping fields (with or without g: prefix)
        """
        if not self.file:
            raise RuntimeError("Feed not started. Call start_feed() first.")
        
        # Helper to get value with or without g: prefix
        def get_field(key):
            return item_data.get(f'g:{key}') or item_data.get(key)
        
        self.file.write('    <item>\n')
        
        # Required fields
        self._write_field('g:id', get_field('id'))
        self._write_field('g:title', get_field('title'))
        self._write_field('g:description', get_field('description'))
        self._write_field('g:link', get_field('link'))
        self._write_field('g:image_link', get_field('image_link'))
        
        # Additional images
        additional_images = get_field('additional_image_link')
        if additional_images:
            # Handle both string (comma-separated) and list formats
            if isinstance(additional_images, list):
                self._write_field('g:additional_image_link', ','.join(additional_images))
            else:
                self._write_field('g:additional_image_link', additional_images)
        
        # Price and availability
        self._write_field('g:availability', get_field('availability'))
        self._write_field('g:price', get_field('price'))
        
        # Sale price (optional)
        if get_field('sale_price'):
            self._write_field('g:sale_price', get_field('sale_price'))
        
        # Product identifiers
        self._write_field('g:brand', get_field('brand'))
        self._write_field('g:condition', get_field('condition') or 'new')
        
        if get_field('gtin'):
            self._write_field('g:gtin', get_field('gtin'))
        
        if get_field('mpn'):
            self._write_field('g:mpn', get_field('mpn'))
        
        # Categories
        self._write_field('g:google_product_category', get_field('google_product_category'))
        
        if get_field('product_type'):
            self._write_field('g:product_type', get_field('product_type'))
        
        # Product attributes
        self._write_field('g:gender', get_field('gender'))
        self._write_field('g:age_group', get_field('age_group'))
        
        if get_field('color'):
            self._write_field('g:color', get_field('color'))
        
        if get_field('size'):
            self._write_field('g:size', get_field('size'))
        
        if get_field('material'):
            self._write_field('g:material', get_field('material'))
        
        if get_field('pattern'):
            self._write_field('g:pattern', get_field('pattern'))
        
        # Product detail - handle as nested XML structure
        product_detail = get_field('product_detail')
        if product_detail and isinstance(product_detail, list):
            self._write_product_details(product_detail)
        
        # Item group ID (for variants)
        if get_field('item_group_id'):
            self._write_field('g:item_group_id', get_field('item_group_id'))
        
        # Shipping
        if get_field('shipping'):
            self._write_field('g:shipping', get_field('shipping'))
        
        # Star rating
        if get_field('product_rating'):
            self._write_field('g:product_rating', get_field('product_rating'))
        
        # Custom labels
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
        
        # Additional fields from transformer_n
        if get_field('size_system'):
            self._write_field('g:size_system', get_field('size_system'))
        
        if get_field('is_bundle'):
            self._write_field('g:is_bundle', get_field('is_bundle'))
        
        if get_field('product_highlight'):
            self._write_field('g:product_highlight', get_field('product_highlight'))
        
        if get_field('TAGS'):
            self._write_field('g:TAGS', get_field('TAGS'))
        
        self.file.write('    </item>\n')
        self.item_count += 1
    
    def _write_field(self, name: str, value: Optional[str]):
        """Write a single XML field"""
        if value is not None and str(value).strip():
            escaped_value = self._escape(str(value))
            self.file.write(f'      <{name}>{escaped_value}</{name}>\n')
    
    def _write_product_details(self, details: List[Dict[str, str]]):
        """
        Write product_detail fields as nested XML
        
        Format:
        <g:product_detail>
          <g:attribute_name>Name</g:attribute_name>
          <g:attribute_value>Value</g:attribute_value>
        </g:product_detail>
        
        Args:
            details: List of dicts with 'attribute_name' and 'attribute_value'
        """
        for detail in details:
            attribute_name = detail.get('attribute_name', '')
            attribute_value = detail.get('attribute_value', '')
            
            if attribute_name and attribute_value:
                self.file.write('      <g:product_detail>\n')
                self.file.write(f'        <g:attribute_name>{self._escape(attribute_name)}</g:attribute_name>\n')
                self.file.write(f'        <g:attribute_value>{self._escape(attribute_value)}</g:attribute_value>\n')
                self.file.write('      </g:product_detail>\n')
    
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
        
        logger.info(f"✅ Closed XML feed with {self.item_count} items")
