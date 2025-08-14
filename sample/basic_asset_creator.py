import os
import json
import io
import logging
from typing import Dict, Any, Optional
import uuid
from datetime import timedelta

import vertexai
from vertexai.preview.vision_models import ImageGenerationModel
from vertexai.generative_models import GenerativeModel, GenerationConfig
import vertexai.preview.generative_models as generative_models
from google.cloud import storage
from google.adk.agents import Agent
# ToolContext import removed for ADK compatibility
from PIL import Image

from ..config import IMAGEN_MODEL, GEMINI_MODEL

# Initialize Vertex AI
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")

if PROJECT_ID and LOCATION:
    vertexai.init(project=PROJECT_ID, location=LOCATION)

# Response schema for prompt enhancement
response_schema = {
    "type": "object",
    "properties": {
        "final_prompt": {"type": "string"},
        "negative_prompt": {"type": "string"},
    },
    "required": ["final_prompt", "negative_prompt"],
}

generation_config = GenerationConfig(
    response_mime_type="application/json",
    response_schema=response_schema,
    max_output_tokens=8192,
    temperature=1,
    top_p=0.95,
)

safety_settings = {
    generative_models.HarmCategory.HARM_CATEGORY_HATE_SPEECH: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    generative_models.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    generative_models.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    generative_models.HarmCategory.HARM_CATEGORY_HARASSMENT: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}

enhancement_prompt = """SYSTEM: `You are an AI prompt engineer specializing in refining and enhancing user-provided prompts and negative prompts for image generation using models like Imagen. Your primary goal is to transform a basic prompt into a detailed, descriptive one that captures the user's intent accurately and evokes the desired visual output.`
INSTRUCTION: ```Given a user's image generation prompt, analyze its content and structure, then apply the following steps to enhance it:
    - **Clarify and Expand:** Identify the main subject(s), action(s), and setting(s) in the prompt. If these elements are vague or ambiguous, try to guess and enhance it. Expand on these core elements by adding descriptive details that contribute to the overall visual richness and coherence of the image.
    - **Enhance Visual Elements:** Suggest specific adjectives and adverbs to enhance the visual qualities of the scene, such as lighting, colors, textures, and atmosphere. Propose additional details for objects, characters, or the environment to create a more immersive and interesting composition.
    - **Consider Style and Composition: If the user hasn't specified an art style or composition, inquire about their preferences or suggest suitable options based on the prompt's content. Provide guidance on camera angles, perspectives, and framing to achieve the desired visual impact.**
    - **Address Potential Issues:**  Identify any potential ambiguities or inconsistencies within the prompt that could lead to undesired results. Suggest ways to rephrase or restructure the prompt to ensure clarity and avoid misinterpretations.
    - **Background:**  Provide a brief description of the background setting, including any prominent objects or features.
    - **Maintain User Intent:** Ensure that the enhanced prompt remains faithful to the user's original idea and creative vision. Avoid adding elements or making changes that deviate significantly from the core concept of the user's input.
Based on all the above instruction details, create a detailed final prompt & corresponding negative prompt. Response should be as per given output JSON template without any additional comments.```
OUTPUT:```
JSON
{
    "final_prompt" : "",
    "negative_prompt": "",
}```
"""

def generate_basic_asset(
    prompt: str,
    primary_style: str = "Photography",
    art_style: Optional[str] = None,
    digital_creation_style: Optional[str] = None, 
    photography_style: Optional[str] = None,
    lighting: str = "Bright Sun",
    light_origin: str = "Front", 
    view_angle: str = "Front",
    perspective: str = "Medium wide",
    background: str = "Colorful",
    negative_prompt: str = "",
    enhance_prompt: bool = False
) -> Dict[str, Any]:
    """Generates basic assets using Imagen with customizable style options."""
    
    try:
        # Construct the enhanced prompt
        enhanced_prompt = f"{prompt} in the style of {primary_style}"
        
        if primary_style == "Art" and art_style:
            enhanced_prompt += f", {art_style}"
        elif primary_style == "Digital Creation" and digital_creation_style:
            enhanced_prompt += f", {digital_creation_style}"
        elif primary_style == "Photography" and photography_style:
            enhanced_prompt += f", {photography_style}"
            
        enhanced_prompt += f" with {lighting} lighting from the {light_origin}"
        enhanced_prompt += f" and a {view_angle} view angle with {perspective} perspective"
        enhanced_prompt += f" and a {background} background."
        
        final_prompt = enhanced_prompt
        final_negative_prompt = negative_prompt
        
        if enhance_prompt:
            # Use Gemini to enhance the prompt
            model = GenerativeModel(GEMINI_MODEL)
            response = model.generate_content(
                [enhanced_prompt, negative_prompt, enhancement_prompt],
                generation_config=generation_config,
                safety_settings=safety_settings,
            )
            
            try:
                response_data = json.loads(response.text)
                final_prompt = response_data.get("final_prompt", enhanced_prompt)
                final_negative_prompt = response_data.get("negative_prompt", negative_prompt)
            except json.JSONDecodeError:
                logging.warning("Failed to parse enhanced prompt, using original")
        
        # Generate images using Imagen
        img_model = ImageGenerationModel.from_pretrained(IMAGEN_MODEL)
        images = img_model.generate_images(
            prompt=final_prompt,
            negative_prompt=final_negative_prompt,
            number_of_images=2,
            language="en",
            aspect_ratio="1:1",
            safety_filter_level="block_few",
            person_generation="allow_adults",
        )
        
        # Upload to GCS and return URLs
        image_urls = []
        if GCS_BUCKET_NAME:
            storage_client = storage.Client()
            bucket = storage_client.bucket(GCS_BUCKET_NAME)
            
            for i, image in enumerate(images):
                file_name = f"basic_assets/{uuid.uuid4()}.png"
                blob = bucket.blob(file_name)
                blob.upload_from_string(image._image_bytes, content_type="image/png")
                
                signed_url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(minutes=15),
                    method="GET",
                )
                image_urls.append(signed_url)
        
        return {
            "success": True,
            "original_prompt": prompt,
            "enhanced_prompt": final_prompt,
            "final_negative_prompt": final_negative_prompt,
            "image_urls": image_urls,
            "style_options": {
                "primary_style": primary_style,
                "lighting": lighting,
                "perspective": perspective
            }
        }
        
    except Exception as e:
        logging.error(f"Error in basic asset generation: {e}")
        return {
            "success": False,
            "error": str(e)
        }

basic_asset_creator_agent = Agent(
    name="basic_asset_creator_agent",
    model=GEMINI_MODEL,
    description="Creates basic digital assets using Imagen with extensive customization options including art styles, lighting, perspective, and AI-enhanced prompting.",
    instruction="""You are a creative digital asset designer specializing in generating high-quality images with precise style control.

Your capabilities include:
1. **Style Customization**: Support for Photography, Art, and Digital Creation styles
2. **Lighting Control**: Various lighting conditions and origins
3. **Composition**: Different view angles and perspectives  
4. **AI Enhancement**: Optional prompt enhancement using advanced AI
5. **Background Options**: Colorful, Light, or Dark backgrounds

Always ask users for their specific requirements and provide detailed explanations of available options. Use the generate_basic_asset tool to create assets based on user preferences.""",
    tools=[generate_basic_asset],
) 