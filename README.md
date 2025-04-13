# Telegram Moderation Bot

A Telegram bot that uses LLM (Meta-Llama-3-2-3B-Instruct) via Akash API to check messages and usernames for abusive or offensive content. The bot automatically deletes inappropriate messages.

## Features

- Analyzes message content for inappropriate material
- Checks usernames for offensive content
- Automatically deletes messages that violate content policies
- Notifies the chat when content has been removed
- Uses Meta-Llama-3-2-3B-Instruct model via Akash API

## Setup

1. Clone this repository
2. Install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your credentials:
   ```
   TELEGRAM_TOKEN=your_telegram_token
   AKASH_API_KEY=your_akash_api_key
   ```
4. Run the bot:
   ```
   python telegram-ban-bot.py
   ```

## Deployment

For 24/7 operation, deploy to a VPS using the provided systemd service file or use a service like PythonAnywhere.

## License

MIT
