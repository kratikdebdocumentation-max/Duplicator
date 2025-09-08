"""
API Client module for Shoonya API operations.
Handles login, order placement, and market data retrieval.
"""

import requests
from retrying import retry
from api_helper import ShoonyaApiPy
from config import Config
import pyotp


class APIClient:
    """Shoonya API client wrapper."""
    
    def __init__(self, config: Config):
        """Initialize API client with configuration."""
        self.config = config
        self.api = ShoonyaApiPy()
        self.is_logged_in = False
        self.client_name = None
    
    @retry(stop_max_attempt_number=2, wait_fixed=10000)
    def login(self):
        """Login to Shoonya master account."""
        try:
            # Generate fresh 2FA code like the working project
            twoFA_code = pyotp.TOTP(self.config.twoFA).now()
            
            login_status = self.api.login(
                userid=self.config.USER_ID,
                password=self.config.PASSWORD,
                twoFA=twoFA_code,
                vendor_code=self.config.VENDOR_CODE,
                api_secret=self.config.API_SECRET,
                imei=self.config.IMEI,
            )
            
            if not login_status:
                print("❌ Login failed: No response from API")
                return False, None
                
            self.client_name = login_status.get("uname")
            self.is_logged_in = True
            print(f"✅ Login Successful! Welcome {self.client_name} - Master ACCOUNT")
            return True, self.client_name
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error during login: {e}")
            raise
        except Exception as e:
            print(f"❌ Unexpected error during login: {e}")
            raise
    
    def get_quote(self, exchange, token):
        """Get current quote for a symbol."""
        try:
            quote = self.api.get_quotes(exchange=exchange, token=token)
            return quote
        except Exception as e:
            print(f"❌ Error getting quote: {e}")
            return None
    
    def search_symbol(self, exchange, search_text):
        """Search for symbols matching the search text."""
        try:
            data = self.api.searchscrip(exchange=exchange, searchtext=search_text)
            return data
        except Exception as e:
            print(f"❌ Error searching symbol: {e}")
            return None
    
    def place_order(self, buy_or_sell, product_type, exchange, tradingsymbol, 
                   quantity, discloseqty, price_type, price, trigger_price, retention, remarks):
        """Place an order."""
        try:
            order_resp = self.api.place_order(
                buy_or_sell=buy_or_sell,
                product_type=product_type,
                exchange=exchange,
                tradingsymbol=tradingsymbol,
                quantity=quantity,
                discloseqty=discloseqty,
                price_type=price_type,
                price=price,
                retention=retention,
                remarks=remarks
            )
            return order_resp
        except Exception as e:
            print(f"❌ Error placing order: {e}")
            return None
    
    def subscribe_symbol(self, exchange, token):
        """Subscribe to symbol for real-time updates."""
        try:
            self.api.subscribe(f"{exchange}|{token}")
            return True
        except Exception as e:
            print(f"❌ Error subscribing to symbol: {e}")
            return False
    
    def unsubscribe_symbol(self, exchange, token):
        """Unsubscribe from symbol."""
        try:
            unsub_token = f"{exchange}|{token}"
            self.api.unsubscribe([unsub_token])
            return True
        except Exception as e:
            print(f"❌ Error unsubscribing from symbol: {e}")
            return False
    
    def cancel_order(self, order_id):
        """Cancel an order."""
        try:
            cancel_resp = self.api.cancel_order(order_id)
            return cancel_resp
        except Exception as e:
            print(f"❌ Error canceling order: {e}")
            return None
    
    def modify_order(self, order_id, new_price, new_quantity):
        """Modify an order."""
        try:
            modify_resp = self.api.modify_order(
                order_id=order_id,
                new_price=new_price,
                new_quantity=new_quantity
            )
            return modify_resp
        except Exception as e:
            print(f"❌ Error modifying order: {e}")
            return None