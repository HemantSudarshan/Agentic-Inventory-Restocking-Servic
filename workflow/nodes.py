"""
LangGraph State and Node definitions for Inventory Agent workflow.

This module defines the state schema and individual node functions
that make up the agentic workflow per PS.md requirements.
"""

from typing import TypedDict, Optional, List, Dict, Any
from datetime import datetime


class InventoryState(TypedDict):
    """
    State maintained by LangGraph throughout the workflow.
    
    This matches the 3-step agentic flow from PS.md:
    - Step A (Data Retrieval): product_id → inventory_data
    - Step B (Reasoning): inventory_data + safety_metrics → recommendation
    - Step C (Action): recommendation → action
    """
    # Input
    product_id: str
    mode: str  # "mock" or "input"
    request_data: Optional[Dict[str, Any]]  # For input mode
    
    # Step A: Data Retrieval
    inventory_data: Optional[Dict[str, Any]]
    
    # Safety Calculations
    safety_metrics: Optional[Dict[str, Any]]
    
    # Step B: AI Reasoning
    recommendation: Optional[Dict[str, Any]]
    
    # Step C: Action Generation
    action: Optional[Dict[str, Any]]
    
    # Metadata
    error: Optional[str]
    timestamp: str
    trace_id: str


# ==================== Node Functions ====================

def data_loader_node(state: InventoryState) -> InventoryState:
    """
    Step A: Query demand forecast from CSV/database.
    
    Per PS.md: "The Agent queries a mock 'Demand Forecast' CSV/Database."
    """
    from agents.data_loader import load_data, load_mock_data
    from models.schemas import InventoryRequest
    
    try:
        product_id = state["product_id"]
        mode = state.get("mode", "mock")
        
        if mode == "mock":
            inventory_data = load_mock_data(product_id)
        else:
            # Input mode - use provided data
            request_data = state.get("request_data", {})
            request = InventoryRequest(
                product_id=product_id,
                mode=mode,
                **request_data
            )
            inventory_data = load_data(request)
        
        return {
            **state,
            "inventory_data": inventory_data,
            "error": None
        }
    except Exception as e:
        return {
            **state,
            "inventory_data": None,
            "error": f"Data loading failed: {str(e)}"
        }


def safety_calculator_node(state: InventoryState) -> InventoryState:
    """
    Calculate safety stock, reorder point, and shortage metrics.
    
    This uses statistical formulas (Z-score, standard deviation)
    to determine inventory thresholds.
    """
    from agents.safety_calculator import process_inventory_data
    
    if state.get("error"):
        return state
    
    try:
        inventory_data = state["inventory_data"]
        demand_history = inventory_data["demand_history"]
        lead_time = inventory_data["lead_time_days"]
        service_level = inventory_data.get("service_level", 0.95)
        current_stock = inventory_data["current_stock"]
        
        avg_demand, std_dev, safety_stock, reorder_point = process_inventory_data(
            demand_history=demand_history,
            lead_time=lead_time,
            service_level=service_level
        )
        
        shortage = max(0, reorder_point - current_stock)
        
        safety_metrics = {
            "avg_demand": avg_demand,
            "std_dev": std_dev,
            "safety_stock": safety_stock,
            "reorder_point": reorder_point,
            "current_stock": current_stock,
            "shortage": shortage,
            "needs_restock": shortage > 0
        }
        
        return {
            **state,
            "safety_metrics": safety_metrics,
            "error": None
        }
    except Exception as e:
        return {
            **state,
            "safety_metrics": None,
            "error": f"Safety calculation failed: {str(e)}"
        }


def reasoning_node(state: InventoryState) -> InventoryState:
    """
    Step B: AI determines if low stock is a crisis or demand is dropping.
    
    Per PS.md: "The AI determines if the low stock is a crisis or if 
    demand is dropping anyway (avoiding overstock)."
    
    Uses LLM (Gemini/Llama) to analyze context and make recommendation.
    """
    from agents.reasoning_agent import ReasoningAgent
    
    if state.get("error"):
        return state
    
    try:
        inventory_data = state["inventory_data"]
        safety_metrics = state["safety_metrics"]
        
        # Prepare context for AI reasoning
        context = {
            "product_id": state["product_id"],
            "current_stock": safety_metrics["current_stock"],
            "safety_stock": safety_metrics["safety_stock"],
            "reorder_point": safety_metrics["reorder_point"],
            "shortage": safety_metrics["shortage"],
            "avg_demand": safety_metrics["avg_demand"],
            "std_dev": safety_metrics["std_dev"],
            "lead_time_days": inventory_data["lead_time_days"],
            "demand_history": inventory_data["demand_history"],
            "unit_price": inventory_data.get("unit_price", 100)
        }
        
        agent = ReasoningAgent()
        recommendation = agent.analyze(context)
        
        return {
            **state,
            "recommendation": recommendation,
            "error": None
        }
    except Exception as e:
        return {
            **state,
            "recommendation": None,
            "error": f"AI reasoning failed: {str(e)}"
        }


def action_generator_node(state: InventoryState) -> InventoryState:
    """
    Step C: Generate JSON payload for Purchase Order or Transfer Order.
    
    Per PS.md: "The Agent generates a JSON payload for a Purchase Order
    or suggests moving stock from a different warehouse."
    """
    from agents.action_agent import generate_action
    
    if state.get("error"):
        return state
    
    try:
        recommendation = state["recommendation"]
        inventory_data = state["inventory_data"]
        safety_metrics = state["safety_metrics"]
        
        action = generate_action(
            product_id=state["product_id"],
            recommended_action=recommendation["action"],
            quantity=recommendation["quantity"],
            unit_price=inventory_data.get("unit_price", 100)
        )
        
        # Enrich action with metadata
        action_data = {
            "order": action,
            "status": "executed" if recommendation["confidence"] >= 0.6 else "pending",
            "confidence": recommendation["confidence"],
            "reasoning": recommendation["reasoning"],
            "safety_metrics": safety_metrics
        }
        
        return {
            **state,
            "action": action_data,
            "error": None
        }
    except Exception as e:
        return {
            **state,
            "action": None,
            "error": f"Action generation failed: {str(e)}"
        }


# ==================== Routing Functions ====================

def route_on_error(state: InventoryState) -> str:
    """Route to error handling if any step failed."""
    if state.get("error"):
        return "error"
    return "continue"


def route_by_confidence(state: InventoryState) -> str:
    """
    Route based on AI confidence score.
    
    - High confidence (≥0.6): Auto-execute
    - Low confidence (<0.6): Pending for human review
    """
    if state.get("error"):
        return "error"
    
    recommendation = state.get("recommendation", {})
    confidence = recommendation.get("confidence", 0)
    
    if confidence >= 0.6:
        return "execute"
    return "pending"
