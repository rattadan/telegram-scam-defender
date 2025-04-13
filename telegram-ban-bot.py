import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
TOKEN = os.getenv("TELEGRAM_TOKEN")
AKASH_API_KEY = os.getenv("AKASH_API_KEY")
CONTENT_MODERATION_PROMPT = os.getenv("CONTENT_MODERATION_PROMPT", "You are a content moderation assistant. Analyze the following message and determine if it contains abusive, offensive, harmful, or inappropriate content. Reply with only 'SAFE' or 'UNSAFE'.")
USERNAME_MODERATION_PROMPT = os.getenv("USERNAME_MODERATION_PROMPT", "You are a content moderation assistant. Analyze the following username and determine if it contains abusive, offensive, harmful, or inappropriate content. Reply with only 'SAFE' or 'UNSAFE'.")

# Initialize OpenAI client with Akash endpoint
client = OpenAI(
    api_key=AKASH_API_KEY,
    base_url="https://chatapi.akash.network/api/v1"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text('Hi! I am a moderation bot. I will check messages for abusive content.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text('I monitor chat messages for abusive content. Inappropriate messages will be removed.')

async def check_content(text: str) -> bool:
    """
    Check if the given text contains abusive or offensive content using OpenAI's API.
    Returns True if content is safe, False if it should be deleted.
    """
    try:
        response = client.chat.completions.create(
            model="Meta-Llama-3-2-3B-Instruct",
            messages=[
                {"role": "system", "content": CONTENT_MODERATION_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.0
        )
        result = response.choices[0].message.content.strip()
        logger.info(f"Message analyzed: {text[:30]}... Result: {result}")
        return result == "SAFE"
    except Exception as e:
        logger.error(f"Error checking content: {e}")
        # Default to safe in case of API errors
        return True

async def check_username(username: str) -> bool:
    """
    Check if the given username contains abusive or offensive content using OpenAI's API.
    Returns True if username is safe, False if it's inappropriate.
    """
    try:
        response = client.chat.completions.create(
            model="Meta-Llama-3-2-3B-Instruct",
            messages=[
                {"role": "system", "content": USERNAME_MODERATION_PROMPT},
                {"role": "user", "content": username}
            ],
            temperature=0.0
        )
        result = response.choices[0].message.content.strip()
        logger.info(f"Username analyzed: {username} Result: {result}")
        return result == "SAFE"
    except Exception as e:
        logger.error(f"Error checking username: {e}")
        # Default to safe in case of API errors
        return True

async def moderate_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Moderate messages for abusive content."""
    # Skip messages without text
    if not update.message or not update.message.text:
        return
    
    message_text = update.message.text
    username = update.message.from_user.username or update.message.from_user.first_name
    
    # First check the username (only needs to be done once per user, could be optimized)
    username_safe = await check_username(username)
    if not username_safe:
        # Take action against user with inappropriate username
        try:
            await update.message.delete()
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"User with inappropriate username had their message removed."
            )
            logger.info(f"Deleted message from user with inappropriate username: {username}")
            return
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")
    
    # Then check the message content
    content_safe = await check_content(message_text)
    if not content_safe:
        try:
            await update.message.delete()
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"A message containing inappropriate content was removed."
            )
            logger.info(f"Deleted message with inappropriate content from {username}")
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # Add message handler for content moderation
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, moderate_message))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    if not TOKEN or not AKASH_API_KEY:
        logger.error("Please set TELEGRAM_TOKEN and AKASH_API_KEY environment variables")
    else:
        main()