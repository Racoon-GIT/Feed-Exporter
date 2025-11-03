"""
Streaming XML Feed Generator for Google Shopping
Writes XML incrementally to file instead of holding everything in memory
MEMORY OPTIMIZED for large feeds (10,000+ items)
"""

from lxml import etree
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
        
        # Create XML writer
        self.writer = etree.xmlfile(self.file, encoding='utf-8')
        self.writer.__enter__()
        
        # Write root element and feed metadata
        self.feed = self.writer.element(
            'feed',
            nsmap={
                None: "http://www.w3.org/2005/Atom",
                'g': "http://base.google.com/ns/1.0"
            }
        )
        self.feed.__enter__()
        
        # Write feed metadata
        self._write_element('title', shop_info.get('title', 'Product Feed'))
        
        link_elem = etree.Element('link', rel='self', href=shop_info.get('url', ''))
        self.writer.write(link_elem)
        
        self._write_element('updated', datetime.now(timezone.utc).isoformat())
        
        self.items_written = 0
        
        logger.info(f"Streaming XML generator initialized: {output_path}")
    
    def _write_element(self, tag: str, text: str):
        """Write a simple text element"""
        elem = etree.Element(tag)
        elem.text = text
        self.writer.write(elem)
    
    def add_item(self, item_data: Dict):
        """
        Add a single item to the feed (writes immediately)
        
        Args:
            item_data: Dictionary with item fields (g:id, g:title, etc.)
        """
        # Create entry element
        with self.writer.element('entry'):
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
                                self._write_google_element('additional_image_link', img_url)
                
                elif field == 'g:product_detail':
                    # Structured product details
                    if isinstance(value, list):
                        for detail in value:
                            with self.writer.element("{http://base.google.com/ns/1.0}product_detail"):
                                self._write_google_element('attribute_name', detail.get('attribute_name', ''))
                                self._write_google_element('attribute_value', detail.get('attribute_value', ''))
                
                elif field.startswith('g:'):
                    # Standard Google Shopping field
                    field_name = field[2:]  # Remove 'g:' prefix
                    self._write_google_element(field_name, str(value))
                
                else:
                    # Standard Atom field
                    self._write_element(field, str(value))
        
        self.items_written += 1
        
        # Log progress every 1000 items
        if self.items_written % 1000 == 0:
            logger.info(f"  Written {self.items_written} items to XML...")
    
    def _write_google_element(self, tag: str, text: str):
        """Write a Google Shopping namespaced element"""
        elem = etree.Element("{http://base.google.com/ns/1.0}" + tag)
        elem.text = text
        self.writer.write(elem)
    
    def close(self):
        """Finalize and close the XML file"""
        # Close feed element
        self.feed.__exit__(None, None, None)
        
        # Close XML writer
        self.writer.__exit__(None, None, None)
        
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
