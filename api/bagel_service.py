#!/usr/bin/env python3
"""
Bagel RL Legal AI Service Integration
Connects the main LexAI application with the deployed Bagel RL model
"""

import requests
import json
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class BagelLegalService:
    """
    Service class for integrating with deployed Bagel RL legal model
    """
    
    def __init__(self, model_endpoint: str = "http://35.184.175.255:8000"):
        """
        Initialize the Bagel service
        
        Args:
            model_endpoint: The URL of the deployed Bagel RL model server
        """
        self.model_endpoint = model_endpoint
        self.available = self._check_availability()
        
    def _check_availability(self) -> bool:
        """Check if the Bagel model server is available"""
        try:
            response = requests.get(f"{self.model_endpoint}/health", timeout=5)
            return response.status_code == 200 and response.json().get("status") == "healthy"
        except Exception as e:
            logger.warning(f"Bagel service unavailable: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get the status of the Bagel model server"""
        try:
            if not self.available:
                return {
                    "status": "unavailable",
                    "model_loaded": False,
                    "error": "Service not available"
                }
                
            response = requests.get(f"{self.model_endpoint}/status", timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "status": "error",
                    "model_loaded": False,
                    "error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            logger.error(f"Failed to get Bagel status: {e}")
            return {
                "status": "error", 
                "model_loaded": False,
                "error": str(e)
            }
    
    def legal_query(
        self, 
        query: str, 
        context: str = "legal_research",
        privacy_level: str = "confidential",
        max_length: int = 400,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Process a legal query through the Bagel RL model
        
        Args:
            query: The legal question or request
            context: Legal context (e.g., 'employment_law', 'contract_analysis')
            privacy_level: Privacy protection level
            max_length: Maximum response length
            temperature: Model creativity (0.0-1.0)
            
        Returns:
            Dictionary with response, metadata, and processing info
        """
        if not self.available:
            return self._fallback_response(query, context, "Service unavailable")
            
        try:
            payload = {
                "query": query,
                "context": context,
                "privacy_level": privacy_level,
                "max_length": max_length,
                "temperature": temperature
            }
            
            logger.info(f"🔍 Sending query to Bagel RL: {query[:100]}...")
            
            response = requests.post(
                f"{self.model_endpoint}/query",
                json=payload,
                timeout=30,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Bagel RL responded successfully")
                return {
                    "success": True,
                    "response": result["response"],
                    "context": result["context"],
                    "privacy_protected": result["privacy_protected"],
                    "processing_time": result["processing_time"],
                    "model_version": result["model_version"],
                    "confidence_score": result["confidence_score"],
                    "source": "bagel_rl_trained_model"
                }
            else:
                logger.error(f"Bagel RL error: HTTP {response.status_code}")
                return self._fallback_response(query, context, f"HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"Bagel query failed: {e}")
            return self._fallback_response(query, context, str(e))
    
    def _fallback_response(self, query: str, context: str, error: str) -> Dict[str, Any]:
        """Generate fallback response when Bagel service is unavailable"""
        logger.warning(f"Using fallback response for: {query[:50]}...")
        
        # Generate context-aware fallback based on query type
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["constitutional", "first amendment", "free speech"]):
            fallback_text = """**Constitutional Law Analysis:**

Key precedents for First Amendment analysis:
- **Tinker v. Des Moines (1969)**: Students don't shed constitutional rights at school
- **Brandenburg v. Ohio (1969)**: Speech restrictions require imminent lawless action
- **Central Hudson (1980)**: Commercial speech test framework

**Analysis Framework:**
1. Is this protected speech?
2. What level of scrutiny applies?
3. Content-based vs. content-neutral restrictions?
4. Constitutional review standards?

**Recommendation**: Apply strict scrutiny for content-based restrictions."""
            
        elif any(word in query_lower for word in ["employment", "discrimination", "title vii", "religious"]):
            fallback_text = """**Employment Law Analysis:**

**Title VII Framework:**
- Protected classes: Race, color, religion, sex, national origin
- Disparate treatment vs. disparate impact analysis
- McDonnell Douglas burden-shifting framework

**Religious Accommodation:**
- Employee must show: sincere belief, conflict, notice
- Employer must provide reasonable accommodation unless undue hardship
- *Groff v. DeJoy (2023)* raised undue hardship standard

**Strategy**: Document accommodation requests and employer responses."""
            
        elif any(word in query_lower for word in ["patent", "alice", "intellectual property"]):
            fallback_text = """**Patent Law Analysis:**

**Alice Corp Framework (software patents):**
- Step 1: Is claim directed to abstract idea?
- Step 2: Does it contain inventive concept?

**Claim Construction Standards:**
- *Markman v. Westview (1996)*: Question of law for judge
- *Phillips v. AWH (2005)*: Intrinsic evidence hierarchy

**Strategy**: Focus on specific technical implementation, avoid abstract concepts."""
            
        elif any(word in query_lower for word in ["contract", "agreement", "breach"]):
            fallback_text = """**Contract Law Analysis:**

**Formation Elements:**
- Offer, acceptance, consideration, capacity, legality
- Mutual assent and definiteness requirements

**Breach Analysis:**
- Material vs. minor breach determination
- Anticipatory breach doctrine
- Excuse doctrines: impossibility, impracticability

**Remedies:**
- Expectation damages (benefit of bargain)
- Reliance damages and restitution
- Specific performance for unique goods/services"""
            
        else:
            fallback_text = """**General Legal Analysis:**

**Systematic Approach:**
1. **Jurisdiction**: Determine applicable law and venue
2. **Legal Framework**: Identify relevant statutes and precedents
3. **Factual Development**: Gather key facts for analysis
4. **Strategic Considerations**: Assess litigation vs. settlement

**Research Methodology:**
- Primary sources: Statutes, regulations, case law
- Secondary sources: Treatises, practice guides
- Current developments: Recent decisions, pending legislation

**Recommendation**: Provide more specific facts for detailed analysis."""
        
        return {
            "success": False,
            "response": fallback_text,
            "context": context,
            "privacy_protected": True,
            "processing_time": 0.1,
            "model_version": "fallback_v1.0",
            "confidence_score": 0.6,
            "source": "fallback_legal_knowledge",
            "error": error,
            "fallback_reason": "Bagel RL service unavailable"
        }

# Global instance for use in Flask app
bagel_service = BagelLegalService()

def get_bagel_status() -> Dict[str, Any]:
    """Get current Bagel service status"""
    return bagel_service.get_status()

def query_bagel_legal_ai(
    query: str,
    context: str = "legal_research",
    privacy_level: str = "confidential"
) -> Dict[str, Any]:
    """
    Main function to query the Bagel RL legal AI
    
    Args:
        query: Legal question or request
        context: Legal context for the query
        privacy_level: Privacy protection level
        
    Returns:
        AI response with metadata
    """
    return bagel_service.legal_query(query, context, privacy_level)

if __name__ == "__main__":
    # Test the service
    print("🚀 Testing Bagel RL Legal Service")
    print("=" * 50)
    
    # Check status
    status = get_bagel_status()
    print(f"📊 Service Status: {status}")
    
    # Test query
    test_query = "What are the key elements of a prima facie employment discrimination case under Title VII?"
    print(f"\n🔍 Test Query: {test_query}")
    
    result = query_bagel_legal_ai(test_query, "employment_law")
    print(f"\n💬 Response: {result['response'][:200]}...")
    print(f"✅ Success: {result['success']}")
    print(f"🛡️ Privacy Protected: {result['privacy_protected']}")
    print(f"🎯 Confidence: {result['confidence_score']}")
    print(f"📍 Source: {result['source']}")