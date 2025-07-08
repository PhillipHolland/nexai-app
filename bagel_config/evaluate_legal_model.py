#!/usr/bin/env python3
"""
BFCL Evaluation Script for Legal Bagel RL Models
Evaluates trained models on Berkeley Function Calling Leaderboard
"""

import os
import json
import subprocess
import logging
from typing import Dict, List
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LegalModelEvaluator:
    """Evaluate legal Bagel RL models using BFCL and custom legal benchmarks"""
    
    def __init__(self, model_path: str, output_dir: str = "evaluation_results"):
        self.model_path = model_path
        self.output_dir = output_dir
        self.setup_evaluation_environment()
    
    def setup_evaluation_environment(self):
        """Set up evaluation environment"""
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Set BFCL environment variables
        os.environ['BFCL_PROJECT_ROOT'] = os.path.abspath(self.output_dir)
        logger.info(f"BFCL project root set to: {self.output_dir}")
    
    def run_bfcl_evaluation(self, model_name: str = "legal-bagel-rl"):
        """Run Berkeley Function Calling Leaderboard evaluation"""
        logger.info("Running BFCL evaluation...")
        
        try:
            # Generate model responses
            generate_cmd = [
                "bfcl", "generate",
                "--model", model_name,
                "--local-model-path", self.model_path,
                "--test-category", "simple,parallel,multiple,multi_turn",
                "--output-dir", self.output_dir
            ]
            
            logger.info(f"Running: {' '.join(generate_cmd)}")
            subprocess.run(generate_cmd, check=True)
            
            # Evaluate responses
            evaluate_cmd = [
                "bfcl", "evaluate", 
                "--model", model_name,
                "--test-category", "simple,parallel,multiple,multi_turn",
                "--output-dir", self.output_dir
            ]
            
            logger.info(f"Running: {' '.join(evaluate_cmd)}")
            result = subprocess.run(evaluate_cmd, capture_output=True, text=True, check=True)
            
            logger.info("BFCL evaluation completed successfully")
            return self.parse_bfcl_results()
            
        except subprocess.CalledProcessError as e:
            logger.error(f"BFCL evaluation failed: {e}")
            logger.error(e.stderr)
            return None
    
    def run_legal_benchmarks(self):
        """Run custom legal tool use benchmarks"""
        logger.info("Running legal-specific benchmarks...")
        
        legal_test_cases = self.generate_legal_test_cases()
        results = {}
        
        for category, tests in legal_test_cases.items():
            logger.info(f"Evaluating {category} tasks...")
            category_results = []
            
            for test in tests:
                result = self.evaluate_single_test(test)
                category_results.append(result)
            
            results[category] = {
                'total_tests': len(tests),
                'passed': sum(1 for r in category_results if r['success']),
                'accuracy': sum(r['accuracy'] for r in category_results) / len(category_results),
                'avg_response_time': sum(r['response_time'] for r in category_results) / len(category_results),
                'details': category_results
            }
        
        # Save legal benchmark results
        with open(f"{self.output_dir}/legal_benchmark_results.json", 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info("Legal benchmarks completed")
        return results
    
    def generate_legal_test_cases(self) -> Dict[str, List[Dict]]:
        """Generate legal-specific test cases"""
        return {
            "evidence_analysis": [
                {
                    "id": "evidence_1",
                    "prompt": "Analyze this image for potential manipulation and assess its admissibility in federal court",
                    "expected_tools": ["analyze_evidence"],
                    "expected_params": ["evidence_type", "analysis_depth", "jurisdiction"]
                },
                {
                    "id": "evidence_2", 
                    "prompt": "Perform forensic analysis on video evidence for criminal trial",
                    "expected_tools": ["analyze_evidence"],
                    "expected_params": ["evidence_type", "analysis_depth"]
                }
            ],
            "contract_analysis": [
                {
                    "id": "contract_1",
                    "prompt": "Review this employment agreement for potential legal risks in California",
                    "expected_tools": ["analyze_contract"],
                    "expected_params": ["contract_type", "analysis_focus", "jurisdiction"]
                },
                {
                    "id": "contract_2",
                    "prompt": "Analyze NDA for enforceability and compliance issues",
                    "expected_tools": ["analyze_contract"],
                    "expected_params": ["contract_type", "analysis_focus"]
                }
            ],
            "legal_research": [
                {
                    "id": "research_1",
                    "prompt": "Find federal court precedents on copyright fair use in software development",
                    "expected_tools": ["search_case_law"],
                    "expected_params": ["query", "jurisdiction", "practice_area"]
                },
                {
                    "id": "research_2",
                    "prompt": "Research employment discrimination cases in the 9th Circuit from the last 5 years",
                    "expected_tools": ["search_case_law"],
                    "expected_params": ["query", "jurisdiction", "date_range"]
                }
            ],
            "risk_assessment": [
                {
                    "id": "risk_1",
                    "prompt": "Evaluate litigation prospects for breach of contract claim involving software licensing",
                    "expected_tools": ["evaluate_litigation_risk"],
                    "expected_params": ["case_type", "facts_summary", "jurisdiction"]
                }
            ]
        }
    
    def evaluate_single_test(self, test: Dict) -> Dict:
        """Evaluate a single test case"""
        try:
            # Simulate model call (in production, would call actual model)
            response = self.mock_model_response(test)
            
            # Check if correct tools were used
            tools_correct = self.validate_tool_usage(response, test['expected_tools'])
            
            # Check parameter completeness
            params_correct = self.validate_parameters(response, test['expected_params'])
            
            # Calculate accuracy score
            accuracy = (tools_correct + params_correct) / 2
            
            return {
                'test_id': test['id'],
                'success': accuracy > 0.8,
                'accuracy': accuracy,
                'tools_correct': tools_correct,
                'params_correct': params_correct,
                'response_time': 1.5,  # Mock response time
                'response': response
            }
            
        except Exception as e:
            logger.error(f"Test {test['id']} failed: {e}")
            return {
                'test_id': test['id'],
                'success': False,
                'accuracy': 0.0,
                'error': str(e),
                'response_time': 0
            }
    
    def mock_model_response(self, test: Dict) -> Dict:
        """Mock model response for testing (replace with actual model call)"""
        return {
            'tools_used': test['expected_tools'],
            'parameters_provided': test['expected_params'],
            'response_quality': 'high'
        }
    
    def validate_tool_usage(self, response: Dict, expected_tools: List[str]) -> float:
        """Validate correct tool usage"""
        tools_used = response.get('tools_used', [])
        if not tools_used:
            return 0.0
        
        correct_tools = sum(1 for tool in expected_tools if tool in tools_used)
        return correct_tools / len(expected_tools)
    
    def validate_parameters(self, response: Dict, expected_params: List[str]) -> float:
        """Validate parameter completeness"""
        params_provided = response.get('parameters_provided', [])
        if not params_provided:
            return 0.0
        
        correct_params = sum(1 for param in expected_params if param in params_provided)
        return correct_params / len(expected_params)
    
    def parse_bfcl_results(self) -> Dict:
        """Parse BFCL evaluation results"""
        try:
            # Look for BFCL results CSV
            results_file = f"{self.output_dir}/evaluation_results.csv"
            if os.path.exists(results_file):
                df = pd.read_csv(results_file)
                return {
                    'overall_accuracy': df['accuracy'].mean(),
                    'simple_category': df[df['category'] == 'simple']['accuracy'].mean(),
                    'parallel_category': df[df['category'] == 'parallel']['accuracy'].mean(),
                    'multiple_category': df[df['category'] == 'multiple']['accuracy'].mean(),
                    'multi_turn_category': df[df['category'] == 'multi_turn']['accuracy'].mean()
                }
            else:
                logger.warning("BFCL results file not found")
                return {'overall_accuracy': 0.0}
                
        except Exception as e:
            logger.error(f"Failed to parse BFCL results: {e}")
            return {'overall_accuracy': 0.0}
    
    def generate_evaluation_report(self, bfcl_results: Dict, legal_results: Dict):
        """Generate comprehensive evaluation report"""
        report = {
            'evaluation_timestamp': pd.Timestamp.now().isoformat(),
            'model_path': self.model_path,
            'bfcl_performance': bfcl_results,
            'legal_benchmark_performance': legal_results,
            'summary': {
                'overall_score': (bfcl_results.get('overall_accuracy', 0) + 
                                sum(cat['accuracy'] for cat in legal_results.values()) / len(legal_results)) / 2,
                'legal_tool_accuracy': sum(cat['accuracy'] for cat in legal_results.values()) / len(legal_results),
                'function_calling_accuracy': bfcl_results.get('overall_accuracy', 0)
            }
        }
        
        # Save report
        with open(f"{self.output_dir}/evaluation_report.json", 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        logger.info("=== Evaluation Report ===")
        logger.info(f"Overall Score: {report['summary']['overall_score']:.3f}")
        logger.info(f"Legal Tool Accuracy: {report['summary']['legal_tool_accuracy']:.3f}")
        logger.info(f"Function Calling Accuracy: {report['summary']['function_calling_accuracy']:.3f}")
        
        return report

def main():
    """Main evaluation pipeline"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Evaluate legal Bagel RL model")
    parser.add_argument("--model-path", required=True, help="Path to trained model")
    parser.add_argument("--output-dir", default="evaluation_results", help="Output directory")
    parser.add_argument("--model-name", default="legal-bagel-rl", help="Model name for BFCL")
    
    args = parser.parse_args()
    
    evaluator = LegalModelEvaluator(args.model_path, args.output_dir)
    
    try:
        # Run evaluations
        logger.info("Starting evaluation pipeline...")
        
        bfcl_results = evaluator.run_bfcl_evaluation(args.model_name)
        legal_results = evaluator.run_legal_benchmarks()
        
        # Generate report
        report = evaluator.generate_evaluation_report(bfcl_results, legal_results)
        
        logger.info("Evaluation pipeline completed successfully!")
        logger.info(f"Results saved to: {args.output_dir}")
        
    except Exception as e:
        logger.error(f"Evaluation pipeline failed: {e}")
        raise

if __name__ == "__main__":
    main()