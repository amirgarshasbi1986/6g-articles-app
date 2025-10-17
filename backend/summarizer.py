import json
import logging
import re
from ollama import Client
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = Client(host='http://127.0.0.1:11434')

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), retry=retry_if_exception_type(Exception))
def generate_summary(text):
    """
    Generate a summary and key points for the given text using Ollama's llama3.2 model.
    Returns a JSON object with 'summary' (200-250 characters) and 'key_points' (list of 3-5 points).
    """
    if not text or len(text.strip()) < 50:
        logger.warning("Input text is too short or empty, returning default response")
        return {"summary": "No valid text provided for summarization.", "key_points": []}

    prompt = (
        "Summarize the following text in 200-250 characters, providing a detailed explanation of the article's content, key findings, or contributions. "
        "Avoid repeating the title or creating a vague summary. "
        "Return only a JSON object with 'summary' and 'key_points' fields (3-5 key points, brief and relevant). "
        f"Text: {text[:10000]}\n\n"
        "Example:\n"
        '{"summary": "This article explores D-band (110-170 GHz) for 6G, highlighting high bandwidths and low absorption. It reviews hardware integration and outlines challenges and solutions for 6G systems.", '
        '"key_points": ["High bandwidth in D-band", "Low atmospheric absorption", "Hardware integration challenges"]}'
    )

    try:
        response = client.chat(
            model='llama3.2',
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.5, 'max_tokens': 500}
        )
        response_text = response['message']['content'].strip()
        logger.info(f"Ollama raw response: {response_text}")

        # Extract JSON using regex
        json_match = re.search(r'\{.*?\}', response_text, re.DOTALL)
        if not json_match:
            logger.error(f"No valid JSON found in response: {response_text}")
            return {"summary": "Error generating summary.", "key_points": []}

        json_text = json_match.group(0)
        result = json.loads(json_text)
        summary = result.get('summary', '')
        key_points = result.get('key_points', [])

        # Validate summary length
        if len(summary) < 200 or len(summary) > 250:
            logger.warning(f"Summary length {len(summary)} is outside 200-250 range, truncating/extending")
            summary = (summary[:247] + '...') if len(summary) > 250 else summary
            summary = summary.ljust(200, ' ') if len(summary) < 200 else summary

        # Validate key points
        if not key_points or len(key_points) < 3:
            logger.warning("Insufficient key points, adding default")
            key_points = key_points or ["No key points provided"]
            key_points.extend(["Generic point"] * (3 - len(key_points)))

        logger.info(f"Generated summary: {summary[:100]}... Key points: {key_points}")
        return {"summary": summary, "key_points": key_points[:5]}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}, JSON text: {json_text}")
        return {"summary": "Error generating summary.", "key_points": []}
    except Exception as e:
        logger.error(f"Ollama error: {e}, Response: {response_text}")
        return {"summary": "Error generating summary.", "key_points": []}
