from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from helpers.pr import process_pull_request, ACTIONS_TO_PROCESS_PR, ACTIONS_TO_UPDATE_DESC, process_pr_desc
from helpers.utils import is_github_signature_valid
from helpers.config import load_config
import logging
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(title="GitHub PR Processor")

@app.post("/github-webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handle GitHub webhook events.
    This endpoint processes incoming webhook events from GitHub.
    """
    payload = await request.json()
    body = await request.body()
    event = request.headers.get("X-GitHub-Event")
    
    # Load configuration
    config = load_config()
    
    # Check signature if enabled
    if config["check_signature"] and not is_github_signature_valid(
        request.headers, body, config["webhook_secret"]
    ):
        logger.error("Invalid webhook signature")
        return HTTPException(status_code=401, detail="Invalid signature")
    
    # Process pull request events
    if event == "pull_request":
        action = payload.get("action", "")
        logger.info(f"Received pull_request event with action: {action}")
        
        # Process PR for review
        if config["auto_pr_review"] and action in ACTIONS_TO_PROCESS_PR:
            logger.info(f"Adding task to process PR #{payload['pull_request']['number']}")
            background_tasks.add_task(process_pull_request, payload)
        
        # Process PR description updates
        if config["edit_pr_desc"] and action in ACTIONS_TO_UPDATE_DESC:
            logger.info(f"Adding task to process PR description #{payload['pull_request']['number']}")
            background_tasks.add_task(process_pr_desc, payload)
    
    # Log other events
    else:
        logger.info(f"Received event: {event} (not processing)")
    
    return JSONResponse(content={"message": "Webhook received"})

@app.get("/")
def health_check():
    """
    Health check endpoint.
    Returns a simple message to confirm the API is running.
    """
    return JSONResponse(content={"status": "healthy", "message": "GitHub App API is running"})

# Run the application if executed directly
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)