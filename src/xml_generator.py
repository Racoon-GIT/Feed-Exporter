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
            item_data: Dictionary with Google Shopping fields
        """
        if not self.file:
            raise RuntimeError("Feed not started. Call start_feed() first.")
        
        self.file.write('    <item>\n')
        
        # Required fields
        self._write_field('g:id', item_data.get('id'))
        self._write_field('g:title', item_data.get('title'))
        self._write_field('g:description', item_data.get('description'))
        self._write_field('g:link', item_data.get('link'))
        self._write_field('g:image_link', item_data.get('image_link'))
        
        # Additional images
        if item_data.get('additional_image_link'):
            self._write_field('g:additional_image_link', item_data.get('additional_image_link'))
        
        # Price and availability
        self._write_field('g:availability', item_data.get('availability'))
        self._write_field('g:price', item_data.get('price'))
        
        # Product identifiers
        self._write_field('g:brand', item_data.get('brand'))
        self._write_field('g:condition', item_data.get('condition', 'new'))
        
        if item_data.get('gtin'):
            self._write_field('g:gtin', item_data.get('gtin'))
        
        if item_data.get('mpn'):
            self._write_field('g:mpn', item_data.get('mpn'))
        
        # Categories
        self._write_field('g:google_product_category', item_data.get('google_product_category'))
        
        if item_data.get('product_type'):
            self._write_field('g:product_type', item_data.get('product_type'))
        
        # Product attributes
        self._write_field('g:gender', item_data.get('gender'))
        self._write_field('g:age_group', item_data.get('age_group'))
        
        if item_data.get('color'):
            self._write_field('g:color', item_data.get('color'))
        
        if item_data.get('size'):
            self._write_field('g:size', item_data.get('size'))
        
        if item_data.get('material'):
            self._write_field('g:material', item_data.get('material'))
        
        if item_data.get('pattern'):
            self._write_field('g:pattern', item_data.get('pattern'))
        
        if item_data.get('product_detail'):
            self._write_field('g:product_detail', item_data.get('product_detail'))
        
        # Item group ID (for variants)
        if item_data.get('item_group_id'):
            self._write_field('g:item_group_id', item_data.get('item_group_id'))
        
        # Shipping
        if item_data.get('shipping'):
            self._write_field('g:shipping', item_data.get('shipping'))
        
        # Star rating
        if item_data.get('product_rating'):
            self._write_field('g:product_rating', item_data.get('product_rating'))
        
        # Custom labels
        if item_data.get('custom_label_0'):
            self._write_field('g:custom_label_0', item_data.get('custom_label_0'))
        
        if item_data.get('custom_label_1'):
            self._write_field('g:custom_label_1', item_data.get('custom_label_1'))
        
        if item_data.get('custom_label_2'):
            self._write_field('g:custom_label_2', item_data.get('custom_label_2'))
        
        if item_data.get('custom_label_3'):
            self._write_field('g:custom_label_3', item_data.get('custom_label_3'))
        
        if item_data.get('custom_label_4'):
            self._write_field('g:custom_label_4', item_data.get('custom_label_4'))
        
        self.file.write('    </item>\n')
        self.item_count += 1
    
    def _write_field(self, name: str, value: Optional[str]):
        """Write a single XML field"""
        if value is not None and str(value).strip():
            escaped_value = self._escape(str(value))
            self.file.write(f'      <{name}>{escaped_value}</{name}>\n')
    
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
