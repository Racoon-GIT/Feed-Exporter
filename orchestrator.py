"""
Feed Orchestrator - Unified feed generation for all platforms
Handles Google, Meta, and future platforms in a single run

Features:
- Platform feature flags (enable/disable per platform)
- Streaming memory-efficient processing
- Metrics collection per platform
- Backup previous feeds
- Health monitoring
"""

import os
import sys
import json
import logging
import gc
import time
import shutil
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

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

# Import core components
from src.shopify_client import ShopifyClient
from src.config_loader import ConfigLoader

# Import platform-specific components
from platforms.google.mapper import GoogleMapper
from platforms.meta.mapper import MetaMapper
from src.xml_generator import StreamingXMLGenerator as GoogleXMLGenerator
from platforms.meta.xml_generator import MetaXMLGenerator


class FeedOrchestrator:
    """
    Orchestrates feed generation for all enabled platforms
    
    Architecture:
    1. Load platform configuration
    2. Initialize Shopify client (shared)
    3. For each enabled platform:
       a. Initialize platform-specific mapper
       b. Initialize platform-specific XML generator
       c. Stream products and transform
       d. Collect metrics
    4. Save metrics and health status
    """
    
    def __init__(self):
        """Initialize orchestrator"""
        # Load environment variables
        self.shop_url = os.getenv('SHOPIFY_SHOP_URL')
        self.access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        self.base_url = os.getenv('SHOP_BASE_URL', 'https://racoon-lab.it')
        
        if not self.shop_url or not self.access_token:
            raise ValueError("Missing required environment variables")
        
        # Initialize shared components
        logger.info("Initializing Feed Orchestrator...")
        self.client = ShopifyClient(self.shop_url, self.access_token)
        self.config = ConfigLoader('config')
        
        # Load platform configuration
        self.platforms_config = self._load_platforms_config()
        
        # Output directory
        self.output_dir = Path('public')
        self.output_dir.mkdir(exist_ok=True)
        
        # Metrics
        self.metrics = {}
    
    def _load_platforms_config(self) -> Dict:
        """Load platform configuration from JSON"""
        config_file = Path('config/platforms.json')
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load platforms.json: {e}. Using defaults.")
            return {
                "platforms": {
                    "google": {"enabled": True, "feed_filename": "google_shopping_feed.xml"},
                    "meta": {"enabled": True, "feed_filename": "meta_catalog_feed.xml"}
                },
                "settings": {
                    "backup_previous_feed": True,
                    "validate_before_save": True,
                    "collect_metrics": True
                }
            }
    
    def generate_all_feeds(self):
        """
        Generate all enabled platform feeds
        
        Returns:
            True if all enabled feeds succeeded, False otherwise
        """
        start_time = datetime.now(timezone.utc)
        logger.info(f"START: Feed Orchestrator at {start_time.isoformat()}")
        logger.info("="*80)
        
        enabled_platforms = []
        for platform_name, platform_config in self.platforms_config['platforms'].items():
            if platform_config.get('enabled', False):
                enabled_platforms.append(platform_name)
        
        logger.info(f"Enabled platforms: {', '.join(enabled_platforms)}")
        logger.info("="*80)
        
        success_count = 0
        
        for platform_name in enabled_platforms:
            try:
                logger.info(f"\n{'='*80}")
                logger.info(f"GENERATING {platform_name.upper()} FEED")
                logger.info(f"{'='*80}\n")
                
                if self._generate_platform_feed(platform_name):
                    success_count += 1
                    logger.info(f"✅ {platform_name.upper()} feed generated successfully")
                else:
                    logger.error(f"❌ {platform_name.upper()} feed generation failed")
                    
            except Exception as e:
                logger.error(f"❌ Error generating {platform_name} feed: {e}", exc_info=True)
        
        # Save metrics
        if self.platforms_config['settings'].get('collect_metrics', True):
            self._save_metrics()
        
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        logger.info("\n" + "="*80)
        logger.info("FEED ORCHESTRATOR COMPLETED")
        logger.info(f"Total duration: {duration:.0f}s ({duration/60:.1f}min)")
        logger.info(f"Success: {success_count}/{len(enabled_platforms)} platforms")
        logger.info("="*80)
        
        return success_count == len(enabled_platforms)
    
    def _generate_platform_feed(self, platform_name: str) -> bool:
        """
        Generate feed for a specific platform
        
        Args:
            platform_name: 'google' or 'meta'
        
        Returns:
            True if successful, False otherwise
        """
        platform_config = self.platforms_config['platforms'][platform_name]
        platform_start_time = time.time()
        
        # Initialize mapper
        mapper = self._get_mapper(platform_name)
        if not mapper:
            logger.error(f"Unknown platform: {platform_name}")
            return False
        
        # Initialize XML generator
        feed_filename = platform_config.get('feed_filename', f'{platform_name}_feed.xml')
        output_file = self.output_dir / feed_filename
        
        # Backup previous feed if enabled
        if self.platforms_config['settings'].get('backup_previous_feed', True):
            self._backup_feed(output_file)
        
        xml_generator = self._get_xml_generator(platform_name, str(output_file))
        
        # Start feed
        title = platform_config.get('title', f'Racoon Lab - {platform_name.title()} Feed')
        description = platform_config.get('description', f'Product catalog for {platform_name}')
        
        xml_generator.start_feed(
            title=title,
            link=self.base_url,
            description=description
        )
        
        # Process products with since_id pagination
        total_items = 0
        total_products = 0
        page = 1
        last_product_id = 0
        
        logger.info(f"Processing products for {platform_name}...")
        
        while True:
            params = {
                'status': 'active',
                'limit': 250,
                'order': 'id asc',
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
                
                logger.info(f"Page {page}: {len(products)} active products")
                
                # Process each product
                for product in products:
                    try:
                        # Fetch metafields + collections
                        product_with_meta = self.client.get_product_with_metafields_and_collections(product)
                        
                        # Transform using platform mapper
                        metafields = product_with_meta.get('metafields', {})
                        collections = product_with_meta.get('collections', [])
                        items = mapper.transform_product(product_with_meta, metafields, collections)
                        
                        # Write to XML
                        for item in items:
                            xml_generator.add_item(item)
                            total_items += 1
                        
                        total_products += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing product {product.get('id')}: {e}")
                        continue
                
                logger.info(f"Page {page} complete: {total_products} products, {total_items} items")
                
                # Update since_id
                last_product_id = products[-1]['id']
                page += 1
                
                # Clear memory
                gc.collect()
                
            except Exception as e:
                logger.error(f"Error fetching page {page}: {e}")
                break
        
        # Close XML
        xml_generator.end_feed()
        
        # Calculate metrics
        platform_duration = time.time() - platform_start_time
        file_size = output_file.stat().st_size / (1024 * 1024)
        
        # Store metrics
        self.metrics[platform_name] = {
            'platform': platform_name,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'total_products': total_products,
            'total_items': total_items,
            'file_size_mb': round(file_size, 2),
            'duration_seconds': round(platform_duration, 0),
            'feed_filename': feed_filename,
            'success': True
        }
        
        logger.info(f"\n{platform_name.upper()} FEED METRICS:")
        logger.info(f"  Products: {total_products}")
        logger.info(f"  Items: {total_items}")
        logger.info(f"  File size: {file_size:.2f} MB")
        logger.info(f"  Duration: {platform_duration:.0f}s ({platform_duration/60:.1f}min)")
        
        return True
    
    def _get_mapper(self, platform_name: str):
        """Get platform-specific mapper"""
        if platform_name == 'google':
            return GoogleMapper(self.config, self.base_url)
        elif platform_name == 'meta':
            return MetaMapper(self.config, self.base_url)
        else:
            return None
    
    def _get_xml_generator(self, platform_name: str, output_file: str):
        """Get platform-specific XML generator"""
        if platform_name == 'google':
            return GoogleXMLGenerator(output_file)
        elif platform_name == 'meta':
            return MetaXMLGenerator(output_file)
        else:
            raise ValueError(f"Unknown platform: {platform_name}")
    
    def _backup_feed(self, feed_path: Path):
        """Backup previous feed if exists"""
        if feed_path.exists():
            backup_path = feed_path.with_suffix('.xml.backup')
            try:
                shutil.copy2(feed_path, backup_path)
                logger.info(f"✅ Backed up previous feed to {backup_path.name}")
            except Exception as e:
                logger.warning(f"Could not backup feed: {e}")
    
    def _save_metrics(self):
        """Save metrics to JSON file"""
        metrics_file = self.output_dir / 'feed_metrics.json'
        
        try:
            with open(metrics_file, 'w', encoding='utf-8') as f:
                json.dump(self.metrics, f, indent=2)
            
            logger.info(f"✅ Metrics saved to {metrics_file}")
        except Exception as e:
            logger.warning(f"Could not save metrics: {e}")


def main():
    """Main entry point"""
    try:
        orchestrator = FeedOrchestrator()
        success = orchestrator.generate_all_feeds()
        
        if success:
            logger.info("✅ All feeds generated successfully!")
            sys.exit(0)
        else:
            logger.error("❌ Some feeds failed to generate")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
