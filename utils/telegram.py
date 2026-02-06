"""
Telegram Bot Integration for Inventory Agent

Features:
- Send rich notifications with order details
- Receive commands via webhook (/start, /status, /approve, /reject)
- Inline keyboards for order approval workflow
"""

import os
import httpx
import asyncio
from typing import Optional, Dict, Any, List
import structlog
from datetime import datetime

logger = structlog.get_logger()

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else None
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:8000")

# Store registered chat IDs (in production, use database)
registered_chats: Dict[str, Dict[str, Any]] = {}


# ==================== Outbound Notifications ====================

async def send_telegram_notification(order_data: Dict[str, Any]) -> bool:
    """
    Send order notification to ALL registered Telegram users.
    No .env editing needed - users just scan QR and start bot.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram bot token not configured - skipping notification")
        return False
    
    # If no users registered yet, check if fallback TELEGRAM_CHAT_ID is set
    if not registered_chats and not TELEGRAM_CHAT_ID:
        logger.warning("No Telegram users registered yet")
        return False
    
    try:
        confidence = order_data.get("confidence", 0)
        status = order_data.get("status", "unknown")
        
        # Confidence indicator
        conf_emoji = "🟢" if confidence >= 0.8 else ("🟡" if confidence >= 0.6 else "🔴")
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
        
        # Add inline keyboard for pending orders
        keyboard = None
        if status == "pending":
            order_id = order_data.get('order_id', '')[:50]
            keyboard = {
                "inline_keyboard": [[
                    {"text": "✅ Approve", "callback_data": f"approve_{order_id}"},
                    {"text": "❌ Reject", "callback_data": f"reject_{order_id}"}
                ]]
            }
        
        # Broadcast to all registered users
        success_count = 0
        recipients = list(registered_chats.keys()) if registered_chats else [TELEGRAM_CHAT_ID]
        
        for chat_id in recipients:
            if await _send_message(chat_id, message, keyboard):
                success_count += 1
        
        logger.info(f"Telegram notification sent to {success_count}/{len(recipients)} users")
        return success_count > 0
        
    except Exception as e:
        logger.error("Failed to send Telegram notification", error=str(e))
        return False


async def send_telegram_low_confidence_alert(order_data: Dict[str, Any]) -> bool:
    """
    Send low-confidence order alert to ALL registered users requiring approval.
    """
    if not TELEGRAM_BOT_TOKEN:
        return False
    
    if not registered_chats and not TELEGRAM_CHAT_ID:
        logger.warning("No Telegram users registered yet")
        return False
    
    try:
        order_id = order_data.get('order_id', '')[:50]
        
        message = f"""
🚨 *APPROVAL REQUIRED*

📦 *Material:* {order_data.get('product_id', 'Unknown')}
📊 *Quantity:* {order_data.get('quantity', 0):,} units
🔴 *Confidence:* {int(order_data.get('confidence', 0) * 100)}% (Below threshold)

💰 *Est. Cost:* ${order_data.get('estimated_cost', 0):,.2f}

📝 *AI Reasoning:*
_{order_data.get('reasoning', 'No reasoning')[:150]}_

⚠️ This order requires manual approval due to low AI confidence.

🆔 Order: `{order_id}`
"""
        
        keyboard = {
            "inline_keyboard": [[
                {"text": "✅ Approve", "callback_data": f"approve_{order_id}"},
                {"text": "❌ Reject", "callback_data": f"reject_{order_id}"}
            ], [
                {"text": "📊 View Dashboard", "url": f"{DASHBOARD_URL}/dashboard"}
            ]]
        }
        
        # Broadcast to all registered users
        success_count = 0
        recipients = list(registered_chats.keys()) if registered_chats else [TELEGRAM_CHAT_ID]
        
        for chat_id in recipients:
            if await _send_message(chat_id, message, keyboard):
                success_count += 1
        
        logger.info(f"Low-confidence alert sent to {success_count}/{len(recipients)} users")
        return success_count > 0
            
    except Exception as e:
        logger.error("Failed to send Telegram alert", error=str(e))
        return False


async def _send_message(chat_id: str, text: str, reply_markup: Dict = None) -> bool:
    """Helper to send Telegram message."""
    if not TELEGRAM_API_BASE:
        return False
        
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    
    if reply_markup:
        payload["reply_markup"] = reply_markup
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{TELEGRAM_API_BASE}/sendMessage", json=payload, timeout=10)
        return response.status_code == 200


# ==================== Inbound Webhook Handler ====================

async def handle_telegram_update(update: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process incoming Telegram updates (messages, callbacks).
    
    Returns response message to send back.
    """
    try:
        # Handle callback queries (inline button clicks)
        if "callback_query" in update:
            return await _handle_callback(update["callback_query"])
        
        # Handle text messages
        message = update.get("message", {})
        text = message.get("text", "")
        chat_id = str(message.get("chat", {}).get("id", ""))
        user_name = message.get("from", {}).get("first_name", "User")
        
        if not text or not chat_id:
            return {"status": "ignored", "reason": "no text or chat_id"}
        
        # Route commands
        if text.startswith("/start"):
            return await _handle_start(chat_id, user_name)
        elif text.startswith("/status"):
            return await _handle_status(chat_id)
        elif text.startswith("/approve"):
            order_id = text.replace("/approve", "").strip()
            return await _handle_approve(chat_id, order_id)
        elif text.startswith("/reject"):
            order_id = text.replace("/reject", "").strip()
            return await _handle_reject(chat_id, order_id)
        elif text.startswith("/help"):
            return await _handle_help(chat_id)
        else:
            return await _handle_unknown(chat_id, text)
            
    except Exception as e:
        logger.error("Error handling Telegram update", error=str(e))
        return {"status": "error", "error": str(e)}


async def _handle_start(chat_id: str, user_name: str) -> Dict[str, Any]:
    """Handle /start command - register user."""
    registered_chats[chat_id] = {
        "registered_at": datetime.now().isoformat(),
        "user_name": user_name
    }
    
    message = f"""
👋 *Welcome, {user_name}!*

You're now registered for Inventory Agent notifications!

✅ *Auto-Registered* - No configuration needed
🔔 *Your Chat ID:* `{chat_id}`

*Available Commands:*
• /status - View current inventory status
• /approve `<order_id>` - Approve pending order
• /reject `<order_id>` - Reject pending order
• /help - Show this help

📊 *Dashboard:* {DASHBOARD_URL}/dashboard

🎉 You'll now receive all inventory alerts automatically!
"""
    
    await _send_message(chat_id, message)
    logger.info(f"New user registered: {user_name} (chat_id: {chat_id})")
    return {"status": "registered", "chat_id": chat_id}


async def _handle_status(chat_id: str) -> Dict[str, Any]:
    """Handle /status command - show pending orders."""
    message = f"""
📊 *Inventory Agent Status*

🟢 Service: Running
📦 Mode: Mock Data
🔗 Dashboard: {DASHBOARD_URL}/dashboard

To check pending orders, visit the dashboard or use:
`POST /orders?status=pending`
"""
    
    await _send_message(chat_id, message)
    return {"status": "status_sent"}


async def _handle_approve(chat_id: str, order_id: str) -> Dict[str, Any]:
    """Handle /approve command."""
    if not order_id:
        await _send_message(chat_id, "❌ Usage: `/approve <order_id>`")
        return {"status": "error", "reason": "no order_id"}
    
    # In production, this would call the database to update order status
    message = f"""
✅ *Order Approved*

Order `{order_id}` has been marked for approval.

⚠️ *Note:* Full approval requires API call:
```
PATCH /orders/{order_id}/status
{{"status": "executed"}}
```
"""
    
    await _send_message(chat_id, message)
    return {"status": "approved", "order_id": order_id}


async def _handle_reject(chat_id: str, order_id: str) -> Dict[str, Any]:
    """Handle /reject command."""
    if not order_id:
        await _send_message(chat_id, "❌ Usage: `/reject <order_id>`")
        return {"status": "error", "reason": "no order_id"}
    
    message = f"""
❌ *Order Rejected*

Order `{order_id}` has been marked for rejection.

⚠️ *Note:* Full rejection requires API call:
```
PATCH /orders/{order_id}/status
{{"status": "rejected"}}
```
"""
    
    await _send_message(chat_id, message)
    return {"status": "rejected", "order_id": order_id}


async def _handle_callback(callback: Dict[str, Any]) -> Dict[str, Any]:
    """Handle inline button callbacks."""
    data = callback.get("data", "")
    chat_id = str(callback.get("message", {}).get("chat", {}).get("id", ""))
    
    if data.startswith("approve_"):
        order_id = data.replace("approve_", "")
        await _send_message(chat_id, f"✅ Order `{order_id}` approved via button!")
        return {"status": "approved", "order_id": order_id}
    elif data.startswith("reject_"):
        order_id = data.replace("reject_", "")
        await _send_message(chat_id, f"❌ Order `{order_id}` rejected via button!")
        return {"status": "rejected", "order_id": order_id}
    
    return {"status": "unknown_callback"}


async def _handle_help(chat_id: str) -> Dict[str, Any]:
    """Handle /help command."""
    message = f"""
🤖 *Inventory Agent Bot*

*Commands:*
• /start - Register for notifications
• /status - View service status
• /approve `<id>` - Approve order
• /reject `<id>` - Reject order
• /help - Show this help

*Notifications:*
• 🟢 High confidence orders auto-execute
• 🟡 Medium confidence require review
• 🔴 Low confidence need approval

*Dashboard:*
{DASHBOARD_URL}/dashboard
"""
    
    await _send_message(chat_id, message)
    return {"status": "help_sent"}


async def _handle_unknown(chat_id: str, text: str) -> Dict[str, Any]:
    """Handle unknown messages."""
    await _send_message(chat_id, f"❓ Unknown command. Type /help for available commands.")
    return {"status": "unknown_command"}


# ==================== Setup Info ====================

def get_telegram_setup_info() -> Dict[str, Any]:
    """Return setup information for Telegram integration."""
    bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "InventoryAgentBot")
    
    return {
        "configured": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        "bot_link": f"https://t.me/{bot_username}",
        "qr_url": f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=https://t.me/{bot_username}",
        "webhook_url": "/telegram/webhook",
        "registered_chats": len(registered_chats),
        "commands": ["/start", "/status", "/approve", "/reject", "/help"],
        "setup_instructions": [
            f"1. Open Telegram and search for @{bot_username}",
            "2. Click 'Start' to activate the bot",
            "3. Send /start to get your Chat ID",
            "4. Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env",
            "5. Restart the server to enable notifications"
        ]
    }

