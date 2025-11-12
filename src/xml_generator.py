"""
Streaming XML Generator for Google Shopping Feed - RSS Format
Writes items one-by-one to avoid memory buildup
"""

import logging
from typing import Dict, Optional
from xml.sax.saxutils import escape

logger = logging.getLogger(__name__)


class StreamingXMLGenerator:
    def __init__(self, output_path: str, shop_info: Dict):
        self.output_path = output_path
        self.shop_info = shop_info
        self.file = None
        self.item_count = 0
        
        # Start XML file with RSS format
        self._start_feed()
    
    def _start_feed(self):
        """Start XML feed with RSS header"""
        self.file = open(self.output_path, 'w', encoding='utf-8')
        
        # RSS header
        self.file.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        self.file.write('<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">\n')
        self.file.write('  <channel>\n')
        
        # Channel metadata
        title = escape(self.shop_info.get('title', 'Product Feed'))
        url = escape(self.shop_info.get('url', ''))
        
        self.file.write(f'    <title>{title}</title>\n')
        self.file.write(f'    <link>{url}</link>\n')
        self.file.write('    <description>Google Shopping Product Feed</description>\n')
        
        logger.info(f"Started RSS feed: {self.output_path}")
    
    def add_item(self, item: Dict):
        """Add single item to feed (streaming)"""
        self.file.write('    <item>\n')
        
        for key, value in item.items():
            if value:  # Only write non-empty values
                escaped_value = escape(str(value))
                self.file.write(f'      <{key}>{escaped_value}</{key}>\n')
        
        self.file.write('    </item>\n')
        self.item_count += 1
    
    def close(self):
        """Finalize and close XML feed"""
        # Close channel and rss tags
        self.file.write('  </channel>\n')
        self.file.write('</rss>\n')
        self.file.close()
        
        logger.info(f"Closed feed with {self.item_count} items")
