"""
Main Feed Generator - v4.1 SINCE_ID PAGINATION
Uses since_id instead of page_info to allow status=active filter on all pages

ARCHITECTURE:
1. Open XML generator
2. Fetch ONE page (250 active products) using since_id
3. Process each product immediately
4. Update since_id and fetch next page
5. Stop when no more products

ADVANTAGE: No Python filtering needed - API returns ONLY active products
"""

import os
import sys
import logging
import gc
import requests
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
        Generate Google Shopping feed with since_id pagination
        
        Uses since_id instead of page_info so we can keep status='active' filter
        on ALL pages - no Python filtering needed!
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
            
            # Step 2: Process page by page with since_id
            logger.info("="*80)
            logger.info("Processing products (since_id pagination)...")
            
            total_items = 0
            total_products = 0
            page = 1
            last_product_id = 0
            
            while True:
                logger.info(f"Fetching page {page}...")
                
                params = {
                    'status': 'active',  # ✅ Works with since_id!
                    'limit': 250,
                    'order': 'id asc',  # Required for since_id
                    'fields': 'id,title,handle,vendor,product_type,tags,body_html,variants,images,image,status'
                }
                
                if last_product_id > 0:
                    params['since_id'] = last_product_id
                
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
                    
                    # All products are active (filtered by API)
                    logger.info(f"Page {page}: {len(products)} active products")
                    
                    # Process each product IMMEDIATELY
                    for product in products:
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
                    
                    # Update since_id for next page
                    last_product_id = products[-1]['id']
                    page += 1
                    
                    # Clear memory
                    gc.collect()
                        
                except Exception as e:
                    logger.error(f"Error fetching page {page}: {e}")
                    break
            
            # Step 3: Close XML
            logger.info("="*80)
            logger.info("Finalizing XML...")
            xml_generator.end_feed()
            
            # Metrics
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            file_size = output_file.stat().st_size / (1024 * 1024)
            
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
    """Main entry point"""
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
