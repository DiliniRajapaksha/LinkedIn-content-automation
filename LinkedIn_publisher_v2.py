"""
Notion to LinkedIn Auto-Poster

This script automates LinkedIn posting by reading scheduled posts from a Notion database
and publishing them to LinkedIn. It supports both text and image posts, with proper
timezone handling and status tracking.

Features:
- Reads scheduled posts from a Notion database
- Posts to LinkedIn automatically at scheduled times
- Supports text and image posts
- Updates post status in Notion after publishing
- Runs as a GitHub Action for automated deployment
- Timezone-aware scheduling (defaults to Australia/Brisbane)

GitHub: https://github.com/DiliniRajapaksha/LinkedInContent
"""

import asyncio
import aiohttp
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import schedule
import time
import logging
import os
from pathlib import Path
import pytz
try:
    from dotenv import load_dotenv
except ImportError:
    pass  # dotenv not required when running in GitHub Actions

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class PostContent:
    """Data class for post content from Notion"""
    id: str
    post_content: str
    property_image: List[str]
    schedule_date: str



@dataclass
class WorkflowConfig:
    """Configuration for the workflow"""
    notion_api_token: str
    notion_database_id: str
    linkedin_access_token: str
    linkedin_person_id: str
    timezone: str = "Australia/Brisbane"

class NotionClient:
    """Client for interacting with Notion API"""
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
    
    async def get_scheduled_posts(self, database_id: str) -> List[PostContent]:
        """
        Fetch posts from Notion database with Status=Scheduled and Post Types contains LinkedIn
        """
        # Convert current time to Brisbane time
        brisbane_tz = pytz.timezone('Australia/Brisbane')
        today = datetime.now(brisbane_tz).strftime('%Y-%m-%d')

        logger.info(f"Fetching scheduled posts for Brisbane date: {today}")
        
        query_body = {
            "filter": {
                "and": [
                    {
                        "property": "Status",
                        "status": {
                            "equals": "Scheduled"
                        }
                    },
                    {
                        "property": "Schedule Date",
                        "date": {
                            "equals": today
                        }
                    }
                ]
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/databases/{database_id}/query",
                headers=self.headers,
                json=query_body
            ) as response:
                if response.status != 200:
                    logger.error(f"Notion API error: {response.status}")
                    return []
                
                data = await response.json()
                posts = []
                
                for page in data.get("results", []):
                    try:
                        post = self._parse_notion_page(page)
                        if post:
                            posts.append(post)
                    except Exception as e:
                        logger.error(f"Error parsing Notion page: {e}")
                        continue
                
                return posts
    
    def _parse_notion_page(self, page: Dict[str, Any]) -> Optional[PostContent]:
        """Parse a Notion page into PostContent"""
        try:
            properties = page["properties"]
            
            # Extract LinkedIn post content
            linkedin_post = properties.get("LinkedIn Post", {})
            if linkedin_post.get("type") == "rich_text":
                post_content = "".join([text["plain_text"] for text in linkedin_post["rich_text"]])
            else:
                post_content = ""
            
            # Extract images
            image_property = properties.get("Image", {})
            images = []
            if image_property.get("type") == "files":
                for file_obj in image_property["files"]:
                    if file_obj.get("type") == "file":
                        images.append(file_obj["file"]["url"])
                    elif file_obj.get("type") == "external":
                        images.append(file_obj["external"]["url"])
            
            # Extract schedule date
            schedule_date_prop = properties.get("Schedule Date", {})
            schedule_date = ""
            if schedule_date_prop.get("type") == "date" and schedule_date_prop["date"]:
                schedule_date = schedule_date_prop["date"]["start"]
            
            return PostContent(
                id=page["id"],
                post_content=post_content,
                property_image=images,
                schedule_date=schedule_date
            )
        except Exception as e:
            logger.error(f"Error parsing Notion page: {e}")
            return None
    
    async def update_post_status(self, page_id: str, status: str, publication_date: Optional[str] = None):
        """Update post status in Notion"""
        update_data = {
            "properties": {
                "Status": {
                    "status": {
                        "name": status
                    }
                }
            }
        }
        
        if publication_date:
            update_data["properties"]["Publication Date"] = {
                "date": {
                    "start": publication_date
                }
            }
        
        async with aiohttp.ClientSession() as session:
            async with session.patch(
                f"{self.base_url}/pages/{page_id}",
                headers=self.headers,
                json=update_data
            ) as response:
                if response.status != 200:
                    logger.error(f"Failed to update Notion page: {response.status}")
                    return False
                return True



class LinkedInClient:
    """Client for LinkedIn API posting"""
    
    def __init__(self, access_token: str, person_id: str):
        self.access_token = access_token
        self.person_id = person_id
        self.base_url = "https://api.linkedin.com/v2"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }
    
    async def post_text(self, content: str) -> bool:
        """Post text-only content to LinkedIn"""
        post_data = {
            "author": f"urn:li:person:{self.person_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": content
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/ugcPosts",
                headers=self.headers,
                json=post_data
            ) as response:
                if response.status not in [200, 201]:
                    logger.error(f"LinkedIn text post failed: {response.status}")
                    return False
                logger.info("LinkedIn text post successful")
                return True
    
    async def post_with_image(self, content: str, image_data: bytes) -> bool:
        """Post content with image to LinkedIn"""
        try:
            # First, upload the image
            upload_url = await self._upload_image(image_data)
            if not upload_url:
                return False
            
            # Then create the post with the uploaded image
            post_data = {
                "author": f"urn:li:person:{self.person_id}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": content
                        },
                        "shareMediaCategory": "IMAGE",
                        "media": [
                            {
                                "status": "READY",
                                "description": {
                                    "text": "Image"
                                },
                                "media": upload_url,
                                "title": {
                                    "text": "Image"
                                }
                            }
                        ]
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/ugcPosts",
                    headers=self.headers,
                    json=post_data
                ) as response:
                    if response.status not in [200, 201]:
                        logger.error(f"LinkedIn image post failed: {response.status}")
                        return False
                    logger.info("LinkedIn image post successful")
                    return True
                    
        except Exception as e:
            logger.error(f"Error posting with image: {e}")
            return False
    
    async def _upload_image(self, image_data: bytes) -> Optional[str]:
        """Upload image to LinkedIn and return media URN"""
        # Register upload
        register_data = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": f"urn:li:person:{self.person_id}",
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent"
                    }
                ]
            }
        }
        
        async with aiohttp.ClientSession() as session:
            # Register upload
            async with session.post(
                f"{self.base_url}/assets?action=registerUpload",
                headers=self.headers,
                json=register_data
            ) as response:
                if response.status not in [200, 201]:
                    logger.error(f"LinkedIn upload registration failed: {response.status}")
                    return None
                
                upload_response = await response.json()
                upload_url = upload_response["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
                asset_id = upload_response["value"]["asset"]
            
            # Upload the actual image
            upload_headers = {"Authorization": f"Bearer {self.access_token}"}
            async with session.put(upload_url, headers=upload_headers, data=image_data) as response:
                if response.status not in [200, 201]:
                    logger.error(f"LinkedIn image upload failed: {response.status}")
                    return None
                
                return asset_id

class LinkedInPosterWorkflow:
    """Main workflow orchestrator"""
    
    def __init__(self, config: WorkflowConfig):
        self.config = config
        self.notion_client = NotionClient(config.notion_api_token)
        self.linkedin_client = LinkedInClient(config.linkedin_access_token, config.linkedin_person_id)
    
    async def download_image(self, url: str) -> Optional[bytes]:
        """Download image from URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        logger.error(f"Failed to download image: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return None
    
    async def process_scheduled_posts(self):
        """Main workflow logic - process all scheduled posts for today"""
        logger.info("Starting scheduled post processing...")
        
        try:
            # Get scheduled posts from Notion
            posts = await self.notion_client.get_scheduled_posts(self.config.notion_database_id)
            logger.info(f"Found {len(posts)} scheduled posts")
            
            for post in posts:
                await self._process_single_post(post)
                
        except Exception as e:
            logger.error(f"Error in workflow: {e}")
    
    async def _process_single_post(self, post: PostContent):
        """Process a single post"""
        logger.info(f"Processing post: {post.id}")
        
        try:
            # Check if post has images
            if post.property_image and len(post.property_image) > 0:
                await self._handle_image_post(post)
            else:
                await self._handle_text_post(post)
                
        except Exception as e:
            logger.error(f"Error processing post {post.id}: {e}")
    
    async def _handle_image_post(self, post: PostContent):
        """Handle post with image"""
        logger.info(f"Handling image post: {post.id}")
        
        # Download image
        image_url = post.property_image[0]  # Use first image
        image_data = await self.download_image(image_url)
        
        if not image_data:
            logger.error("Failed to download image, skipping post")
            return
        
        success = await self.linkedin_client.post_with_image(post.post_content, image_data)
        if success:
            # Update Notion with publication date in Brisbane time
            brisbane_tz = pytz.timezone('Australia/Brisbane')
            publication_date = datetime.now(brisbane_tz).isoformat()
            await self.notion_client.update_post_status(
                post.id, "Posted", publication_date
            )
            logger.info(f"Successfully posted image post: {post.id}")
        else:
            logger.error(f"Failed to post to LinkedIn: {post.id}")
    
    async def _handle_text_post(self, post: PostContent):
        """Handle text-only post"""
        logger.info(f"Handling text post: {post.id}")
        
        success = await self.linkedin_client.post_text(post.post_content)
        if success:
            # Update Notion with publication date and status in Brisbane time
            brisbane_tz = pytz.timezone('Australia/Brisbane')
            publication_date = datetime.now(brisbane_tz).isoformat()
            await self.notion_client.update_post_status(
                post.id, "Posted", publication_date
            )
            logger.info(f"Successfully posted text post: {post.id}")
        else:
            logger.error(f"Failed to post to LinkedIn: {post.id}")

def run_workflow():
    """Synchronous wrapper for async workflow"""
    # Try to load from .env file if it exists (for local development)
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        try:
            load_dotenv(env_path)
            logger.info("Loaded configuration from .env file")
        except Exception:
            logger.info("Running without .env file (normal in GitHub Actions)")
    
    # Configuration from environment variables
    config = WorkflowConfig(
        notion_api_token=os.getenv("NOTION_API_TOKEN"),
        notion_database_id=os.getenv("NOTION_DATABASE_ID"),
        linkedin_access_token=os.getenv("LINKEDIN_ACCESS_TOKEN"),
        linkedin_person_id=os.getenv("LINKEDIN_PERSON_ID"),
        timezone=os.getenv("TIMEZONE", "Australia/Brisbane")
    )
    
    workflow = LinkedInPosterWorkflow(config)
    asyncio.run(workflow.process_scheduled_posts())

# def main():
#     """Main function to set up scheduling"""
#     logger.info("LinkedIn Poster Workflow started")
    
#     # Schedule to run daily at 6 AM (matching the n8n schedule)
#     schedule.every().day.at("06:00").do(run_workflow)
    
#     logger.info("Workflow scheduled to run daily at 6:00 AM")
    
#     # Keep the script running
#     while True:
#         schedule.run_pending()
#         time.sleep(60)  # Check every minute

if __name__ == "__main__":
    run_workflow()

"""
Requirements.txt:
aiohttp>=3.8.0
schedule>=1.2.0

Setup Instructions:
1. Create a Notion integration and get your API token:
   - Go to https://www.notion.so/my-integrations
   - Create a new integration
   - Copy the API token
   - Share your Notion database with the integration

2. Set up LinkedIn API access:
   - Create a LinkedIn Developer App at https://www.linkedin.com/developers/apps
   - Request the necessary permissions for posting
   - Get your access token and person ID

3. Configure environment variables:
   - Copy .env.example to .env for local development
   - Set up GitHub Secrets for deployment

4. Install dependencies:
   pip install -r requirements.txt

5. Run the script:
   - For one-time run: python LinkedIn_publisher_v2.py
   - For scheduled execution: python LinkedIn_publisher_v2.py --schedule

Key Features:
- Automated LinkedIn posting from Notion database
- Support for both text and image posts
- Timezone-aware scheduling (defaults to Australia/Brisbane)
- Proper status tracking in Notion
- GitHub Actions integration for automated deployment
- Environment-based configuration for security
- Detailed logging for monitoring and debugging

Note: This script is designed to run as a GitHub Action, scheduled
to execute daily at 6 AM Brisbane time (20:00 UTC previous day).
For local development, environment variables can be set in a .env file.
"""