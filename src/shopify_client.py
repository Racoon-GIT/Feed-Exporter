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
        
        # Rate limiting intelligente basato su crediti Shopify
        self.min_request_interval = 0.5  # Base interval (veloce quando hai crediti)
        self.last_request_time = 0
        self.available_credits = 40  # Shopify bucket size
        self.max_credits = 40
        
        # Retry settings
        self.max_retries = 3
        self.retry_delay = 5  # seconds
    
    def _rate_limit(self):
        """
        Rate limiting intelligente basato su crediti Shopify
        
        Logica:
        - Crediti >= 30: veloce (0.5s)
        - Crediti 20-29: normale (1.0s)
        - Crediti 10-19: cauto (1.5s)
        - Crediti < 10: lento (2.5s) per ricaricare
        """
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        # Calcola wait time in base ai crediti disponibili
        if self.available_credits >= 30:
            wait_time = 0.5  # Veloce
        elif self.available_credits >= 20:
            wait_time = 1.0  # Normale
        elif self.available_credits >= 10:
            wait_time = 1.5  # Cauto
        else:
            wait_time = 2.5  # Lento - lascia ricaricare il bucket
            logger.info(f"⚠️ Pochi crediti ({self.available_credits}/{self.max_credits}), rallento...")
        
        if time_since_last < wait_time:
            sleep_time = wait_time - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _update_credits_from_header(self, response_headers: Dict):
        """
        Aggiorna i crediti disponibili leggendo l'header Shopify
        
        Header format: "X-Shopify-Shop-Api-Call-Limit: 32/40"
        Significa: 32 crediti usati su 40 disponibili → 8 crediti rimasti
        """
        call_limit = response_headers.get('X-Shopify-Shop-Api-Call-Limit', '')
        
        if call_limit:
            try:
                # Parse "32/40" format
                used, total = call_limit.split('/')
                used = int(used)
                total = int(total)
                
                # Calcola crediti disponibili
                self.available_credits = total - used
                self.max_credits = total
                
                # Log solo quando i crediti sono bassi
                if self.available_credits < 15:
                    logger.debug(f"📊 Crediti Shopify: {self.available_credits}/{total} disponibili")
                    
            except (ValueError, AttributeError) as e:
                logger.debug(f"Could not parse credit header '{call_limit}': {e}")
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make API request with rate limiting and retry logic"""
        url = f"{self.base_url}/{endpoint}"
        
        for attempt in range(self.max_retries):
            try:
                self._rate_limit()
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                
                # Aggiorna crediti dagli header (sempre, anche in caso di errore)
                self._update_credits_from_header(response.headers)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:  # Rate limit
                    retry_after = int(float(response.headers.get('Retry-After', self.retry_delay)))
                    logger.warning(f"⚠️ Rate limited! Aspetto {retry_after}s (crediti: {self.available_credits}/{self.max_credits})")
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
                    'limit': limit,
                    'fields': 'id,title,handle,vendor,product_type,tags,body_html,variants,images,image,status'
                }
                
                # Only add status filter on first page
                # When using page_info, Shopify doesn't allow other filters
                if not page_info:
                    params['status'] = 'active'
                else:
                    params['page_info'] = page_info
                
                # Make request directly to access headers
                url = f"{self.base_url}/products.json"
                self._rate_limit()
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                
                # Aggiorna crediti dagli header
                self._update_credits_from_header(response.headers)
                
                if response.status_code != 200:
                    logger.error(f"API error {response.status_code}: {response.text}")
                    break
                
                data = response.json()
                products = data.get('products', [])
                
                if not products:
                    break
                
                # Filter active products (can't use status param with page_info in API)
                active_products = [p for p in products if p.get('status', '').lower() == 'active']
                
                all_products.extend(active_products)
                logger.info(f"  Page {page}: Retrieved {len(products)} products ({len(active_products)} active, total: {len(all_products)})")
                
                # Check for next page in HTTP headers
                link_header = response.headers.get('Link', '')
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
        Get collection titles for a product using correct Shopify API
        
        Returns:
            List of collection titles (e.g., ["Summer Collection", "Best Sellers"])
        """
        titles = []
        
        # Get custom collections
        try:
            data = self._make_request('custom_collections.json', {'product_id': product_id})
            for collection in data.get('custom_collections', []):
                title = collection.get('title', '')
                if title:
                    titles.append(title)
        except Exception as e:
            logger.warning(f"Error fetching custom collections for product {product_id}: {e}")
        
        # Get smart collections
        try:
            data = self._make_request('smart_collections.json', {'product_id': product_id})
            for collection in data.get('smart_collections', []):
                title = collection.get('title', '')
                if title:
                    titles.append(title)
        except Exception as e:
            logger.warning(f"Error fetching smart collections for product {product_id}: {e}")
        
        return titles
    
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
