"""Main FastAPI application with LangGraph workflow orchestration.

Phase 2 Enhancements:
- Rate limiting
- Slack notifications
- Batch processing
- Database persistence
- Dashboard UI
- Webhook callbacks
"""

import os
import asyncio
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Security, Depends, Request
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import PlainTextResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from dotenv import load_dotenv
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from models.schemas import (
    InventoryRequest, 
    InventoryResponse, 
    DebugResponse,
    ErrorResponse,
    BatchInventoryRequest,
    BatchInventoryResponse,
    OrderListResponse
)
from agents.data_loader import load_data
from agents.safety_calculator import process_inventory_data
from agents.reasoning_agent import ReasoningAgent
from agents.action_agent import generate_action
from utils.logging import setup_logging, get_logger
from utils import metrics
from utils.rate_limiter import limiter, rate_limit_exceeded_handler, RATE_LIMITS
from utils.notifications import send_slack_notification, send_webhook_callback
from utils.database import (
    init_database, 
    save_order, 
    get_orders, 
    get_order_by_id,
    update_order_status,
    log_audit_event,
    get_dashboard_stats
)

# Load environment variables
load_dotenv()

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events."""
    # Startup
    logger.info("Initializing database...")
    await init_database()
    logger.info("Application startup complete")
    yield
    # Shutdown
    logger.info("Application shutdown")


# Initialize FastAPI app
app = FastAPI(
    title="Agentic Inventory Restocking Service",
    description="AI-powered inventory management with automatic restocking decisions",
    version="2.0.0",
    lifespan=lifespan
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Configurable business logic thresholds
CONFIDENCE_THRESHOLD = float(os.getenv("AUTO_EXECUTE_THRESHOLD", "0.6"))
logger.info(f"Auto-execute confidence threshold: {CONFIDENCE_THRESHOLD}")

# Mount static files for dashboard
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize reasoning agent (singleton)
reasoning_agent = ReasoningAgent()

# Security: API Key Header
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def get_api_key(api_key_header: str = Security(api_key_header)):
    """
    Validate API Key for endpoint access.
    
    SECURITY: Fails closed by default. Set DEV_MODE=true to disable auth in development.
    """
    expected_key = os.getenv("API_KEY")
    dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"
    
    if not expected_key:
        if dev_mode:
            # Explicitly enabled dev mode - allow access with warning
            logger.warning("⚠️  DEV_MODE enabled - API security DISABLED")
            return None
        else:
            # Production default: fail closed
            logger.error("Server misconfigured: API_KEY not set and DEV_MODE not enabled")
            raise HTTPException(
                status_code=500,
                detail="Server configuration error: Authentication not configured"
            )
    
    if api_key_header != expected_key:
        logger.warning(f"Invalid API key attempt")
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    
    return api_key_header


def get_client_ip(request: Request) -> str:
    """Get client IP address from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ============================================================
# Core Endpoints
# ============================================================

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Agentic Inventory Restocking Service",
        "status": "running",
        "version": "2.0.0"
    }


@app.get("/dashboard")
async def dashboard():
    """Serve the dashboard UI."""
    return FileResponse("static/dashboard.html")


@app.post("/inventory-trigger", response_model=InventoryResponse)
@limiter.limit(RATE_LIMITS["inventory_trigger"])
async def inventory_trigger(
    request: Request,
    inventory_request: InventoryRequest, 
    api_key: str = Depends(get_api_key)
):
    """
    Main endpoint to trigger inventory analysis and restocking decisions.
    
    Supports two modes:
    - mock: Uses bundled sample data (for testing/demos)
    - input: Accepts full data in request body (for production)
    
    Workflow:
    1. Load data (mock or input mode)
    2. Calculate safety stock and reorder point
    3. Detect if restock needed (current_stock < ROP)
    4. AI analyzes and recommends action
    5. Generate purchase order or transfer
    6. Route based on confidence (auto-execute or review)
    7. Save to database & send notifications
    """
    try:
        # Track request
        metrics.inventory_trigger_total.labels(
            mode=inventory_request.mode, 
            status="started"
        ).inc()
        
        client_ip = get_client_ip(request)
        
        logger.info("Processing inventory trigger", 
                   product_id=inventory_request.product_id, 
                   mode=inventory_request.mode,
                   client_ip=client_ip)
        
        # Log audit event
        await log_audit_event(
            event_type="inventory_trigger",
            product_id=inventory_request.product_id,
            details=f"mode={inventory_request.mode}",
            user_ip=client_ip
        )
        
        # Step 1: Load data (run sync operation in thread pool to avoid blocking)
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, load_data, inventory_request)
        logger.info("Data loaded", product_id=data["product_id"])
        
        # Step 2: Calculate safety parameters
        avg_demand, std_dev, safety_stock, reorder_point = process_inventory_data(
            demand_history=data["demand_history"],
            lead_time=data["lead_time_days"],
            service_level=data["service_level"]
        )
        
        # Update metrics
        metrics.current_safety_stock.labels(product_id=data["product_id"]).set(safety_stock)
        metrics.current_reorder_point.labels(product_id=data["product_id"]).set(reorder_point)
        
        logger.info("Safety calculations complete",
                   safety_stock=safety_stock,
                   reorder_point=reorder_point)
        
        # Step 3: Check if restock needed
        current_stock = data["current_stock"]
        shortage = reorder_point - current_stock
        
        if current_stock >= reorder_point:
            # Stock is sufficient, no action needed
            return InventoryResponse(
                status="executed",
                safety_stock=safety_stock,
                reorder_point=reorder_point,
                current_stock=current_stock,
                shortage=shortage,
                recommended_action="none",
                recommended_quantity=0,
                confidence_score=1.0,
                order=None,
                reasoning=f"Stock level ({current_stock}) is above reorder point ({reorder_point:.0f}). No action needed."
            )
        
        # Track shortage event
        metrics.inventory_shortage_total.labels(product_id=data["product_id"]).inc()
        
        logger.info("Restock needed",
                   current_stock=current_stock,
                   shortage=shortage)
        
        # Step 4: AI reasoning
        context = {
            "product_id": data["product_id"],
            "current_stock": current_stock,
            "safety_stock": safety_stock,
            "reorder_point": reorder_point,
            "shortage": shortage,
            "avg_demand": avg_demand,
            "lead_time_days": data["lead_time_days"],
            "demand_history": data["demand_history"]
        }
        
        recommendation = await reasoning_agent.analyze(context)
        llm_provider = recommendation.pop("_llm_provider", "unknown")
        
        # Track LLM call
        metrics.llm_calls_total.labels(provider=llm_provider, status="success").inc()
        
        logger.info("AI recommendation received",
                   action=recommendation["action"],
                   quantity=recommendation["quantity"],
                   confidence=recommendation["confidence"])
        
        # Step 5: Generate action
        order = generate_action(data["product_id"], recommendation)
        
        # Step 6: Route based on confidence
        if recommendation["confidence"] >= CONFIDENCE_THRESHOLD:
            status = "executed"
            metrics.orders_generated_total.labels(
                type=order.type,
                execution_status="auto_executed"
            ).inc()
        else:
            status = "pending_review"
            metrics.orders_generated_total.labels(
                type=order.type,
                execution_status="pending_review"
            ).inc()
        
        # Step 7: Save to database
        order_data = {
            "order_id": order.id,
            "product_id": data["product_id"],
            "action": recommendation["action"],
            "quantity": recommendation["quantity"],
            "confidence": recommendation["confidence"],
            "status": status,
            "llm_provider": llm_provider,
            "reasoning": recommendation["reasoning"],
            "safety_stock": safety_stock,
            "reorder_point": reorder_point,
            "current_stock": current_stock,
            "shortage": shortage,
            "estimated_cost": order.cost
        }
        await save_order(order_data)
        
        # Step 8: Send notifications
        if recommendation["confidence"] < CONFIDENCE_THRESHOLD:
            # Send Slack notification for low-confidence orders
            await send_slack_notification(order_data)
        
        # Send webhook callback if provided
        if inventory_request.callback_url:
            asyncio.create_task(send_webhook_callback(
                inventory_request.callback_url,
                order_data
            ))
        
        # Track success
        metrics.inventory_trigger_total.labels(
            mode=inventory_request.mode,
            status="success"
        ).inc()
        
        return InventoryResponse(
            status=status,
            safety_stock=safety_stock,
            reorder_point=reorder_point,
            current_stock=current_stock,
            shortage=shortage,
            recommended_action=recommendation["action"],
            recommended_quantity=recommendation["quantity"],
            confidence_score=recommendation["confidence"],
            order=order if status == "executed" else None,
            reasoning=recommendation["reasoning"]
        )
        
    except Exception as e:
        # Track failure
        metrics.inventory_trigger_total.labels(
            mode=inventory_request.mode,
            status="error"
        ).inc()
        
        logger.error("Inventory trigger failed",
                    error=str(e),
                    product_id=inventory_request.product_id)
        
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code="PROCESSING_ERROR",
                message=str(e),
                details={"product_id": inventory_request.product_id}
            ).model_dump()
        )


# ============================================================
# Batch Processing
# ============================================================

@app.post("/inventory-trigger-batch", response_model=BatchInventoryResponse)
@limiter.limit(RATE_LIMITS["batch"])
async def inventory_trigger_batch(
    request: Request,
    batch_request: BatchInventoryRequest,
    api_key: str = Depends(get_api_key)
):
    """
    Batch processing endpoint - analyze multiple products at once.
    
    Processes products in parallel for efficiency.
    Returns results for all products, including any errors.
    """
    try:
        logger.info(f"Batch processing {len(batch_request.products)} products")
        
        async def process_single(product_id: str) -> Dict[str, Any]:
            """Process a single product and return result."""
            try:
                req = InventoryRequest(
                    product_id=product_id,
                    mode=batch_request.mode
                )
                result = await inventory_trigger(request, req, api_key)
                return {
                    "product_id": product_id,
                    "success": True,
                    "result": result.model_dump()
                }
            except Exception as e:
                return {
                    "product_id": product_id,
                    "success": False,
                    "error": str(e)
                }
        
        # Process all products in parallel
        tasks = [process_single(pid) for pid in batch_request.products]
        results = await asyncio.gather(*tasks)
        
        successful = sum(1 for r in results if r["success"])
        
        return BatchInventoryResponse(
            total=len(batch_request.products),
            successful=successful,
            failed=len(batch_request.products) - successful,
            results=results
        )
        
    except Exception as e:
        logger.error(f"Batch processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Database & Orders Endpoints
# ============================================================

@app.get("/orders", response_model=OrderListResponse)
@limiter.limit(RATE_LIMITS["orders"])
async def list_orders(
    request: Request,
    limit: int = 50,
    status: Optional[str] = None,
    product_id: Optional[str] = None,
    api_key: str = Depends(get_api_key)
):
    """Get list of orders with optional filtering."""
    orders = await get_orders(limit=limit, status=status, product_id=product_id)
    return OrderListResponse(
        orders=orders,
        total=len(orders)
    )


@app.get("/orders/{order_id}")
@limiter.limit(RATE_LIMITS["orders"])
async def get_order(
    request: Request,
    order_id: str,
    api_key: str = Depends(get_api_key)
):
    """Get a single order by ID."""
    order = await get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.post("/orders/{order_id}/approve")
async def approve_order(
    request: Request,
    order_id: str,
    api_key: str = Depends(get_api_key)
):
    """Approve a pending order."""
    client_ip = get_client_ip(request)
    success = await update_order_status(order_id, "approved", approved_by=client_ip)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to approve order")
    
    await log_audit_event(
        event_type="order_approved",
        order_id=order_id,
        user_ip=client_ip
    )
    
    return {"status": "approved", "order_id": order_id}


@app.post("/orders/{order_id}/reject")
async def reject_order(
    request: Request,
    order_id: str,
    api_key: str = Depends(get_api_key)
):
    """Reject a pending order."""
    client_ip = get_client_ip(request)
    success = await update_order_status(order_id, "rejected", approved_by=client_ip)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to reject order")
    
    await log_audit_event(
        event_type="order_rejected",
        order_id=order_id,
        user_ip=client_ip
    )
    
    return {"status": "rejected", "order_id": order_id}


# ============================================================
# Dashboard Stats
# ============================================================

@app.get("/dashboard/stats")
@limiter.limit(RATE_LIMITS["orders"])
async def dashboard_stats(
    request: Request,
    api_key: str = Depends(get_api_key)
):
    """Get dashboard statistics."""
    return await get_dashboard_stats()


# ============================================================
# Debug & Metrics
# ============================================================

@app.get("/debug/{product_id}", response_model=DebugResponse)
@limiter.limit(RATE_LIMITS["debug"])
async def debug_product(
    request: Request,
    product_id: str, 
    mode: str = "mock", 
    api_key: str = Depends(get_api_key)
):
    """
    Debug endpoint to view calculations without triggering orders.
    
    Shows safety stock calculations and current status.
    """
    try:
        # Load data (run in thread pool)
        inv_request = InventoryRequest(product_id=product_id, mode=mode)
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, load_data, inv_request)
        
        # Calculate safety parameters
        avg_demand, std_dev, safety_stock, reorder_point = process_inventory_data(
            demand_history=data["demand_history"],
            lead_time=data["lead_time_days"],
            service_level=data["service_level"]
        )
        
        current_stock = data["current_stock"]
        shortage = reorder_point - current_stock
        would_trigger = current_stock < reorder_point
        
        return DebugResponse(
            product_id=product_id,
            mode=mode,
            calculations={
                "avg_daily_demand": avg_demand,
                "std_dev": std_dev,
                "safety_stock": safety_stock,
                "reorder_point": reorder_point
            },
            current_status={
                "current_stock": current_stock,
                "shortage": shortage
            },
            would_trigger=would_trigger,
            trigger_reason=f"current_stock ({current_stock}) < reorder_point ({reorder_point:.0f})" if would_trigger else None
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": str(e)}
        )


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint."""
    return PlainTextResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
