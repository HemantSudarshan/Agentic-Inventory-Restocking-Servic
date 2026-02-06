"""
Telegram Notifications for Inventory Agent
Sends rich notifications with order details to Telegram bot
"""

import os
import httpx
import asyncio
from typing import Optional, Dict, Any
import structlog

logger = structlog.get_logger()

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def send_telegram_notification(order_data: Dict[str, Any]) -> bool:
    """
    Send order notification to Telegram with rich formatting.
    
    Args:
        order_data: Order details from the inventory trigger
        
    Returns:
        True if sent successfully, False otherwise
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured - skipping notification")
        return False
    
    try:
        # Build message with emojis for easy reading
        confidence = order_data.get("confidence", 0)
        status = order_data.get("status", "unknown")
        
        # Confidence indicator
        if confidence >= 0.8:
            conf_emoji = "🟢"
        elif confidence >= 0.6:
            conf_emoji = "🟡"
        else:
            conf_emoji = "🔴"
        
        # Status indicator
        status_emoji = "✅" if status == "executed" else "⏳"
        
        message = f"""
{status_emoji} *Inventory Order Alert*

📦 *Material:* {order_data.get('product_id', 'Unknown')}
📊 *Units Needed:* {order_data.get('quantity', 0):,}
{conf_emoji} *Confidence:* {int(confidence * 100)}%
📋 *Status:* {status.upper()}

💰 *Est. Cost:* ${order_data.get('estimated_cost', 0):,.2f}
📉 *Shortage:* {order_data.get('shortage', 0):,.0f} units
🎯 *Reorder Point:* {order_data.get('reorder_point', 0):,.0f}

📝 *AI Reasoning:*
_{order_data.get('reasoning', 'No details')[:200]}..._

🕐 Order ID: `{order_data.get('order_id', 'N/A')[:25]}`
"""
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info("Telegram notification sent", order_id=order_data.get('order_id'))
                return True
            else:
                logger.error("Telegram API error", status=response.status_code, body=response.text)
                return False
                
    except Exception as e:
        logger.error("Failed to send Telegram notification", error=str(e))
        return False


async def send_telegram_low_confidence_alert(order_data: Dict[str, Any]) -> bool:
    """
    Send urgent alert for low-confidence orders requiring human review.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    
    try:
        message = f"""
🚨 *APPROVAL REQUIRED*

A low-confidence order needs your review:

📦 {order_data.get('product_id')}
📊 Qty: {order_data.get('quantity', 0):,} units
🔴 Confidence: {int(order_data.get('confidence', 0) * 100)}%

⚡ *Action needed:* Go to dashboard and approve/reject

🔗 Dashboard: http://localhost:8000/dashboard
"""
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10)
            return response.status_code == 200
            
    except Exception as e:
        logger.error("Failed to send Telegram alert", error=str(e))
        return False


def get_telegram_setup_info() -> Dict[str, Any]:
    """
    Return setup information for Telegram integration.
    Includes QR code link and setup instructions.
    """
    bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "InventoryAgentBot")
    
    return {
        "configured": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        "bot_link": f"https://t.me/{bot_username}",
        "qr_url": f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=https://t.me/{bot_username}",
        "setup_instructions": [
            f"1. Open Telegram and search for @{bot_username}",
            "2. Click 'Start' to activate the bot",
            "3. Send /start to get your Chat ID",
            "4. Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env",
            "5. Restart the server to enable notifications"
        ]
    }
