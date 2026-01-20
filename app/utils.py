import cloudinary
import cloudinary.uploader
import os

def configure_cloudinary():
    cloudinary.config(
        cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
        api_key = os.environ.get('CLOUDINARY_API_KEY'),
        api_secret = os.environ.get('CLOUDINARY_API_SECRET')
    )

def upload_file(file, folder="uploads"):
    """
    Uploads a file to Cloudinary and returns the secure URL.
    Fallback to local storage if Cloudinary keys are missing (for dev).
    """
    if not os.environ.get('CLOUDINARY_CLOUD_NAME'):
        # Fallback for local development without keys
        return None
        
    try:
        configure_cloudinary()
        upload_result = cloudinary.uploader.upload(file, folder=folder, resource_type="auto")
        return upload_result['secure_url']
    except Exception as e:
        print(f"Cloudinary Upload Error: {e}")
        return None
