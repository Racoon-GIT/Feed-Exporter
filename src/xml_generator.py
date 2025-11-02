"""
XML Feed Generator for Google Shopping
Version: 3.0 - With Multiple Images & Star Rating Support
"""

from lxml import etree
from typing import List, Dict
from datetime import datetime


class XMLFeedGenerator:
    def __init__(self):
        self.nsmap = {
            None: "http://www.w3.org/2005/Atom",
            'g': "http://base.google.com/ns/1.0"
        }
    
    def generate_feed(self, items: List[Dict], shop_info: Dict) -> str:
        """Generate complete Google Shopping XML feed"""
        
        # Create root element
        root = etree.Element("feed", nsmap=self.nsmap)
        
        # Add feed metadata
        self._add_feed_metadata(root, shop_info)
        
        # Add items
        for item_data in items:
            self._add_item(root, item_data)
        
        # Convert to string
        xml_string = etree.tostring(
            root,
            pretty_print=True,
            xml_declaration=True,
            encoding='UTF-8'
        )
        
        return xml_string.decode('utf-8')
    
    def _add_feed_metadata(self, root, shop_info: Dict):
        """Add feed-level metadata"""
        title = etree.SubElement(root, "title")
        title.text = shop_info.get('title', 'Product Feed')
        
        link = etree.SubElement(root, "link", rel="self", href=shop_info.get('url', ''))
        
        updated = etree.SubElement(root, "updated")
        updated.text = datetime.utcnow().isoformat() + 'Z'
    
    def _add_item(self, root, item_data: Dict):
        """Add a single item to the feed"""
        entry = etree.SubElement(root, "entry")
        
        # Add each field
        for field, value in item_data.items():
            if not value:  # Skip empty values
                continue
            
            # Handle special field types
            if field == 'g:additional_image_link':
                # Multiple additional images
                if isinstance(value, list):
                    for img_url in value:
                        if img_url:
                            elem = etree.SubElement(entry, "{http://base.google.com/ns/1.0}additional_image_link")
                            elem.text = img_url
            
            elif field == 'g:product_detail':
                # Structured product details
                if isinstance(value, list):
                    for detail in value:
                        detail_elem = etree.SubElement(entry, "{http://base.google.com/ns/1.0}product_detail")
                        
                        attr_name = etree.SubElement(detail_elem, "{http://base.google.com/ns/1.0}attribute_name")
                        attr_name.text = detail.get('attribute_name', '')
                        
                        attr_value = etree.SubElement(detail_elem, "{http://base.google.com/ns/1.0}attribute_value")
                        attr_value.text = detail.get('attribute_value', '')
            
            elif field.startswith('g:'):
                # Standard Google Shopping field
                field_name = field[2:]  # Remove 'g:' prefix
                elem = etree.SubElement(entry, "{http://base.google.com/ns/1.0}" + field_name)
                elem.text = str(value)
            
            else:
                # Standard Atom field
                elem = etree.SubElement(entry, field)
                elem.text = str(value)
    
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
