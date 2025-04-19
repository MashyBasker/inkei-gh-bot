import hmac
import hashlib
import logging
from .config import get_config_value

logger = logging.getLogger(__name__)

def is_github_signature_valid(headers, payload, webhook_secret=None):
    """
    Verify that the webhook request is signed with the correct secret.
    
    Args:
        headers: Request headers containing the signature
        payload: Raw request body
        webhook_secret: Webhook secret to validate against (optional)
    
    Returns:
        bool: True if signature is valid, False otherwise
    """
    if webhook_secret is None:
        webhook_secret = get_config_value("webhook_secret")
    
    if not webhook_secret:
        logger.warning("No webhook secret configured, skipping signature verification")
        return True
    
    # Get signature from headers
    signature_header = headers.get("X-Hub-Signature-256")
    if not signature_header:
        logger.warning("No X-Hub-Signature-256 header found in the request")
        return False
    
    # Compute expected signature
    hmac_gen = hmac.new(
        webhook_secret.encode('utf-8'),
        payload,
        hashlib.sha256
    )
    expected_signature = f"sha256={hmac_gen.hexdigest()}"
    
    # Compare signatures
    return hmac.compare_digest(signature_header, expected_signature)

def extract_repo_info(payload):
    """
    Extract repository owner and name from webhook payload.
    
    Args:
        payload: The webhook payload
        
    Returns:
        tuple: (owner, repo_name) or (None, None) if not found
    """
    if not payload or 'repository' not in payload:
        return None, None
    
    repo = payload['repository']
    owner = repo['owner']['login']
    name = repo['name']
    
    return owner, name

def extract_pr_info(payload):
    """
    Extract pull request information from webhook payload.
    
    Args:
        payload: The webhook payload
        
    Returns:
        dict: Dictionary containing PR info or None if not found
    """
    if not payload or 'pull_request' not in payload:
        return None
    
    pr = payload['pull_request']
    return {
        'number': pr['number'],
        'title': pr['title'],
        'body': pr['body'] or '',
        'user': pr['user']['login'],
        'head_sha': pr['head']['sha'],
        'base_branch': pr['base']['ref'],
        'head_branch': pr['head']['ref'],
        'html_url': pr['html_url']
    }

def extract_installation_id(payload):
    """
    Extract GitHub App installation ID from webhook payload.
    
    Args:
        payload: The webhook payload
        
    Returns:
        int: Installation ID or None if not found
    """
    if not payload or 'installation' not in payload:
        return None
    
    return payload['installation']['id']