"""Main FastAPI application with LangGraph workflow orchestration.

Phase 2 Enhancements:
- Rate limiting
- Slack notifications
- Batch processing
- Database persistence
- Dashboard UI
- Webhook callbacks

Phase 4 Enhancements:
- LangGraph StateGraph workflow (PS.md compliance)
- Dashboard session-based authentication
- Enhanced agent tracing
"""

import os
import asyncio
import secrets
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager
from hashlib import sha256

from fastapi import FastAPI, HTTPException, Security, Depends, Request, Cookie, Form
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import PlainTextResponse, HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from dotenv import load_dotenv
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import numpy as np
from scipy.stats import norm

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
from utils.telegram import send_telegram_notification, send_telegram_low_confidence_alert
from utils.database import (
    init_database, 
    save_order, 
    get_orders, 
    get_order_by_id,
    update_order_status,
    log_audit_event,
    get_dashboard_stats
)
from utils.mongodb import connect_mongodb, close_mongodb

# Load environment variables
load_dotenv()

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events."""
    # Startup
    logger.info("Initializing databases...")
    await init_database()  # SQLite fallback
    await connect_mongodb()  # MongoDB Atlas (if configured)
    logger.info("Application startup complete")
    yield
    # Shutdown
    logger.info("Application shutdown")
    await close_mongodb()


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
CONFIDENCE_THRESHOLD = float(os.getenv("AUTO_EXECUTE_THRESHOLD", "0.95"))
logger.info(f"Auto-execute confidence threshold: {CONFIDENCE_THRESHOLD}")

# Mount static files for dashboard
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize reasoning agent (singleton)
reasoning_agent = ReasoningAgent()

# Dashboard Authentication
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "admin123")
SESSION_TOKENS: Dict[str, str] = {}

# Import LangGraph workflow
try:
    from workflow.graph import run_inventory_analysis
    LANGGRAPH_AVAILABLE = True
    logger.info("LangGraph workflow initialized successfully")
except ImportError as e:
    LANGGRAPH_AVAILABLE = False
    logger.warning(f"LangGraph not available: {e}")

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
        "version": "2.0.0",
        "langgraph_enabled": LANGGRAPH_AVAILABLE
    }


@app.get("/config")
async def get_config(session_token: Optional[str] = Cookie(None)):
    """
    Serve configuration to dashboard (authenticated users only).
    Returns the API key needed for /inventory-trigger calls.
    """
    # Verify user is authenticated via session token
    if not session_token or session_token not in SESSION_TOKENS:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return {
        "api_key": os.getenv("API_KEY", "dev-inventory-agent-2026")
    }


# ============================================================
# Authentication Endpoints
# ============================================================

# Track which sessions have completed notification setup
SETUP_COMPLETED: Dict[str, bool] = {}


@app.get("/login")
async def login_page():
    """Serve the login page."""
    return FileResponse("static/login.html")


@app.post("/auth/login")
async def authenticate(
    password: str = Form(...),
):
    """
    Authenticate user and set session cookie.
    Default password: admin123 (set DASHBOARD_PASSWORD env var to change)
    Redirects to notification setup on first login.
    """
    if sha256(password.encode()).hexdigest() == sha256(DASHBOARD_PASSWORD.encode()).hexdigest():
        token = secrets.token_urlsafe(32)
        SESSION_TOKENS[token] = "authenticated"
        
        # Redirect to setup page for first-time login
        response = RedirectResponse(url="/setup-notifications", status_code=303)
        response.set_cookie("session", token, httponly=True)
        return response
    raise HTTPException(status_code=401, detail="Invalid password")


@app.get("/auth/logout")
async def logout():
    """Clear session and redirect to login."""
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session")
    return response


@app.get("/setup-notifications")
async def setup_notifications_page(session: str = Cookie(None)):
    """
    Serve the notification setup page.
    Shown after first login to configure Telegram/Slack notifications.
    """
    if not session or session not in SESSION_TOKENS:
        return RedirectResponse(url="/login")
    
    # If already completed setup, redirect to dashboard
    if SETUP_COMPLETED.get(session, False):
        return RedirectResponse(url="/dashboard")
    
    return FileResponse("static/setup-notifications.html")


@app.post("/setup-notifications/save")
async def save_notification_settings(
    request: Request,
    session: str = Cookie(None)
):
    """
    Save notification preferences and mark setup as complete.
    """
    if not session or session not in SESSION_TOKENS:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        data = await request.json()
        telegram_connected = data.get("telegram_connected", False)
        slack_webhook = data.get("slack_webhook", "")
        
        # Log the setup completion
        logger.info("Notification setup completed",
                   telegram=telegram_connected,
                   slack_configured=bool(slack_webhook))
        
        # Mark setup as complete for this session
        SETUP_COMPLETED[session] = True
        
        return {"status": "saved", "telegram": telegram_connected, "slack": bool(slack_webhook)}
    except Exception as e:
        logger.error(f"Failed to save notification settings: {e}")
        SETUP_COMPLETED[session] = True  # Still mark as complete
        return {"status": "skipped"}


@app.post("/setup-notifications/skip")
async def skip_notification_setup(session: str = Cookie(None)):
    """
    Skip notification setup and proceed to dashboard.
    """
    if not session or session not in SESSION_TOKENS:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    SETUP_COMPLETED[session] = True
    logger.info("Notification setup skipped")
    return {"status": "skipped"}


@app.get("/dashboard")
async def dashboard(session: str = Cookie(None)):
    """
    Serve the dashboard UI.
    Requires valid session cookie (obtained via /auth/login).
    """
    if not session or session not in SESSION_TOKENS:
        return RedirectResponse(url="/login")
    return FileResponse("static/dashboard.html")


@app.get("/verify-calculation/{product_id}")
async def verify_calculation(
    product_id: str,
    api_key: str = Depends(get_api_key)
):
    """
    Show step-by-step calculation verification for a product.
    Returns all intermediate values and formulas used.
    """
    try:
        # Load data using mock data loader directly
        from agents.data_loader import load_mock_data
        data = load_mock_data(product_id)
        
        # Get raw values (convert numpy arrays to lists for JSON serialization)
        demand = list(data["demand_history"]) if hasattr(data["demand_history"], 'tolist') else list(data["demand_history"])
        lead_time = int(data["lead_time_days"])
        service_level = float(data["service_level"])
        current_stock = int(data["current_stock"])
        unit_price = float(data.get("unit_price", 0))
        
        # Step-by-step calculations
        avg_demand = float(np.mean(demand))
        std_dev = float(np.std(demand, ddof=1))
        z_score = float(norm.ppf(service_level))
        
        # Safety Stock = Z × σ × √L
        safety_stock = z_score * std_dev * np.sqrt(lead_time)
        
        # ROP = (Avg Demand × Lead Time) + Safety Stock
        reorder_point = (avg_demand * lead_time) + safety_stock
        
        # Shortage
        shortage = max(0, reorder_point - current_stock)
        
        # Order quantity
        order_qty = round(shortage) if shortage > 0 else 0
        
        return {
            "product_id": product_id,
            "inputs": {
                "demand_history": demand,
                "lead_time_days": lead_time,
                "service_level": service_level,
                "current_stock": current_stock,
                "unit_price": unit_price
            },
            "step_by_step": {
                "step_1_avg_demand": {
                    "formula": "Average = Sum(demand) / Count",
                    "calculation": f"{sum(demand)} / {len(demand)}",
                    "result": float(round(avg_demand, 2)),
                    "unit": "units/day"
                },
                "step_2_std_dev": {
                    "formula": "σ = √(Σ(x - μ)² / (n-1))",
                    "result": float(round(std_dev, 2)),
                    "unit": "units"
                },
                "step_3_z_score": {
                    "formula": f"Z = NORM.INV({service_level})",
                    "description": f"For {service_level*100}% service level",
                    "result": float(round(z_score, 4))
                },
                "step_4_safety_stock": {
                    "formula": "SS = Z × σ × √L",
                    "calculation": f"{z_score:.3f} × {std_dev:.2f} × √{lead_time}",
                    "result": float(round(safety_stock, 2)),
                    "unit": "units"
                },
                "step_5_reorder_point": {
                    "formula": "ROP = (Avg Demand × Lead Time) + Safety Stock",
                    "calculation": f"({avg_demand:.2f} × {lead_time}) + {safety_stock:.2f}",
                    "result": float(round(reorder_point, 2)),
                    "unit": "units"
                },
                "step_6_shortage": {
                    "formula": "Shortage = ROP - Current Stock",
                    "calculation": f"{reorder_point:.2f} - {current_stock}",
                    "result": float(round(shortage, 2)),
                    "unit": "units"
                }
            },
            "decision": {
                "needs_restock": bool(current_stock < reorder_point),
                "order_quantity": int(order_qty),
                "estimated_cost": float(round(order_qty * unit_price, 2)),
                "reason": f"Current stock ({current_stock}) is {'below' if current_stock < reorder_point else 'above'} reorder point ({reorder_point:.0f})"
            },
            "formulas_reference": {
                "safety_stock": "SS = Z × σ × √L (Z=service level Z-score, σ=demand std dev, L=lead time)",
                "reorder_point": "ROP = (Avg Daily Demand × Lead Time) + Safety Stock",
                "eoq": "EOQ = √(2DS/H) (D=annual demand, S=order cost, H=holding cost)"
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Product not found: {str(e)}")
    except Exception as e:
        import traceback
        print(f"VERIFICATION ERROR: {str(e)}")
        traceback.print_exc()
        logger.error(f"Verification error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Calculation error: {str(e)}")


@app.get("/telegram/setup")
async def telegram_setup():
    """
    Get Telegram bot setup information with QR code.
    Scan to open the bot and start receiving notifications.
    """
    from utils.telegram import get_telegram_setup_info
    return get_telegram_setup_info()


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """
    Telegram webhook endpoint for receiving bot commands.
    
    Handles: /start, /status, /approve, /reject, /help
    Also handles inline keyboard callbacks.
    """
    from utils.telegram import handle_telegram_update
    
    try:
        update = await request.json()
        logger.info("Received Telegram update", update_id=update.get("update_id"))
        result = await handle_telegram_update(update)
        return {"ok": True, "result": result}
    except Exception as e:
        logger.error("Telegram webhook error", error=str(e))
        return {"ok": False, "error": str(e)}



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
            # Send Telegram alert for low-confidence orders requiring review
            asyncio.create_task(send_telegram_low_confidence_alert(order_data))
        else:
            # Send Telegram notification for executed orders
            asyncio.create_task(send_telegram_notification(order_data))
        
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
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
