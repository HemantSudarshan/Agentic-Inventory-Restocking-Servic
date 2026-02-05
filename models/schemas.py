"""Pydantic models for request/response validation."""

from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any
from datetime import datetime


class InventoryRequest(BaseModel):
    """Request model for inventory trigger endpoint."""
    
    product_id: str = Field(..., description="Unique product identifier")
    mode: Literal["mock", "input"] = Field(default="mock", description="Data source mode")
    
    # Optional fields for 'input' mode
    current_stock: Optional[int] = Field(None, ge=0, description="Current inventory level")
    demand_history: Optional[List[float]] = Field(None, min_length=3, description="Historical demand data (min 3 points)")
    lead_time_days: Optional[int] = Field(None, ge=1, description="Supplier lead time in days")
    service_level: Optional[float] = Field(default=0.95, ge=0.5, le=0.99, description="Target service level (0.5-0.99)")
    unit_price: Optional[float] = Field(None, ge=0, description="Unit price for cost calculations")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "product_id": "STEEL_SHEETS",
                    "mode": "mock"
                },
                {
                    "product_id": "STEEL_SHEETS",
                    "mode": "input",
                    "current_stock": 150,
                    "demand_history": [100, 120, 110, 130, 125, 115, 140],
                    "lead_time_days": 7,
                    "service_level": 0.95,
                    "unit_price": 500
                }
            ]
        }


class SafetyParams(BaseModel):
    """Safety stock calculation parameters."""
    
    safety_stock: float = Field(..., description="Calculated safety stock quantity")
    reorder_point: float = Field(..., description="Reorder point threshold")
    avg_demand: float = Field(..., description="Average daily demand")
    std_dev: float = Field(..., description="Demand standard deviation")


class OrderAction(BaseModel):
    """Purchase order or transfer action."""
    
    po_number: str = Field(..., description="Order/transfer number")
    type: Literal["purchase_order", "transfer"] = Field(..., description="Action type")
    items: List[Dict[str, Any]] = Field(..., description="Order line items")
    created_at: datetime = Field(default_factory=datetime.now, description="Order creation timestamp")


class InventoryResponse(BaseModel):
    """Success response from inventory trigger."""
    
    status: Literal["executed", "pending_review"] = Field(..., description="Execution status")
    safety_stock: float = Field(..., description="Calculated safety stock")
    reorder_point: float = Field(..., description="Reorder point threshold")
    current_stock: int = Field(..., description="Current inventory level")
    shortage: float = Field(..., description="Units below ROP (negative means surplus)")
    recommended_action: str = Field(..., description="Recommended action (restock/transfer)")
    recommended_quantity: int = Field(..., description="Recommended order quantity")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="AI confidence score")
    order: Optional[OrderAction] = Field(None, description="Generated order (if auto-executed)")
    reasoning: str = Field(..., description="AI reasoning for decision")


class DebugResponse(BaseModel):
    """Debug endpoint response."""
    
    product_id: str
    mode: str
    calculations: Dict[str, float]
    current_status: Dict[str, float]
    would_trigger: bool
    trigger_reason: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response model."""
    
    status: Literal["error"] = "error"
    error_code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
