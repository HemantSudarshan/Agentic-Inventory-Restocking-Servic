"""Action generation module for purchase orders and transfers."""

from datetime import datetime
from typing import Dict, Any
from models.schemas import OrderAction


def generate_action(product_id: str, recommendation: Dict[str, Any]) -> OrderAction:
    """
    Generate PO or Transfer order based on AI recommendation.
    
    Args:
        product_id: Product identifier
        recommendation: AI recommendation with action and quantity
        
    Returns:
        OrderAction with PO number, type, and items
        
    Example:
        >>> rec = {"action": "restock", "quantity": 2000}
        >>> order = generate_action("STEEL_SHEETS", rec)
        >>> order.type
        'purchase_order'
    """
    action_type = recommendation["action"]
    quantity = recommendation["quantity"]
    timestamp = datetime.now().strftime("%Y%m%d")
    
    if action_type == "restock":
        return OrderAction(
            po_number=f"PO-{timestamp}-{product_id}",
            type="purchase_order",
            items=[{
                "material_id": product_id, 
                "quantity": quantity
            }]
        )
    else:  # transfer
        return OrderAction(
            po_number=f"TR-{timestamp}-{product_id}",
            type="transfer",
            items=[{
                "material_id": product_id, 
                "quantity": quantity,
                "source": "WAREHOUSE_B",
                "destination": "WAREHOUSE_A"
            }]
        )
