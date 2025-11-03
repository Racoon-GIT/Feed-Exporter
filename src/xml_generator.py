"""
Streaming XML Feed Generator for Google Shopping
Writes XML incrementally to file instead of holding everything in memory
MEMORY OPTIMIZED for large feeds (10,000+ items)
No lxml dependency for streaming - uses direct file writing
"""

from typing import Dict
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class StreamingXMLGenerator:
    """
    Memory-efficient XML generator that writes items as they're added
    instead of building the entire tree in memory first.
    """
    
    def __init__(self, output_path: str, shop_info: Dict):
        """
        Initialize streaming XML generator
        
        Args:
            output_path: Path where XML file will be written
            shop_info: Dictionary with 'title' and 'url'
        """
        self.output_path = output_path
        self.shop_info = shop_info
        
        # Open file for writing
        self.file = open(output_path, 'wb')
        
        # Write XML declaration
        self.file.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        
        # Write opening feed tag
        self.file.write(b'<feed xmlns="http://www.w3.org/2005/Atom" xmlns:g="http://base.google.com/ns/1.0">\n')
        
        # Write feed metadata
        self._write_simple('title', shop_info.get('title', 'Product Feed'))
        self.file.write(f'  <link rel="self" href="{shop_info.get("url", "")}"/>\n'.encode('utf-8'))
        self._write_simple('updated', datetime.now(timezone.utc).isoformat())
        
        self.items_written = 0
        
        logger.info(f"Streaming XML generator initialized: {output_path}")
    
    def _write_simple(self, tag: str, text: str):
        """Write a simple text element"""
        from xml.sax.saxutils import escape
        text_escaped = escape(str(text))
        self.file.write(f'  <{tag}>{text_escaped}</{tag}>\n'.encode('utf-8'))
    
    def _write_google(self, tag: str, text: str):
        """Write a Google Shopping namespaced element"""
        from xml.sax.saxutils import escape
        text_escaped = escape(str(text))
        self.file.write(f'    <g:{tag}>{text_escaped}</g:{tag}>\n'.encode('utf-8'))
    
    def add_item(self, item_data: Dict):
        """
        Add a single item to the feed (writes immediately)
        
        Args:
            item_data: Dictionary with item fields (g:id, g:title, etc.)
        """
        from xml.sax.saxutils import escape
        
        # Write opening entry tag
        self.file.write(b'  <entry>\n')
        
        # Add each field
        for field, value in item_data.items():
            if not value and value != 0:  # Skip empty values but allow 0
                continue
            
            # Handle special field types
            if field == 'g:additional_image_link':
                # Multiple additional images
                if isinstance(value, list):
                    for img_url in value:
                        if img_url:
                            self._write_google('additional_image_link', img_url)
            
            elif field == 'g:product_detail':
                # Structured product details
                if isinstance(value, list):
                    for detail in value:
                        self.file.write(b'    <g:product_detail>\n')
                        attr_name = escape(str(detail.get('attribute_name', '')))
                        attr_value = escape(str(detail.get('attribute_value', '')))
                        self.file.write(f'      <g:attribute_name>{attr_name}</g:attribute_name>\n'.encode('utf-8'))
                        self.file.write(f'      <g:attribute_value>{attr_value}</g:attribute_value>\n'.encode('utf-8'))
                        self.file.write(b'    </g:product_detail>\n')
            
            elif field.startswith('g:'):
                # Standard Google Shopping field
                field_name = field[2:]  # Remove 'g:' prefix
                self._write_google(field_name, str(value))
            
            else:
                # Standard Atom field (not used typically, but keep for compatibility)
                text_escaped = escape(str(value))
                self.file.write(f'    <{field}>{text_escaped}</{field}>\n'.encode('utf-8'))
        
        # Write closing entry tag
        self.file.write(b'  </entry>\n')
        
        self.items_written += 1
        
        # Log progress every 1000 items
        if self.items_written % 1000 == 0:
            logger.info(f"  Written {self.items_written} items to XML...")
    
    def close(self):
        """Finalize and close the XML file"""
        # Write closing feed tag
        self.file.write(b'</feed>\n')
        
        # Close file
        self.file.close()
        
        logger.info(f"XML generation complete: {self.items_written} items written")


# Legacy class for compatibility (uses streaming under the hood)
class XMLFeedGenerator:
    """
    Legacy interface that maintains compatibility with old code
    but uses streaming generation internally
    """
    
    def __init__(self):
        self.nsmap = {
            None: "http://www.w3.org/2005/Atom",
            'g': "http://base.google.com/ns/1.0"
        }
    
    def generate_feed(self, items: list, shop_info: Dict) -> str:
        """
        Generate complete feed (kept for compatibility but not recommended for large feeds)
        For large feeds, use StreamingXMLGenerator directly
        """
        import tempfile
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix='.xml') as tmp:
            tmp_path = tmp.name
        
        # Use streaming generator
        generator = StreamingXMLGenerator(tmp_path, shop_info)
        
        for item in items:
            generator.add_item(item)
        
        generator.close()
        
        # Read back the file
        with open(tmp_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Clean up temp file
        import os
        os.unlink(tmp_path)
        
        return content
    
    def save_feed(self, xml_content: str, filepath: str):
        """Save feed to file"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(xml_content)


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
