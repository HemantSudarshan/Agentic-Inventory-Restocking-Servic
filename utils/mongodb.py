"""
MongoDB Atlas Integration Module

Provides async MongoDB connection and database operations for production deployment.
Falls back to SQLite if MONGODB_URI is not configured.
"""
import os
from typing import Optional, Dict, List, Any
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import structlog

logger = structlog.get_logger()

# MongoDB connection globals
MONGODB_URI = os.getenv("MONGODB_URI")
mongo_client: Optional[AsyncIOMotorClient] = None
mongo_db = None


async def connect_mongodb():
    """
    Connect to MongoDB Atlas on application startup.
    
    Falls back to SQLite if MONGODB_URI environment variable is not set.
    """
    global mongo_client, mongo_db
    
    if MONGODB_URI:
        try:
            mongo_client = AsyncIOMotorClient(
                MONGODB_URI,
                serverSelectionTimeoutMS=5000  # 5 second timeout
            )
            # Verify connection
            await mongo_client.admin.command('ping')
            mongo_db = mongo_client.inventory_db
            logger.info("✅ Connected to MongoDB Atlas", db="MongoDB")
        except Exception as e:
            logger.error("❌ Failed to connect to MongoDB", error=str(e))
            logger.warning("⚠️ Falling back to SQLite")
            mongo_client = None
            mongo_db = None
    else:
        logger.info("ℹ️ No MONGODB_URI configured - using SQLite", db="SQLite")


async def close_mongodb():
    """Close MongoDB connection on application shutdown."""
    global mongo_client
    
    if mongo_client:
        mongo_client.close()
        logger.info("✅ Closed MongoDB connection")


def get_db():
    """
    Get MongoDB database instance.
    
    Returns:
        MongoDB database object, or None if not connected (use SQLite fallback)
    """
    return mongo_db


async def save_order(order_data: Dict[str, Any]) -> bool:
    """
    Save order to MongoDB or SQLite fallback.
    
    Args:
        order_data: Order dictionary containing order details
        
    Returns:
        True if saved successfully, False otherwise
    """
    db = get_db()
    
    if db is not None:
        # Use MongoDB
        try:
            order_doc = {
                **order_data,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            result = await db.orders.insert_one(order_doc)
            logger.info("💾 Order saved to MongoDB", 
                       order_id=order_data.get("order_id"),
                       mongo_id=str(result.inserted_id))
            return True
        except Exception as e:
            logger.error("❌ Failed to save order to MongoDB", error=str(e))
            return False
    else:
        # SQLite fallback handled by existing code
        logger.debug("Using SQLite for order storage")
        return False  # Caller should handle SQLite


async def get_orders(
    status: Optional[str] = None,
    limit: int = 100,
    skip: int = 0
) -> List[Dict[str, Any]]:
    """
    Retrieve orders from MongoDB.
    
    Args:
        status: Filter by status (executed, pending_review, etc.)
        limit: Maximum number of orders to return
        skip: Number of orders to skip (pagination)
        
    Returns:
        List of order dictionaries
    """
    db = get_db()
    
    if db is not None:
        try:
            query = {}
            if status:
                query["status"] = status
            
            cursor = db.orders.find(query).sort("created_at", -1).skip(skip).limit(limit)
            orders = await cursor.to_list(length=limit)
            
            # Convert ObjectId to string for JSON serialization
            for order in orders:
                order["_id"] = str(order["_id"])
            
            logger.debug("📋 Retrieved orders from MongoDB", count=len(orders))
            return orders
        except Exception as e:
            logger.error("❌ Failed to retrieve orders from MongoDB", error=str(e))
            return []
    else:
        # SQLite fallback handled by existing code
        return []


async def get_order_by_id(order_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific order by ID from MongoDB.
    
    Args:
        order_id: The order ID to retrieve
        
    Returns:
        Order dictionary or None if not found
    """
    db = get_db()
    
    if db is not None:
        try:
            order = await db.orders.find_one({"order_id": order_id})
            if order:
                order["_id"] = str(order["_id"])
            return order
        except Exception as e:
            logger.error("❌ Failed to get order from MongoDB", 
                        order_id=order_id, error=str(e))
            return None
    else:
        return None


async def update_order_status(order_id: str, new_status: str) -> bool:
    """
    Update order status in MongoDB.
    
    Args:
        order_id: The order ID to update
        new_status: New status value
        
    Returns:
        True if updated successfully, False otherwise
    """
    db = get_db()
    
    if db is not None:
        try:
            result = await db.orders.update_one(
                {"order_id": order_id},
                {
                    "$set": {
                        "status": new_status,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info("✅ Order status updated", 
                           order_id=order_id, new_status=new_status)
                return True
            else:
                logger.warning("⚠️ Order not found for update", order_id=order_id)
                return False
        except Exception as e:
            logger.error("❌ Failed to update order status", 
                        order_id=order_id, error=str(e))
            return False
    else:
        return False
