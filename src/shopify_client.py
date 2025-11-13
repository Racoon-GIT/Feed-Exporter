"""
Shopify API Client with Collections Support
Handles rate limiting and memory-efficient streaming
"""

import requests
import time
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ShopifyClient:
    def __init__(self, shop_url: str, access_token: str):
        """
        Initialize Shopify API client
        
        Args:
            shop_url: Full shop URL (e.g., 'racoon-lab.myshopify.com')
            access_token: Admin API access token
        """
        self.shop_url = shop_url.replace('https://', '').replace('http://', '')
        self.access_token = access_token
        self.base_url = f"https://{self.shop_url}/admin/api/2024-10"
        self.headers = {
            'X-Shopify-Access-Token': access_token,
            'Content-Type': 'application/json'
        }
        
        # Rate limiting (Shopify: 2 requests/second for standard plans)
        self.min_request_interval = 0.5  # 500ms between requests
        self.last_request_time = 0
        
        # Retry settings
        self.max_retries = 3
        self.retry_delay = 2  # seconds
    
    def _rate_limit(self):
        """Enforce rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make API request with rate limiting and retry logic"""
        url = f"{self.base_url}/{endpoint}"
        
        for attempt in range(self.max_retries):
            try:
                self._rate_limit()
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:  # Rate limit
                    retry_after = int(response.headers.get('Retry-After', self.retry_delay))
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue
                else:
                    logger.error(f"API error {response.status_code}: {response.text}")
                    response.raise_for_status()
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    raise
        
        return {}
    
    def get_products_count(self) -> int:
        """Get total count of active products"""
        try:
            data = self._make_request('products/count.json', {'status': 'active'})
            count = data.get('count', 0)
            logger.info(f"Total active products: {count}")
            return count
        except Exception as e:
            logger.error(f"Error getting products count: {e}")
            return 0
    
    def get_all_products(self, limit: int = 250) -> List[Dict]:
        """
        Get all active products with pagination
        
        CRITICAL: Includes 'status' field in API call (required for filtering)
        
        Args:
            limit: Products per page (max 250)
        
        Returns:
            List of product dictionaries
        """
        all_products = []
        page_info = None
        page = 1
        
        logger.info("Fetching all active products...")
        
        while True:
            try:
                params = {
                    'status': 'active',  # ✅ CRITICAL: Request status field
                    'limit': limit,
                    'fields': 'id,title,handle,vendor,product_type,tags,body_html,variants,images,image,status'
                }
                
                if page_info:
                    params['page_info'] = page_info
                
                data = self._make_request('products.json', params)
                products = data.get('products', [])
                
                if not products:
                    break
                
                all_products.extend(products)
                logger.info(f"  Page {page}: Retrieved {len(products)} products (total: {len(all_products)})")
                
                # Check for next page
                link_header = data.get('link', '')
                if 'rel="next"' in link_header:
                    # Extract page_info from link header
                    import re
                    match = re.search(r'page_info=([^&>]+)', link_header)
                    if match:
                        page_info = match.group(1)
                        page += 1
                    else:
                        break
                else:
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching products page {page}: {e}")
                break
        
        logger.info(f"✅ Retrieved {len(all_products)} total active products")
        return all_products
    
    def get_product_metafields(self, product_id: str) -> Dict:
        """
        Get metafields for a single product
        
        Returns metafields organized by namespace:
        {
            'mm-google-shopping': {'gender': 'female', 'color': 'red', ...},
            'stamped': {'rating': '4.5', ...},
            ...
        }
        """
        try:
            data = self._make_request(f'products/{product_id}/metafields.json', {'limit': 250})
            metafields_list = data.get('metafields', [])
            
            # Organize by namespace
            organized = {}
            for mf in metafields_list:
                namespace = mf.get('namespace', '')
                key = mf.get('key', '')
                value = mf.get('value', '')
                
                if namespace not in organized:
                    organized[namespace] = {}
                
                organized[namespace][key] = value
            
            return organized
            
        except Exception as e:
            logger.error(f"Error fetching metafields for product {product_id}: {e}")
            return {}
    
    def get_product_collections(self, product_id: str) -> List[str]:
        """
        Get collection titles for a product
        
        Returns:
            List of collection titles (e.g., ["Summer Collection", "Best Sellers"])
        """
        try:
            data = self._make_request(f'products/{product_id}/collections.json')
            collections_data = data.get('custom_collections', []) + data.get('smart_collections', [])
            
            # Extract titles
            titles = []
            for collection in collections_data:
                title = collection.get('title', '')
                if title:
                    titles.append(title)
            
            return titles
            
        except Exception as e:
            logger.error(f"Error fetching collections for product {product_id}: {e}")
            return []
    
    def get_product_with_metafields_and_collections(self, product: Dict) -> Dict:
        """
        Enrich a product with its metafields and collections
        
        This is called once per product in the streaming process.
        
        Args:
            product: Basic product dict from get_all_products()
        
        Returns:
            Same product dict with added 'metafields' and 'collections' keys
        """
        product_id = str(product.get('id', ''))
        
        # Get metafields
        metafields = self.get_product_metafields(product_id)
        product['metafields'] = metafields
        
        # Get collections
        collections = self.get_product_collections(product_id)
        product['collections'] = collections
        
        return product
