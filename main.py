"""
Main Feed Generator - v3.5 STABLE
Streaming processing for memory efficiency (512MB RAM limit)

ARCHITECTURE:
1. Fetch basic products list (no metafields) - ~50MB
2. Process ONE product at a time:
   - Fetch metafields + collections for this product
   - Transform to Google Shopping items
   - Write directly to XML
   - Clear memory
3. No large lists in memory - everything streams to file

PERFORMANCE:
- 1,042 products → ~10,500 items
- Time: ~12-18 minutes
- Memory: <400MB peak
"""

import os
import sys
import logging
import gc
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
        Generate complete Google Shopping feed with streaming
        
        STREAMING ARCHITECTURE:
        1. Fetch products list (no metafields) - LOW memory
        2. Open XML generator in streaming mode
        3. For each product:
           a. Fetch metafields + collections
           b. Transform to items
           c. Write to XML immediately
           d. Clear memory (gc.collect)
        4. Close XML generator
        
        This keeps memory usage <400MB even for 10,000+ items
        """
        try:
            start_time = datetime.now(timezone.utc)
            logger.info(f"🚀 FEED GENERATION STARTED at {start_time.isoformat()}")
            logger.info("="*80)
            
            # Step 1: Get products list (no metafields yet)
            logger.info("📦 Step 1: Fetching products list...")
            products = self.client.get_all_products()
            
            if not products:
                logger.error("❌ No products retrieved from Shopify")
                return False
            
            logger.info(f"✅ Retrieved: {len(products)} products")
            logger.info("="*80)
            
            # Step 2: Open XML generator in streaming mode
            output_file = self.output_dir / 'google_shopping_feed.xml'
            logger.info(f"📝 Step 2: Opening XML generator (streaming mode)...")
            logger.info(f"   Output: {output_file}")
            
            xml_generator = StreamingXMLGenerator(str(output_file))
            xml_generator.start_feed(
                title="Racoon Lab - Google Shopping Feed",
                link=self.base_url,
                description="Custom sneakers and footwear from Racoon Lab"
            )
            
            # Step 3: Process products one by one (streaming)
            logger.info("="*80)
            logger.info("🔄 Step 3: Processing products (streaming)...")
            
            total_items = 0
            progress_interval = 50  # Log every 50 products
            
            for idx, product in enumerate(products, 1):
                try:
                    # 3a. Fetch metafields + collections for THIS product
                    product_with_meta = self.client.get_product_with_metafields_and_collections(product)
                    
                    # 3b. Transform to Google Shopping items
                    metafields = product_with_meta.get('metafields', {})
                    collections = product_with_meta.get('collections', [])
                    items = self.transformer.transform_product(product_with_meta, metafields, collections)
                    
                    # 3c. Write items to XML immediately
                    for item in items:
                        xml_generator.add_item(item)
                        total_items += 1
                    
                    # 3d. Progress logging
                    if idx % progress_interval == 0:
                        logger.info(f"   Progress: {idx}/{len(products)} products ({total_items} items)")
                    
                    # 3e. Clear memory periodically
                    if idx % 100 == 0:
                        gc.collect()
                    
                except Exception as e:
                    logger.error(f"❌ Error processing product {product.get('id')}: {e}")
                    continue
            
            # Step 4: Close XML generator
            logger.info("="*80)
            logger.info("📝 Step 4: Finalizing XML...")
            xml_generator.end_feed()
            
            # Step 5: Success metrics
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            file_size = output_file.stat().st_size / (1024 * 1024)  # MB
            
            logger.info("="*80)
            logger.info("✅ FEED GENERATION COMPLETED")
            logger.info(f"   Total products: {len(products)}")
            logger.info(f"   Total items: {total_items}")
            logger.info(f"   File size: {file_size:.2f} MB")
            logger.info(f"   Duration: {duration:.0f}s ({duration/60:.1f}min)")
            logger.info(f"   Output: {output_file}")
            logger.info("="*80)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ FEED GENERATION FAILED: {e}", exc_info=True)
            return False


def main():
    """Main entry point for cron job"""
    try:
        generator = FeedGeneratorService()
        success = generator.generate_feed()
        
        if success:
            logger.info("✅ Feed generation successful!")
            sys.exit(0)
        else:
            logger.error("❌ Feed generation failed!")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
