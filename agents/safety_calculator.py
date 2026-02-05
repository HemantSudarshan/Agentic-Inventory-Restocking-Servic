"""Safety stock calculation module with supply chain formulas."""

import math
import numpy as np
from scipy.stats import norm
from typing import Tuple


def calculate_safety_stock(std_dev: float, lead_time: int, service_level: float = 0.95) -> float:
    """
    Calculate Safety Stock using formula: SS = Z × σ × √L
    
    Safety stock is the extra inventory kept to prevent stockouts due to
    demand variability and lead time uncertainty.
    
    Args:
        std_dev: Standard deviation of daily demand
        lead_time: Lead time in days
        service_level: Target service level (0.5 to 0.99)
                      0.95 = 95% (Z=1.65), 0.99 = 99% (Z=2.33)
    
    Returns:
        Safety stock quantity (units)
    
    Example:
        >>> calculate_safety_stock(std_dev=20, lead_time=7, service_level=0.95)
        87.17  # approximately 87 units
    """
    if std_dev < 0:
        raise ValueError("Standard deviation must be non-negative")
    if lead_time <= 0:
        raise ValueError("Lead time must be positive")
    if not (0.5 <= service_level <= 0.99):
        raise ValueError("Service level must be between 0.5 and 0.99")
    
    # Calculate Z-score from service level using inverse CDF
    z = norm.ppf(service_level)  # 1.65 for 95%, 2.33 for 99%
    
    return z * std_dev * math.sqrt(lead_time)


def calculate_reorder_point(avg_demand: float, lead_time: int, safety_stock: float) -> float:
    """
    Calculate Reorder Point: ROP = (Avg Daily Demand × Lead Time) + Safety Stock
    
    The reorder point is the inventory level that triggers a new order.
    
    Args:
        avg_demand: Average daily demand
        lead_time: Lead time in days
        safety_stock: Calculated safety stock
    
    Returns:
        Reorder point threshold (units)
    
    Example:
        >>> calculate_reorder_point(avg_demand=100, lead_time=7, safety_stock=87)
        787
    """
    if avg_demand < 0:
        raise ValueError("Average demand must be non-negative")
    if lead_time <= 0:
        raise ValueError("Lead time must be positive")
    if safety_stock < 0:
        raise ValueError("Safety stock must be non-negative")
    
    return (avg_demand * lead_time) + safety_stock


def calculate_eoq(annual_demand: float, order_cost: float, holding_cost: float) -> float:
    """
    Calculate Economic Order Quantity (EOQ).
    
    EOQ = √((2 × D × S) / H)
    
    EOQ minimizes total inventory costs by balancing ordering costs
    and holding costs.
    
    Args:
        annual_demand: Annual demand (units/year)
        order_cost: Cost per order ($/order)
        holding_cost: Annual holding cost per unit ($/unit/year)
    
    Returns:
        Economic order quantity (units)
    
    Example:
        >>> calculate_eoq(annual_demand=36500, order_cost=50, holding_cost=5)
        606.22
    """
    if annual_demand <= 0:
        raise ValueError("Annual demand must be positive")
    if order_cost <= 0:
        raise ValueError("Order cost must be positive")
    if holding_cost <= 0:
        raise ValueError("Holding cost must be positive")
    
    return math.sqrt((2 * annual_demand * order_cost) / holding_cost)


def process_inventory_data(
    demand_history: list, 
    lead_time: int, 
    service_level: float
) -> Tuple[float, float, float, float]:
    """
    Process demand history and calculate all safety parameters.
    
    This is the main function that orchestrates the complete calculation pipeline.
    
    Args:
        demand_history: List of historical demand values (min 3 data points)
        lead_time: Lead time in days
        service_level: Target service level (0.5 to 0.99)
    
    Returns:
        Tuple of (avg_demand, std_dev, safety_stock, reorder_point)
    
    Raises:
        ValueError: If demand_history has less than 3 data points
    
    Example:
        >>> demand = [100, 120, 110, 130, 125, 115, 140]
        >>> avg, std, ss, rop = process_inventory_data(demand, lead_time=7, service_level=0.95)
        >>> print(f"ROP: {rop:.0f} units")
        ROP: 787 units
    """
    if len(demand_history) < 3:
        raise ValueError("demand_history must have at least 3 data points")
    
    # Calculate statistics
    avg_demand = np.mean(demand_history)
    std_dev = np.std(demand_history, ddof=1)  # Sample standard deviation
    
    # Calculate safety parameters
    safety_stock = calculate_safety_stock(std_dev, lead_time, service_level)
    reorder_point = calculate_reorder_point(avg_demand, lead_time, safety_stock)
    
    return avg_demand, std_dev, safety_stock, reorder_point
