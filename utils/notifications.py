"""Notification utilities for Slack, webhooks, and email."""

import os
import httpx
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


async def send_slack_notification(
    order: Dict[str, Any],
    webhook_url: Optional[str] = None,
    channel: Optional[str] = None
) -> bool:
    """
    Send order notification to Slack.
    
    Args:
        order: Order details dictionary
        webhook_url: Slack webhook URL (uses env var if not provided)
        channel: Optional channel override
        
    Returns:
        bool: True if sent successfully
    """
    webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
    
    if not webhook_url:
        logger.warning("No Slack webhook URL configured, skipping notification")
        return False
    
    # Determine emoji and color based on confidence
    confidence = order.get("confidence", 0)
    if confidence >= 0.8:
        emoji = "✅"
        color = "#36a64f"  # Green
        status_text = "Auto-Executed"
    elif confidence >= 0.6:
        emoji = "🟡"
        color = "#ffcc00"  # Yellow
        status_text = "Auto-Executed (Review Recommended)"
    else:
        emoji = "⚠️"
        color = "#ff6600"  # Orange
        status_text = "Needs Human Review"
    
    # Build Slack message
    message = {
        "channel": channel,
        "username": "Inventory Agent",
        "icon_emoji": ":robot_face:",
        "attachments": [
            {
                "color": color,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"{emoji} Inventory Order Generated",
                            "emoji": True
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Product:*\n{order.get('product_id', 'Unknown')}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Action:*\n{order.get('action', 'Unknown').upper()}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Quantity:*\n{order.get('quantity', 0):,} units"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Confidence:*\n{confidence:.0%}"
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Status:* {status_text}"
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"📋 Order ID: `{order.get('order_id', 'N/A')}` | 🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                            }
                        ]
                    }
                ]
            }
        ]
    }
    
    # Add reasoning if available
    if order.get("reasoning"):
        message["attachments"][0]["blocks"].insert(3, {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*AI Reasoning:*\n_{order['reasoning'][:500]}..._" if len(order.get('reasoning', '')) > 500 else f"*AI Reasoning:*\n_{order['reasoning']}_"
            }
        })
    
    # Add action buttons for low confidence orders
    if confidence < 0.6:
        message["attachments"][0]["blocks"].append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Approve"},
                    "style": "primary",
                    "value": order.get("order_id", "")
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Reject"},
                    "style": "danger",
                    "value": order.get("order_id", "")
                }
            ]
        })
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json=message,
                timeout=10.0
            )
            
            if response.status_code == 200:
                logger.info(f"Slack notification sent for order {order.get('order_id')}")
                return True
            else:
                logger.error(f"Slack notification failed: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {str(e)}")
        return False


async def send_webhook_callback(
    callback_url: str,
    order: Dict[str, Any],
    include_metadata: bool = True
) -> bool:
    """
    Send order result to external webhook callback URL.
    
    Args:
        callback_url: URL to POST results to
        order: Order details dictionary
        include_metadata: Whether to include processing metadata
        
    Returns:
        bool: True if sent successfully
    """
    if not callback_url:
        return False
    
    payload = {
        "event": "order.generated",
        "timestamp": datetime.now().isoformat(),
        "data": order
    }
    
    if include_metadata:
        payload["metadata"] = {
            "service": "inventory-restocking-agent",
            "version": "1.0.0",
            "llm_provider": order.get("llm_provider", "unknown")
        }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                callback_url,
                json=payload,
                timeout=30.0,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code in [200, 201, 202, 204]:
                logger.info(f"Webhook callback sent to {callback_url}")
                return True
            else:
                logger.warning(f"Webhook callback returned {response.status_code}")
                return False
                
    except Exception as e:
        logger.error(f"Webhook callback failed: {str(e)}")
        return False


async def send_email_notification(
    order: Dict[str, Any],
    recipient: Optional[str] = None
) -> bool:
    """
    Send order notification via email (stub for future implementation).
    
    Args:
        order: Order details dictionary
        recipient: Email recipient (uses env var if not provided)
        
    Returns:
        bool: True if sent successfully
    """
    recipient = recipient or os.getenv("NOTIFICATION_EMAIL")
    
    if not recipient:
        logger.debug("No email recipient configured, skipping email notification")
        return False
    
    # TODO: Implement email sending (SendGrid, SES, SMTP)
    logger.info(f"Email notification would be sent to {recipient} for order {order.get('order_id')}")
    return False
