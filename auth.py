"""
Authentication Module

Handles token acquisition, caching, and refresh logic for CSM API.
"""

import requests
from datetime import datetime, timedelta
from typing import Optional
from config import (
    CSM_AUTH_URL,
    CSM_USERNAME,
    CSM_PASSWORD,
    TOKEN_CACHE_DURATION_MINUTES
)

# Global token cache
_cached_token: Optional[str] = None
_token_expiry: Optional[datetime] = None


def get_bearer_token() -> str:
    """
    Get a valid bearer token from CSM API.
    
    Caches the token and returns the cached token if it's still valid.
    Automatically refreshes when expiry time is approaching.
    
    Returns:
        str: The bearer token (without 'Bearer' prefix)
        
    Raises:
        Exception: If token acquisition fails
    """
    global _cached_token, _token_expiry
    
    # Return cached token if valid
    if _cached_token and _token_expiry and datetime.now() < _token_expiry:
        print("✅ Using cached token...")
        return _cached_token
    
    print("🔄 Acquiring new token...")
    try:
        payload = {
            "userName": CSM_USERNAME,
            "password": CSM_PASSWORD
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        response = requests.post(CSM_AUTH_URL, json=payload, headers=headers)
        
        if response.status_code == 200:
            # Extract token from response headers (case-insensitive)
            auth_header = (
                response.headers.get("authorization") or 
                response.headers.get("Authorization") or 
                ""
            )
            
            if auth_header:
                # Clean up Bearer prefix if present
                _cached_token = auth_header.replace("Bearer ", "").replace("bearer ", "").strip()
            else:
                # Try to get token from response body
                try:
                    res_data = response.json()
                    _cached_token = res_data.get("token") or res_data.get("access_token")
                except Exception:
                    pass
            
            # Set token expiry (refresh 5 minutes before actual expiry)
            _token_expiry = datetime.now() + timedelta(minutes=TOKEN_CACHE_DURATION_MINUTES)
            
            print(f"✅ [TOKEN ACQUIRED] Expiry: {_token_expiry.strftime('%Y-%m-%d %H:%M:%S')}")
            return _cached_token
        else:
            raise Exception(f"Token acquisition failed with status code: {response.status_code}")
    
    except Exception as e:
        print(f"❌ Token acquisition error: {e}")
        raise


def invalidate_token_cache() -> None:
    """Invalidate the cached token to force a refresh on next request."""
    global _cached_token, _token_expiry
    _cached_token = None
    _token_expiry = None
    print("🔄 Token cache invalidated")
