"""
Shopify API Client with Rate Limiting
Handles automatic retry and rate limit management
"""

import requests
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ShopifyClient:
    def __init__(self, shop_url: str, access_token: str):
        self.shop_url = shop_url
        self.access_token = access_token
        self.base_url = f"https://{shop_url}/admin/api/2024-10"
        self.headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json"
        }
        
        # Rate limiting tracking
        self.last_request_time = 0
        self.min_request_interval = 0.5  # 500ms = 2 req/sec max
        self.bucket_size = 40
        self.current_bucket_level = 40
        
    def _wait_for_rate_limit(self):
        """Ensure we don't exceed rate limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
    
    def _update_rate_limit_from_headers(self, headers: Dict):
        """Update rate limit tracking from response headers"""
        rate_limit = headers.get('X-Shopify-Shop-Api-Call-Limit', '')
        
        if rate_limit:
            try:
                current, maximum = rate_limit.split('/')
                self.current_bucket_level = int(maximum) - int(current)
                
                # If bucket is getting low, slow down
                if self.current_bucket_level < 5:
                    logger.warning(f"⚠️ Rate limit bucket low: {current}/{maximum}")
                    time.sleep(2)  # Wait 2 seconds to let bucket refill
                    
            except Exception as e:
                logger.debug(f"Could not parse rate limit header: {e}")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make HTTP request with automatic retry and rate limiting"""
        url = f"{self.base_url}{endpoint}"
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Wait for rate limit
                self._wait_for_rate_limit()
                
                # Make request
                response = requests.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    timeout=30,
                    **kwargs
                )
                
                # Update timing
                self.last_request_time = time.time()
                
                # Update rate limit tracking
                self._update_rate_limit_from_headers(response.headers)
                
                # Handle rate limiting (429)
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 2))
                    logger.warning(f"⏳ Rate limited! Waiting {retry_after}s...")
                    time.sleep(retry_after)
                    retry_count += 1
                    continue
                
                # Handle server errors (5xx) with exponential backoff
                if response.status_code >= 500:
                    wait_time = min(2 ** retry_count, 60)  # Max 60s
                    logger.warning(f"⚠️ Server error {response.status_code}, retry {retry_count+1}/{max_retries} in {wait_time}s")
                    time.sleep(wait_time)
                    retry_count += 1
                    continue
                
                # Success or client error (4xx) - return
                return response
                
            except requests.exceptions.Timeout:
                wait_time = min(2 ** retry_count, 30)
                logger.warning(f"⏱️ Timeout, retry {retry_count+1}/{max_retries} in {wait_time}s")
                time.sleep(wait_time)
                retry_count += 1
                
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Request failed: {e}")
                retry_count += 1
                time.sleep(2 ** retry_count)
        
        # All retries failed
        raise Exception(f"Failed after {max_retries} retries")
    
    def get_products(self, limit: int = 250, fields: Optional[str] = None) -> List[Dict]:
        """Get all products with pagination"""
        products = []
        
        params = {'limit': limit}
        if fields:
            params['fields'] = fields
        
        logger.info("📦 Fetching products from Shopify...")
        
        next_url = f"/products.json"
        page = 1
        
        while next_url:
            logger.info(f"  Page {page}...")
            
            response = self._make_request('GET', next_url, params=params if page == 1 else None)
            
            if response.status_code != 200:
                logger.error(f"❌ Error {response.status_code}: {response.text[:200]}")
                break
            
            data = response.json()
            page_products = data.get('products', [])
            products.extend(page_products)
            
            logger.info(f"  ✅ Retrieved {len(page_products)} products (total: {len(products)})")
            
            # Check for pagination (Link header)
            link_header = response.headers.get('Link', '')
            next_url = None
            
            if 'rel="next"' in link_header:
                # Parse Link header: <url>; rel="next"
                for link in link_header.split(','):
                    if 'rel="next"' in link:
                        next_url = link.split(';')[0].strip('<> ')
                        # Extract just the path after base URL
                        next_url = next_url.split('/admin/api/2024-10')[-1]
                        break
            
            page += 1
            
            # Safety: don't fetch more than 50 pages
            if page > 50:
                logger.warning("⚠️ Reached 50 pages limit, stopping")
                break
        
        logger.info(f"✅ Total products retrieved: {len(products)}")
        return products
    
    def get_product_metafields(self, product_id: int) -> Dict:
        """Get metafields for a specific product"""
        endpoint = f"/products/{product_id}/metafields.json"
        
        try:
            response = self._make_request('GET', endpoint)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"⚠️ Could not fetch metafields for product {product_id}: {response.status_code}")
                return {'metafields': []}
                
        except Exception as e:
            logger.error(f"❌ Error fetching metafields for product {product_id}: {e}")
            return {'metafields': []}
    
    def get_products_with_metafields(self, limit: int = 250, fields: Optional[str] = None) -> List[Dict]:
        """Get all products with their metafields"""
        products = self.get_products(limit=limit, fields=fields)
        
        logger.info(f"📊 Fetching metafields for {len(products)} products...")
        
        for i, product in enumerate(products, 1):
            if i % 50 == 0:
                logger.info(f"  Progress: {i}/{len(products)}")
            
            product_id = product['id']
            metafields = self.get_product_metafields(product_id)
            product['metafields'] = metafields.get('metafields', [])
        
        logger.info("✅ All metafields fetched")
        return products
    
    def test_connection(self) -> bool:
        """Test API connection"""
        try:
            logger.info("🔍 Testing Shopify API connection...")
            response = self._make_request('GET', '/shop.json')
            
            if response.status_code == 200:
                shop_data = response.json().get('shop', {})
                logger.info(f"✅ Connected to: {shop_data.get('name', 'Unknown')}")
                logger.info(f"   Domain: {shop_data.get('domain', 'Unknown')}")
                return True
            else:
                logger.error(f"❌ Connection failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False


# Example usage
if __name__ == '__main__':
    # Test with your credentials
    SHOP_URL = "racoon-lab.myshopify.com"
    ACCESS_TOKEN = "your_token_here"
    
    client = ShopifyClient(SHOP_URL, ACCESS_TOKEN)
    
    # Test connection
    if client.test_connection():
        # Get first 5 products
        products = client.get_products(limit=5, fields='id,title,tags,variants')
        print(f"\nRetrieved {len(products)} products")
        for p in products:
            print(f"  - {p['title']}")
