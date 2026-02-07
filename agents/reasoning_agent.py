"""Reasoning agent with LLM integration and automatic failover."""

import os
import json
import logging
from typing import Dict, Any, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logger
logger = logging.getLogger(__name__)


# Prompt template for restock decisions
RESTOCK_PROMPT = """You are an inventory management AI agent. Analyze the following inventory situation and recommend an action.

## Current Status:
- Product: {product_id}
- Current Warehouse (A): {current_stock} units
- Other Warehouse (B): {warehouse_b_stock} units
- Safety Stock: {safety_stock:.0f} units
- Reorder Point: {reorder_point:.0f} units
- Shortage: {shortage:.0f} units below ROP
- Average Daily Demand: {avg_demand:.0f} units
- Lead Time: Lead time: {lead_time_days} days purchase, 1-2 days transfer

## Demand Trend (last 7 days):
{demand_history}

## Decision Rules:
1. **Use "transfer"** if:
   - Warehouse B has surplus stock (>200 units available)
   - Shortage is moderate (<500 units)
   - This is faster and costs nothing

2. **Use "restock"** if:
   - Warehouse B has low/no stock
   - Emergency shortage (>500 units OR critical stockout)
   - Need large quantity that Warehouse B can't provide

3. **Confidence scoring**:
   - High (>0.90): Clear shortage + demand data supports action
   - Medium (0.70-0.90): Some uncertainty in demand trend
   - Low (<0.70): Declining demand or unclear situation

## Response Format (JSON only, no markdown):
{{
    "action": "restock" or "transfer",
    "quantity": <number>,
    "confidence": <0.0-1.0>,
    "reasoning": "<brief explanation including why transfer/restock was chosen>"
}}
"""


class LLMProvider:
    """LLM Provider with automatic failover support."""
    
    def __init__(self):
        self.provider_mode = os.getenv("LLM_PROVIDER", "auto")  # auto, primary, backup
        self._primary_llm = None
        self._backup_llm = None
    
    @property
    def primary(self):
        """Lazy-load Gemini (primary LLM)."""
        if self._primary_llm is None:
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if api_key:
                self._primary_llm = ChatGoogleGenerativeAI(
                    model=os.getenv("GEMINI_MODEL", "gemini-1.5-pro"),
                    google_api_key=api_key,
                    temperature=0.3
                )
        return self._primary_llm
    
    @property
    def backup(self):
        """Lazy-load Groq (backup LLM) - FREE and stable."""
        if self._backup_llm is None:
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                self._backup_llm = ChatGroq(
                    model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                    groq_api_key=api_key,
                    temperature=0.3
                )
        return self._backup_llm
    
    def get_llm_chain(self):
        """
        Get ordered list of LLMs to try based on provider mode.
        
        Returns:
            List of (name, llm) tuples in order of preference
        """
        if self.provider_mode == "primary":
            return [("gemini", self.primary)] if self.primary else []
        elif self.provider_mode == "backup":
            return [("groq", self.backup)] if self.backup else []
        else:  # auto - try primary, fallback to backup
            chain = []
            if self.primary:
                chain.append(("gemini", self.primary))
            if self.backup:
                chain.append(("groq", self.backup))
            return chain


class ReasoningAgent:
    """Reasoning agent with automatic LLM failover."""
    
    def __init__(self):
        self.llm_provider = LLMProvider()
    
    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """
        Extract and parse JSON from LLM response with error recovery.
        
        Handles common LLM output issues:
        - Markdown code blocks
        - Text before/after JSON
        - Trailing commas
        - Single quotes instead of double quotes
        """
        import re
        
        # Remove markdown code blocks (case-insensitive, handles any language tag)
        content = content.strip()
        content = re.sub(r'```[a-zA-Z]*\s*', '', content, flags=re.IGNORECASE)
        
        # Find JSON object (handles text before/after JSON)
        start = content.find("{")
        end = content.rfind("}") + 1
        
        if start == -1 or end == 0:
            raise ValueError(f"No JSON object found in response: {content[:100]}")
        
        json_str = content[start:end]
        
        try:
            # First attempt: strict parsing
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.debug(f"Initial JSON parse failed, attempting recovery: {str(e)}")
            
            # Attempt 1: Fix single quotes
            try:
                fixed = json_str.replace("'", '"')
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
            
            # Attempt 2: Remove trailing commas
            try:
                fixed = re.sub(r',(\s*[}\]])', r'\1', json_str)
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
            
            # Attempt 3: Both fixes combined
            try:
                fixed = json_str.replace("'", '"')
                fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)
                return json.loads(fixed)
            except json.JSONDecodeError:
                # All recovery attempts failed
                raise ValueError(
                    f"Could not parse JSON after multiple recovery attempts. "
                    f"Original error: {str(e)}. Content: {json_str[:200]}"
                )

    
    async def _call_llm(self, llm, prompt: str, llm_name: str) -> Optional[Dict[str, Any]]:
        """
        Call a single LLM with retry logic.
        
        Returns:
            Parsed response or None if failed
        """
        try:
            logger.info(f"Calling LLM: {llm_name}")
            response = await llm.ainvoke(prompt)
            result = self._parse_json_response(response.content)
            logger.info(f"LLM call successful: {llm_name}")
            return result
        except Exception as e:
            logger.warning(f"LLM call failed ({llm_name}): {str(e)}", exc_info=True)
            return None
    
    
    def _sanitize_product_id(self, product_id: str) -> str:
        """
        Sanitize product ID to prevent prompt injection.
        
        Allows only alphanumeric characters, underscores, and dashes.
        Truncates to reasonable length.
        """
        import re
        sanitized = re.sub(r'[^A-Za-z0-9_-]', '', product_id)
        return sanitized[:100]  # Max 100 chars
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze inventory context with automatic failover.
        
        Tries primary LLM first (Gemini), falls back to backup (Groq) on failure.
        
        Args:
            context: Dictionary with inventory parameters
            
        Returns:
            Dictionary with action, quantity, confidence, reasoning
            
        Raises:
            ValueError: If no LLM providers configured
            RuntimeError: If all LLM providers fail
        """
        # Sanitize product_id to prevent prompt injection
        safe_context = context.copy()
        if "product_id" in safe_context:
            safe_context["product_id"] = self._sanitize_product_id(safe_context["product_id"])
        
        prompt = RESTOCK_PROMPT.format(**safe_context)
        llm_chain = self.llm_provider.get_llm_chain()
        
        if not llm_chain:
            raise ValueError("No LLM providers configured. Check GOOGLE_API_KEY/GEMINI_API_KEY or GROQ_API_KEY.")
        
        last_error = None
        for llm_name, llm in llm_chain:
            result = await self._call_llm(llm, prompt, llm_name)
            if result:
                # Add metadata about which LLM was used
                result["_llm_provider"] = llm_name
                return result
            last_error = f"{llm_name} failed"
        
        # All LLMs failed
        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")


# --- Standalone functions for testing ---

async def analyze_with_gemini(context: Dict[str, Any]) -> Dict[str, Any]:
    """Direct Gemini call (for testing)."""
    llm = ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-1.5-pro"),
        google_api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"),
        temperature=0.3
    )
    prompt = RESTOCK_PROMPT.format(**context)
    response = await llm.ainvoke(prompt)
    content = response.content
    start = content.find("{")
    end = content.rfind("}") + 1
    return json.loads(content[start:end])


async def analyze_with_groq(context: Dict[str, Any]) -> Dict[str, Any]:
    """Direct Groq call (for testing) - FREE!"""
    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        groq_api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.3
    )
    prompt = RESTOCK_PROMPT.format(**context)
    response = await llm.ainvoke(prompt)
    content = response.content
    start = content.find("{")
    end = content.rfind("}") + 1
    return json.loads(content[start:end])
