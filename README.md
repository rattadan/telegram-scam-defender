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
3. Create a `.env` file with your credentials and configuration:
   ```
   TELEGRAM_TOKEN=your_telegram_token
   AKASH_API_KEY=your_akash_api_key
   CONTENT_MODERATION_PROMPT="You are a content moderation assistant. Analyze the following message and determine if it contains abusive, offensive, harmful, or inappropriate content. Reply with only 'SAFE' or 'UNSAFE'."
   USERNAME_MODERATION_PROMPT="You are a content moderation assistant. Analyze the following username and determine if it contains abusive, offensive, harmful, or inappropriate content. Reply with only 'SAFE' or 'UNSAFE'."
   ```

   You can customize the moderation prompts to adjust how strictly the bot filters content.
4. Run the bot:
   ```
   python telegram-ban-bot.py
   ```

## Deployment

For 24/7 operation, deploy to a VPS using the provided systemd service file or use a service like PythonAnywhere.

## Docker Deployment

You can also run this bot in a Docker container:

1. Build the Docker image:

   ```bash
   docker build -t telegram-ban-bot .
   ```

2. Run the container:

   ```bash
   docker run -d --name telegram-ban-bot --env-file .env telegram-ban-bot
   ```

3. View container logs:

   ```bash
   docker logs telegram-ban-bot
   ```

4. Stop the container:

   ```bash
   docker stop telegram-ban-bot
   ```

5. Start the container again:

   ```bash
   docker start telegram-ban-bot
   ```

## License

MIT
