"""Integration tests for action agent."""

import pytest
from datetime import datetime
from agents.action_agent import generate_action


class TestPurchaseOrderGeneration:
    """Test purchase order generation."""
    
    def test_generate_restock_action(self):
        """Test generating a restock purchase order."""
        recommendation = {
            "action": "restock",
            "quantity": 2000,
            "confidence": 0.92,
            "reasoning": "Stock below ROP"
        }
        
        order = generate_action("STEEL_SHEETS", recommendation)
        
        assert order.type == "purchase_order"
        assert "PO-" in order.po_number
        assert "STEEL_SHEETS" in order.po_number
        assert len(order.items) == 1
        assert order.items[0]["material_id"] == "STEEL_SHEETS"
        assert order.items[0]["quantity"] == 2000
    
    def test_po_number_format(self):
        """Test PO number format includes date."""
        recommendation = {"action": "restock", "quantity": 100}
        order = generate_action("TEST", recommendation)
        
        today = datetime.now().strftime("%Y%m%d")
        assert today in order.po_number


class TestTransferGeneration:
    """Test transfer order generation."""
    
    def test_generate_transfer_action(self):
        """Test generating a transfer order."""
        recommendation = {
            "action": "transfer",
            "quantity": 500,
            "confidence": 0.85,
            "reasoning": "Transfer from nearby warehouse"
        }
        
        order = generate_action("ALUMINUM_BARS", recommendation)
        
        assert order.type == "transfer"
        assert "TR-" in order.po_number
        assert "ALUMINUM_BARS" in order.po_number
        assert len(order.items) == 1
        assert order.items[0]["material_id"] == "ALUMINUM_BARS"
        assert order.items[0]["quantity"] == 500
        assert "source" in order.items[0]
        assert "destination" in order.items[0]
    
    def test_transfer_includes_source(self):
        """Test transfer includes source warehouse."""
        recommendation = {"action": "transfer", "quantity": 100}
        order = generate_action("TEST", recommendation)
        
        assert order.items[0]["source"] == "WAREHOUSE_B"
        assert order.items[0]["destination"] == "WAREHOUSE_A"


class TestActionVariations:
    """Test various action scenarios."""
    
    def test_large_quantity_order(self):
        """Test handling large quantity orders."""
        recommendation = {"action": "restock", "quantity": 10000}
        order = generate_action("PLASTIC_PELLETS", recommendation)
        
        assert order.items[0]["quantity"] == 10000
    
    def test_small_quantity_transfer(self):
        """Test handling small quantity transfers."""
        recommendation = {"action": "transfer", "quantity": 5}
        order = generate_action("TITANIUM_RODS", recommendation)
        
        assert order.items[0]["quantity"] == 5
    
    def test_order_timestamp(self):
        """Test order has timestamp."""
        recommendation = {"action": "restock", "quantity": 100}
        order = generate_action("TEST", recommendation)
        
        assert order.created_at is not None
        assert isinstance(order.created_at, datetime)
