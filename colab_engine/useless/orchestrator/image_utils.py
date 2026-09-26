import base64
import io
import logging
from PIL import Image
import config

logger = logging.getLogger(__name__)

def process_base64_image(b64_data: str, media_type: str) -> str:
    """Decodes, validates, resizes, and re-encodes a base64 image."""
    try:
        image_bytes = base64.b64decode(b64_data)
        if len(image_bytes) > config.MAX_IMAGE_BYTES:
            logger.warning("Image exceeds MAX_IMAGE_BYTES, dropping it.")
            return None

        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size

        if width > config.MAX_IMAGE_DIMENSION or height > config.MAX_IMAGE_DIMENSION:
            scale = config.MAX_IMAGE_DIMENSION / max(width, height)
            new_width = int(width * scale)
            new_height = int(height * scale)
            logger.info(f"Resizing image from {width}x{height} to {new_width}x{new_height}")
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Re-encode
        buffer = io.BytesIO()
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(buffer, format="JPEG", quality=85)
        new_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return new_b64
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        return None

def validate_images(messages: list) -> list:
    """Strip or reject oversized images in OpenAI format messages."""
    for msg in messages:
        if isinstance(msg.get("content"), list):
            image_count = 0
            filtered_content = []
            for block in msg["content"]:
                if block.get("type") == "image_url":
                    image_count += 1
                    if image_count > config.MAX_IMAGES_PER_REQUEST:
                        logger.warning(f"Exceeded MAX_IMAGES_PER_REQUEST ({config.MAX_IMAGES_PER_REQUEST}), ignoring extra image.")
                        continue  # Drop excess images
                    
                    url = block["image_url"]["url"]
                    if url.startswith("data:"):
                        # data:image/png;base64,iVBORw...
                        try:
                            header, b64_data = url.split(",", 1)
                            media_type = header.split(";")[0].split(":")[1]
                            processed_b64 = process_base64_image(b64_data, media_type)
                            if processed_b64:
                                block["image_url"]["url"] = f"data:image/jpeg;base64,{processed_b64}"
                            else:
                                continue # Drop invalid image
                        except Exception as e:
                            logger.error(f"Failed to parse data URL: {e}")
                            continue
                filtered_content.append(block)
            msg["content"] = filtered_content
    return messages
