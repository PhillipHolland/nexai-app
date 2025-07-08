#!/usr/bin/env python3
"""
Specialized Contract Analysis Service with Bagel RL Integration
Advanced contract review, risk assessment, and clause analysis
"""

import os
import json
import logging
import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import hashlib

logger = logging.getLogger(__name__)

# Import Bagel RL service
try:
    from bagel_service import query_bagel_legal_ai
    BAGEL_AVAILABLE = True
except ImportError:
    BAGEL_AVAILABLE = False
    logger.warning("Bagel RL service not available for contract analysis")

@dataclass
class ContractClause:
    """Represents a contract clause with metadata"""
    clause_id: str
    clause_type: str
    text: str
    risk_level: str
    concerns: List[str]
    recommendations: List[str]
    standard_language: Optional[str] = None
    position_start: int = 0
    position_end: int = 0

@dataclass
class ContractAnalysisResult:
    """Complete contract analysis result"""
    contract_id: str
    contract_type: str
    overall_risk_score: float
    key_terms: Dict[str, Any]
    clauses: List[ContractClause]
    missing_clauses: List[str]
    red_flags: List[str]
    recommendations: List[str]
    compliance_issues: List[str]
    financial_terms: Dict[str, Any]
    timeline_analysis: Dict[str, Any]
    bagel_insights: Optional[Dict[str, Any]] = None

class ContractAnalysisService:
    """Specialized contract analysis with Bagel RL enhancement"""
    
    def __init__(self):
        self.standard_clauses = self._load_standard_clauses()
        self.risk_patterns = self._load_risk_patterns()
        self.contract_types = {
            'employment': 'Employment Agreement',
            'service': 'Service Agreement',
            'sales': 'Sales Contract',
            'lease': 'Lease Agreement',
            'nda': 'Non-Disclosure Agreement',
            'partnership': 'Partnership Agreement',
            'licensing': 'Licensing Agreement',
            'consulting': 'Consulting Agreement',
            'construction': 'Construction Contract',
            'merger': 'Merger & Acquisition Agreement'
        }
        
    def analyze_contract(self, contract_text: str, contract_type: str = None, 
                        analysis_depth: str = "comprehensive") -> ContractAnalysisResult:
        """Perform comprehensive contract analysis with Bagel RL"""
        try:
            logger.info(f"Starting contract analysis - Type: {contract_type}, Depth: {analysis_depth}")
            
            # Generate contract ID
            contract_id = hashlib.md5(contract_text.encode()).hexdigest()[:12]
            
            # 1. Detect contract type if not provided
            if not contract_type:
                contract_type = self._detect_contract_type(contract_text)
            
            # 2. Extract key terms and financial information
            key_terms = self._extract_key_terms(contract_text)
            financial_terms = self._extract_financial_terms(contract_text)
            
            # 3. Identify and analyze clauses
            clauses = self._identify_clauses(contract_text, contract_type)
            
            # 4. Risk assessment
            risk_score, red_flags = self._assess_risk(contract_text, clauses)
            
            # 5. Check for missing standard clauses
            missing_clauses = self._check_missing_clauses(contract_text, contract_type)
            
            # 6. Timeline analysis
            timeline_analysis = self._analyze_timeline(contract_text)
            
            # 7. Compliance check
            compliance_issues = self._check_compliance(contract_text, contract_type)
            
            # 8. Generate recommendations
            recommendations = self._generate_recommendations(clauses, missing_clauses, red_flags)
            
            # 9. Enhanced analysis with Bagel RL
            bagel_insights = None
            if BAGEL_AVAILABLE:
                bagel_insights = self._enhance_with_bagel_rl(
                    contract_text, contract_type, key_terms, clauses, analysis_depth
                )
            
            # Compile results
            result = ContractAnalysisResult(
                contract_id=contract_id,
                contract_type=contract_type,
                overall_risk_score=risk_score,
                key_terms=key_terms,
                clauses=clauses,
                missing_clauses=missing_clauses,
                red_flags=red_flags,
                recommendations=recommendations,
                compliance_issues=compliance_issues,
                financial_terms=financial_terms,
                timeline_analysis=timeline_analysis,
                bagel_insights=bagel_insights
            )
            
            logger.info(f"Contract analysis completed - Risk Score: {risk_score}")
            return result
            
        except Exception as e:
            logger.error(f"Contract analysis failed: {e}")
            raise
    
    def _detect_contract_type(self, contract_text: str) -> str:
        """Detect contract type based on content analysis"""
        text_lower = contract_text.lower()
        
        # Contract type indicators
        type_indicators = {
            'employment': ['employment', 'employee', 'salary', 'benefits', 'termination', 'job duties'],
            'service': ['services', 'service provider', 'deliverables', 'scope of work'],
            'sales': ['purchase', 'sale', 'goods', 'delivery', 'payment terms'],
            'lease': ['lease', 'rent', 'tenant', 'landlord', 'premises', 'monthly payment'],
            'nda': ['confidential', 'non-disclosure', 'proprietary information', 'confidentiality'],
            'partnership': ['partnership', 'partners', 'profit sharing', 'joint venture'],
            'licensing': ['license', 'intellectual property', 'royalty', 'licensed technology'],
            'consulting': ['consultant', 'consulting services', 'advisory', 'expertise'],
            'construction': ['construction', 'contractor', 'building', 'materials', 'completion date'],
            'merger': ['merger', 'acquisition', 'purchase price', 'due diligence', 'closing']
        }
        
        scores = {}
        for contract_type, indicators in type_indicators.items():
            score = sum(1 for indicator in indicators if indicator in text_lower)
            scores[contract_type] = score
        
        # Return type with highest score, or 'general' if unclear
        if scores:
            detected_type = max(scores, key=scores.get)
            if scores[detected_type] > 0:
                return detected_type
        
        return 'general'
    
    def _extract_key_terms(self, contract_text: str) -> Dict[str, Any]:
        """Extract key contract terms and parties"""
        key_terms = {
            'parties': [],
            'effective_date': None,
            'termination_date': None,
            'governing_law': None,
            'jurisdiction': None,
            'payment_terms': [],
            'deliverables': [],
            'obligations': []
        }
        
        # Extract parties
        party_patterns = [
            r'between\s+([A-Z][A-Za-z\s&,.]+?)(?:\s+(?:and|,)|\s+\()',
            r'Party\s+(?:A|1|One):\s*([A-Z][A-Za-z\s&,.]+?)(?:\n|$)',
            r'Company:\s*([A-Z][A-Za-z\s&,.]+?)(?:\n|$)',
            r'Client:\s*([A-Z][A-Za-z\s&,.]+?)(?:\n|$)'
        ]
        
        for pattern in party_patterns:
            matches = re.findall(pattern, contract_text, re.IGNORECASE)
            for match in matches:
                party = match.strip().rstrip(',').rstrip('.')
                if party and len(party) < 100:  # Reasonable length check
                    key_terms['parties'].append(party)
        
        # Remove duplicates and clean
        key_terms['parties'] = list(set(key_terms['parties']))[:5]  # Max 5 parties
        
        # Extract dates
        date_patterns = [
            r'effective\s+(?:date|as\s+of):\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
            r'dated\s+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
            r'this\s+\d+\w*\s+day\s+of\s+(\w+),?\s+(\d{4})'
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, contract_text, re.IGNORECASE)
            if matches:
                key_terms['effective_date'] = matches[0] if isinstance(matches[0], str) else ' '.join(matches[0])
                break
        
        # Extract governing law
        gov_law_patterns = [
            r'governed\s+by\s+(?:the\s+)?laws?\s+of\s+([A-Za-z\s]+?)(?:\.|,|\n)',
            r'laws?\s+of\s+(?:the\s+)?([A-Za-z\s]+?)\s+shall\s+govern',
            r'subject\s+to\s+(?:the\s+)?laws?\s+of\s+([A-Za-z\s]+?)(?:\.|,|\n)'
        ]
        
        for pattern in gov_law_patterns:
            matches = re.findall(pattern, contract_text, re.IGNORECASE)
            if matches:
                key_terms['governing_law'] = matches[0].strip()
                break
        
        return key_terms
    
    def _extract_financial_terms(self, contract_text: str) -> Dict[str, Any]:
        """Extract financial terms and payment information"""
        financial_terms = {
            'total_value': None,
            'payment_schedule': [],
            'currency': 'USD',
            'payment_methods': [],
            'late_fees': None,
            'penalties': [],
            'expenses': []
        }
        
        # Extract monetary amounts
        amount_patterns = [
            r'\$([0-9,]+(?:\.[0-9]{2})?)',
            r'([0-9,]+(?:\.[0-9]{2})?)\s+dollars?',
            r'USD\s+([0-9,]+(?:\.[0-9]{2})?)'
        ]
        
        amounts = []
        for pattern in amount_patterns:
            matches = re.findall(pattern, contract_text, re.IGNORECASE)
            amounts.extend(matches)
        
        if amounts:
            # Convert to float and find largest (likely total value)
            numeric_amounts = []
            for amount in amounts:
                try:
                    numeric_amounts.append(float(amount.replace(',', '')))
                except:
                    continue
            
            if numeric_amounts:
                financial_terms['total_value'] = max(numeric_amounts)
        
        # Extract payment terms
        payment_patterns = [
            r'payment\s+(?:due|terms?):\s*([^.\n]+)',
            r'(?:net\s+)?(\d+)\s+days?',
            r'monthly\s+payment\s+of\s+\$([0-9,]+(?:\.[0-9]{2})?)',
            r'installments?\s+of\s+\$([0-9,]+(?:\.[0-9]{2})?)'
        ]
        
        for pattern in payment_patterns:
            matches = re.findall(pattern, contract_text, re.IGNORECASE)
            financial_terms['payment_schedule'].extend(matches)
        
        # Extract late fees and penalties
        penalty_patterns = [
            r'late\s+fee\s+of\s+\$([0-9,]+(?:\.[0-9]{2})?)',
            r'penalty\s+of\s+\$([0-9,]+(?:\.[0-9]{2})?)',
            r'interest\s+(?:rate\s+)?(?:of\s+)?(\d+(?:\.\d+)?%?)'
        ]
        
        for pattern in penalty_patterns:
            matches = re.findall(pattern, contract_text, re.IGNORECASE)
            financial_terms['penalties'].extend(matches)
        
        return financial_terms
    
    def _identify_clauses(self, contract_text: str, contract_type: str) -> List[ContractClause]:
        """Identify and analyze contract clauses"""
        clauses = []
        
        # Common clause patterns
        clause_patterns = {
            'termination': [
                r'termination[^.]*(?:\.|$)',
                r'end\s+(?:of\s+)?(?:this\s+)?(?:agreement|contract)[^.]*(?:\.|$)',
                r'expire[^.]*(?:\.|$)'
            ],
            'confidentiality': [
                r'confidential[^.]*(?:\.|$)',
                r'proprietary\s+information[^.]*(?:\.|$)',
                r'non-disclosure[^.]*(?:\.|$)'
            ],
            'liability': [
                r'liability[^.]*(?:\.|$)',
                r'damages[^.]*(?:\.|$)',
                r'indemnif[^.]*(?:\.|$)'
            ],
            'intellectual_property': [
                r'intellectual\s+property[^.]*(?:\.|$)',
                r'copyright[^.]*(?:\.|$)',
                r'patent[^.]*(?:\.|$)',
                r'trademark[^.]*(?:\.|$)'
            ],
            'dispute_resolution': [
                r'dispute[^.]*(?:\.|$)',
                r'arbitration[^.]*(?:\.|$)',
                r'mediation[^.]*(?:\.|$)'
            ],
            'force_majeure': [
                r'force\s+majeure[^.]*(?:\.|$)',
                r'act\s+of\s+god[^.]*(?:\.|$)',
                r'unforeseeable[^.]*(?:\.|$)'
            ],
            'assignment': [
                r'assignment[^.]*(?:\.|$)',
                r'transfer[^.]*(?:\.|$)',
                r'delegate[^.]*(?:\.|$)'
            ],
            'entire_agreement': [
                r'entire\s+agreement[^.]*(?:\.|$)',
                r'complete\s+agreement[^.]*(?:\.|$)',
                r'supersede[^.]*(?:\.|$)'
            ]
        }
        
        # Find clauses in text
        for clause_type, patterns in clause_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, contract_text, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    clause_text = match.group(0)
                    
                    # Analyze risk for this clause
                    risk_level, concerns, recommendations = self._analyze_clause_risk(
                        clause_text, clause_type, contract_type
                    )
                    
                    clause = ContractClause(
                        clause_id=f"{clause_type}_{len(clauses)}",
                        clause_type=clause_type,
                        text=clause_text,
                        risk_level=risk_level,
                        concerns=concerns,
                        recommendations=recommendations,
                        position_start=match.start(),
                        position_end=match.end()
                    )
                    
                    clauses.append(clause)
        
        return clauses
    
    def _analyze_clause_risk(self, clause_text: str, clause_type: str, 
                           contract_type: str) -> tuple[str, List[str], List[str]]:
        """Analyze risk level of a specific clause"""
        concerns = []
        recommendations = []
        risk_level = "low"
        
        clause_lower = clause_text.lower()
        
        # Risk indicators by clause type
        risk_indicators = {
            'termination': {
                'high': ['immediate termination', 'without cause', 'sole discretion'],
                'medium': ['30 days notice', 'material breach'],
                'concerns': ['May allow arbitrary termination', 'Notice period too short'],
                'recommendations': ['Add specific termination reasons', 'Extend notice period']
            },
            'liability': {
                'high': ['unlimited liability', 'consequential damages', 'punitive damages'],
                'medium': ['limited liability', 'actual damages'],
                'concerns': ['Excessive liability exposure', 'Unclear damage calculation'],
                'recommendations': ['Cap liability amount', 'Exclude consequential damages']
            },
            'confidentiality': {
                'high': ['perpetual confidentiality', 'all information confidential'],
                'medium': ['5 years', 'specific information'],
                'concerns': ['Overly broad confidentiality', 'Unclear exceptions'],
                'recommendations': ['Define confidential information', 'Add standard exceptions']
            }
        }
        
        if clause_type in risk_indicators:
            indicators = risk_indicators[clause_type]
            
            # Check for high risk indicators
            for indicator in indicators.get('high', []):
                if indicator in clause_lower:
                    risk_level = "high"
                    concerns.extend(indicators.get('concerns', []))
                    recommendations.extend(indicators.get('recommendations', []))
                    break
            
            # Check for medium risk indicators if not high
            if risk_level != "high":
                for indicator in indicators.get('medium', []):
                    if indicator in clause_lower:
                        risk_level = "medium"
                        break
        
        return risk_level, concerns, recommendations
    
    def _assess_risk(self, contract_text: str, clauses: List[ContractClause]) -> tuple[float, List[str]]:
        """Assess overall contract risk and identify red flags"""
        red_flags = []
        risk_score = 0.0
        
        # Clause-based risk assessment
        high_risk_clauses = [c for c in clauses if c.risk_level == "high"]
        medium_risk_clauses = [c for c in clauses if c.risk_level == "medium"]
        
        risk_score += len(high_risk_clauses) * 3.0
        risk_score += len(medium_risk_clauses) * 1.5
        
        # Red flag patterns
        red_flag_patterns = [
            (r'without\s+cause', 'Termination without cause allowed'),
            (r'sole\s+discretion', 'Terms subject to sole discretion'),
            (r'unlimited\s+liability', 'Unlimited liability exposure'),
            (r'perpetual', 'Perpetual obligations'),
            (r'non-compete', 'Non-compete restrictions'),
            (r'exclusive\s+rights', 'Exclusive rights granted'),
            (r'no\s+warranty', 'No warranty provided'),
            (r'as\s+is', 'Product/service provided "as is"'),
            (r'waive\s+(?:all\s+)?rights', 'Rights waiver clause'),
            (r'automatic\s+renewal', 'Automatic renewal terms')
        ]
        
        for pattern, flag_description in red_flag_patterns:
            if re.search(pattern, contract_text, re.IGNORECASE):
                red_flags.append(flag_description)
                risk_score += 2.0
        
        # Normalize risk score (0-100)
        risk_score = min(risk_score * 5, 100)
        
        return risk_score, red_flags
    
    def _check_missing_clauses(self, contract_text: str, contract_type: str) -> List[str]:
        """Check for missing standard clauses"""
        missing_clauses = []
        
        # Standard clauses by contract type
        required_clauses = {
            'employment': [
                'termination', 'confidentiality', 'intellectual_property', 
                'dispute_resolution', 'entire_agreement'
            ],
            'service': [
                'scope_of_work', 'payment_terms', 'termination', 'liability',
                'intellectual_property', 'dispute_resolution'
            ],
            'nda': [
                'confidentiality', 'permitted_use', 'return_of_information',
                'duration', 'dispute_resolution'
            ],
            'general': [
                'termination', 'dispute_resolution', 'entire_agreement',
                'governing_law'
            ]
        }
        
        # Check for required clauses
        required = required_clauses.get(contract_type, required_clauses['general'])
        
        clause_check_patterns = {
            'termination': r'terminat',
            'confidentiality': r'confidential',
            'intellectual_property': r'intellectual\s+property',
            'dispute_resolution': r'dispute|arbitration|mediation',
            'entire_agreement': r'entire\s+agreement',
            'governing_law': r'governed\s+by|governing\s+law',
            'scope_of_work': r'scope\s+of\s+work|deliverables',
            'payment_terms': r'payment|fee|compensation',
            'liability': r'liability|damages|indemnif',
            'permitted_use': r'permitted\s+use|authorized\s+use',
            'return_of_information': r'return|destroy|information',
            'duration': r'duration|term|period'
        }
        
        for clause_name in required:
            if clause_name in clause_check_patterns:
                pattern = clause_check_patterns[clause_name]
                if not re.search(pattern, contract_text, re.IGNORECASE):
                    missing_clauses.append(clause_name.replace('_', ' ').title())
        
        return missing_clauses
    
    def _analyze_timeline(self, contract_text: str) -> Dict[str, Any]:
        """Analyze contract timeline and key dates"""
        timeline = {
            'start_date': None,
            'end_date': None,
            'key_milestones': [],
            'notice_periods': [],
            'renewal_terms': None
        }
        
        # Extract dates
        date_patterns = [
            r'effective\s+(?:date|as\s+of):\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
            r'term\s+(?:shall\s+)?(?:begin|commence)\s+(?:on\s+)?(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
            r'expires?\s+(?:on\s+)?(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
            r'until\s+(\d{1,2}[/-]\d{1,2}[/-]\d{4})'
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, contract_text, re.IGNORECASE)
            if matches:
                if not timeline['start_date']:
                    timeline['start_date'] = matches[0]
                elif not timeline['end_date']:
                    timeline['end_date'] = matches[0]
        
        # Extract notice periods
        notice_patterns = [
            r'(\d+)\s+days?\s+(?:prior\s+)?notice',
            r'(\d+)\s+days?\s+advance\s+notice',
            r'notice\s+period\s+of\s+(\d+)\s+days?'
        ]
        
        for pattern in notice_patterns:
            matches = re.findall(pattern, contract_text, re.IGNORECASE)
            timeline['notice_periods'].extend(matches)
        
        # Extract renewal terms
        renewal_patterns = [
            r'automatic(?:ally)?\s+renew',
            r'renew\s+for\s+(?:an\s+)?additional\s+(\d+)\s+(?:year|month)',
            r'renewal\s+term\s+of\s+(\d+)\s+(?:year|month)'
        ]
        
        for pattern in renewal_patterns:
            matches = re.findall(pattern, contract_text, re.IGNORECASE)
            if matches:
                timeline['renewal_terms'] = matches[0] if matches[0] else 'automatic'
        
        return timeline
    
    def _check_compliance(self, contract_text: str, contract_type: str) -> List[str]:
        """Check for compliance issues"""
        compliance_issues = []
        
        # General compliance checks
        if contract_type == 'employment':
            # Employment law compliance
            if 'at will' in contract_text.lower():
                compliance_issues.append('At-will employment may require state-specific disclaimers')
            
            if 'non-compete' in contract_text.lower():
                compliance_issues.append('Non-compete clauses have varying state law requirements')
        
        if contract_type == 'nda':
            # NDA compliance
            if 'return of information' not in contract_text.lower():
                compliance_issues.append('Missing return of confidential information clause')
        
        # General compliance issues
        if 'governing law' not in contract_text.lower():
            compliance_issues.append('Missing governing law clause')
        
        if 'dispute resolution' not in contract_text.lower():
            compliance_issues.append('Missing dispute resolution mechanism')
        
        return compliance_issues
    
    def _generate_recommendations(self, clauses: List[ContractClause], 
                                missing_clauses: List[str], red_flags: List[str]) -> List[str]:
        """Generate contract improvement recommendations"""
        recommendations = []
        
        # Clause-specific recommendations
        for clause in clauses:
            if clause.risk_level == "high":
                recommendations.append(f"Review {clause.clause_type} clause for excessive risk")
            recommendations.extend(clause.recommendations)
        
        # Missing clause recommendations
        for missing in missing_clauses:
            recommendations.append(f"Add {missing} clause for completeness")
        
        # Red flag recommendations
        for flag in red_flags:
            recommendations.append(f"Address red flag: {flag}")
        
        # General recommendations
        recommendations.extend([
            "Have contract reviewed by qualified legal counsel",
            "Ensure all parties understand their obligations",
            "Keep signed copies in secure location",
            "Set calendar reminders for key dates"
        ])
        
        return list(set(recommendations))  # Remove duplicates
    
    def _enhance_with_bagel_rl(self, contract_text: str, contract_type: str,
                              key_terms: Dict[str, Any], clauses: List[ContractClause],
                              analysis_depth: str) -> Optional[Dict[str, Any]]:
        """Enhance contract analysis with Bagel RL"""
        try:
            if not BAGEL_AVAILABLE:
                return None
            
            # Prepare context for Bagel RL
            context = f"""
            Contract Analysis Request:
            
            Contract Type: {contract_type}
            Analysis Depth: {analysis_depth}
            Contract Length: {len(contract_text)} characters
            
            Key Terms Identified:
            - Parties: {', '.join(key_terms.get('parties', []))}
            - Governing Law: {key_terms.get('governing_law', 'Not specified')}
            - Effective Date: {key_terms.get('effective_date', 'Not specified')}
            
            Clauses Found: {len(clauses)}
            High Risk Clauses: {len([c for c in clauses if c.risk_level == 'high'])}
            
            Please provide:
            1. Strategic contract analysis and key insights
            2. Negotiation recommendations and leverage points
            3. Industry-specific considerations for {contract_type} contracts
            4. Potential legal risks and mitigation strategies
            5. Suggested contract improvements and alternatives
            
            Contract text (first 4000 characters):
            {contract_text[:4000]}
            """
            
            # Query Bagel RL for enhanced analysis
            result = query_bagel_legal_ai(
                query=context,
                context=f"contract_analysis_{contract_type}",
                privacy_level="attorney_client"
            )
            
            if result.get('success', False):
                return {
                    'success': True,
                    'strategic_analysis': result['response'],
                    'confidence_score': result.get('confidence_score', 0),
                    'processing_time': result.get('processing_time', 0),
                    'source': 'bagel_rl',
                    'analysis_type': 'enhanced_contract_analysis'
                }
            else:
                return {'success': False, 'error': 'Bagel RL analysis failed'}
                
        except Exception as e:
            logger.error(f"Bagel RL enhancement failed: {e}")
            return {'success': False, 'error': f'Enhancement failed: {str(e)}'}
    
    def _load_standard_clauses(self) -> Dict[str, Dict[str, str]]:
        """Load standard clause templates"""
        return {
            'termination': {
                'standard': 'Either party may terminate this agreement with thirty (30) days written notice.',
                'enhanced': 'Either party may terminate this agreement with thirty (30) days written notice for convenience, or immediately for material breach that remains uncured for ten (10) days after written notice.'
            },
            'confidentiality': {
                'standard': 'The parties agree to maintain confidentiality of all proprietary information.',
                'enhanced': 'Each party agrees to maintain in confidence all Confidential Information received from the other party and to use such information solely for the purposes of this Agreement.'
            },
            'liability': {
                'standard': 'Each party shall be liable for damages caused by their breach of this agreement.',
                'enhanced': 'IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, REGARDLESS OF THE THEORY OF LIABILITY.'
            }
        }
    
    def _load_risk_patterns(self) -> Dict[str, List[str]]:
        """Load risk assessment patterns"""
        return {
            'high_risk': [
                'without cause', 'sole discretion', 'unlimited liability',
                'perpetual', 'irrevocable', 'waive all rights'
            ],
            'medium_risk': [
                'material breach', 'reasonable notice', 'limited liability',
                'specific performance', 'injunctive relief'
            ],
            'low_risk': [
                'mutual agreement', 'good faith', 'reasonable efforts',
                'standard industry practice'
            ]
        }

# Global instance
contract_analysis_service = ContractAnalysisService()

def analyze_contract_comprehensive(contract_text: str, contract_type: str = None,
                                 analysis_depth: str = "comprehensive") -> Dict[str, Any]:
    """Main function for comprehensive contract analysis"""
    try:
        result = contract_analysis_service.analyze_contract(
            contract_text=contract_text,
            contract_type=contract_type,
            analysis_depth=analysis_depth
        )
        
        # Convert dataclass to dict for JSON serialization
        return {
            'success': True,
            'contract_id': result.contract_id,
            'contract_type': result.contract_type,
            'overall_risk_score': result.overall_risk_score,
            'key_terms': result.key_terms,
            'clauses': [
                {
                    'clause_id': clause.clause_id,
                    'clause_type': clause.clause_type,
                    'text': clause.text,
                    'risk_level': clause.risk_level,
                    'concerns': clause.concerns,
                    'recommendations': clause.recommendations,
                    'standard_language': clause.standard_language
                }
                for clause in result.clauses
            ],
            'missing_clauses': result.missing_clauses,
            'red_flags': result.red_flags,
            'recommendations': result.recommendations,
            'compliance_issues': result.compliance_issues,
            'financial_terms': result.financial_terms,
            'timeline_analysis': result.timeline_analysis,
            'bagel_insights': result.bagel_insights,
            'analysis_timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Contract analysis failed: {e}")
        return {
            'success': False,
            'error': f'Contract analysis failed: {str(e)}'
        }

if __name__ == "__main__":
    # Test the service
    print("🔍 Testing Contract Analysis Service")
    print("=" * 50)
    
    # Test employment contract
    sample_contract = """
    EMPLOYMENT AGREEMENT
    
    This Employment Agreement is entered into between ABC Corporation ("Company") 
    and John Smith ("Employee") effective January 1, 2024.
    
    1. Position: Software Engineer
    2. Salary: $85,000 per year
    3. Benefits: Health insurance, 401k matching
    4. Termination: Either party may terminate without cause with 30 days notice
    5. Confidentiality: Employee agrees to maintain confidentiality of proprietary information
    6. Intellectual Property: All work product belongs to Company
    
    This agreement is governed by the laws of California.
    """
    
    result = analyze_contract_comprehensive(sample_contract, "employment")
    
    print(f"Analysis Success: {result['success']}")
    if result['success']:
        print(f"Contract Type: {result['contract_type']}")
        print(f"Risk Score: {result['overall_risk_score']}")
        print(f"Clauses Found: {len(result['clauses'])}")
        print(f"Red Flags: {len(result['red_flags'])}")
        print(f"Missing Clauses: {len(result['missing_clauses'])}")
        
        if result['bagel_insights']:
            print(f"Bagel RL Analysis: {result['bagel_insights']['success']}")
    else:
        print(f"Error: {result['error']}")