#!/usr/bin/env python3
"""
Spanish Language Support Service for LexAI Practice Partner
Multi-language support for broader market reach with legal translation capabilities
"""

import os
import json
import logging
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Import Bagel RL service for enhanced translations
try:
    from bagel_service import query_bagel_legal_ai
    BAGEL_AVAILABLE = True
except ImportError:
    BAGEL_AVAILABLE = False
    logger.warning("Bagel RL service not available for Spanish translations")

@dataclass
class TranslationResult:
    """Translation result with metadata"""
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    confidence_score: float
    legal_context: str
    warnings: List[str]
    bagel_enhanced: bool = False

class SpanishLegalService:
    """Spanish language support for legal documents and interfaces"""
    
    def __init__(self):
        self.translations = self._load_translations()
        self.legal_terms = self._load_legal_terms()
        self.supported_languages = ['en', 'es']
        
    def translate_text(self, text: str, target_language: str = 'es', 
                      legal_context: str = None) -> TranslationResult:
        """Translate text with legal context awareness"""
        try:
            logger.info(f"Translating text to {target_language} with legal context: {legal_context}")
            
            # Detect source language
            source_language = self._detect_language(text)
            
            if source_language == target_language:
                return TranslationResult(
                    original_text=text,
                    translated_text=text,
                    source_language=source_language,
                    target_language=target_language,
                    confidence_score=1.0,
                    legal_context=legal_context or 'general',
                    warnings=[]
                )
            
            # Basic translation using dictionary
            translated_text = self._basic_translate(text, source_language, target_language)
            warnings = []
            
            # Enhanced translation with Bagel RL
            bagel_enhanced = False
            if BAGEL_AVAILABLE and legal_context:
                enhanced_result = self._enhance_with_bagel_rl(
                    text, translated_text, source_language, target_language, legal_context
                )
                if enhanced_result.get('success'):
                    translated_text = enhanced_result['translation']
                    bagel_enhanced = True
                    warnings = enhanced_result.get('warnings', [])
            
            return TranslationResult(
                original_text=text,
                translated_text=translated_text,
                source_language=source_language,
                target_language=target_language,
                confidence_score=0.85 if bagel_enhanced else 0.7,
                legal_context=legal_context or 'general',
                warnings=warnings,
                bagel_enhanced=bagel_enhanced
            )
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_language='unknown',
                target_language=target_language,
                confidence_score=0.0,
                legal_context=legal_context or 'general',
                warnings=[f"Translation failed: {str(e)}"]
            )
    
    def get_ui_translation(self, key: str, language: str = 'es') -> str:
        """Get UI translation for interface elements"""
        if language not in self.translations:
            return key
        
        return self.translations[language].get(key, key)
    
    def translate_legal_document(self, document_text: str, document_type: str = 'contract',
                               target_language: str = 'es') -> Dict[str, Any]:
        """Translate legal document with special handling for legal terms"""
        try:
            logger.info(f"Translating legal document type: {document_type}")
            
            # Split document into sections
            sections = self._split_document_sections(document_text)
            translated_sections = []
            
            for section in sections:
                if section.strip():
                    translation = self.translate_text(
                        section, target_language, f"legal_{document_type}"
                    )
                    translated_sections.append(translation)
            
            # Combine translations
            full_translation = '\n\n'.join([t.translated_text for t in translated_sections])
            
            # Collect all warnings
            all_warnings = []
            for t in translated_sections:
                all_warnings.extend(t.warnings)
            
            # Calculate overall confidence
            confidence_scores = [t.confidence_score for t in translated_sections if t.confidence_score > 0]
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
            
            return {
                'success': True,
                'original_text': document_text,
                'translated_text': full_translation,
                'document_type': document_type,
                'target_language': target_language,
                'confidence_score': avg_confidence,
                'warnings': list(set(all_warnings)),
                'sections_translated': len(translated_sections),
                'bagel_enhanced': any(t.bagel_enhanced for t in translated_sections)
            }
            
        except Exception as e:
            logger.error(f"Document translation failed: {e}")
            return {
                'success': False,
                'error': f'Document translation failed: {str(e)}'
            }
    
    def get_spanish_legal_forms(self) -> Dict[str, Any]:
        """Get Spanish legal form templates"""
        return {
            'contract_template': {
                'title': 'Plantilla de Contrato',
                'sections': [
                    'Partes del Contrato',
                    'Términos y Condiciones', 
                    'Obligaciones',
                    'Pagos',
                    'Terminación',
                    'Ley Aplicable'
                ],
                'content': '''
                CONTRATO DE SERVICIOS LEGALES
                
                Este contrato se celebra entre ________________ (el "Cliente") 
                y ________________ (el "Proveedor") en fecha ________________.
                
                1. SERVICIOS: El Proveedor se compromete a proporcionar...
                2. PAGOS: El Cliente pagará...
                3. PLAZO: Este contrato tendrá vigencia desde...
                4. TERMINACIÓN: Cualquiera de las partes puede...
                5. LEY APLICABLE: Este contrato se regirá por...
                
                ________________               ________________
                Firma del Cliente             Firma del Proveedor
                '''
            },
            'nda_template': {
                'title': 'Acuerdo de Confidencialidad',
                'sections': [
                    'Información Confidencial',
                    'Obligaciones de Confidencialidad',
                    'Excepciones',
                    'Duración',
                    'Remedios'
                ],
                'content': '''
                ACUERDO DE CONFIDENCIALIDAD
                
                Este Acuerdo de Confidencialidad se celebra entre...
                
                1. INFORMACIÓN CONFIDENCIAL: Se considera información confidencial...
                2. OBLIGACIONES: La parte receptora se compromete a...
                3. EXCEPCIONES: Las obligaciones de confidencialidad no se aplicarán...
                4. DURACIÓN: Este acuerdo permanecerá vigente por...
                5. REMEDIOS: El incumplimiento de este acuerdo...
                '''
            }
        }
    
    def _detect_language(self, text: str) -> str:
        """Basic language detection"""
        # Simple heuristic - check for common Spanish words
        spanish_indicators = ['el', 'la', 'de', 'que', 'y', 'en', 'un', 'es', 'se', 'no', 'te', 'lo', 'le', 'da', 'su', 'por', 'son', 'con', 'para', 'al', 'del', 'los', 'una', 'las', 'pero', 'sus', 'ese', 'está', 'todo', 'más', 'ser', 'han', 'era', 'fue', 'son', 'muy', 'sin', 'sobre', 'también', 'hasta', 'año', 'años', 'puede', 'cuando', 'donde', 'mientras', 'durante', 'después', 'antes', 'porque', 'aunque', 'siempre', 'nunca', 'según', 'contra', 'desde', 'hacia', 'entre', 'dentro', 'fuera', 'cada', 'tanto', 'varios', 'otro', 'otros', 'otra', 'otras', 'mismo', 'misma', 'mismos', 'mismas']
        
        text_lower = text.lower()
        spanish_count = sum(1 for word in spanish_indicators if word in text_lower)
        
        # If more than 5% of words are Spanish indicators, assume Spanish
        word_count = len(text.split())
        if word_count > 0 and (spanish_count / word_count) > 0.05:
            return 'es'
        
        return 'en'
    
    def _basic_translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Basic translation using dictionary lookup"""
        if source_lang == 'en' and target_lang == 'es':
            # English to Spanish
            for en_term, es_term in self.legal_terms['en_to_es'].items():
                text = re.sub(r'\b' + re.escape(en_term) + r'\b', es_term, text, flags=re.IGNORECASE)
        elif source_lang == 'es' and target_lang == 'en':
            # Spanish to English
            for es_term, en_term in self.legal_terms['es_to_en'].items():
                text = re.sub(r'\b' + re.escape(es_term) + r'\b', en_term, text, flags=re.IGNORECASE)
        
        return text
    
    def _split_document_sections(self, document_text: str) -> List[str]:
        """Split document into logical sections for translation"""
        # Split by paragraph breaks
        sections = re.split(r'\n\s*\n', document_text)
        
        # Further split very long sections
        final_sections = []
        for section in sections:
            if len(section) > 1000:  # Split long sections
                sentences = re.split(r'(?<=[.!?])\s+', section)
                current_section = ""
                for sentence in sentences:
                    if len(current_section + sentence) > 1000:
                        if current_section:
                            final_sections.append(current_section)
                        current_section = sentence
                    else:
                        current_section += " " + sentence if current_section else sentence
                if current_section:
                    final_sections.append(current_section)
            else:
                final_sections.append(section)
        
        return final_sections
    
    def _enhance_with_bagel_rl(self, original_text: str, basic_translation: str,
                              source_lang: str, target_lang: str, legal_context: str) -> Dict[str, Any]:
        """Enhance translation with Bagel RL"""
        try:
            if not BAGEL_AVAILABLE:
                return {'success': False, 'error': 'Bagel RL not available'}
            
            context = f"""
            Legal Translation Enhancement Request:
            
            Source Language: {source_lang}
            Target Language: {target_lang}
            Legal Context: {legal_context}
            
            Original Text: {original_text}
            
            Basic Translation: {basic_translation}
            
            Please provide:
            1. Enhanced legal translation that maintains legal accuracy
            2. Identify any legal terms that require special attention
            3. Warn about potential legal concept differences between jurisdictions
            4. Suggest improvements for legal clarity and precision
            
            Focus on legal terminology accuracy and cultural legal context.
            """
            
            result = query_bagel_legal_ai(
                query=context,
                context=f"legal_translation_{source_lang}_to_{target_lang}",
                privacy_level="attorney_client"
            )
            
            if result.get('success', False):
                response = result['response']
                
                # Extract enhanced translation from response
                enhanced_translation = basic_translation  # Fallback
                warnings = []
                
                # Simple parsing - in production, would use more sophisticated NLP
                if 'enhanced translation:' in response.lower():
                    parts = response.lower().split('enhanced translation:')
                    if len(parts) > 1:
                        enhanced_part = parts[1].split('\n')[0].strip()
                        if enhanced_part:
                            enhanced_translation = enhanced_part
                
                # Extract warnings
                if 'warning' in response.lower():
                    warning_lines = [line.strip() for line in response.split('\n') if 'warning' in line.lower()]
                    warnings = warning_lines[:3]  # Limit warnings
                
                return {
                    'success': True,
                    'translation': enhanced_translation,
                    'warnings': warnings,
                    'bagel_analysis': response
                }
            else:
                return {'success': False, 'error': 'Bagel RL enhancement failed'}
                
        except Exception as e:
            logger.error(f"Bagel RL translation enhancement failed: {e}")
            return {'success': False, 'error': f'Enhancement failed: {str(e)}'}
    
    def _load_translations(self) -> Dict[str, Dict[str, str]]:
        """Load UI translations"""
        return {
            'es': {
                # Navigation
                'dashboard': 'Panel de Control',
                'clients': 'Clientes',
                'documents': 'Documentos',
                'legal_research': 'Investigación Legal',
                'evidence_analysis': 'Análisis de Evidencia',
                'contracts': 'Contratos',
                'analytics': 'Análisis',
                'settings': 'Configuración',
                'logout': 'Cerrar Sesión',
                
                # Dashboard
                'welcome_to_lexai': 'Bienvenido a LexAI',
                'legal_practice_platform': 'Su plataforma integral de práctica legal con IA',
                'ai_consultations': 'Consultas de IA',
                'documents_analyzed': 'Documentos Analizados',
                'research_queries': 'Consultas de Investigación',
                'active_clients': 'Clientes Activos',
                'practice_overview': 'Resumen de su Práctica',
                
                # Legal Research
                'legal_research_title': 'Investigación Legal',
                'legal_research_subtitle': 'Búsqueda con IA en jurisprudencia, estatutos y precedentes legales',
                'search_query': 'Consulta de Búsqueda',
                'search_placeholder': 'Ingrese su pregunta legal o términos de búsqueda...',
                'filters': 'Filtros',
                'jurisdiction': 'Jurisdicción',
                'all_jurisdictions': 'Todas las Jurisdicciones',
                'federal': 'Federal',
                'court_level': 'Nivel de Tribunal',
                'all_courts': 'Todos los Tribunales',
                'date_range': 'Rango de Fechas',
                'all_dates': 'Todas las Fechas',
                'practice_area': 'Área de Práctica',
                'all_practice_areas': 'Todas las Áreas de Práctica',
                'search_legal_database': 'Buscar Base de Datos Legal',
                'quick_searches': 'Búsquedas Rápidas',
                
                # Contract Analysis
                'contract_analysis': 'Análisis de Contratos',
                'contract_analysis_subtitle': 'Análisis integral de contratos con evaluación de riesgos y IA',
                'contract_text': 'Texto del Contrato',
                'contract_text_placeholder': 'Pegue o escriba el texto del contrato aquí...',
                'contract_type': 'Tipo de Contrato',
                'analysis_depth': 'Profundidad del Análisis',
                'analyze_contract': 'Analizar Contrato',
                'risk_assessment': 'Evaluación de Riesgos',
                'clause_analysis': 'Análisis de Cláusulas',
                'sample_contracts': 'Contratos de Muestra',
                
                # Document Analysis
                'document_analysis': 'Análisis de Documentos',
                'document_upload': 'Subir Documento',
                'drag_drop_files': 'Arrastre archivos aquí o haga clic para seleccionar',
                'supported_formats': 'Formatos soportados: PDF, DOCX, DOC, TXT, RTF',
                'max_file_size': 'Tamaño máximo: 10MB',
                'analyze_document': 'Analizar Documento',
                'privacy_protection': 'Protección de Privacidad',
                'pii_detection': 'Detección de IIP',
                'ai_enhancement': 'Mejora con IA',
                
                # Common
                'search': 'Buscar',
                'analyze': 'Analizar',
                'upload': 'Subir',
                'download': 'Descargar',
                'save': 'Guardar',
                'cancel': 'Cancelar',
                'close': 'Cerrar',
                'loading': 'Cargando...',
                'error': 'Error',
                'success': 'Éxito',
                'warning': 'Advertencia',
                'info': 'Información',
                'results': 'Resultados',
                'no_results': 'No se encontraron resultados',
                'try_again': 'Intentar de nuevo',
                
                # Legal Terms
                'case_law': 'Jurisprudencia',
                'statutes': 'Estatutos',
                'regulations': 'Reglamentos',
                'precedent': 'Precedente',
                'citation': 'Cita',
                'court': 'Tribunal',
                'judge': 'Juez',
                'plaintiff': 'Demandante',
                'defendant': 'Demandado',
                'contract': 'Contrato',
                'agreement': 'Acuerdo',
                'liability': 'Responsabilidad',
                'damages': 'Daños',
                'breach': 'Incumplimiento',
                'termination': 'Terminación',
                'confidentiality': 'Confidencialidad',
                'intellectual_property': 'Propiedad Intelectual',
                'compliance': 'Cumplimiento',
                'dispute_resolution': 'Resolución de Disputas',
                'arbitration': 'Arbitraje',
                'mediation': 'Mediación',
                'jurisdiction_law': 'Ley de Jurisdicción',
                'governing_law': 'Ley Aplicable'
            }
        }
    
    def _load_legal_terms(self) -> Dict[str, Dict[str, str]]:
        """Load legal term translations"""
        return {
            'en_to_es': {
                'contract': 'contrato',
                'agreement': 'acuerdo',
                'party': 'parte',
                'parties': 'partes',
                'liability': 'responsabilidad',
                'damages': 'daños',
                'breach': 'incumplimiento',
                'termination': 'terminación',
                'confidentiality': 'confidencialidad',
                'intellectual property': 'propiedad intelectual',
                'compliance': 'cumplimiento',
                'dispute resolution': 'resolución de disputas',
                'arbitration': 'arbitraje',
                'mediation': 'mediación',
                'jurisdiction': 'jurisdicción',
                'governing law': 'ley aplicable',
                'court': 'tribunal',
                'judge': 'juez',
                'plaintiff': 'demandante',
                'defendant': 'demandado',
                'case law': 'jurisprudencia',
                'statute': 'estatuto',
                'regulation': 'reglamento',
                'precedent': 'precedente',
                'citation': 'cita',
                'legal counsel': 'asesor legal',
                'attorney': 'abogado',
                'lawyer': 'abogado',
                'legal representative': 'representante legal',
                'power of attorney': 'poder notarial',
                'due process': 'debido proceso',
                'constitutional law': 'derecho constitucional',
                'civil law': 'derecho civil',
                'criminal law': 'derecho penal',
                'contract law': 'derecho contractual',
                'tort law': 'derecho de daños',
                'family law': 'derecho familiar',
                'employment law': 'derecho laboral',
                'corporate law': 'derecho corporativo',
                'intellectual property law': 'derecho de propiedad intelectual',
                'real estate law': 'derecho inmobiliario',
                'immigration law': 'derecho migratorio',
                'tax law': 'derecho fiscal',
                'environmental law': 'derecho ambiental',
                'healthcare law': 'derecho sanitario',
                'bankruptcy law': 'derecho concursal',
                'securities law': 'derecho bursátil',
                'merger and acquisition': 'fusión y adquisición',
                'due diligence': 'diligencia debida',
                'non-disclosure agreement': 'acuerdo de confidencialidad',
                'employment agreement': 'contrato de trabajo',
                'service agreement': 'acuerdo de servicios',
                'lease agreement': 'contrato de arrendamiento',
                'partnership agreement': 'acuerdo de sociedad',
                'licensing agreement': 'acuerdo de licencia',
                'consulting agreement': 'acuerdo de consultoría',
                'force majeure': 'fuerza mayor',
                'indemnification': 'indemnización',
                'warranty': 'garantía',
                'disclaimer': 'descargo de responsabilidad',
                'limitation of liability': 'limitación de responsabilidad',
                'entire agreement': 'acuerdo completo',
                'severability': 'divisibilidad',
                'assignment': 'cesión',
                'novation': 'novación',
                'consideration': 'contraprestación',
                'offer': 'oferta',
                'acceptance': 'aceptación',
                'rejection': 'rechazo',
                'counteroffer': 'contraoferta',
                'revocation': 'revocación',
                'rescission': 'rescisión',
                'restitution': 'restitución',
                'specific performance': 'cumplimiento específico',
                'injunctive relief': 'medida cautelar',
                'punitive damages': 'daños punitivos',
                'compensatory damages': 'daños compensatorios',
                'consequential damages': 'daños consecuenciales',
                'liquidated damages': 'daños liquidados',
                'mitigation of damages': 'mitigación de daños',
                'statute of limitations': 'plazo de prescripción',
                'burden of proof': 'carga de la prueba',
                'standard of proof': 'estándar de prueba',
                'preponderance of evidence': 'preponderancia de la evidencia',
                'beyond reasonable doubt': 'más allá de toda duda razonable',
                'admissible evidence': 'evidencia admisible',
                'inadmissible evidence': 'evidencia inadmisible',
                'hearsay': 'testimonio de oídas',
                'expert witness': 'testigo experto',
                'deposition': 'deposición',
                'interrogatories': 'interrogatorios',
                'discovery': 'descubrimiento de pruebas',
                'motion': 'moción',
                'pleading': 'alegato',
                'complaint': 'demanda',
                'answer': 'contestación',
                'counterclaim': 'contrademanda',
                'cross-claim': 'demanda cruzada',
                'third-party claim': 'demanda de terceros',
                'summary judgment': 'juicio sumario',
                'trial': 'juicio',
                'verdict': 'veredicto',
                'judgment': 'sentencia',
                'appeal': 'apelación',
                'appellate court': 'tribunal de apelaciones',
                'supreme court': 'tribunal supremo',
                'federal court': 'tribunal federal',
                'state court': 'tribunal estatal',
                'district court': 'tribunal de distrito',
                'bankruptcy court': 'tribunal de quiebras',
                'family court': 'tribunal familiar',
                'probate court': 'tribunal de sucesiones',
                'small claims court': 'tribunal de reclamaciones menores'
            },
            'es_to_en': {
                'contrato': 'contract',
                'acuerdo': 'agreement',
                'parte': 'party',
                'partes': 'parties',
                'responsabilidad': 'liability',
                'daños': 'damages',
                'incumplimiento': 'breach',
                'terminación': 'termination',
                'confidencialidad': 'confidentiality',
                'propiedad intelectual': 'intellectual property',
                'cumplimiento': 'compliance',
                'resolución de disputas': 'dispute resolution',
                'arbitraje': 'arbitration',
                'mediación': 'mediation',
                'jurisdicción': 'jurisdiction',
                'ley aplicable': 'governing law',
                'tribunal': 'court',
                'juez': 'judge',
                'demandante': 'plaintiff',
                'demandado': 'defendant',
                'jurisprudencia': 'case law',
                'estatuto': 'statute',
                'reglamento': 'regulation',
                'precedente': 'precedent',
                'cita': 'citation',
                'asesor legal': 'legal counsel',
                'abogado': 'attorney',
                'representante legal': 'legal representative',
                'poder notarial': 'power of attorney',
                'debido proceso': 'due process',
                'derecho constitucional': 'constitutional law',
                'derecho civil': 'civil law',
                'derecho penal': 'criminal law',
                'derecho contractual': 'contract law',
                'derecho de daños': 'tort law',
                'derecho familiar': 'family law',
                'derecho laboral': 'employment law',
                'derecho corporativo': 'corporate law',
                'derecho de propiedad intelectual': 'intellectual property law',
                'derecho inmobiliario': 'real estate law',
                'derecho migratorio': 'immigration law',
                'derecho fiscal': 'tax law',
                'derecho ambiental': 'environmental law',
                'derecho sanitario': 'healthcare law',
                'derecho concursal': 'bankruptcy law',
                'derecho bursátil': 'securities law',
                'fusión y adquisición': 'merger and acquisition',
                'diligencia debida': 'due diligence',
                'acuerdo de confidencialidad': 'non-disclosure agreement',
                'contrato de trabajo': 'employment agreement',
                'acuerdo de servicios': 'service agreement',
                'contrato de arrendamiento': 'lease agreement',
                'acuerdo de sociedad': 'partnership agreement',
                'acuerdo de licencia': 'licensing agreement',
                'acuerdo de consultoría': 'consulting agreement',
                'fuerza mayor': 'force majeure',
                'indemnización': 'indemnification',
                'garantía': 'warranty',
                'descargo de responsabilidad': 'disclaimer',
                'limitación de responsabilidad': 'limitation of liability',
                'acuerdo completo': 'entire agreement',
                'divisibilidad': 'severability',
                'cesión': 'assignment',
                'novación': 'novation',
                'contraprestación': 'consideration',
                'oferta': 'offer',
                'aceptación': 'acceptance',
                'rechazo': 'rejection',
                'contraoferta': 'counteroffer',
                'revocación': 'revocation',
                'rescisión': 'rescission',
                'restitución': 'restitution',
                'cumplimiento específico': 'specific performance',
                'medida cautelar': 'injunctive relief',
                'daños punitivos': 'punitive damages',
                'daños compensatorios': 'compensatory damages',
                'daños consecuenciales': 'consequential damages',
                'daños liquidados': 'liquidated damages',
                'mitigación de daños': 'mitigation of damages',
                'plazo de prescripción': 'statute of limitations',
                'carga de la prueba': 'burden of proof',
                'estándar de prueba': 'standard of proof',
                'preponderancia de la evidencia': 'preponderance of evidence',
                'más allá de toda duda razonable': 'beyond reasonable doubt',
                'evidencia admisible': 'admissible evidence',
                'evidencia inadmisible': 'inadmissible evidence',
                'testimonio de oídas': 'hearsay',
                'testigo experto': 'expert witness',
                'deposición': 'deposition',
                'interrogatorios': 'interrogatories',
                'descubrimiento de pruebas': 'discovery',
                'moción': 'motion',
                'alegato': 'pleading',
                'demanda': 'complaint',
                'contestación': 'answer',
                'contrademanda': 'counterclaim',
                'demanda cruzada': 'cross-claim',
                'demanda de terceros': 'third-party claim',
                'juicio sumario': 'summary judgment',
                'juicio': 'trial',
                'veredicto': 'verdict',
                'sentencia': 'judgment',
                'apelación': 'appeal',
                'tribunal de apelaciones': 'appellate court',
                'tribunal supremo': 'supreme court',
                'tribunal federal': 'federal court',
                'tribunal estatal': 'state court',
                'tribunal de distrito': 'district court',
                'tribunal de quiebras': 'bankruptcy court',
                'tribunal familiar': 'family court',
                'tribunal de sucesiones': 'probate court',
                'tribunal de reclamaciones menores': 'small claims court'
            }
        }

# Global instance
spanish_service = SpanishLegalService()

def translate_legal_text(text: str, target_language: str = 'es', 
                        legal_context: str = None) -> Dict[str, Any]:
    """Main function for legal text translation"""
    try:
        result = spanish_service.translate_text(text, target_language, legal_context)
        
        return {
            'success': True,
            'original_text': result.original_text,
            'translated_text': result.translated_text,
            'source_language': result.source_language,
            'target_language': result.target_language,
            'confidence_score': result.confidence_score,
            'legal_context': result.legal_context,
            'warnings': result.warnings,
            'bagel_enhanced': result.bagel_enhanced,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Legal translation failed: {e}")
        return {
            'success': False,
            'error': f'Translation failed: {str(e)}'
        }

def translate_legal_document(document_text: str, document_type: str = 'contract',
                           target_language: str = 'es') -> Dict[str, Any]:
    """Main function for legal document translation"""
    return spanish_service.translate_legal_document(document_text, document_type, target_language)

def get_ui_translation(key: str, language: str = 'es') -> str:
    """Get UI translation"""
    return spanish_service.get_ui_translation(key, language)

def get_spanish_legal_forms() -> Dict[str, Any]:
    """Get Spanish legal forms"""
    return spanish_service.get_spanish_legal_forms()

if __name__ == "__main__":
    # Test the service
    print("🌐 Testing Spanish Legal Service")
    print("=" * 50)
    
    # Test basic translation
    sample_text = "This contract is governed by the laws of California."
    result = translate_legal_text(sample_text, 'es', 'contract')
    
    print(f"Translation Success: {result['success']}")
    if result['success']:
        print(f"Original: {result['original_text']}")
        print(f"Translated: {result['translated_text']}")
        print(f"Confidence: {result['confidence_score']}")
        print(f"Bagel Enhanced: {result['bagel_enhanced']}")
    else:
        print(f"Error: {result['error']}")
    
    # Test UI translation
    print("\n🖥️ Testing UI Translations")
    print("-" * 30)
    ui_keys = ['dashboard', 'legal_research', 'contract_analysis', 'document_analysis']
    for key in ui_keys:
        translation = get_ui_translation(key, 'es')
        print(f"{key}: {translation}")
    
    # Test document translation
    print("\n📄 Testing Document Translation")
    print("-" * 30)
    sample_contract = """
    SERVICE AGREEMENT
    
    This Service Agreement is entered into between Company A and Company B.
    
    1. Services: The provider will deliver consulting services.
    2. Payment: Client will pay $5,000 monthly.
    3. Termination: Either party may terminate with 30 days notice.
    4. Confidentiality: All information must remain confidential.
    5. Governing Law: This agreement is governed by California law.
    """
    
    doc_result = translate_legal_document(sample_contract, 'service', 'es')
    print(f"Document Translation Success: {doc_result['success']}")
    if doc_result['success']:
        print(f"Confidence: {doc_result['confidence_score']}")
        print(f"Sections: {doc_result['sections_translated']}")
        print(f"Warnings: {len(doc_result['warnings'])}")
    else:
        print(f"Error: {doc_result['error']}")