"""
LangGraph StateGraph workflow for Inventory Agent.

This module builds the actual graph that represents the agentic workflow
per PS.md requirements:
- Step A (Data Retrieval): Query demand forecast
- Step B (Reasoning): AI determines crisis vs dropping demand
- Step C (Action): Generate PO or transfer order
"""

from langgraph.graph import StateGraph, END
from datetime import datetime
import uuid

from .nodes import (
    InventoryState,
    data_loader_node,
    safety_calculator_node,
    reasoning_node,
    action_generator_node,
    route_on_error,
    route_by_confidence
)


def build_inventory_workflow() -> StateGraph:
    """
    Build the LangGraph workflow for inventory analysis.
    
    Graph Structure:
    ```
    START → load_data → calculate_safety → ai_reasoning → route_by_confidence
                                                              ↓
                                                    ┌────────┴────────┐
                                                    ↓                 ↓
                                              generate_action   generate_action
                                              (execute)         (pending)
                                                    ↓                 ↓
                                                   END               END
    ```
    """
    # Create the graph with state schema
    workflow = StateGraph(InventoryState)
    
    # Add nodes (Step A, B, C per PS.md)
    workflow.add_node("load_data", data_loader_node)
    workflow.add_node("calculate_safety", safety_calculator_node)
    workflow.add_node("ai_reasoning", reasoning_node)
    workflow.add_node("generate_action", action_generator_node)
    
    # Set entry point
    workflow.set_entry_point("load_data")
    
    # Add edges (linear flow with error checking)
    workflow.add_conditional_edges(
        "load_data",
        route_on_error,
        {
            "continue": "calculate_safety",
            "error": END
        }
    )
    
    workflow.add_conditional_edges(
        "calculate_safety",
        route_on_error,
        {
            "continue": "ai_reasoning",
            "error": END
        }
    )
    
    workflow.add_conditional_edges(
        "ai_reasoning",
        route_on_error,
        {
            "continue": "generate_action",
            "error": END
        }
    )
    
    # Final node goes to END
    workflow.add_edge("generate_action", END)
    
    return workflow


# Compile the workflow into a runnable app
def create_inventory_agent():
    """
    Create a compiled LangGraph agent for inventory analysis.
    
    Usage:
        agent = create_inventory_agent()
        result = agent.invoke({
            "product_id": "STEEL_SHEETS",
            "mode": "mock",
            "timestamp": datetime.now().isoformat(),
            "trace_id": str(uuid.uuid4())
        })
    """
    workflow = build_inventory_workflow()
    return workflow.compile()


# Pre-compiled agent instance
inventory_agent = create_inventory_agent()


def run_inventory_analysis(
    product_id: str,
    mode: str = "mock",
    request_data: dict = None
) -> InventoryState:
    """
    Execute the inventory analysis workflow.
    
    Args:
        product_id: Product to analyze
        mode: "mock" or "input"
        request_data: Optional data for input mode
        
    Returns:
        Final state with all results
    """
    initial_state: InventoryState = {
        "product_id": product_id,
        "mode": mode,
        "request_data": request_data,
        "inventory_data": None,
        "safety_metrics": None,
        "recommendation": None,
        "action": None,
        "error": None,
        "timestamp": datetime.now().isoformat(),
        "trace_id": str(uuid.uuid4())
    }
    
    result = inventory_agent.invoke(initial_state)
    return result
