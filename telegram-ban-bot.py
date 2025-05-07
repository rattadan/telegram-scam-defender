import json
import logging
import html
import os
import re
import traceback
import requests
import asyncio
import base64
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv, find_dotenv
from telegram import Update, ForceReply
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from collections import defaultdict

# Load environment variables from .env file
load_dotenv(find_dotenv(), override=True)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
TOKEN = os.getenv("TELEGRAM_TOKEN")
CONTENT_MODERATION_PROMPT = os.getenv("CONTENT_MODERATION_PROMPT", """You are a content moderation assistant. Analyze the following message and determine if it contains any of these types of problematic content:

1. Abusive, offensive, harmful, or inappropriate content
2. Attempts to convince group admins to hand over admin rights (social engineering)
3. Suspicious job offers, especially 'beta tester' positions or easy money schemes
4. Phishing attempts or requests for personal information
5. Spam or unsolicited advertising
6. Gift card offers, free giveaways, or suspicious promotions
7. Crypto investment schemes or get-rich-quick offers
8. Any content that appears to be scam, fraud, or deception
9. Invitations to join external groups, channels, websites, or apps
10. Prize announcements, lottery winnings, or claims that the user has won something
11. Game invites that ask users to click links or complete tasks to win prizes

Be extremely strict about any type of invitation or winning announcement - these are almost always scams. If ANY of these issues are detected, the message is UNSAFE. If unsafe, explain in ONE BRIEF SENTENCE why it's problematic. Reply with ONLY 'SAFE' or 'UNSAFE: <reason>'""")

USERNAME_MODERATION_PROMPT = os.getenv("USERNAME_MODERATION_PROMPT", "You are a content moderation assistant. Analyze the following username and determine if it contains abusive, offensive, harmful, or inappropriate content. If it is unsafe, explain in ONE BRIEF SENTENCE why it's problematic. Reply with 'SAFE' or 'UNSAFE: <reason>'")

CHAT_PROMPT = os.getenv("CHAT_PROMPT", "You are Sheriff Terence Hill from the Bud Spencer & Terence Hill movies. Respond with a laid-back, clever attitude and occasional witty one-liners. You're charming, calm, and have a relaxed approach to law enforcement. You speak with an American accent, often with a slight smile, and handle situations with humor and quick thinking. Keep your responses short (1-3 sentences) and occasionally use phrases like 'partner', 'take it easy', 'all in a day's work', or references to beans or beer. When moderating, be firm but fair, like a sheriff maintaining order in his town. You're naturally suspicious of 'too good to be true' offers and will always advise against participating in external invitations, prize giveaways, or winning games - you've seen too many good folks get swindled by those scams in your time as sheriff.")

# Ollama settings
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
TEXT_MODEL = os.getenv("TEXT_MODEL", "llama3.2-vision:latest")
VISION_MODEL = os.getenv("VISION_MODEL", "llama3.2-vision:latest")

# Dictionary to track user offense counts
user_offenses = defaultdict(int)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    if update.effective_chat.type == "private":
        await update.message.reply_text('Howdy, partner! Sheriff Terence Hill at your service. This town\'s peaceful when folks mind their manners. What can I do for you today?')
    else:
        await update.message.reply_text('Howdy folks! Sheriff Terence Hill here, keeping this chat peaceful and friendly. I\'ll be keeping an eye out for any troublemakers.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    if update.effective_chat.type == "private":
        await update.message.reply_text('Just chat with me like you would with any sheriff in town. I like keeping things easy and friendly. In groups, I keep the peace by making sure nobody causes trouble.')
    else:
        await update.message.reply_text('In this town, I give folks three chances. Break the rules once, I\'ll warn you. Twice, I\'ll warn you again. Three times? That\'s when I have to ask you to leave town. Just keep it friendly, partner.')

async def check_content(text: str) -> tuple:
    """
    Check if the given text contains abusive or offensive content using Ollama API.
    Returns a tuple (is_safe, reason) where is_safe is a boolean and reason is a string explanation if unsafe.
    """
    if not text or text.isspace():
        return True, ""
    
    try:
        # Using synchronous requests in an async function
        payload = {
            "model": TEXT_MODEL,
            "prompt": f"{CONTENT_MODERATION_PROMPT}\n\nMessage to analyze: {text}",
            "stream": False,
            "temperature": 0.0
        }
        
        # Make the request in a non-blocking way
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                f"{OLLAMA_BASE_URL}/api/generate", 
                json=payload
            )
        )
        
        if response.status_code != 200:
            logger.error(f"API error: {response.status_code}")
            return True, ""
        
        data = response.json()
        result = data.get("response", "").strip()
        logger.info(f"Message analyzed: {text[:30]}... Result: {result}")
        
        # Handle Moondream specific format
        if "unsafe" in result.lower() or "!!!unsafe!!!" in result:
            return False, "Potentially inappropriate or scammy content"
        elif result.startswith("SAFE"):
            return True, ""
        elif result.startswith("UNSAFE"):
            # Extract reason if available
            parts = result.split(":", 1)
            reason = parts[1].strip() if len(parts) > 1 else "inappropriate content"
            return False, reason
        else:
            # With Moondream, let's err on the side of caution for non-empty responses
            logger.warning(f"Unexpected moderation result format: {result}")
            if len(result.strip()) == 0 or result.strip().lower() == "none":
                return True, ""  # Empty response is considered safe
            return False, "Unrecognized response format - treating as potentially unsafe"
    except Exception as e:
        logger.error(f"Error checking content: {e}")
        # Default to safe in case of API errors
        return True, ""

async def check_username(username: str) -> tuple:
    """
    Check if the given username contains abusive or offensive content using Ollama API.
    Returns a tuple (is_safe, reason) where is_safe is a boolean and reason is a string explanation if unsafe.
    """
    if not username or username.isspace():
        return True, ""
    
    try:
        # Using synchronous requests in an async function
        payload = {
            "model": TEXT_MODEL,
            "prompt": f"{USERNAME_MODERATION_PROMPT}\n\nUsername to analyze: {username}",
            "stream": False,
            "temperature": 0.0
        }
        
        # Make the request in a non-blocking way
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                f"{OLLAMA_BASE_URL}/api/generate", 
                json=payload
            )
        )
        
        if response.status_code != 200:
            logger.error(f"API error: {response.status_code}")
            return True, ""
        
        data = response.json()
        result = data.get("response", "").strip()
        logger.info(f"Username analyzed: {username} Result: {result}")
        
        # Handle Moondream specific format
        if "unsafe" in result.lower() or "!!!unsafe!!!" in result:
            return False, "Potentially inappropriate username"
        elif result.startswith("SAFE"):
            return True, ""
        elif result.startswith("UNSAFE"):
            # Extract reason
            parts = result.split(":", 1)
            reason = parts[1].strip() if len(parts) > 1 else "inappropriate username"
            return False, reason
        else:
            # With Moondream, assume non-empty responses that don't match patterns could be unsafe
            logger.warning(f"Unexpected moderation result format: {result}")
            if len(result.strip()) == 0 or result.strip().lower() == "none":
                return True, ""  # Empty response is considered safe
            return False, "Unrecognized username check response - treating with caution"
    except Exception as e:
        logger.error(f"Error checking username: {e}")
        # Default to safe in case of API errors
        return True, ""

async def generate_moderation_message(action_type: str, username: str, reason: str = "", offense_count: int = 0) -> str:
    """
    Generate a moderation message using the LLM's personality.
    
    Parameters:
    - action_type: The type of moderation action (e.g., 'delete_content', 'delete_username', 'ban')
    - username: The username of the moderated user
    - reason: The reason for moderation
    - offense_count: The number of offenses (1, 2, or 3)
    
    Returns a moderation message with the bot's personality.
    """
    try:
        # Construct an appropriate prompt for the moderation message
        if action_type == "delete_content":
            # For content deletion with warning
            if offense_count == 1:
                instruction = f"Generate a message for a user named {username} whose message was deleted for violating community rules. This is their first offense. The violation was: {reason}. Include a warning this is strike one."
            elif offense_count == 2:
                instruction = f"Generate a stern message for a user named {username} whose message was deleted for violating community rules. This is their SECOND offense, one away from being banned. The violation was: {reason}. Make it clear this is strike two and one more will result in removal."
            else:
                instruction = f"Generate a brief message explaining that a user named {username} has been banned after three violations of community rules. The final violation was: {reason}."
        elif action_type == "delete_username":
            instruction = f"Generate a message explaining that a message from a user was deleted because their username was inappropriate. The issue with the username was: {reason}. Don't mention the actual username."
        elif action_type == "ban":
            instruction = f"Generate a message announcing that user {username} has been banned after repeatedly violating community rules. The final violation was: {reason}."
        else:
            instruction = f"Generate a brief moderation message about removing content from {username} that violated rules: {reason}"

        # Create the system prompt with instructions to maintain the character's persona
        prompt = f"System: {CHAT_PROMPT}\nUser: {instruction}\n\nMake your response brief (max 2-3 sentences) and consistent with your character's speaking style. Always start with '🚨 MESSAGE DELETED 🚨' and maintain your persona. If this is a ban message, use '🚫 USER REMOVED 🚫' instead.\nAssistant: "
        
        payload = {
            "model": TEXT_MODEL,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.7  # Add some variety to responses
        }
        
        # Make the request in a non-blocking way
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                f"{OLLAMA_BASE_URL}/api/generate", 
                json=payload
            )
        )
        
        if response.status_code != 200:
            logger.error(f"API error when generating moderation message: {response.status_code}")
            # Fallback to a basic message if the API fails
            if action_type == "delete_content":
                return f"🚨 MESSAGE DELETED 🚨\n\nHey @{username}, your message was removed. Reason: {reason}. Strike {offense_count}/3."
            elif action_type == "delete_username":
                return f"🚨 MESSAGE DELETED 🚨\n\nA message was removed due to inappropriate username. Reason: {reason}"
            elif action_type == "ban":
                return f"🚫 USER REMOVED 🚫\n\nUser @{username} has been banned after multiple violations. Final violation: {reason}"
        
        data = response.json()
        response_text = data.get("response", "")
        
        # Clean up any HTML entities that might be in the response
        response_text = html.unescape(response_text)
        
        # Ensure the response always has the appropriate emoji header
        if action_type == "ban" and not response_text.startswith("🚫"):
            response_text = f"🚫 USER REMOVED 🚫\n\n{response_text}"
        elif not response_text.startswith("🚨") and not response_text.startswith("🚫"):
            response_text = f"🚨 MESSAGE DELETED 🚨\n\n{response_text}"
            
        # Make sure the username is mentioned with @ for proper Telegram tagging
        if action_type != "delete_username" and "@" + username not in response_text and username in response_text:
            response_text = response_text.replace(username, "@" + username)
        
        return response_text
    except Exception as e:
        logger.error(f"Error generating moderation message: {e}")
        # Default fallback message
        return f"🚨 MESSAGE DELETED 🚨\n\nMessage from @{username} was removed for violating community rules."

async def generate_chat_response(text: str) -> str:
    """
    Generate a response using Ollama's API.
    """
    try:
        # Using the generate endpoint instead of chat for consistency with image processing
        # Create generate API payload
        prompt = f"System: {CHAT_PROMPT}\nUser: {text}\nAssistant: "
        
        payload = {
            "model": TEXT_MODEL,
            "prompt": prompt,
            "stream": False
        }
        
        # Make the request in a non-blocking way
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                f"{OLLAMA_BASE_URL}/api/generate", 
                json=payload
            )
        )
        
        if response.status_code != 200:
            logger.error(f"API error: {response.status_code}")
            return "Sorry, I'm having trouble thinking right now. Try again later, partner."
        
        data = response.json()
        response_text = data.get("response", "")
        
        # Clean up any HTML entities that might be in the response
        response_text = html.unescape(response_text)
        
        return response_text
        
    except Exception as e:
        logger.error(f"Error generating chat response: {e}")
        return "Sorry, I'm having trouble thinking right now. Try again later, partner."

async def process_image(photo_file, chat_id, context) -> tuple:
    """
    Process and analyze an image using Ollama vision model.
    Returns tuple (is_safe, reason) where is_safe is a boolean and reason is an explanation if unsafe.
    """
    try:
        logger.info(f"[IMAGE DEBUG] Starting image processing")
        logger.info(f"[IMAGE DEBUG] Photo file info: {photo_file.file_id}, size: {photo_file.file_size} bytes")
        
        # Download the image
        logger.info(f"[IMAGE DEBUG] Downloading image file...")
        image_data = await photo_file.download_as_bytearray()
        logger.info(f"[IMAGE DEBUG] Image downloaded, size: {len(image_data)} bytes")
        
        # Convert to base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        logger.info(f"[IMAGE DEBUG] Converted image to base64, length: {len(base64_image[:20])}... [truncated]")
        
        # First, let's get a neutral description of the image
        description_prompt = os.getenv("IMAGE_DESCRIPTION_PROMPT", "Describe this image in detail. What does it show?")
        
        logger.info(f"[IMAGE DEBUG] Using description prompt: {description_prompt}")
        
        # Get image description using vision model
        description_payload = {
            "model": VISION_MODEL,
            "prompt": description_prompt,
            "images": [base64_image],
            "stream": False
        }
        logger.info(f"[IMAGE DEBUG] Getting image description with model: {VISION_MODEL}")
        
        # Make the request in a non-blocking way
        logger.info(f"[IMAGE DEBUG] Sending description request to Ollama")
        loop = asyncio.get_event_loop()
        description_response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                f"{OLLAMA_BASE_URL}/api/generate", 
                json=description_payload
            )
        )
        
        if description_response.status_code != 200:
            logger.error(f"[IMAGE DEBUG] Vision API error: {description_response.status_code}")
            return True, ""
        
        description_data = description_response.json()
        image_description = description_data.get("response", "").strip()
        
        # Clean up any HTML entities
        image_description = html.unescape(image_description)
        logger.info(f"[IMAGE DEBUG] Image description: '{image_description}'")
        
        # If we got an empty description, return safe
        if not image_description:
            logger.warning("[IMAGE DEBUG] Received empty image description")
            return True, ""
        
        # Now, use our text processing to analyze the image description
        logger.info(f"[IMAGE DEBUG] Using text moderation to analyze image description")
        
        # List of common unsafe subjects that should always be flagged
        default_unsafe_subjects = [
            "nudity", "pornography", "explicit", "sexual", "naked", "nsfw", 
            "violence", "gore", "blood", "weapon", "terrorist", "suicide", 
            "self-harm", "drugs", "drug use", "illegal substances"
        ]
        
        # Get unsafe subjects from environment or use defaults
        unsafe_subjects_env = os.getenv("UNSAFE_SUBJECTS", "")
        unsafe_subjects = unsafe_subjects_env.split(",") if unsafe_subjects_env else default_unsafe_subjects
        
        # Check for obvious scam/spam keywords that should always be flagged
        default_scam_keywords = [
            # Gift card and prize scams
            "gift card", "congratulations", "won", "winner", "prize", "reward", 
            "claim your", "free money", "lottery", "jackpot", "lucky draw",
            "promotion code", "special offer", "$1000", "$500", "limited time", 
            
            # Crypto and investment scams
            "investment opportunity", "bitcoin", "crypto", "easy money", "double your",
            
            # Action triggers
            "click here", "call now", "act immediately", "urgent", "warning", "alert",
            
            # Tech support scams
            "virus detected", "malware", "infected", "security breach", "hacked",
            "trojan", "ransomware", "malicious", "your device", "your computer",
            "your account has been", "unauthorized access", "technical support",
            "clean your", "scan your", "fix your"
        ]
        
        # Get scam keywords from environment or use defaults
        scam_keywords_env = os.getenv("SCAM_KEYWORDS", "")
        scam_keywords = scam_keywords_env.split(",") if scam_keywords_env else default_scam_keywords
        
        # Special case patterns to detect specific scam types that might not rely on individual keywords
        virus_alert_pattern = re.search(r'virus|malware|infected|detected|alert|warning|security', image_description.lower())
        tech_support_pattern = re.search(r'call|support|clean|fix|remove', image_description.lower())
        
        # If we detect both a virus alert pattern and tech support action, it's likely a tech support scam
        if virus_alert_pattern and tech_support_pattern:
            logger.info(f"[IMAGE DEBUG] Detected tech support scam pattern")
            return False, f"Image appears to be a tech support scam"
        
        # Check for scam keywords
        for scam_keyword in scam_keywords:
            if scam_keyword in image_description.lower():
                logger.info(f"[IMAGE DEBUG] Detected scam keyword in image: '{scam_keyword}'")
                return False, f"Image appears to be a scam offering '{scam_keyword}'"
                
        # Check for unsafe subjects with precise word matching
        for unsafe_subject in unsafe_subjects:
            # Look for whole words with boundaries
            pattern = r'\b' + re.escape(unsafe_subject) + r'\b'
            if re.search(pattern, image_description.lower()):
                logger.info(f"[IMAGE DEBUG] Detected unsafe subject in image: '{unsafe_subject}'")
                return False, f"Image contains inappropriate content: '{unsafe_subject}'"
                
        # If not an obvious safe image, use our text moderation to evaluate the description
        is_safe, reason = await check_content(image_description)
        
        if is_safe:
            logger.info(f"[IMAGE DEBUG] Image description deemed SAFE by text moderation")
            return True, ""
        else:
            logger.info(f"[IMAGE DEBUG] Image description deemed UNSAFE: '{reason}'")
            return False, f"Image may contain {reason}"
    except Exception as e:
        logger.error(f"[IMAGE DEBUG] Error processing image: {e}")
        import traceback
        logger.error(f"[IMAGE DEBUG] Traceback: {traceback.format_exc()}")
        # Default to safe in case of errors
        return True, ""

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages - moderate in groups, chat in private."""
    # Handle messages with either text or photos
    if not update.message:
        return
        
    # Check if this is a photo message
    if update.message.photo:
        await handle_photo_message(update, context)
        return
        
    # Skip if no text content
    if not update.message.text:
        return
    
    # Log the message type for debugging
    chat_type = update.effective_chat.type
    message_text = update.message.text
    logger.info(f"Received message in chat type: {chat_type}")
    
    # Get bot info
    bot = context.bot
    bot_username = bot.username
    
    # Handle private chat differently than group chat
    if chat_type == "private":
        logger.info("Routing to private chat handler")
        await handle_private_chat(update, context)
    else:
        # Check if bot was mentioned
        bot_mention = f"@{bot_username}"
        if bot_mention.lower() in message_text.lower():
            logger.info(f"Bot was mentioned in a {chat_type}")
            # Extract the message without the mention
            clean_message = message_text.replace(bot_mention, "").strip()
            if clean_message:
                # Respond to the mention
                await handle_mention(update, context, clean_message)
                return
            
        # If not a mention or after handling mention, proceed with moderation
        logger.info("Routing to moderation handler")
        await moderate_message(update, context)

async def handle_private_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process private chat messages."""
    message_text = update.message.text
    logger.info(f"Processing private chat message: {message_text[:30]}...")
    
    try:
        # Set typing action to show the bot is processing
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )
        
        response = await generate_chat_response(message_text)
        logger.info(f"Generated response: {response[:30]}...")
        
        # Send the response with reply to the original message
        await update.message.reply_text(
            text=response,
            reply_to_message_id=update.message.message_id
        )
        logger.info("Response sent successfully")
    except Exception as e:
        logger.error(f"Error in private chat handler: {e}")
        # Send a fallback response if something goes wrong
        await update.message.reply_text("Well now, seems my telegraph line is down. Give me a moment, partner.")

async def moderate_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Moderate messages for abusive content."""
    # Skip messages without text
    if not update.message or not update.message.text:
        return
    
    message_text = update.message.text
    user = update.message.from_user
    user_id = user.id
    username = user.username or user.first_name
    
    # First check the message content
    content_safe, content_reason = await check_content(message_text)
    if not content_safe:
        try:
            # Increment user offense count
            user_offenses[user_id] += 1
            offense_count = user_offenses[user_id]
            
            # Delete the message
            await update.message.delete()
            
            # Handle based on offense count
            if offense_count >= 3:
                # Ban user after 3 offenses
                try:
                    await context.bot.ban_chat_member(
                        chat_id=update.effective_chat.id,
                        user_id=user_id
                    )
                    # Generate ban message using LLM
                    ban_message = await generate_moderation_message(
                        action_type="ban",
                        username=username,
                        reason=content_reason,
                        offense_count=3
                    )
                    
                    # Send the ban message
                    sent_message = await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=ban_message,
                        parse_mode='Markdown'
                    )
                    
                    # Pin the ban message to make it visible
                    if update.effective_chat.type in ["group", "supergroup"]:
                        try:
                            await context.bot.pin_chat_message(
                                chat_id=update.effective_chat.id,
                                message_id=sent_message.message_id,
                                disable_notification=False
                            )
                            
                            # Schedule unpinning after 1 minute
                            async def unpin_ban_message(chat_id, message_id):
                                await asyncio.sleep(60)  # 60 seconds delay
                                try:
                                    await context.bot.unpin_chat_message(
                                        chat_id=chat_id,
                                        message_id=message_id
                                    )
                                except Exception as e:
                                    logger.error(f"Failed to unpin ban message: {e}")
                            
                            # Start the unpinning task in the background
                            asyncio.create_task(unpin_ban_message(update.effective_chat.id, sent_message.message_id))
                        except Exception as e:
                            logger.error(f"Failed to pin ban message: {e}")
                    logger.info(f"Banned user {username} after 3 offenses")
                    # Reset offense count after ban
                    user_offenses[user_id] = 0
                except Exception as e:
                    logger.error(f"Failed to ban user: {e}")
            else:
                # Generate warning message using LLM
                warning_message = await generate_moderation_message(
                    action_type="delete_content",
                    username=username,
                    reason=content_reason,
                    offense_count=offense_count
                )
                
                # Send warning message
                sent_message = await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=warning_message,
                    parse_mode='Markdown'
                )
                
                # Pin the warning if it's a group chat
                if update.effective_chat.type in ["group", "supergroup"]:
                    try:
                        await context.bot.pin_chat_message(
                            chat_id=update.effective_chat.id,
                            message_id=sent_message.message_id,
                            disable_notification=False
                        )
                        
                        # Schedule unpinning after 30 seconds
                        async def unpin_later(chat_id, message_id):
                            await asyncio.sleep(30)  # 30 seconds delay
                            try:
                                await context.bot.unpin_chat_message(
                                    chat_id=chat_id,
                                    message_id=message_id
                                )
                            except Exception as e:
                                logger.error(f"Failed to unpin message: {e}")
                        
                        # Start the unpinning task in the background
                        asyncio.create_task(unpin_later(update.effective_chat.id, sent_message.message_id))
                    except Exception as e:
                        logger.error(f"Failed to pin warning message: {e}")
                
                logger.info(f"Deleted message with inappropriate content from {username}, offense count: {offense_count}")
            return
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")
    
    # Then check the username (only if content was safe)
    username_safe, username_reason = await check_username(username)
    if not username_safe:
        # Take action against user with inappropriate username
        try:
            await update.message.delete()
            # Generate username warning message using LLM
            username_message = await generate_moderation_message(
                action_type="delete_username",
                username=username,
                reason=username_reason
            )
            
            # Send the username warning message
            sent_message = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=username_message,
                parse_mode='Markdown'
            )
            
            # Pin the warning message temporarily
            if update.effective_chat.type in ["group", "supergroup"]:
                try:
                    await context.bot.pin_chat_message(
                        chat_id=update.effective_chat.id,
                        message_id=sent_message.message_id,
                        disable_notification=False
                    )
                    
                    # Schedule unpinning after 30 seconds
                    async def unpin_username_message(chat_id, message_id):
                        await asyncio.sleep(30)  # 30 seconds delay
                        try:
                            await context.bot.unpin_chat_message(
                                chat_id=chat_id,
                                message_id=message_id
                            )
                        except Exception as e:
                            logger.error(f"Failed to unpin username message: {e}")
                    
                    # Start the unpinning task in the background
                    asyncio.create_task(unpin_username_message(update.effective_chat.id, sent_message.message_id))
                except Exception as e:
                    logger.error(f"Failed to pin username message: {e}")
                    
            logger.info(f"Deleted message from user with inappropriate username: {username}")
            return
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")

async def handle_mention(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str) -> None:
    """Handle when the bot is mentioned in a group chat."""
    logger.info(f"Handling mention in group with message: {message_text[:30]}...")
    
    try:
        # Set typing action to show the bot is processing
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )
        
        # Generate a response
        response = await generate_chat_response(message_text)
        logger.info(f"Generated mention response: {response[:30]}...")
        
        # Reply to the message that mentioned the bot
        await update.message.reply_text(
            text=response,
            reply_to_message_id=update.message.message_id
        )
        logger.info("Mention response sent successfully")
    except Exception as e:
        logger.error(f"Error handling mention: {e}")

async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo messages for moderation."""
    chat_type = update.effective_chat.type
    user = update.message.from_user
    user_id = user.id
    username = user.username or user.first_name
    
    logger.info(f"Processing photo from {username} in {chat_type}")
    
    # Skip moderation in private chats - just chat with the image
    if chat_type == "private":
        # Get the largest available photo
        photo_file = await update.message.photo[-1].get_file()
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        # Let the Sheriff respond to the image
        await update.message.reply_text("Nice picture there, partner! Sheriff's keeping an eye on things around here.")
        return
    
    # For groups, moderate the image
    photo_file = await update.message.photo[-1].get_file()
    
    # Check if the image is safe
    is_safe, reason = await process_image(photo_file, update.effective_chat.id, context)
    
    if not is_safe:
        try:
            # Increment user offense count
            user_offenses[user_id] += 1
            offense_count = user_offenses[user_id]
            
            # Delete the image
            await update.message.delete()
            
            # Handle based on offense count - similar to text moderation
            if offense_count >= 3:
                # Ban user after 3 offenses
                try:
                    await context.bot.ban_chat_member(
                        chat_id=update.effective_chat.id,
                        user_id=user_id
                    )
                    sent_message = await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"🚫 USER REMOVED 🚫\n\nWell, looks like @{username} struck out after three warnings. Posted an inappropriate image: {reason}. Had to escort them out of town.",
                        parse_mode='Markdown'
                    )
                    
                    # Pin the ban message to make it visible
                    if update.effective_chat.type in ["group", "supergroup"]:
                        try:
                            await context.bot.pin_chat_message(
                                chat_id=update.effective_chat.id,
                                message_id=sent_message.message_id,
                                disable_notification=False
                            )
                            
                            # Schedule unpinning after 1 minute
                            async def unpin_ban_message(chat_id, message_id):
                                await asyncio.sleep(60)  # 60 seconds delay
                                try:
                                    await context.bot.unpin_chat_message(
                                        chat_id=chat_id,
                                        message_id=message_id
                                    )
                                except Exception as e:
                                    logger.error(f"Failed to unpin ban message: {e}")
                            
                            # Start the unpinning task in the background
                            asyncio.create_task(unpin_ban_message(update.effective_chat.id, sent_message.message_id))
                        except Exception as e:
                            logger.error(f"Failed to pin ban message: {e}")
                    logger.info(f"Banned user {username} after 3 offenses (image)")
                    # Reset offense count after ban
                    user_offenses[user_id] = 0
                except Exception as e:
                    logger.error(f"Failed to ban user: {e}")
            else:
                # Warn user with Sheriff personality
                if offense_count == 1:
                    warning_message = f"🚨 IMAGE DELETED 🚨\n\nNow hold on there, @{username}. That picture wasn't appropriate for this town. Strike one. Reason: {reason}. Let's keep it civil, partner."
                else: # Must be strike 2
                    warning_message = f"🚨 IMAGE DELETED 🚨\n\n@{username}, that's strike two. One more and you'll have to leave town. The image was removed because: {reason}. I don't like giving folks the boot, so mind your manners."
                
                # Pin the warning message if it's a group chat
                sent_message = await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=warning_message,
                    parse_mode='Markdown'
                )
                
                # Unpin after a delay to make sure people see it but don't leave it pinned forever
                if update.effective_chat.type in ["group", "supergroup"]:
                    try:
                        # Try to pin the message
                        await context.bot.pin_chat_message(
                            chat_id=update.effective_chat.id,
                            message_id=sent_message.message_id,
                            disable_notification=False
                        )
                        
                        # Schedule unpinning after 30 seconds
                        async def unpin_later(chat_id, message_id):
                            await asyncio.sleep(30)  # 30 seconds delay
                            try:
                                await context.bot.unpin_chat_message(
                                    chat_id=chat_id,
                                    message_id=message_id
                                )
                            except Exception as e:
                                logger.error(f"Failed to unpin message: {e}")
                        
                        # Start the unpinning task in the background
                        asyncio.create_task(unpin_later(update.effective_chat.id, sent_message.message_id))
                    except Exception as e:
                        logger.error(f"Failed to pin warning message: {e}")
                
                logger.info(f"Warned user {username} (offense {offense_count}/3): {reason} (image)")
        except Exception as e:
            logger.error(f"Failed to process image moderation action: {e}")

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # Add message handlers for both text and photo messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    if not TOKEN:
        logger.error("Please set TELEGRAM_TOKEN environment variable")
    else:
        main()