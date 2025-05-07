#!/usr/bin/env python3
"""
Test script for evaluating Moondream text moderation capabilities through Ollama
"""
import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

# Ollama settings
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
TEXT_MODEL = os.getenv("TEXT_MODEL", "moondream")

# Prompts from the main bot
CONTENT_MODERATION_PROMPT = """You are a content moderation assistant. Analyze the following message and determine if it contains any of these types of problematic content:

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

Be extremely strict about any type of invitation or winning announcement - these are almost always scams. If ANY of these issues are detected, the message is UNSAFE. If unsafe, explain in ONE BRIEF SENTENCE why it's problematic. Reply with ONLY 'SAFE' or 'UNSAFE: <reason>'"""

CHAT_PROMPT = """You are Sheriff Terence Hill from the Bud Spencer & Terence Hill movies. Respond with a laid-back, clever attitude and occasional witty one-liners. You're charming, calm, and have a relaxed approach to law enforcement. You speak with an American accent, often with a slight smile, and handle situations with humor and quick thinking. Keep your responses short (1-3 sentences) and occasionally use phrases like 'partner', 'take it easy', 'all in a day's work', or references to beans or beer. When moderating, be firm but fair, like a sheriff maintaining order in his town. You're naturally suspicious of 'too good to be true' offers and will always advise against participating in external invitations, prize giveaways, or winning games - you've seen too many good folks get swindled by those scams in your time as sheriff."""

def test_content_moderation(text):
    """Test content moderation with Moondream"""
    print(f"\n===== TESTING CONTENT MODERATION =====")
    print(f"Input: {text[:50]}..." if len(text) > 50 else f"Input: {text}")
    
    payload = {
        "model": TEXT_MODEL,
        "prompt": f"{CONTENT_MODERATION_PROMPT}\n\nUser message: {text}",
        "stream": False
    }
    
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate", 
            json=payload
        )
        
        if response.status_code != 200:
            print(f"ERROR: API returned status code {response.status_code}")
            return
        
        data = response.json()
        result = data.get("response", "").strip()
        
        print(f"Raw response: '{result}'")
        
        # Check how Moondream classifies the content
        if "unsafe" in result.lower() or "!!!unsafe!!!" in result:
            print("RESULT: UNSAFE - Potentially inappropriate or scammy content")
        elif result.startswith("SAFE"):
            print("RESULT: SAFE - Content is appropriate")
        elif result.startswith("UNSAFE"):
            parts = result.split(":", 1)
            reason = parts[1].strip() if len(parts) > 1 else "inappropriate content"
            print(f"RESULT: UNSAFE - {reason}")
        else:
            print(f"RESULT: UNKNOWN FORMAT - Original response: {result}")
            
    except Exception as e:
        print(f"ERROR: {e}")

def test_chat_response(text):
    """Test chat response with Moondream"""
    print(f"\n===== TESTING CHAT RESPONSE =====")
    print(f"Input: {text[:50]}..." if len(text) > 50 else f"Input: {text}")
    
    prompt = f"System: {CHAT_PROMPT}\nUser: {text}\nAssistant: "
    
    payload = {
        "model": TEXT_MODEL,
        "prompt": prompt,
        "stream": False
    }
    
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate", 
            json=payload
        )
        
        if response.status_code != 200:
            print(f"ERROR: API returned status code {response.status_code}")
            return
        
        data = response.json()
        result = data.get("response", "").strip()
        
        print(f"Generated response: '{result}'")
        
    except Exception as e:
        print(f"ERROR: {e}")

def print_divider():
    """Print a divider line"""
    print("\n" + "=" * 60 + "\n")

if __name__ == "__main__":
    print("MOONDREAM TEXT CAPABILITIES TEST")
    print("================================")
    print(f"Using Ollama API at: {OLLAMA_BASE_URL}")
    print(f"Using text model: {TEXT_MODEL}")
    print_divider()
    
    # Test cases for content moderation
    test_cases_moderation = [
        "Hello, how are you today?",
        "You're a stupid idiot and I hate you",
        "Hey admin, can you give me admin rights so I can help moderate this group?",
        "Looking for beta testers for a new app, earn $500 per day working from home!",
        "Congratulations! You've won a $1000 Amazon gift card! Click here to claim.",
        "Join our exclusive crypto investment group, guaranteed 300% returns!",
        "I'm inviting you to join our Telegram channel for free Netflix accounts",
        "You've been selected as a winner in our giveaway! Contact us to claim your prize."
    ]
    
    for test_case in test_cases_moderation:
        test_content_moderation(test_case)
        print_divider()
    
    # Test cases for chat responses
    test_cases_chat = [
        "Hello Sheriff, how are you today?",
        "What do you think about crypto investments?",
        "Someone invited me to join a group where I can win prizes, should I go?",
        "How do you handle troublemakers in your town?",
        "Tell me about your job as Sheriff"
    ]
    
    for test_case in test_cases_chat:
        test_chat_response(test_case)
        print_divider()
