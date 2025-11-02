"""
Main Feed Generator Script for Production
Runs as cron job on Render.com
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('feed_generation.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import modules
from src.shopify_client import ShopifyClient
from src.transformer import ProductTransformer
from src.xml_generator import XMLFeedGenerator
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
        self.client = ShopifyClient(self.shop_url, self.access_token)
        self.config = ConfigLoader('config')
        self.transformer = ProductTransformer(self.config, self.base_url)
        self.generator = XMLFeedGenerator()
        
        # Output directory
        self.output_dir = Path('public')
        self.output_dir.mkdir(exist_ok=True)
        
    def generate_feed(self):
        """Generate complete Google Shopping feed"""
        try:
            logger.info("=" * 70)
            logger.info("🚀 FEED GENERATION STARTED")
            logger.info("=" * 70)
            logger.info(f"Time: {datetime.utcnow().isoformat()}Z")
            logger.info(f"Shop: {self.shop_url}")
            logger.info("")
            
            # Test connection
            logger.info("Testing Shopify connection...")
            if not self.client.test_connection():
                raise Exception("Failed to connect to Shopify API")
            
            # Fetch products with metafields
            logger.info("Fetching products with metafields...")
            products = self.client.get_products_with_metafields(
                limit=250,
                fields='id,title,handle,body_html,vendor,product_type,tags,variants,images'
            )
            
            logger.info(f"Retrieved {len(products)} products")
            
            # Transform products
            logger.info("Transforming products to Google Shopping format...")
            all_items = []
            products_with_reviews = 0
            
            for i, product in enumerate(products, 1):
                if i % 100 == 0:
                    logger.info(f"  Progress: {i}/{len(products)}")
                
                # Prepare metafields
                metafields = {'metafields': product.get('metafields', [])}
                
                # Check for reviews
                has_reviews = any(
                    mf.get('namespace') in ['stamped', 'reviews', 'judgeme', 'loox']
                    and mf.get('key') in ['reviews_average', 'rating', 'avg_rating']
                    for mf in metafields.get('metafields', [])
                )
                if has_reviews:
                    products_with_reviews += 1
                
                # Transform
                items = self.transformer.transform_product(product, metafields)
                all_items.extend(items)
            
            logger.info(f"Generated {len(all_items)} feed items from {len(products)} products")
            logger.info(f"Products with reviews: {products_with_reviews}")
            
            # Generate XML
            logger.info("Generating XML feed...")
            shop_info = {
                'title': 'Racoon Lab - Sneakers Personalizzate',
                'url': self.base_url
            }
            
            xml_content = self.generator.generate_feed(all_items, shop_info)
            
            # Save feed
            feed_path = self.output_dir / 'google_shopping_feed.xml'
            self.generator.save_feed(xml_content, str(feed_path))
            
            file_size = len(xml_content.encode('utf-8'))
            file_size_mb = file_size / (1024 * 1024)
            
            logger.info(f"Feed saved to: {feed_path}")
            logger.info(f"Feed size: {file_size_mb:.2f} MB")
            
            # Save metadata
            metadata = {
                'generated_at': datetime.utcnow().isoformat() + 'Z',
                'product_count': len(products),
                'item_count': len(all_items),
                'products_with_reviews': products_with_reviews,
                'file_size_bytes': file_size,
                'status': 'success'
            }
            
            import json
            metadata_path = self.output_dir / 'feed_metadata.json'
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info("")
            logger.info("=" * 70)
            logger.info("✅ FEED GENERATION COMPLETED SUCCESSFULLY")
            logger.info("=" * 70)
            logger.info(f"Total items: {len(all_items)}")
            logger.info(f"File size: {file_size_mb:.2f} MB")
            logger.info(f"Products with reviews: {products_with_reviews}")
            logger.info("")
            
            return {
                'success': True,
                'items': len(all_items),
                'products': len(products),
                'file_size': file_size,
                'products_with_reviews': products_with_reviews
            }
            
        except Exception as e:
            logger.error("=" * 70)
            logger.error("❌ FEED GENERATION FAILED")
            logger.error("=" * 70)
            logger.error(f"Error: {str(e)}")
            logger.exception(e)
            
            # Save error metadata
            import json
            metadata = {
                'generated_at': datetime.utcnow().isoformat() + 'Z',
                'status': 'error',
                'error': str(e)
            }
            
            metadata_path = self.output_dir / 'feed_metadata.json'
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            raise


def main():
    """Main entry point"""
    try:
        service = FeedGeneratorService()
        result = service.generate_feed()
        
        print("\n✅ Success!")
        print(f"Generated {result['items']} items from {result['products']} products")
        print(f"File size: {result['file_size'] / (1024*1024):.2f} MB")
        
        if result['products_with_reviews'] > 0:
            print(f"⭐ {result['products_with_reviews']} products have star ratings!")
        
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
