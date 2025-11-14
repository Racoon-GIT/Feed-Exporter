"""
Main Feed Generator - v4.0 PAGE-BY-PAGE STREAMING
Memory-efficient processing for 512MB RAM limit

ARCHITECTURE:
1. Open XML generator
2. Fetch ONE page (250 products)
3. Process each product immediately:
   - Fetch metafields + collections
   - Transform to Google Shopping items
   - Write directly to XML
4. Clear memory and fetch next page
5. Repeat until no more pages

This avoids loading all products in memory at once
"""

import os
import sys
import logging
import gc
import requests
import re
from datetime import datetime, timezone
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('feed_generation.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import modules
from src.shopify_client import ShopifyClient
from src.transformer import ProductTransformer
from src.xml_generator import StreamingXMLGenerator
from src.config_loader import ConfigLoader


class FeedGeneratorService:
    def __init__(self):
        # Load environment variables
        self.shop_url = os.getenv('SHOPIFY_SHOP_URL')
        self.access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        self.base_url = os.getenv('SHOP_BASE_URL', 'https://racoon-lab.it')
        
        if not self.shop_url or not self.access_token:
            raise ValueError("Missing required environment variables: SHOPIFY_SHOP_URL, SHOPIFY_ACCESS_TOKEN")
        
        # Initialize components
        logger.info("Initializing feed generator...")
        self.client = ShopifyClient(self.shop_url, self.access_token)
        self.config = ConfigLoader('config')
        self.transformer = ProductTransformer(self.config, self.base_url)
        
        # Output directory
        self.output_dir = Path('public')
        self.output_dir.mkdir(exist_ok=True)
        
    def generate_feed(self):
        """
        Generate complete Google Shopping feed with page-by-page streaming
        
        MEMORY-EFFICIENT ARCHITECTURE:
        - Fetch ONE page at a time (250 products)
        - Process immediately (no accumulation)
        - Write to XML and clear memory
        - Repeat for next page
        
        Keeps memory <400MB even with 16,000+ products
        """
        try:
            start_time = datetime.now(timezone.utc)
            logger.info(f"START: Feed generation at {start_time.isoformat()}")
            logger.info("="*80)
            
            # Step 1: Open XML generator
            output_file = self.output_dir / 'google_shopping_feed.xml'
            logger.info(f"Opening XML generator: {output_file}")
            
            xml_generator = StreamingXMLGenerator(str(output_file))
            xml_generator.start_feed(
                title="Racoon Lab - Google Shopping Feed",
                link=self.base_url,
                description="Custom sneakers and footwear from Racoon Lab"
            )
            
            # Step 2: Process page by page
            logger.info("="*80)
            logger.info("Processing products (page-by-page streaming)...")
            
            total_items = 0
            total_products = 0
            page = 1
            page_info = None
            
            while True:
                # Fetch ONE page
                logger.info(f"Fetching page {page}...")
                
                params = {
                    'limit': 250,
                    'fields': 'id,title,handle,vendor,product_type,tags,body_html,variants,images,image,status'
                }
                
                # Only add status filter on first page (Shopify API restriction)
                if not page_info:
                    params['status'] = 'active'
                else:
                    params['page_info'] = page_info
                
                url = f"https://{self.client.shop_url}/admin/api/2024-10/products.json"
                
                try:
                    self.client._rate_limit()
                    response = requests.get(url, headers=self.client.headers, params=params, timeout=30)
                    
                    if response.status_code != 200:
                        logger.error(f"API error {response.status_code}: {response.text}")
                        break
                    
                    data = response.json()
                    products = data.get('products', [])
                    
                    if not products:
                        logger.info(f"No more products, finished at page {page}")
                        break
                    
                    # Filter active products (can't use status param with page_info)
                    active_products = [p for p in products if p.get('status', '').lower() == 'active']
                    
                    logger.info(f"Page {page}: {len(active_products)} active products")
                    
                    # Process each product IMMEDIATELY (don't accumulate)
                    for product in active_products:
                        try:
                            # Fetch metafields + collections
                            product_with_meta = self.client.get_product_with_metafields_and_collections(product)
                            
                            # Transform to Google Shopping items
                            metafields = product_with_meta.get('metafields', {})
                            collections = product_with_meta.get('collections', [])
                            items = self.transformer.transform_product(product_with_meta, metafields, collections)
                            
                            # Write to XML immediately
                            for item in items:
                                xml_generator.add_item(item)
                                total_items += 1
                            
                            total_products += 1
                            
                        except Exception as e:
                            logger.error(f"Error processing product {product.get('id')}: {e}")
                            continue
                    
                    logger.info(f"Page {page} complete: {total_products} products total, {total_items} items total")
                    
                    # Check for next page
                    link_header = response.headers.get('Link', '')
                    if 'rel="next"' in link_header:
                        match = re.search(r'page_info=([^&>]+)', link_header)
                        if match:
                            page_info = match.group(1)
                            page += 1
                            
                            # Clear memory after each page
                            gc.collect()
                        else:
                            break
                    else:
                        break
                        
                except Exception as e:
                    logger.error(f"Error fetching page {page}: {e}")
                    break
            
            # Step 3: Close XML generator
            logger.info("="*80)
            logger.info("Finalizing XML...")
            xml_generator.end_feed()
            
            # Success metrics
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            file_size = output_file.stat().st_size / (1024 * 1024)  # MB
            
            logger.info("="*80)
            logger.info("FEED GENERATION COMPLETED")
            logger.info(f"Total products: {total_products}")
            logger.info(f"Total items: {total_items}")
            logger.info(f"File size: {file_size:.2f} MB")
            logger.info(f"Duration: {duration:.0f}s ({duration/60:.1f}min)")
            logger.info(f"Output: {output_file}")
            logger.info("="*80)
            
            return True
            
        except Exception as e:
            logger.error(f"FEED GENERATION FAILED: {e}", exc_info=True)
            return False


def main():
    """Main entry point for cron job"""
    try:
        generator = FeedGeneratorService()
        success = generator.generate_feed()
        
        if success:
            logger.info("Feed generation successful!")
            sys.exit(0)
        else:
            logger.error("Feed generation failed!")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
