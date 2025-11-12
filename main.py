"""
Main Feed Generator Script for Production - MEMORY OPTIMIZED
Handles large stores (1000+ products) within 512MB RAM limit
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
        self.client = ShopifyClient(self.shop_url, self.access_token)
        self.config = ConfigLoader('config')
        self.transformer = ProductTransformer(self.config, self.base_url)
        
        # Output directory
        self.output_dir = Path('public')
        self.output_dir.mkdir(exist_ok=True)
        
    def generate_feed(self):
        """Generate complete Google Shopping feed with memory optimization"""
        try:
            logger.info("=" * 70)
            logger.info("🚀 FEED GENERATION STARTED (MEMORY OPTIMIZED)")
            logger.info("=" * 70)
            logger.info(f"Time: {datetime.now(timezone.utc).isoformat()}")
            logger.info(f"Shop: {self.shop_url}")
            logger.info("")
            
            # Test connection
            logger.info("Testing Shopify connection...")
            if not self.client.test_connection():
                raise Exception("Failed to connect to Shopify API")
            
            # Fetch ALL collections ONCE (for mapping later)
            logger.info("Fetching all collections (custom + smart)...")
            collections_map = self.client.get_all_collections()
            logger.info(f"✅ Collections map ready with {len(collections_map)} collections")
            
            # Fetch products WITHOUT metafields (saves memory)
            logger.info("Fetching products (without metafields)...")
            products = self.client.get_products(
                limit=250,
                fields='id,title,handle,body_html,vendor,product_type,tags,variants,images,status'
            )
            
            logger.info(f"Retrieved {len(products)} products")
            
            # Initialize streaming XML generator
            feed_path = self.output_dir / 'google_shopping_feed.xml'
            shop_info = {
                'title': 'Racoon Lab - Sneakers Personalizzate',
                'url': self.base_url
            }
            
            generator = StreamingXMLGenerator(str(feed_path), shop_info)
            
            # Process ONE product at a time with metafields
            total_items = 0
            products_with_reviews = 0
            
            logger.info("Processing products one-by-one with metafields (memory efficient)...")
            
            for i, product in enumerate(products, 1):
                # Progress logging
                if i % 100 == 0:
                    logger.info(f"  Progress: {i}/{len(products)} products ({total_items} items)")
                
                # Fetch metafields ONLY for this product (then discard)
                metafields_data = self.client.get_product_metafields(product['id'])
                metafields = {'metafields': metafields_data.get('metafields', [])}
                
                # Fetch collection IDs for this product and map to names
                collection_ids = self.client.get_product_collection_ids(product['id'])
                collection_names = [collections_map.get(cid, '') for cid in collection_ids if cid in collections_map]
                
                # Add collections to product data (for transformer)
                product['collections'] = collection_names
                
                # Check if has reviews
                has_reviews = any(
                    mf.get('namespace') in ['stamped', 'reviews', 'judgeme', 'loox']
                    and mf.get('key') in ['reviews_average', 'rating', 'avg_rating']
                    for mf in metafields.get('metafields', [])
                )
                if has_reviews:
                    products_with_reviews += 1
                
                # Transform product (creates items for all variants)
                items = self.transformer.transform_product(product, metafields)
                
                # Write items IMMEDIATELY to XML (streaming)
                for item in items:
                    generator.add_item(item)
                    total_items += 1
                
                # Clear this product and metafields from memory
                del metafields_data
                del metafields
                del collection_ids
                del collection_names
                del items
                
                # Force garbage collection every 50 products
                if i % 50 == 0:
                    gc.collect()
            
            # Finalize XML
            logger.info("Finalizing XML feed...")
            generator.close()
            
            file_size = feed_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            
            logger.info(f"Feed saved to: {feed_path}")
            logger.info(f"Feed size: {file_size_mb:.2f} MB")
            
            # Save metadata
            metadata = {
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'product_count': len(products),
                'item_count': total_items,
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
            logger.info(f"Total items: {total_items}")
            logger.info(f"File size: {file_size_mb:.2f} MB")
            logger.info(f"Products with reviews: {products_with_reviews}")
            logger.info(f"Memory optimization: Per-product streaming with metafields")
            logger.info("")
            
            return {
                'success': True,
                'items': total_items,
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
                'generated_at': datetime.now(timezone.utc).isoformat(),
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
        print(f"Memory optimized: Per-product streaming ⚡")
        
        if result['products_with_reviews'] > 0:
            print(f"⭐ {result['products_with_reviews']} products have star ratings!")
        
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
