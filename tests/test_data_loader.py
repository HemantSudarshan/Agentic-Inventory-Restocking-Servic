"""Integration tests for data loader module."""

import pytest
from pathlib import Path
from agents.data_loader import load_data, load_mock_data
from models.schemas import InventoryRequest


class TestMockDataLoading:
    """Test mock data loading functionality."""
    
    def test_load_mock_data_steel_sheets(self):
        """Test loading STEEL_SHEETS mock data."""
        data = load_mock_data("STEEL_SHEETS")
        
        assert data["product_id"] == "STEEL_SHEETS"
        assert data["current_stock"] == 150
        assert data["lead_time_days"] == 7
        assert data["service_level"] == 0.95
        assert data["unit_price"] == 500
        assert len(data["demand_history"]) == 30
    
    def test_load_mock_data_all_products(self):
        """Test loading all products in mock data."""
        products = ["STEEL_SHEETS", "ALUMINUM_BARS", "COPPER_WIRE", 
                   "PLASTIC_PELLETS", "TITANIUM_RODS", "RUBBER_SHEETS"]
        
        for product_id in products:
            data = load_mock_data(product_id)
            assert data["product_id"] == product_id
            assert data["current_stock"] > 0
            assert len(data["demand_history"]) >= 3
    
    def test_load_mock_data_invalid_product(self):
        """Test error handling for invalid product."""
        with pytest.raises(ValueError, match="not found"):
            load_mock_data("INVALID_PRODUCT")


class TestInputDataMode:
    """Test input mode data loading."""
    
    def test_load_input_mode_valid(self):
        """Test loading valid input data."""
        request = InventoryRequest(
            product_id="TEST_PRODUCT",
            mode="input",
            current_stock=100,
            demand_history=[50, 60, 55, 65, 58],
            lead_time_days=5,
            service_level=0.95,
            unit_price=200
        )
        
        data = load_data(request)
        
        assert data["product_id"] == "TEST_PRODUCT"
        assert data["current_stock"] == 100
        assert len(data["demand_history"]) == 5
    
    def test_load_input_mode_missing_stock(self):
        """Test error for missing current_stock in input mode."""
        request = InventoryRequest(
            product_id="TEST",
            mode="input",
            demand_history=[50, 60, 55],
            lead_time_days=5
        )
        
        with pytest.raises(ValueError, match="current_stock is required"):
            load_data(request)
    
    def test_load_input_mode_insufficient_demand_history(self):
        """Test error for insufficient demand history."""
        # Pydantic will validate before load_data is called
        with pytest.raises(Exception):  # Pydantic ValidationError
            request = InventoryRequest(
                product_id="TEST",
                mode="input",
                current_stock=100,
                demand_history=[50, 60],  # Only 2 points, min is 3
                lead_time_days=5
            )


class TestDualModeSwitch:
    """Test switching between mock and input modes."""
    
    def test_switch_to_mock_mode(self):
        """Test switching to mock mode."""
        request = InventoryRequest(
            product_id="STEEL_SHEETS",
            mode="mock"
        )
        
        data = load_data(request)
        assert data["product_id"] == "STEEL_SHEETS"
        assert "current_stock" in data
    
    def test_switch_to_input_mode(self):
        """Test switching to input mode."""
        request = InventoryRequest(
            product_id="CUSTOM",
            mode="input",
            current_stock=500,
            demand_history=[100, 120, 115, 130],
            lead_time_days=10,
            service_level=0.99
        )
        
        data = load_data(request)
        assert data["product_id"] == "CUSTOM"
        assert data["current_stock"] == 500
