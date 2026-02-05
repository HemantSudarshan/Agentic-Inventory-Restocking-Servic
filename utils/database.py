"""Database utilities for order persistence and audit logging."""

import os
import aiosqlite
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "inventory.db"


async def init_database():
    """Initialize database tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Orders table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE NOT NULL,
                product_id TEXT NOT NULL,
                action TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                confidence REAL,
                status TEXT DEFAULT 'pending',
                llm_provider TEXT,
                reasoning TEXT,
                safety_stock REAL,
                reorder_point REAL,
                current_stock REAL,
                shortage REAL,
                estimated_cost REAL,
                supplier_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                executed_at TIMESTAMP,
                approved_by TEXT,
                approved_at TIMESTAMP
            )
        """)
        
        # Audit log table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                order_id TEXT,
                product_id TEXT,
                details TEXT,
                user_ip TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Products cache table (for analytics)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT UNIQUE NOT NULL,
                last_stock_level REAL,
                last_reorder_point REAL,
                last_safety_stock REAL,
                total_orders INTEGER DEFAULT 0,
                total_quantity_ordered INTEGER DEFAULT 0,
                last_order_date TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.commit()
        logger.info("Database initialized successfully")


async def save_order(order: Dict[str, Any]) -> bool:
    """
    Save order to database.
    
    Args:
        order: Order dictionary with all details
        
    Returns:
        bool: True if saved successfully
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO orders (
                    order_id, product_id, action, quantity, confidence,
                    status, llm_provider, reasoning, safety_stock,
                    reorder_point, current_stock, shortage, estimated_cost,
                    executed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order.get("order_id"),
                order.get("product_id"),
                order.get("action"),
                order.get("quantity"),
                order.get("confidence"),
                order.get("status", "pending"),
                order.get("llm_provider"),
                order.get("reasoning"),
                order.get("safety_stock"),
                order.get("reorder_point"),
                order.get("current_stock"),
                order.get("shortage"),
                order.get("estimated_cost"),
                datetime.now().isoformat() if order.get("status") == "executed" else None
            ))
            
            # Update product cache
            await db.execute("""
                INSERT INTO products (product_id, last_stock_level, last_reorder_point,
                    last_safety_stock, total_orders, total_quantity_ordered, last_order_date)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(product_id) DO UPDATE SET
                    last_stock_level = excluded.last_stock_level,
                    last_reorder_point = excluded.last_reorder_point,
                    last_safety_stock = excluded.last_safety_stock,
                    total_orders = total_orders + 1,
                    total_quantity_ordered = total_quantity_ordered + excluded.total_quantity_ordered,
                    last_order_date = excluded.last_order_date,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                order.get("product_id"),
                order.get("current_stock"),
                order.get("reorder_point"),
                order.get("safety_stock"),
                order.get("quantity", 0),
                datetime.now().isoformat()
            ))
            
            await db.commit()
            logger.info(f"Order {order.get('order_id')} saved to database")
            return True
            
    except Exception as e:
        logger.error(f"Failed to save order: {str(e)}")
        return False


async def get_orders(
    limit: int = 50,
    status: Optional[str] = None,
    product_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get orders from database with optional filtering.
    
    Args:
        limit: Maximum number of orders to return
        status: Filter by status (pending, executed, rejected)
        product_id: Filter by product ID
        
    Returns:
        List of order dictionaries
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            
            query = "SELECT * FROM orders WHERE 1=1"
            params = []
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            if product_id:
                query += " AND product_id = ?"
                params.append(product_id)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
                
    except Exception as e:
        logger.error(f"Failed to get orders: {str(e)}")
        return []


async def get_order_by_id(order_id: str) -> Optional[Dict[str, Any]]:
    """Get a single order by ID."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            
            async with db.execute(
                "SELECT * FROM orders WHERE order_id = ?", (order_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
                
    except Exception as e:
        logger.error(f"Failed to get order {order_id}: {str(e)}")
        return None


async def update_order_status(
    order_id: str,
    status: str,
    approved_by: Optional[str] = None
) -> bool:
    """Update order status (for approval workflow)."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            if status in ["approved", "rejected"]:
                await db.execute("""
                    UPDATE orders 
                    SET status = ?, approved_by = ?, approved_at = ?
                    WHERE order_id = ?
                """, (status, approved_by, datetime.now().isoformat(), order_id))
            else:
                await db.execute(
                    "UPDATE orders SET status = ? WHERE order_id = ?",
                    (status, order_id)
                )
            
            await db.commit()
            return True
            
    except Exception as e:
        logger.error(f"Failed to update order status: {str(e)}")
        return False


async def log_audit_event(
    event_type: str,
    order_id: Optional[str] = None,
    product_id: Optional[str] = None,
    details: Optional[str] = None,
    user_ip: Optional[str] = None
):
    """Log an audit event."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO audit_log (event_type, order_id, product_id, details, user_ip)
                VALUES (?, ?, ?, ?, ?)
            """, (event_type, order_id, product_id, details, user_ip))
            await db.commit()
            
    except Exception as e:
        logger.error(f"Failed to log audit event: {str(e)}")


async def get_dashboard_stats() -> Dict[str, Any]:
    """Get statistics for dashboard display."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Total orders
            async with db.execute("SELECT COUNT(*) FROM orders") as cursor:
                total_orders = (await cursor.fetchone())[0]
            
            # Orders by status
            async with db.execute("""
                SELECT status, COUNT(*) as count FROM orders GROUP BY status
            """) as cursor:
                status_counts = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Recent orders
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM orders ORDER BY created_at DESC LIMIT 10
            """) as cursor:
                recent_orders = [dict(row) for row in await cursor.fetchall()]
            
            # Avg confidence
            async with db.execute("SELECT AVG(confidence) FROM orders") as cursor:
                avg_confidence = (await cursor.fetchone())[0] or 0
            
            # Products summary
            async with db.execute("""
                SELECT product_id, total_orders, total_quantity_ordered 
                FROM products ORDER BY total_orders DESC LIMIT 10
            """) as cursor:
                top_products = [dict(row) for row in await cursor.fetchall()]
            
            return {
                "total_orders": total_orders,
                "status_breakdown": status_counts,
                "recent_orders": recent_orders,
                "average_confidence": round(avg_confidence, 3),
                "top_products": top_products
            }
            
    except Exception as e:
        logger.error(f"Failed to get dashboard stats: {str(e)}")
        return {
            "total_orders": 0,
            "status_breakdown": {},
            "recent_orders": [],
            "average_confidence": 0,
            "top_products": []
        }
