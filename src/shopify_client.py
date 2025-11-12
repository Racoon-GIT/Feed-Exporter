"""
Shopify API Client with Rate Limiting - MEMORY OPTIMIZED
Reduces memory usage by not fetching metafields unless needed
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
        """Get all products with pagination (WITHOUT metafields to save memory)"""
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
    
    def get_all_collections(self) -> Dict[int, str]:
        """
        Get all collections (custom + smart) and return mapping: collection_id -> title
        This is called ONCE at the beginning to avoid repeated API calls
        """
        collections_map = {}
        
        try:
            # Fetch custom collections
            logger.info("📚 Fetching custom collections...")
            endpoint = "/custom_collections.json"
            params = {'limit': 250, 'fields': 'id,title'}
            
            response = self._make_request('GET', endpoint, params=params)
            
            if response.status_code == 200:
                custom_collections = response.json().get('custom_collections', [])
                for col in custom_collections:
                    collections_map[col['id']] = col['title']
                logger.info(f"  ✅ Retrieved {len(custom_collections)} custom collections")
            
            # Fetch smart collections
            logger.info("📚 Fetching smart collections...")
            endpoint = "/smart_collections.json"
            
            response = self._make_request('GET', endpoint, params=params)
            
            if response.status_code == 200:
                smart_collections = response.json().get('smart_collections', [])
                for col in smart_collections:
                    collections_map[col['id']] = col['title']
                logger.info(f"  ✅ Retrieved {len(smart_collections)} smart collections")
            
            logger.info(f"✅ Total collections mapped: {len(collections_map)}")
            return collections_map
            
        except Exception as e:
            logger.error(f"❌ Error fetching collections: {e}")
            return {}
    
    def get_product_collection_ids(self, product_id: int) -> List[int]:
        """
        Get collection IDs for a specific product
        Returns list of collection_ids (to be mapped with get_all_collections)
        """
        endpoint = f"/collects.json"
        params = {'product_id': product_id, 'limit': 250}
        
        try:
            response = self._make_request('GET', endpoint, params=params)
            
            if response.status_code == 200:
                collects = response.json().get('collects', [])
                collection_ids = [collect['collection_id'] for collect in collects]
                return collection_ids
            else:
                logger.warning(f"⚠️ Could not fetch collections for product {product_id}: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error fetching collections for product {product_id}: {e}")
            return []
    
    def get_products_with_metafields(self, limit: int = 250, fields: Optional[str] = None, 
                                    max_products: Optional[int] = None) -> List[Dict]:
        """
        Get products with their metafields
        
        WARNING: This method is MEMORY INTENSIVE for large stores.
        Use get_products() + selective get_product_metafields() instead.
        
        Args:
            limit: Products per page
            fields: Fields to fetch
            max_products: Maximum number of products to fetch metafields for (to limit memory)
        """
        logger.warning("⚠️ get_products_with_metafields is memory intensive!")
        logger.warning("⚠️ Consider using get_products() + selective metafield fetching")
        
        products = self.get_products(limit=limit, fields=fields)
        
        # Limit number of products if specified
        if max_products and len(products) > max_products:
            logger.warning(f"⚠️ Limiting metafield fetch to first {max_products} products to save memory")
            products_to_fetch = products[:max_products]
            products_skipped = products[max_products:]
            
            # Add empty metafields to skipped products
            for product in products_skipped:
                product['metafields'] = []
        else:
            products_to_fetch = products
        
        logger.info(f"📊 Fetching metafields for {len(products_to_fetch)} products...")
        
        for i, product in enumerate(products_to_fetch, 1):
            if i % 50 == 0:
                logger.info(f"  Progress: {i}/{len(products_to_fetch)}")
            
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
