import logging
import os
import uuid
from typing import Dict, Any
from io import BytesIO
from datetime import datetime, timedelta, timezone

import vertexai
from vertexai.preview.vision_models import ImageGenerationModel, Image
from google.cloud import storage
from .config import IMAGEN_MODEL

# --- Initialize Vertex AI and GCS Client ---
try:
    PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
    LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")

    if not all([PROJECT_ID, LOCATION, GCS_BUCKET_NAME]):
        raise ValueError(
            "Missing required environment variables: "
            "GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, or GCS_BUCKET_NAME"
        )

    vertexai.init(project=PROJECT_ID, location=LOCATION)
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)

except (ImportError, ValueError) as e:
    logging.error(f"Failed to initialize Vertex AI or GCS: {e}")
    # Set to None to prevent tool execution if initialization fails
    ImageGenerationModel = None
    bucket = None


def generate_image(prompt: str, num_samples: int = 1) -> Dict[str, Any]:
    """
    Generates new images based on a descriptive prompt using the Vertex AI Imagen model,
    uploads them to GCS, and returns their public URLs.

    Args:
        prompt: The detailed text prompt describing the desired image.
        num_samples: The number of images to generate (1-8).

    Returns:
        A dictionary containing a list of public URLs to the generated images.
    """
    if not ImageGenerationModel or not bucket:
        error_message = "Image generation service is not configured. Please check environment variables."
        logging.error(error_message)
        return {"error": error_message}

    logging.info(f"Generating {num_samples} image(s) for prompt: '{prompt}'")
    try:
        model = ImageGenerationModel.from_pretrained(IMAGEN_MODEL)

        # Generate images
        images = model.generate_images(
            prompt=prompt,
            number_of_images=num_samples,
            # Add other parameters like seed, aspect_ratio as needed
        )

        image_urls = []
        for i, image in enumerate(images):
            # Create a unique filename
            file_name = f"generated/{uuid.uuid4()}.png"
            blob = bucket.blob(file_name)

            # Upload the image bytes to GCS
            # The image object has a private _image_bytes attribute
            blob.upload_from_string(image._image_bytes, content_type="image/png")

            # Instead of making the blob public, generate a temporary signed URL
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=15),  # URL is valid for 15 minutes
                method="GET",
            )
            image_urls.append(signed_url)
            logging.info(f"Successfully uploaded image {i+1} and generated signed URL.")

        return {"image_urls": image_urls}

    except Exception as e:
        logging.error(f"An error occurred during image generation or upload: {e}")
        return {"error": str(e)}

# The list of tools to be exposed by the agent.
# The ADK will automatically wrap this function into a FunctionTool.
tools = [generate_image] 