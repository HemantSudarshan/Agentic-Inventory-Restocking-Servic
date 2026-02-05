"""Main FastAPI application with LangGraph workflow orchestration."""

import os
import asyncio
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from dotenv import load_dotenv
from typing import Dict, Any

from models.schemas import (
    InventoryRequest, 
    InventoryResponse, 
    DebugResponse,
    ErrorResponse
)
from agents.data_loader import load_data
from agents.safety_calculator import process_inventory_data
from agents.reasoning_agent import ReasoningAgent
from agents.action_agent import generate_action
from utils.logging import setup_logging, get_logger
from utils import metrics

# Load environment variables
load_dotenv()

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Agentic Inventory Restocking Service",
    description="AI-powered inventory management with automatic restocking decisions",
    version="1.0.0"
)

# Initialize reasoning agent (singleton)
reasoning_agent = ReasoningAgent()

# Security: API Key Header
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    """Validate API Key for endpoint access."""
    expected_key = os.getenv("API_KEY")
    if not expected_key:
        # If no API_KEY set in env, allow access (dev mode)
        logger.warning("No API_KEY set in environment - running in INSECURE mode")
        return None
    if api_key_header != expected_key:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key_header


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Agentic Inventory Restocking Service",
        "status": "running",
        "version": "1.0.0"
    }


@app.post("/inventory-trigger", response_model=InventoryResponse)
async def inventory_trigger(request: InventoryRequest, api_key: str = Depends(get_api_key)):
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
    """
    try:
        # Track request
        metrics.inventory_trigger_total.labels(
            mode=request.mode, 
            status="started"
        ).inc()
        
        logger.info("Processing inventory trigger", 
                   product_id=request.product_id, 
                   mode=request.mode)
        
        # Step 1: Load data (run sync operation in thread pool to avoid blocking)
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, load_data, request)
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
        confidence_threshold = 0.6
        if recommendation["confidence"] >= confidence_threshold:
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
        
        # Track success
        metrics.inventory_trigger_total.labels(
            mode=request.mode,
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
            mode=request.mode,
            status="error"
        ).inc()
        
        logger.error("Inventory trigger failed",
                    error=str(e),
                    product_id=request.product_id)
        
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code="PROCESSING_ERROR",
                message=str(e),
                details={"product_id": request.product_id}
            ).model_dump()
        )


@app.get("/debug/{product_id}", response_model=DebugResponse)
async def debug_product(product_id: str, mode: str = "mock", api_key: str = Depends(get_api_key)):
    """
    Debug endpoint to view calculations without triggering orders.
    
    Shows safety stock calculations and current status.
    """
    try:
        # Load data (run in thread pool)
        request = InventoryRequest(product_id=product_id, mode=mode)
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, load_data, request)
        
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
