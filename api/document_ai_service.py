#!/usr/bin/env python3
"""
Document AI Service - Enhanced document processing with Bagel RL integration
Handles document upload, processing, and AI-powered analysis
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import hashlib
import mimetypes
import re
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

# Import dependencies with fallbacks
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("PyPDF2 not available - PDF processing disabled")

try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logger.warning("python-docx not available - DOCX processing disabled")

try:
    from bagel_service import query_bagel_legal_ai
    BAGEL_AVAILABLE = True
except ImportError:
    BAGEL_AVAILABLE = False
    logger.warning("Bagel service not available - using fallback analysis")

class DocumentAIService:
    """
    Enhanced document processing service with Bagel RL integration
    """
    
    def __init__(self, upload_folder: str = "/tmp/lexai_uploads"):
        self.upload_folder = upload_folder
        self.allowed_extensions = {
            'pdf', 'docx', 'doc', 'txt', 'rtf'
        }
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        
        # Create upload directory if it doesn't exist
        os.makedirs(upload_folder, exist_ok=True)
        
    def is_allowed_file(self, filename: str) -> bool:
        """Check if file extension is allowed"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions
    
    def detect_pii(self, content: str) -> Dict[str, Any]:
        """Basic PII detection before sending to Bagel RL"""
        pii_patterns = {
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b',
            'phone': r'\b\d{3}-\d{3}-\d{4}\b|\b\(\d{3}\)\s*\d{3}-\d{4}\b',
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'credit_card': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
            'address': r'\b\d+\s+[A-Za-z0-9\s]+(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Court|Ct|Place|Pl)\b'
        }
        
        detected_pii = {}
        for pii_type, pattern in pii_patterns.items():
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                detected_pii[pii_type] = len(matches)
        
        return {
            'has_pii': bool(detected_pii),
            'pii_types': list(detected_pii.keys()),
            'pii_counts': detected_pii,
            'risk_level': 'high' if len(detected_pii) > 2 else 'medium' if detected_pii else 'low'
        }
    
    def extract_text_from_file(self, file_path: str, filename: str) -> Dict[str, Any]:
        """Extract text content from uploaded document"""
        try:
            file_extension = filename.rsplit('.', 1)[1].lower()
            content = ""
            
            if file_extension == 'pdf':
                if not PDF_AVAILABLE:
                    return {
                        'success': False,
                        'error': 'PDF processing not available. Please install PyPDF2.'
                    }
                content = self._extract_pdf_text(file_path)
            elif file_extension in ['docx', 'doc']:
                if not DOCX_AVAILABLE:
                    return {
                        'success': False,
                        'error': 'DOCX processing not available. Please install python-docx.'
                    }
                content = self._extract_docx_text(file_path)
            elif file_extension == 'txt':
                content = self._extract_txt_text(file_path)
            else:
                return {
                    'success': False,
                    'error': f'Unsupported file type: {file_extension}'
                }
            
            # Detect PII in content
            pii_analysis = self.detect_pii(content)
            
            return {
                'success': True,
                'content': content,
                'word_count': len(content.split()),
                'char_count': len(content),
                'file_type': file_extension,
                'pii_analysis': pii_analysis
            }
            
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return {
                'success': False,
                'error': f'Failed to extract text: {str(e)}'
            }
    
    def _extract_pdf_text(self, file_path: str) -> str:
        """Extract text from PDF file"""
        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            raise
        return text.strip()
    
    def _extract_docx_text(self, file_path: str) -> str:
        """Extract text from DOCX file"""
        try:
            doc = docx.Document(file_path)
            text = []
            for paragraph in doc.paragraphs:
                text.append(paragraph.text)
            return '\n'.join(text)
        except Exception as e:
            logger.error(f"DOCX extraction error: {e}")
            raise
    
    def _extract_txt_text(self, file_path: str) -> str:
        """Extract text from TXT file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(file_path, 'r', encoding='latin-1') as file:
                return file.read()
    
    def classify_document_type(self, content: str, filename: str) -> Dict[str, Any]:
        """Use Bagel RL to classify document type and extract key information"""
        try:
            if not BAGEL_AVAILABLE:
                return self._fallback_classification(content, filename)
            
            # Create classification query
            classification_query = f"""
            Analyze this legal document and classify its type. Document filename: {filename}
            
            Document content preview (first 2000 characters):
            {content[:2000]}
            
            Please identify:
            1. Document type (contract, motion, brief, correspondence, etc.)
            2. Practice area (corporate, litigation, family, etc.)
            3. Key parties mentioned
            4. Important dates or deadlines
            5. Priority level (high, medium, low)
            6. Recommended next actions
            """
            
            # Query Bagel RL for document classification
            result = query_bagel_legal_ai(
                query=classification_query,
                context="document_analysis",
                privacy_level="attorney_client"
            )
            
            if result.get('success', False):
                return {
                    'success': True,
                    'classification': result['response'],
                    'confidence': result.get('confidence_score', 0),
                    'source': result.get('source', 'bagel_rl')
                }
            else:
                return self._fallback_classification(content, filename)
                
        except Exception as e:
            logger.error(f"Document classification failed: {e}")
            return self._fallback_classification(content, filename)
    
    def _fallback_classification(self, content: str, filename: str) -> Dict[str, Any]:
        """Fallback document classification using keyword analysis"""
        content_lower = content.lower()
        filename_lower = filename.lower()
        
        # Document type classification
        doc_type = "unknown"
        if any(word in content_lower for word in ['contract', 'agreement', 'terms']):
            doc_type = "contract"
        elif any(word in content_lower for word in ['motion', 'court', 'petition']):
            doc_type = "motion"
        elif any(word in content_lower for word in ['brief', 'memorandum', 'argument']):
            doc_type = "brief"
        elif any(word in filename_lower for word in ['email', 'letter', 'correspondence']):
            doc_type = "correspondence"
        elif any(word in content_lower for word in ['invoice', 'bill', 'payment']):
            doc_type = "billing"
        
        # Practice area classification
        practice_area = "general"
        if any(word in content_lower for word in ['employment', 'discrimination', 'title vii']):
            practice_area = "employment_law"
        elif any(word in content_lower for word in ['patent', 'trademark', 'intellectual']):
            practice_area = "intellectual_property"
        elif any(word in content_lower for word in ['divorce', 'custody', 'family']):
            practice_area = "family_law"
        elif any(word in content_lower for word in ['corporate', 'merger', 'acquisition']):
            practice_area = "corporate_law"
        elif any(word in content_lower for word in ['constitutional', 'first amendment']):
            practice_area = "constitutional_law"
        
        return {
            'success': True,
            'classification': f"""**Document Classification (Fallback Analysis):**
            
**Document Type:** {doc_type.title()}
**Practice Area:** {practice_area.replace('_', ' ').title()}
**Analysis Method:** Keyword-based classification

**Recommendation:** For detailed AI analysis, ensure Bagel RL service is available for enhanced legal document processing.""",
            'confidence': 0.6,
            'source': 'fallback_keywords'
        }
    
    def analyze_document_with_bagel(self, content: str, filename: str, analysis_type: str = "general") -> Dict[str, Any]:
        """Perform detailed document analysis using Bagel RL"""
        try:
            if not BAGEL_AVAILABLE:
                return self._fallback_analysis(content, filename, analysis_type)
            
            # Create analysis query based on type
            if analysis_type == "contract":
                query = f"""
                Perform comprehensive contract analysis of this document:
                
                Filename: {filename}
                Content: {content[:8000]}
                
                Please provide:
                1. Contract type and purpose
                2. Key terms and clauses
                3. Parties and their obligations
                4. Important dates and deadlines
                5. Potential risks or issues
                6. Recommendations for review
                7. Missing or unclear provisions
                """
            elif analysis_type == "litigation":
                query = f"""
                Analyze this litigation document:
                
                Filename: {filename}
                Content: {content[:8000]}
                
                Please provide:
                1. Document type (motion, brief, discovery, etc.)
                2. Case summary and key issues
                3. Legal arguments presented
                4. Factual background
                5. Procedural status
                6. Critical deadlines
                7. Strategic recommendations
                """
            else:
                query = f"""
                Analyze this legal document comprehensively:
                
                Filename: {filename}
                Content: {content[:8000]}
                
                Please provide:
                1. Document summary
                2. Key legal issues
                3. Important facts and dates
                4. Potential concerns
                5. Recommended actions
                6. Compliance considerations
                """
            
            # Query Bagel RL
            result = query_bagel_legal_ai(
                query=query,
                context=f"document_analysis_{analysis_type}",
                privacy_level="attorney_client"
            )
            
            if result.get('success', False):
                return {
                    'success': True,
                    'analysis': result['response'],
                    'confidence': result.get('confidence_score', 0),
                    'processing_time': result.get('processing_time', 0),
                    'source': result.get('source', 'bagel_rl'),
                    'analysis_type': analysis_type
                }
            else:
                return self._fallback_analysis(content, filename, analysis_type)
                
        except Exception as e:
            logger.error(f"Document analysis failed: {e}")
            return self._fallback_analysis(content, filename, analysis_type)
    
    def _fallback_analysis(self, content: str, filename: str, analysis_type: str) -> Dict[str, Any]:
        """Fallback analysis when Bagel RL is not available"""
        content_lower = content.lower()
        
        if analysis_type == "contract":
            analysis = f"""**Contract Analysis (Fallback):**
            
**Document:** {filename}
**Analysis:** Basic keyword-based contract review

**Key Elements Found:**
• Parties: {self._extract_parties(content)}
• Dates: {self._extract_dates(content)}
• Financial Terms: {self._extract_amounts(content)}

**Recommendations:**
• Review with qualified legal counsel
• Verify all terms and conditions
• Check for missing standard clauses
• Ensure proper execution requirements

**Note:** This is a basic analysis. For comprehensive contract review, use the full Bagel RL service."""
        
        elif analysis_type == "litigation":
            analysis = f"""**Litigation Document Analysis (Fallback):**
            
**Document:** {filename}
**Analysis:** Basic litigation document review

**Key Elements:**
• Case References: {self._extract_case_references(content)}
• Deadlines: {self._extract_dates(content)}
• Parties: {self._extract_parties(content)}

**Recommendations:**
• Calendar all deadlines immediately
• Review procedural requirements
• Verify compliance with court rules
• Prepare response strategy

**Note:** This is a basic analysis. For detailed litigation analysis, use the full Bagel RL service."""
        
        else:
            analysis = f"""**General Document Analysis (Fallback):**
            
**Document:** {filename}
**Analysis:** Basic legal document review

**Key Information:**
• Document Length: {len(content.split())} words
• Key Dates: {self._extract_dates(content)}
• Parties Mentioned: {self._extract_parties(content)}

**Recommendations:**
• Classify document type for appropriate review
• Identify key legal issues
• Determine next action items
• Consult with relevant practice area expert

**Note:** This is a basic analysis. For comprehensive legal analysis, use the full Bagel RL service."""
        
        return {
            'success': True,
            'analysis': analysis,
            'confidence': 0.4,
            'processing_time': 0.1,
            'source': 'fallback_analysis',
            'analysis_type': analysis_type
        }
    
    def _extract_parties(self, content: str) -> str:
        """Extract potential party names from content"""
        # Look for common patterns: "X vs Y", "X and Y", "X, Y"
        patterns = [
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(?:vs?\.?|v\.?)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+and\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'([A-Z][A-Z\s]+(?:LLC|INC|CORP|LTD))'
        ]
        
        parties = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            parties.extend([match if isinstance(match, str) else ' '.join(match) for match in matches])
        
        return ', '.join(list(set(parties))[:3]) if parties else 'Not clearly identified'
    
    def _extract_dates(self, content: str) -> str:
        """Extract dates from content"""
        date_patterns = [
            r'\b\d{1,2}/\d{1,2}/\d{4}\b',
            r'\b\d{1,2}-\d{1,2}-\d{4}\b',
            r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b'
        ]
        
        dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            dates.extend(matches)
        
        return ', '.join(list(set(dates))[:3]) if dates else 'No dates found'
    
    def _extract_amounts(self, content: str) -> str:
        """Extract monetary amounts from content"""
        amount_patterns = [
            r'\$[\d,]+\.?\d*',
            r'USD\s+[\d,]+\.?\d*',
            r'(?:dollars?|USD)\s+[\d,]+\.?\d*'
        ]
        
        amounts = []
        for pattern in amount_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            amounts.extend(matches)
        
        return ', '.join(list(set(amounts))[:3]) if amounts else 'No amounts found'
    
    def _extract_case_references(self, content: str) -> str:
        """Extract case law references from content"""
        case_patterns = [
            r'[A-Z][a-z]+\s+v\.?\s+[A-Z][a-z]+',
            r'\d+\s+[A-Z][a-z]+\s+\d+',
            r'\b\d+\s+F\.\d+\s+\d+\b'
        ]
        
        cases = []
        for pattern in case_patterns:
            matches = re.findall(pattern, content)
            cases.extend(matches)
        
        return ', '.join(list(set(cases))[:3]) if cases else 'No case references found'
    
    def process_uploaded_document(self, file_data: bytes, filename: str, analysis_type: str = "general") -> Dict[str, Any]:
        """Complete document processing pipeline"""
        try:
            # Validate file
            if not self.is_allowed_file(filename):
                return {
                    'success': False,
                    'error': 'File type not allowed. Supported formats: PDF, DOCX, TXT'
                }
            
            if len(file_data) > self.max_file_size:
                return {
                    'success': False,
                    'error': f'File too large. Maximum size: {self.max_file_size/1024/1024:.0f}MB'
                }
            
            # Save file temporarily
            safe_filename = secure_filename(filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            temp_filename = f"{timestamp}_{safe_filename}"
            temp_path = os.path.join(self.upload_folder, temp_filename)
            
            with open(temp_path, 'wb') as f:
                f.write(file_data)
            
            # Extract text
            text_result = self.extract_text_from_file(temp_path, filename)
            if not text_result['success']:
                os.remove(temp_path)  # Clean up
                return text_result
            
            content = text_result['content']
            
            # Classify document
            classification_result = self.classify_document_type(content, filename)
            
            # Perform detailed analysis
            analysis_result = self.analyze_document_with_bagel(content, filename, analysis_type)
            
            # Clean up temporary file
            os.remove(temp_path)
            
            return {
                'success': True,
                'filename': filename,
                'file_info': {
                    'size': len(file_data),
                    'type': text_result['file_type'],
                    'word_count': text_result['word_count'],
                    'char_count': text_result['char_count']
                },
                'pii_analysis': text_result.get('pii_analysis', {}),
                'classification': classification_result,
                'analysis': analysis_result,
                'processed_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            return {
                'success': False,
                'error': f'Processing failed: {str(e)}'
            }

# Global instance
document_ai_service = DocumentAIService()

def process_document_upload(file_data: bytes, filename: str, analysis_type: str = "general") -> Dict[str, Any]:
    """Main function to process document uploads with Bagel RL integration"""
    return document_ai_service.process_uploaded_document(file_data, filename, analysis_type)

if __name__ == "__main__":
    # Test the service
    print("🚀 Testing Document AI Service")
    print("=" * 50)
    
    # Test with sample text
    sample_text = """
    EMPLOYMENT AGREEMENT
    
    This Employment Agreement is entered into on January 1, 2024, between ABC Corporation 
    and John Smith, residing at 123 Main Street, New York, NY 10001.
    
    1. Position: Software Engineer
    2. Start Date: January 15, 2024
    3. Salary: $85,000 per year
    4. Benefits: Health insurance, 401k matching
    5. Termination: Either party may terminate with 30 days notice
    
    Employee agrees to maintain confidentiality of proprietary information.
    Employee's contact: john.smith@email.com, (555) 123-4567
    """
    
    # Test PII detection
    pii_result = document_ai_service.detect_pii(sample_text)
    print(f"PII Detection: {pii_result}")
    
    # Test classification
    classification = document_ai_service.classify_document_type(sample_text, "employment_agreement.txt")
    print(f"Classification Success: {classification['success']}")
    print(f"Classification: {classification['classification'][:200]}...")
    
    # Test analysis
    analysis = document_ai_service.analyze_document_with_bagel(sample_text, "employment_agreement.txt", "contract")
    print(f"Analysis Success: {analysis['success']}")
    print(f"Analysis: {analysis['analysis'][:200]}...")