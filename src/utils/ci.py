import os
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_ci_run_url():
    server_url = os.environ.get('GITHUB_SERVER_URL', '')
    repository = os.environ.get('GITHUB_REPOSITORY', '')
    run_id = os.environ.get('GITHUB_RUN_ID', '')
    
    if all([server_url, repository, run_id]):
        url = f"{server_url}/{repository}/actions/runs/{run_id}"
        logger.info(f"CI run URL successfully generated: {url}")
        return url
    
    logger.warning("Failed to generate CI run URL - missing environment variables")
    return '' 