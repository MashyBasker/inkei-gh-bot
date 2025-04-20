import logging
import re
import json
import aiohttp
import os
from .install import GitHubClient
from .endpoints import (
    get_pull_url, 
    get_pull_files_url, 
    get_pull_comments_url, 
    get_pull_reviews_url,
    get_status_url
)
from .utils import extract_repo_info, extract_pr_info, extract_installation_id

logger = logging.getLogger(__name__)

# Define which PR actions to process
ACTIONS_TO_PROCESS_PR = ["opened", "synchronize", "reopened"]
ACTIONS_TO_UPDATE_DESC = ["opened", "edited"]

async def process_pull_request(payload):
    """
    Process a pull request webhook payload.
    This function is called in response to PR actions that require processing.
    
    Args:
        payload: The webhook payload from GitHub
    """
    # Extract required information
    owner, repo = extract_repo_info(payload)
    pr_info = extract_pr_info(payload)
    installation_id = extract_installation_id(payload)
    
    if not all([owner, repo, pr_info, installation_id]):
        logger.error("Missing required information from webhook payload")
        return
    
    logger.info(f"Processing PR #{pr_info['number']} from {owner}/{repo}")
    
    # Create GitHub client
    client = GitHubClient(installation_id=installation_id)
    
    try:
        # Get PR files
        files_url = get_pull_files_url(owner, repo, pr_info['number'])
        files = await client.get(files_url)
        
        # Analyze PR content
        analysis_results = await analyze_pr_content_with_gemini(client, owner, repo, pr_info, files)
        
        # Add a comment with analysis results
        if analysis_results:
            comment_url = get_pull_comments_url(owner, repo, pr_info['number'])
            comment = create_pr_comment(analysis_results)
            await client.post(comment_url, json={"body": comment})
            
            # Set commit status
            status_url = get_status_url(owner, repo, pr_info['head_sha'])
            await client.post(status_url, json={
                "state": "success",
                "description": "PR analysis complete",
                "context": "pr-processor"
            })
            
        logger.info(f"Successfully processed PR #{pr_info['number']}")
        
    except Exception as e:
        logger.error(f"Error processing PR #{pr_info['number']}: {e}")
        # Set error status
        try:
            status_url = get_status_url(owner, repo, pr_info['head_sha'])
            await client.post(status_url, json={
                "state": "error",
                "description": "Error processing PR",
                "context": "pr-processor"
            })
        except Exception:
            logger.error("Failed to set error status")

async def process_pr_desc(payload):
    """
    Process a PR description update.
    This function is called in response to PR actions that modify the description.
    
    Args:
        payload: The webhook payload from GitHub
    """
    # Extract required information
    owner, repo = extract_repo_info(payload)
    pr_info = extract_pr_info(payload)
    installation_id = extract_installation_id(payload)
    
    if not all([owner, repo, pr_info, installation_id]):
        logger.error("Missing required information from webhook payload")
        return
    
    logger.info(f"Processing PR description #{pr_info['number']} from {owner}/{repo}")
    
    # Create GitHub client
    client = GitHubClient(installation_id=installation_id)
    
    try:
        # Check if description needs formatting
        if needs_description_formatting(pr_info['body']):
            # Format the description
            new_body = format_pr_description(pr_info['body'])
            
            # Update the PR description
            pr_url = get_pull_url(owner, repo, pr_info['number'])
            await client.patch(pr_url, json={"body": new_body})
            
            logger.info(f"Updated description for PR #{pr_info['number']}")
        else:
            logger.info(f"No description update needed for PR #{pr_info['number']}")
    
    except Exception as e:
        logger.error(f"Error processing PR description #{pr_info['number']}: {e}")

async def analyze_pr_content(client, owner, repo, pr_info, files):
    """
    Analyze the content of a pull request.
    
    Args:
        client: GitHub client
        owner: Repository owner
        repo: Repository name
        pr_info: Pull request information
        files: Files changed in the PR
        
    Returns:
        dict: Analysis results
    """
    # Simple analysis - count files by type
    file_types = {}
    total_additions = 0
    total_deletions = 0
    total_changes = 0
    
    for file in files:
        # Get file extension
        ext = file['filename'].split('.')[-1] if '.' in file['filename'] else 'no_extension'
        file_types[ext] = file_types.get(ext, 0) + 1
        
        # Count changes
        total_additions += file['additions']
        total_deletions += file['deletions']
        total_changes += file['changes']
    
    # Check for large PRs
    is_large_pr = total_changes > 500
    
    # Check for test files
    has_tests = any('test' in file['filename'].lower() for file in files)
    
    # Return analysis results
    return {
        "file_count": len(files),
        "file_types": file_types,
        "additions": total_additions,
        "deletions": total_deletions,
        "total_changes": total_changes,
        "is_large_pr": is_large_pr,
        "has_tests": has_tests
    }

async def analyze_pr_content_with_gemini(client, owner, repo, pr_info, files):
    """
    Analyze the content of a pull request with Gemini AI.
    
    Args:
        client: GitHub client
        owner: Repository owner
        repo: Repository name
        pr_info: Pull request information
        files: Files changed in the PR
        
    Returns:
        dict: Analysis results including AI review
    """
    # Get basic analysis first
    basic_analysis = await analyze_pr_content(client, owner, repo, pr_info, files)
    
    # Prepare PR data for Gemini
    pr_data = {
        "title": pr_info.title,
        "description": pr_info.body or "",
        "author": pr_info.user.login,
        "branch": pr_info.head.ref,
        "base_branch": pr_info.base.ref,
        "changed_files": [
            {
                "filename": file['filename'],
                "status": file['status'],
                "additions": file['additions'],
                "deletions": file['deletions'],
                "changes": file['changes'],
                "patch": file.get('patch', "No patch available")
            }
            for file in files
        ]
    }
    
    # Create prompt for Gemini
    prompt = """
    You are an expert code reviewer. Review the following PR carefully and provide constructive feedback.
    Your review should be formatted in markdown and include:
    
    1. A summary of the changes
    2. Key observations and feedback
    3. Specific issues found (if any)
    4. Suggestions for improvement
    5. Any security concerns or best practices that should be addressed
    
    Be concise but thorough. Provide actionable feedback that helps improve the code quality.
    
    PR DETAILS:
    """
    
    # Add PR information to the prompt
    prompt += json.dumps(pr_data)
    
    # Call Gemini API
    try:
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            return {**basic_analysis, "ai_review": "Gemini API key not found in environment"}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": gemini_api_key
                },
                json={
                    "contents": [{
                        "parts": [{
                            "text": prompt
                        }]
                    }]
                }
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    ai_review = result["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    ai_review = f"Error from Gemini API: {response.status}"
    except Exception as e:
        ai_review = f"Error generating AI review: {str(e)}"
    
    # Add AI review to analysis results
    return {
        **basic_analysis,
        "ai_review": ai_review
    }

async def post_pr_comment(client, owner, repo, pr_number, analysis):
    """
    Post a PR comment with the analysis results.
    
    Args:
        client: GitHub client
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        analysis: Analysis results including AI review
    """
    # Create comment body with basic stats and AI review
    comment_body = f"""
## PR Analysis Results

Files changed: {analysis['file_count']}
Total changes: {analysis['total_changes']} (+{analysis['additions']}, -{analysis['deletions']})

File types:
{format_file_types(analysis['file_types'])}

{':warning: This is a large PR' if analysis['is_large_pr'] else ''}
{':x: No test files detected' if not analysis['has_tests'] else ':white_check_mark: Test files included'}

## 🤖 AI Code Review

{analysis['ai_review']}

---
*Generated with Gemini AI*
"""
    
    await client.issues.create_comment(
        owner=owner,
        repo=repo,
        issue_number=pr_number,
        body=comment_body
    )

def format_file_types(file_types):
    """Format file types for display in markdown"""
    return "\n".join([f"* {ext}: {count}" for ext, count in file_types.items()])

def create_pr_comment(analysis_results):
    """
    Create a comment for a pull request based on analysis results.
    
    Args:
        analysis_results: The analysis results including AI review
        
    Returns:
        str: The comment text
    """
    comment = "## PR Analysis Results\n\n"
    
    # Add file statistics
    comment += f"**Files changed:** {analysis_results['file_count']}\n"
    comment += f"**Total changes:** {analysis_results['total_changes']} "
    comment += f"(+{analysis_results['additions']}, -{analysis_results['deletions']})\n\n"
    
    # Add file types
    comment += "**File types:**\n"
    for ext, count in analysis_results['file_types'].items():
        comment += f"- {ext}: {count}\n"
    
    # Add warnings/suggestions based on basic analysis
    comment += "\n### Suggestions\n"
    
    if analysis_results['is_large_pr']:
        comment += "⚠️ **This is a large PR.** Consider breaking it down into smaller PRs.\n"
    
    if not analysis_results['has_tests'] and analysis_results['file_count'] > 1:
        comment += "📝 **No test files detected.** Consider adding tests for your changes.\n"
    
    # Add AI review if available
    if 'ai_review' in analysis_results and analysis_results['ai_review']:
        comment += "\n## 🤖 AI Code Review\n\n"
        comment += analysis_results['ai_review']
        comment += "\n\n---\n*Generated with Gemini AI*"
    
    return comment

def needs_description_formatting(description):
    """
    Check if a PR description needs formatting.
    
    Args:
        description: The PR description
        
    Returns:
        bool: True if formatting is needed, False otherwise
    """
    if not description:
        return True
    
    # Check if description already has required sections
    required_sections = ['## Summary', '## Changes', '## Testing']
    return not all(section in description for section in required_sections)

def format_pr_description(description):
    """
    Format a PR description to include required sections.
    
    Args:
        description: The PR description
        
    Returns:
        str: The formatted description
    """
    # If no description, create a template
    if not description:
        return """## Summary
<!-- Provide a brief summary of your changes -->

## Changes
<!-- List the changes you've made -->
- 

## Testing
<!-- Describe how you tested your changes -->
"""
    
    # Check for existing sections
    has_summary = re.search(r'##\s*Summary', description, re.IGNORECASE)
    has_changes = re.search(r'##\s*Changes', description, re.IGNORECASE)
    has_testing = re.search(r'##\s*Testing', description, re.IGNORECASE)
    
    # Add missing sections
    new_description = description
    
    if not has_summary:
        new_description = "## Summary\n<!-- Provide a brief summary of your changes -->\n\n" + new_description
    
    if not has_changes:
        new_description += "\n\n## Changes\n<!-- List the changes you've made -->\n- "
    
    if not has_testing:
        new_description += "\n\n## Testing\n<!-- Describe how you tested your changes -->"
    
    return new_description