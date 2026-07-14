from dotenv import load_dotenv
load_dotenv()

from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'fallback-secret-key')
JWT_ALGORITHM = "HS256"
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'FounderOps2024!')

# WordPress Write-Safety Configuration
# Configurable so the approval token lifetime can be tuned without redesigning
# the safety contract. Must remain short-lived per the approved architecture.
WP_APPROVAL_TOKEN_TTL_MINUTES = int(os.environ.get('WP_APPROVAL_TOKEN_TTL_MINUTES', '60'))

# Model Configuration
PAGE_GENERATION_MODEL = os.environ.get('PAGE_GENERATION_MODEL', 'gpt-5.2')
QUALITY_SCORING_MODEL = os.environ.get('QUALITY_SCORING_MODEL', 'claude-sonnet-4-5-20250929')
REWRITE_MODEL = os.environ.get('REWRITE_MODEL', 'gemini-3-flash-preview')
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
