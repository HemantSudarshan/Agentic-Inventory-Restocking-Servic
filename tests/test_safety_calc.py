"""Unit tests for safety stock calculation formulas."""

import pytest
import numpy as np
from agents.safety_calculator import (
    calculate_safety_stock,
    calculate_reorder_point,
    calculate_eoq,
    process_inventory_data
)


class TestSafetyStockCalculation:
    """Test safety stock formula (SS = Z × σ × √L)."""
    
    def test_safety_stock_95_service_level(self):
        """Test SS calculation at 95% service level."""
        ss = calculate_safety_stock(std_dev=20, lead_time=7, service_level=0.95)
        assert 85 < ss < 90  # Should be ~87 units (1.65 × 20 × √7)
    
    def test_safety_stock_99_service_level(self):
        """Test SS calculation at 99% service level."""
        ss = calculate_safety_stock(std_dev=20, lead_time=7, service_level=0.99)
        assert 120 < ss < 125  # Should be ~123 units (2.33 × 20 × √7)
    
    def test_safety_stock_different_lead_time(self):
        """Test SS scales with lead time."""
        ss_short = calculate_safety_stock(std_dev=20, lead_time=3, service_level=0.95)
        ss_long = calculate_safety_stock(std_dev=20, lead_time=12, service_level=0.95)
        assert ss_long > ss_short  # Longer lead time = higher safety stock
    
    def test_safety_stock_validation(self):
        """Test input validation."""
        with pytest.raises(ValueError):
            calculate_safety_stock(std_dev=-1, lead_time=7, service_level=0.95)
        with pytest.raises(ValueError):
            calculate_safety_stock(std_dev=20, lead_time=0, service_level=0.95)
        with pytest.raises(ValueError):
            calculate_safety_stock(std_dev=20, lead_time=7, service_level=1.5)


class TestReorderPoint:
    """Test reorder point formula (ROP = Avg Demand × Lead Time + SS)."""
    
    def test_reorder_point_calculation(self):
        """Test ROP calculation."""
        rop = calculate_reorder_point(avg_demand=100, lead_time=7, safety_stock=87)
        assert rop == 787  # (100 × 7) + 87
    
    def test_reorder_point_no_safety_stock(self):
        """Test ROP without safety stock."""
        rop = calculate_reorder_point(avg_demand=100, lead_time=7, safety_stock=0)
        assert rop == 700
    
    def test_reorder_point_validation(self):
        """Test input validation."""
        with pytest.raises(ValueError):
            calculate_reorder_point(avg_demand=-1, lead_time=7, safety_stock=87)
        with pytest.raises(ValueError):
            calculate_reorder_point(avg_demand=100, lead_time=0, safety_stock=87)


class TestEOQ:
    """Test Economic Order Quantity formula."""
    
    def test_eoq_calculation(self):
        """Test EOQ calculation."""
        eoq = calculate_eoq(annual_demand=36500, order_cost=50, holding_cost=5)
        # EOQ = √((2 × 36500 × 50) / 5) = √730000 ≈ 854.4
        assert 850 < eoq < 860  # Should be ~854 units
    
    def test_eoq_validation(self):
        """Test input validation."""
        with pytest.raises(ValueError):
            calculate_eoq(annual_demand=0, order_cost=50, holding_cost=5)
        with pytest.raises(ValueError):
            calculate_eoq(annual_demand=1000, order_cost=-10, holding_cost=5)


class TestProcessInventoryData:
    """Test full processing pipeline."""
    
    def test_process_inventory_data(self):
        """Test full processing with realistic data."""
        demand = [100, 120, 110, 130, 125, 115, 140]
        avg, std, ss, rop = process_inventory_data(demand, lead_time=7, service_level=0.95)
        
        # Verify calculations
        assert 110 < avg < 125  # Average should be ~120
        assert std > 0  # Should have variance
        assert ss > 0  # Should have safety stock
        assert rop > ss  # ROP should be greater than SS
        assert rop > avg * 7  # ROP should exceed lead time demand
    
    def test_process_with_stable_demand(self):
        """Test with low variability demand."""
        demand = [100, 101, 99, 100, 100, 101, 99]  # Very stable
        avg, std, ss, rop = process_inventory_data(demand, lead_time=7, service_level=0.95)
        
        assert 99 < avg < 101  # Average ~100
        assert std < 1  # Very low std dev
        assert ss < 10  # Low safety stock due to stability
    
    def test_process_with_volatile_demand(self):
        """Test with high variability demand."""
        demand = [50, 150, 75, 125, 100, 80, 120]  # High variance
        avg, std, ss, rop = process_inventory_data(demand, lead_time=7, service_level=0.95)
        
        assert std > 20  # High std dev
        assert ss > 50  # Higher safety stock due to volatility
    
    def test_process_validation(self):
        """Test input validation."""
        with pytest.raises(ValueError):
            process_inventory_data([100, 120], lead_time=7, service_level=0.95)  # Too few points


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_zero_variance_demand(self):
        """Test with zero variance (constant demand)."""
        demand = [100, 100, 100, 100]
        avg, std, ss, rop = process_inventory_data(demand, lead_time=7, service_level=0.95)
        
        assert avg == 100
        assert std == 0  # No variance
        assert ss == 0  # No safety stock needed
        assert rop == 700  # Just lead time demand
    
    def test_minimum_service_level(self):
        """Test minimum service level (50%)."""
        ss = calculate_safety_stock(std_dev=20, lead_time=7, service_level=0.5)
        assert ss == 0  # Z-score at 50% is 0
    
    def test_single_day_lead_time(self):
        """Test with 1-day lead time."""
        ss = calculate_safety_stock(std_dev=20, lead_time=1, service_level=0.95)
        assert 30 < ss < 35  # 1.65 × 20 × √1 = 33
