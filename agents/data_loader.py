"""Data loading module supporting both mock and input modes."""

import pandas as pd
from pathlib import Path
from typing import Dict, Any
from functools import lru_cache
from models.schemas import InventoryRequest


# Path to data directory
DATA_DIR = Path(__file__).parent.parent / "data"


def load_data(request: InventoryRequest) -> Dict[str, Any]:
    """
    Load inventory data based on mode (mock or input).
    
    Args:
        request: InventoryRequest with mode and product details
        
    Returns:
        Dictionary with all required inventory parameters
        
    Raises:
        ValueError: If product not found in mock mode
        FileNotFoundError: If mock data files missing
    """
    if request.mode == "mock":
        return load_mock_data(request.product_id)
    else:
        # Input mode: validate required fields
        if request.current_stock is None:
            raise ValueError("current_stock is required in 'input' mode")
        if request.demand_history is None or len(request.demand_history) < 3:
            raise ValueError("demand_history must have at least 3 data points")
        if request.lead_time_days is None:
            raise ValueError("lead_time_days is required in 'input' mode")
        
        return request.model_dump()


@lru_cache(maxsize=100)
def load_mock_data(product_id: str) -> Dict[str, Any]:
    """
    Load mock data from CSV files for testing and demos.
    
    Args:
        product_id: Product identifier to look up
        
    Returns:
        Dictionary with product inventory parameters
        
    Raises:
        FileNotFoundError: If CSV files don't exist
        ValueError: If product_id not found in data
    """
    inventory_path = DATA_DIR / "mock_inventory.csv"
    demand_path = DATA_DIR / "mock_demand.csv"
    
    if not inventory_path.exists():
        raise FileNotFoundError(f"Mock inventory data not found at {inventory_path}")
    if not demand_path.exists():
        raise FileNotFoundError(f"Mock demand data not found at {demand_path}")
    
    # Load data
    inventory = pd.read_csv(inventory_path)
    demand = pd.read_csv(demand_path)
    
    # Filter for product
    product_inv = inventory[inventory["product_id"] == product_id]
    if product_inv.empty:
        raise ValueError(f"Product '{product_id}' not found in mock inventory data")
    
    product_inv = product_inv.iloc[0]
    product_demand = demand[demand["product_id"] == product_id]["quantity"].tolist()
    
    if not product_demand:
        raise ValueError(f"No demand history found for product '{product_id}'")
    
    return {
        "product_id": product_id,
        "current_stock": int(product_inv["current_stock"]),
        "demand_history": product_demand,
        "lead_time_days": int(product_inv["lead_time_days"]),
        "service_level": float(product_inv["service_level"]),
        "unit_price": float(product_inv.get("unit_price", 100))
    }
