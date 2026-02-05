"""Prometheus metrics for monitoring."""

from prometheus_client import Counter, Histogram, Gauge


# Request metrics
inventory_trigger_total = Counter(
    'inventory_trigger_total',
    'Total inventory trigger requests',
    ['mode', 'status']
)

llm_calls_total = Counter(
    'llm_calls_total',
    'Total LLM API calls',
    ['provider', 'status']
)

# Response time metrics
request_duration_seconds = Histogram(
    'request_duration_seconds',
    'Request duration in seconds',
    ['endpoint']
)

llm_duration_seconds = Histogram(
    'llm_duration_seconds',
    'LLM call duration in seconds',
    ['provider']
)

# Business metrics
orders_generated_total = Counter(
    'orders_generated_total',
    'Total orders generated',
    ['type', 'execution_status']
)

inventory_shortage_total = Counter(
    'inventory_shortage_total',
    'Total inventory shortage events',
    ['product_id']
)

current_reorder_point = Gauge(
    'current_reorder_point',
    'Current reorder point threshold',
    ['product_id']
)

current_safety_stock = Gauge(
    'current_safety_stock',
    'Current safety stock level',
    ['product_id']
)
