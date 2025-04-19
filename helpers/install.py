import jwt
import time
import httpx
import logging
from .config import get_config_value
from .endpoints import get_access_token_url

logger = logging.getLogger(__name__)

async def generate_jwt():
    """
    Generate a JWT (JSON Web Token) for GitHub App authentication.
    
    Returns:
        str: The generated JWT token
    """
    # Get configuration values
    app_id = get_config_value("app_id")
    private_key = get_config_value("private_key")
    
    if not app_id or not private_key:
        raise ValueError("GitHub App ID and private key are required")
    
    # Replace newline literals with actual newlines if needed
    if "\\n" in private_key and not private_key.startswith("-----"):
        private_key = private_key.replace("\\n", "\n")
    
    # Create JWT payload
    now = int(time.time())
    payload = {
        'iat': now - 60,  # Issued at time (60 seconds in the past to allow for clock drift)
        'exp': now + (10 * 60),  # Expiration time (10 minutes in the future)
        'iss': app_id  # Issuer (GitHub App ID)
    }
    
    # Sign and return the JWT
    try:
        token = jwt.encode(payload, private_key, algorithm='RS256')
        return token
    except Exception as e:
        logger.error(f"Failed to generate JWT: {e}")
        raise

async def get_installation_token(installation_id):
    """
    Get an installation access token for a GitHub App installation.
    
    Args:
        installation_id: The ID of the installation
        
    Returns:
        dict: The installation token response including 'token' and 'expires_at'
    """
    # Generate JWT for authentication
    jwt_token = await generate_jwt()
    
    # Prepare headers for the request
    headers = {
        'Authorization': f'Bearer {jwt_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    # Make the request to GitHub API
    url = get_access_token_url(installation_id)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers)
            
            if response.status_code != 201:
                logger.error(f"Failed to get installation token: {response.status_code} - {response.text}")
                response.raise_for_status()
                
            token_data = response.json()
            logger.info(f"Successfully obtained installation token, expires at {token_data.get('expires_at')}")
            return token_data
            
        except Exception as e:
            logger.error(f"Error getting installation token: {e}")
            raise

class GitHubClient:
    """
    Client for making authenticated requests to GitHub API.
    """
    
    def __init__(self, token=None, installation_id=None):
        """
        Initialize GitHub client.
        
        Args:
            token: Installation token (if already available)
            installation_id: Installation ID (to get a token if not provided)
        """
        self.token = token
        self.installation_id = installation_id
        self._token_expires_at = None
    
    async def ensure_token(self):
        """
        Ensure we have a valid installation token.
        
        Returns:
            str: The installation token
        """
        # If we don't have a token but have an installation ID, get a token
        if not self.token and self.installation_id:
            token_data = await get_installation_token(self.installation_id)
            self.token = token_data['token']
            self._token_expires_at = token_data['expires_at']
        elif not self.token:
            raise ValueError("No token or installation_id provided")
            
        return self.token
    
    async def request(self, method, url, **kwargs):
        """
        Make an authenticated request to GitHub API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: API endpoint URL
            **kwargs: Additional arguments to pass to httpx
            
        Returns:
            dict or list: JSON response from GitHub API
        """
        # Ensure we have a token
        token = await self.ensure_token()
        
        # Prepare headers
        headers = kwargs.pop('headers', {})
        headers.update({
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github.v3+json'
        })
        
        # Make the request
        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, headers=headers, **kwargs)
            
            if response.status_code >= 400:
                logger.error(f"GitHub API error: {response.status_code} - {response.text}")
                response.raise_for_status()
                
            return response.json() if response.content else None
    
    async def get(self, url, **kwargs):
        """Make a GET request to GitHub API"""
        return await self.request('GET', url, **kwargs)
    
    async def post(self, url, json=None, **kwargs):
        """Make a POST request to GitHub API"""
        return await self.request('POST', url, json=json, **kwargs)
    
    async def patch(self, url, json=None, **kwargs):
        """Make a PATCH request to GitHub API"""
        return await self.request('PATCH', url, json=json, **kwargs)
    
    async def put(self, url, json=None, **kwargs):
        """Make a PUT request to GitHub API"""
        return await self.request('PUT', url, json=json, **kwargs)
    
    async def delete(self, url, **kwargs):
        """Make a DELETE request to GitHub API"""
        return await self.request('DELETE', url, **kwargs)