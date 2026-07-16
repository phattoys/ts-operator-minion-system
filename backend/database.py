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

# Execution Manifest Intake Configuration (Phase 3)
# Dedicated server-to-server intake secret -- deliberately separate from
# ADMIN_PASSWORD (the founder login credential). Never log or return this
# value. Empty by default so /receive fails closed (no valid signature can
# ever be produced) until explicitly configured for a real TSAF delivery.
EXECUTION_MANIFEST_INTAKE_SECRET = os.environ.get('EXECUTION_MANIFEST_INTAKE_SECRET', '')
# Replay window: how old a request timestamp may be before it's rejected.
EXECUTION_MANIFEST_INTAKE_REPLAY_WINDOW_SECONDS = int(os.environ.get('EXECUTION_MANIFEST_INTAKE_REPLAY_WINDOW_SECONDS', '300'))
# Hard cap on inbound packet size, enforced server-side (never rely only on
# the browser/client for size control).
EXECUTION_MANIFEST_MAX_BYTES = int(os.environ.get('EXECUTION_MANIFEST_MAX_BYTES', str(5 * 1024 * 1024)))  # 5 MB default

# Model Configuration
PAGE_GENERATION_MODEL = os.environ.get('PAGE_GENERATION_MODEL', 'gpt-5.2')
QUALITY_SCORING_MODEL = os.environ.get('QUALITY_SCORING_MODEL', 'claude-sonnet-4-5-20250929')
REWRITE_MODEL = os.environ.get('REWRITE_MODEL', 'gemini-3-flash-preview')
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
