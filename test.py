import requests
import logging
from time import sleep

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
access_token = 'EAAYsLDJCjQoBO5gNXukFZCPcu93n4g0TCF7gmmnePAeMmUV4tAx594AHRkzf1I4UDAlZC8r4xGq4yQjrPIYhZAaafq4Ab5dfY1G13b8kJx1f0sZCoHs99FbXchL5aZApTR6vJOTGEgUuWhSEZC4lfsvpZAg9eZBE1S1poTK88SsiB6tinnbHHOlhIdaXySNgzG4cUrNRDFNd'
instagram_account_id = '17841467413345329'
image_path = '/Users/nikitapermyakov/bot-portugal-news/test.jpg'  # Update this path to your image file
caption = 'Your caption here'
comment_text = 'Your comment here'


def upload_media(access_token, instagram_account_id, image_path, caption):
    upload_url = f'https://graph.facebook.com/v20.0/{instagram_account_id}/media'
    files = {
        'image': open(image_path, 'rb'),
    }
    data = {
        'caption': caption,
        'access_token': access_token,
        'media_type': 'IMAGE'
    }
    response = requests.post(upload_url, files=files, data=data)
    if response.status_code == 200:
        media_id = response.json().get('id')
        if media_id:
            logger.info(f'Media ID: {media_id}')
            return media_id
        else:
            logger.error(f'Failed to retrieve media ID: {response.json()}')
            return None
    else:
        logger.error(f'Failed to upload media: {response.json()}')
        return None


def publish_media(access_token, instagram_account_id, media_id):
    publish_url = f'https://graph.facebook.com/v20.0/{instagram_account_id}/media_publish'
    params = {
        'creation_id': media_id,
        'access_token': access_token
    }

    response = requests.post(publish_url, data=params)
    if response.status_code == 200:
        published_media_id = response.json().get('id')
        if published_media_id:
            logger.info('Media published successfully')
            return published_media_id
        else:
            logger.error(f'Failed to retrieve published media ID: {response.json()}')
            return None
    else:
        logger.error(f'Failed to publish media: {response.json()}')
        return None


def add_comment(access_token, media_id, comment_text):
    url = f'https://graph.facebook.com/v20.0/{media_id}/comments'
    params = {
        'message': comment_text,
        'access_token': access_token
    }

    response = requests.post(url, data=params)
    if response.status_code == 200:
        logger.info('Comment added successfully')
    else:
        logger.error(f'Failed to add comment: {response.json()}')


def main():
    media_id = upload_media(access_token, instagram_account_id, image_path, caption)
    if media_id:
        published_media_id = publish_media(access_token, instagram_account_id, media_id)
        if published_media_id:
            add_comment(access_token, published_media_id, comment_text)


if __name__ == "__main__":
    main()
