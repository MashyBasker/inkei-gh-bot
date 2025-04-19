from .config import get_config_value

# Base API URL
def get_api_base():
    """Get the base GitHub API URL"""
    return get_config_value("api_base_url", "https://api.github.com")

# Authentication endpoints
def get_access_token_url(installation_id):
    """Get URL for retrieving an installation access token"""
    return f"{get_api_base()}/app/installations/{installation_id}/access_tokens"

# Repository endpoints
def get_repo_url(owner, repo):
    """Get URL for a repository"""
    return f"{get_api_base()}/repos/{owner}/{repo}"

# Pull request endpoints
def get_pulls_url(owner, repo):
    """Get URL for pull requests in a repository"""
    return f"{get_repo_url(owner, repo)}/pulls"

def get_pull_url(owner, repo, pr_number):
    """Get URL for a specific pull request"""
    return f"{get_pulls_url(owner, repo)}/{pr_number}"

def get_pull_files_url(owner, repo, pr_number):
    """Get URL for files changed in a pull request"""
    return f"{get_pull_url(owner, repo, pr_number)}/files"

def get_pull_comments_url(owner, repo, pr_number):
    """Get URL for comments on a pull request"""
    # Note: PR comments use the issues API
    return f"{get_api_base()}/repos/{owner}/{repo}/issues/{pr_number}/comments"

def get_pull_reviews_url(owner, repo, pr_number):
    """Get URL for reviews on a pull request"""
    return f"{get_pull_url(owner, repo, pr_number)}/reviews"

# Commit endpoints
def get_commits_url(owner, repo):
    """Get URL for commits in a repository"""
    return f"{get_repo_url(owner, repo)}/commits"

def get_commit_url(owner, repo, sha):
    """Get URL for a specific commit"""
    return f"{get_commits_url(owner, repo)}/{sha}"

def get_status_url(owner, repo, sha):
    """Get URL for status of a commit"""
    return f"{get_repo_url(owner, repo)}/statuses/{sha}"

# Content endpoints
def get_contents_url(owner, repo, path=""):
    """Get URL for contents in a repository"""
    base = f"{get_repo_url(owner, repo)}/contents"
    if path:
        return f"{base}/{path}"
    return base