"""
Privacy-First Legal AI Service
Automatically anonymizes sensitive data before AI processing
"""
import re
import hashlib
import json
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
from enum import Enum

class PrivacyLevel(Enum):
    PUBLIC = "public"
    CONFIDENTIAL = "confidential" 
    PRIVILEGED = "privileged"
    ATTORNEY_CLIENT = "attorney_client"

class SensitivityType(Enum):
    PERSON_NAME = "person_name"
    COMPANY_NAME = "company_name"
    ADDRESS = "address"
    PHONE = "phone"
    EMAIL = "email"
    SSN = "ssn"
    FINANCIAL = "financial"
    MEDICAL = "medical"
    CASE_NUMBER = "case_number"
    LEGAL_MATTER = "legal_matter"

@dataclass
class AnonymizationResult:
    anonymized_text: str
    entity_mapping: Dict[str, str]
    privacy_level: PrivacyLevel
    redacted_entities: List[str]
    confidence_score: float

class PrivacyFirstAI:
    """
    AI service that automatically anonymizes sensitive data
    while preserving legal context for analysis
    """
    
    def __init__(self, bagel_endpoint: str = None):
        self.bagel_endpoint = bagel_endpoint
        self.entity_cache = {}
        self.anonymization_patterns = self._load_anonymization_patterns()
    
    def _load_anonymization_patterns(self) -> Dict:
        """Load regex patterns for sensitive data detection"""
        return {
            SensitivityType.PERSON_NAME: [
                r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',  # John Smith
                r'\b[A-Z][a-z]+, [A-Z][a-z]+\b',  # Smith, John
            ],
            SensitivityType.COMPANY_NAME: [
                r'\b[A-Z][A-Za-z\s]+ (Corp|Inc|LLC|Ltd|Co)\b',
                r'\b[A-Z][A-Za-z\s]+ (Corporation|Company|Limited)\b',
            ],
            SensitivityType.ADDRESS: [
                r'\d+\s+[A-Za-z\s]+(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd)',
                r'\b\d{5}(-\d{4})?\b',  # ZIP codes
            ],
            SensitivityType.PHONE: [
                r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
                r'\(\d{3}\)\s*\d{3}[-.]?\d{4}',
            ],
            SensitivityType.EMAIL: [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            ],
            SensitivityType.SSN: [
                r'\b\d{3}-\d{2}-\d{4}\b',
                r'\b\d{9}\b',
            ],
            SensitivityType.FINANCIAL: [
                r'\$[\d,]+\.?\d*',  # Dollar amounts
                r'\b\d{13,19}\b',  # Credit card numbers
                r'\b\d{9,12}\b',   # Account numbers
            ],
        }
    
    def anonymize_for_ai_processing(
        self, 
        text: str, 
        context: str = "general",
        privacy_level: PrivacyLevel = PrivacyLevel.CONFIDENTIAL
    ) -> AnonymizationResult:
        """
        Anonymize text while preserving legal context for AI analysis
        """
        entity_mapping = {}
        anonymized_text = text
        redacted_entities = []
        
        # Detect and replace sensitive entities
        for sensitivity_type, patterns in self.anonymization_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, anonymized_text, re.IGNORECASE)
                for match in matches:
                    original = match.group()
                    anonymized = self._get_anonymized_replacement(
                        original, sensitivity_type, context
                    )
                    
                    # Store mapping for potential de-anonymization
                    entity_id = self._generate_entity_id(original, sensitivity_type)
                    entity_mapping[anonymized] = {
                        'original': original,
                        'type': sensitivity_type.value,
                        'entity_id': entity_id
                    }
                    
                    anonymized_text = anonymized_text.replace(original, anonymized)
                    redacted_entities.append(sensitivity_type.value)
        
        # Legal context preservation
        anonymized_text = self._preserve_legal_context(anonymized_text, context)
        
        confidence_score = self._calculate_anonymization_confidence(
            text, anonymized_text, entity_mapping
        )
        
        return AnonymizationResult(
            anonymized_text=anonymized_text,
            entity_mapping=entity_mapping,
            privacy_level=privacy_level,
            redacted_entities=list(set(redacted_entities)),
            confidence_score=confidence_score
        )
    
    def _get_anonymized_replacement(
        self, 
        original: str, 
        sensitivity_type: SensitivityType, 
        context: str
    ) -> str:
        """Generate context-appropriate anonymized replacement"""
        
        replacements = {
            SensitivityType.PERSON_NAME: {
                'plaintiff': '[PLAINTIFF]',
                'defendant': '[DEFENDANT]', 
                'client': '[CLIENT]',
                'witness': '[WITNESS]',
                'default': '[PARTY-{}]'
            },
            SensitivityType.COMPANY_NAME: {
                'corporate': '[ENTITY-{}]',
                'defendant': '[DEFENDANT-CORP]',
                'plaintiff': '[PLAINTIFF-CORP]',
                'default': '[COMPANY-{}]'
            },
            SensitivityType.ADDRESS: {
                'residence': '[ADDRESS-RESIDENCE]',
                'business': '[ADDRESS-BUSINESS]',
                'incident': '[LOCATION-INCIDENT]',
                'default': '[ADDRESS-REDACTED]'
            },
            SensitivityType.FINANCIAL: {
                'damages': '[AMOUNT-DAMAGES]',
                'settlement': '[AMOUNT-SETTLEMENT]',
                'salary': '[INCOME-AMOUNT]',
                'default': '[AMOUNT-REDACTED]'
            }
        }
        
        type_replacements = replacements.get(
            sensitivity_type, 
            {'default': f'[{sensitivity_type.value.upper()}-REDACTED]'}
        )
        
        # Use context-specific replacement if available
        for context_key, replacement in type_replacements.items():
            if context_key in context.lower():
                if '{}' in replacement:
                    entity_counter = self._get_entity_counter(sensitivity_type)
                    return replacement.format(entity_counter)
                return replacement
        
        # Default replacement
        default_replacement = type_replacements['default']
        if '{}' in default_replacement:
            entity_counter = self._get_entity_counter(sensitivity_type)
            return default_replacement.format(entity_counter)
        
        return default_replacement
    
    def _get_entity_counter(self, sensitivity_type: SensitivityType) -> str:
        """Get incrementing counter for entity type"""
        counter_key = f"{sensitivity_type.value}_counter"
        if counter_key not in self.entity_cache:
            self.entity_cache[counter_key] = 0
        self.entity_cache[counter_key] += 1
        return chr(64 + self.entity_cache[counter_key])  # A, B, C, etc.
    
    def _generate_entity_id(self, original: str, sensitivity_type: SensitivityType) -> str:
        """Generate consistent ID for entity across documents"""
        combined = f"{sensitivity_type.value}:{original.lower()}"
        return hashlib.md5(combined.encode()).hexdigest()[:8]
    
    def _preserve_legal_context(self, text: str, context: str) -> str:
        """Preserve important legal context markers"""
        
        # Preserve legal procedure terms
        legal_context_markers = {
            'motion': 'MOTION',
            'summary judgment': 'SUMMARY-JUDGMENT',
            'discovery': 'DISCOVERY',
            'deposition': 'DEPOSITION',
            'settlement': 'SETTLEMENT',
            'trial': 'TRIAL',
            'appeal': 'APPEAL'
        }
        
        for marker, replacement in legal_context_markers.items():
            text = re.sub(
                rf'\b{marker}\b', 
                f'[{replacement}]', 
                text, 
                flags=re.IGNORECASE
            )
        
        return text
    
    def _calculate_anonymization_confidence(
        self, 
        original: str, 
        anonymized: str, 
        entity_mapping: Dict
    ) -> float:
        """Calculate confidence score for anonymization quality"""
        
        # Basic metrics
        entities_found = len(entity_mapping)
        text_length = len(original)
        
        # More entities found in longer text = higher confidence
        base_confidence = min(0.9, entities_found / (text_length / 100))
        
        # Penalty for potential missed entities (heuristic)
        potential_names = len(re.findall(r'\b[A-Z][a-z]+\b', original))
        anonymized_names = len(re.findall(r'\b[A-Z][a-z]+\b', anonymized))
        
        if potential_names > anonymized_names:
            missed_ratio = (potential_names - anonymized_names) / potential_names
            base_confidence *= (1 - missed_ratio * 0.3)
        
        return round(base_confidence, 3)
    
    def secure_ai_query(
        self, 
        query: str, 
        context: str = "legal_research",
        privacy_level: PrivacyLevel = PrivacyLevel.CONFIDENTIAL
    ) -> Dict[str, Any]:
        """
        Process AI query with automatic anonymization
        """
        
        # Step 1: Anonymize the query
        anonymization_result = self.anonymize_for_ai_processing(
            query, context, privacy_level
        )
        
        # Step 2: Send anonymized query to AI service
        if self.bagel_endpoint:
            ai_response = self._query_bagel_ai(
                anonymization_result.anonymized_text,
                context
            )
        else:
            # Fallback to standard AI processing
            ai_response = self._process_with_standard_ai(
                anonymization_result.anonymized_text
            )
        
        # Step 3: Return results with privacy metadata
        return {
            'response': ai_response,
            'privacy_metadata': {
                'anonymization_confidence': anonymization_result.confidence_score,
                'entities_redacted': anonymization_result.redacted_entities,
                'privacy_level': privacy_level.value,
                'can_deanonymize': bool(anonymization_result.entity_mapping)
            },
            'original_query_hash': hashlib.sha256(query.encode()).hexdigest()[:16]
        }
    
    def _query_bagel_ai(self, anonymized_query: str, context: str) -> str:
        """Send anonymized query to Bagel RL endpoint"""
        # Implementation for Bagel RL API call
        # This will use the trained model for privacy-aware responses
        return f"Bagel AI Response to: {anonymized_query}"
    
    def _process_with_standard_ai(self, anonymized_query: str) -> str:
        """Fallback AI processing for anonymized queries"""
        return f"Standard AI Response to: {anonymized_query}"

# Example usage
if __name__ == "__main__":
    privacy_ai = PrivacyFirstAI()
    
    # Example: Anonymize sensitive legal query
    sensitive_query = """
    My client John Smith was injured in a car accident involving ABC Corporation's 
    delivery truck. The accident occurred at 123 Main Street in downtown Chicago. 
    John's medical bills total $85,000 and he earns $120,000 annually as an engineer.
    We need to research similar cases for settlement negotiations.
    """
    
    result = privacy_ai.secure_ai_query(
        sensitive_query,
        context="personal_injury_research",
        privacy_level=PrivacyLevel.ATTORNEY_CLIENT
    )
    
    print("Privacy-Enhanced AI Query Result:")
    print(f"Response: {result['response']}")
    print(f"Privacy Confidence: {result['privacy_metadata']['anonymization_confidence']}")
    print(f"Entities Protected: {result['privacy_metadata']['entities_redacted']}")