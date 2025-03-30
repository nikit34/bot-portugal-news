import os
import logging

logger = logging.getLogger(__name__)


def get_ci_run_url():
    server_url = os.environ.get('GITHUB_SERVER_URL', '')
    repository = os.environ.get('GITHUB_REPOSITORY', '')
    run_id = os.environ.get('GITHUB_RUN_ID', '')
    
    if all([server_url, repository, run_id]):
        return f"{server_url}/{repository}/actions/runs/{run_id}"
    return '' 