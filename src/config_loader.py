"""
Configuration Loader for Production
Uses hardcoded values instead of Excel files
"""


class ConfigLoader:
    def __init__(self, config_dir=None):
        # Static values for Italian market
        self.static_values = {
            'condition': 'new',
            'age_group': 'adult',
            'google_product_category': '187',  # Shoes
            'size_system': 'IT',
            'custom_label_2': '',
            'custom_label_3': '',
            'custom_label_4': ''
        }
        
        # Field mapping (not used directly but kept for compatibility)
        self.field_mapping = {}
        
        # Tag categories (not used directly but kept for compatibility)
        self.tag_categories = {}
    
    def get_static_value(self, key: str, default=None):
        """Get a static configuration value"""
        return self.static_values.get(key, default)
