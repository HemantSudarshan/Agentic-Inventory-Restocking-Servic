The Objective  
Build a mini-service that monitors inventory levels and, instead of just  
sending an alert, uses an AI Agent to analyze a demand forecast and  
draft a "Restock Strategy" or a "Transfer Order."

The Core Workflow  
Inventory Trigger: A Node.js/Python script detects that a specific raw  
material (e.g., "Steel Sheets") has fallen below the safety stock level.

The Agentic Flow:

Step A (Data Retrieval): The Agent queries a mock "Demand Forecast"  
CSV/Database.

Step B (Reasoning): The AI determines if the low stock is a crisis or if  
demand is dropping anyway (avoiding overstock).

Step C (Action): The Agent generates a JSON payload for a Purchase Order  
or suggests moving stock from a different warehouse.

Technical Requirements

Backend \= Fast API or Flask

AI Orchestration \= LangGraph, CrewAI, or simple OpenAI Function Calling

Model \= GPT-4o-mini/Gemini 2.5 Flash or Llama 3 (for cost-efficient  
reasoning)

Data Source \= SQLite or a simple Pandas Data Frame (Mock ERP data)