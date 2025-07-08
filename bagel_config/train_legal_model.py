#!/usr/bin/env python3
"""
Legal Tool Use Training Script for Bagel RL
Trains Qwen3 models on legal-specific tool use tasks
"""

import os
import json
import subprocess
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LegalToolTrainer:
    def __init__(self, config_path="legal_tools_config.json"):
        self.config_path = config_path
        self.load_config()
        self.setup_environment()
    
    def load_config(self):
        """Load training configuration"""
        with open(self.config_path, 'r') as f:
            self.config = json.load(f)
        logger.info(f"Loaded config from {self.config_path}")
    
    def setup_environment(self):
        """Set up training environment"""
        self.output_dir = f"legal_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"Created output directory: {self.output_dir}")
    
    def generate_synthetic_data(self):
        """Generate synthetic legal tool use datasets"""
        logger.info("Generating synthetic legal training data...")
        
        # Legal scenarios for tool use training
        legal_scenarios = [
            {
                "task": "evidence_analysis",
                "query": "Analyze this image for potential deepfake manipulation",
                "tools": ["analyze_evidence"],
                "context": "Criminal case requiring digital evidence authentication"
            },
            {
                "task": "contract_review", 
                "query": "Review this employment contract for potential risks",
                "tools": ["analyze_contract"],
                "context": "Client seeking employment agreement review"
            },
            {
                "task": "legal_research",
                "query": "Find precedents for copyright infringement in software",
                "tools": ["search_case_law"],
                "context": "IP litigation preparation"
            },
            {
                "task": "risk_assessment",
                "query": "Evaluate litigation prospects for breach of contract claim",
                "tools": ["evaluate_litigation_risk"],
                "context": "Client considering legal action"
            }
        ]
        
        # Generate training examples
        training_data = []
        for scenario in legal_scenarios:
            for i in range(50):  # Generate 50 variations per scenario
                example = self.create_training_example(scenario, i)
                training_data.append(example)
        
        # Save synthetic dataset
        with open(f"{self.output_dir}/legal_synthetic_dataset.json", 'w') as f:
            json.dump(training_data, f, indent=2)
        
        logger.info(f"Generated {len(training_data)} synthetic training examples")
        return training_data
    
    def create_training_example(self, scenario, variation_id):
        """Create individual training example"""
        return {
            "id": f"{scenario['task']}_{variation_id}",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a legal AI assistant with access to specialized legal tools. Use the appropriate tools to help with legal analysis and research."
                },
                {
                    "role": "user", 
                    "content": f"Context: {scenario['context']}\n\nRequest: {scenario['query']}"
                },
                {
                    "role": "assistant",
                    "content": f"I'll help you with this {scenario['task']}. Let me use the appropriate legal tools.",
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {
                                "name": scenario['tools'][0],
                                "arguments": self.generate_tool_arguments(scenario['tools'][0], scenario)
                            }
                        }
                    ]
                }
            ],
            "tools": self.get_tool_definitions()
        }
    
    def generate_tool_arguments(self, tool_name, scenario):
        """Generate appropriate arguments for each tool"""
        if tool_name == "analyze_evidence":
            return json.dumps({
                "evidence_type": "image",
                "analysis_depth": "comprehensive",
                "jurisdiction": "federal"
            })
        elif tool_name == "analyze_contract":
            return json.dumps({
                "contract_type": "employment",
                "analysis_focus": ["risk_assessment", "clause_analysis"],
                "jurisdiction": "california"
            })
        elif tool_name == "search_case_law":
            return json.dumps({
                "query": "copyright infringement software",
                "jurisdiction": "federal",
                "practice_area": "corporate"
            })
        elif tool_name == "evaluate_litigation_risk":
            return json.dumps({
                "case_type": "breach of contract",
                "facts_summary": "Contractor failed to deliver software on time",
                "jurisdiction": "california"
            })
        return "{}"
    
    def get_tool_definitions(self):
        """Get tool definitions from config"""
        return self.config["tool_schemas"]
    
    def train_model(self):
        """Execute Bagel RL training"""
        logger.info("Starting Bagel RL training...")
        
        # Generate synthetic data first
        self.generate_synthetic_data()
        
        # Update config with output directory
        training_config = self.config.copy()
        training_config["output_dir"] = self.output_dir
        training_config["dataset_path"] = f"{self.output_dir}/legal_synthetic_dataset.json"
        
        # Save updated config
        config_file = f"{self.output_dir}/training_config.json"
        with open(config_file, 'w') as f:
            json.dump(training_config, f, indent=2)
        
        # Run Bagel RL training
        cmd = [
            "python", "train.py",
            "--config", config_file,
            "--output-dir", self.output_dir
        ]
        
        logger.info(f"Running command: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info("Training completed successfully!")
            logger.info(result.stdout)
        except subprocess.CalledProcessError as e:
            logger.error(f"Training failed: {e}")
            logger.error(e.stderr)
            raise
    
    def evaluate_model(self):
        """Evaluate trained model on legal benchmarks"""
        logger.info("Evaluating trained model...")
        
        # Run BFCL evaluation
        cmd = [
            "bfcl", "generate",
            "--model", self.config["model_config"]["base_model"],
            "--local-model-path", self.output_dir,
            "--test-category", "simple,parallel,multiple"
        ]
        
        try:
            subprocess.run(cmd, check=True)
            logger.info("BFCL evaluation completed")
        except subprocess.CalledProcessError as e:
            logger.error(f"Evaluation failed: {e}")
    
    def merge_and_save_model(self):
        """Merge LoRA adapters and save final model"""
        logger.info("Merging and saving final model...")
        
        cmd = [
            "python", "save_merge_model.py",
            "--base_model", self.config["model_config"]["base_model"],
            "--adapter_path", self.output_dir,
            "--output_dir", f"{self.output_dir}/merged_model",
            "--trust_remote_code"
        ]
        
        try:
            subprocess.run(cmd, check=True)
            logger.info(f"Model saved to {self.output_dir}/merged_model")
        except subprocess.CalledProcessError as e:
            logger.error(f"Model merging failed: {e}")

def main():
    """Main training pipeline"""
    trainer = LegalToolTrainer()
    
    try:
        # Full training pipeline
        trainer.train_model()
        trainer.evaluate_model() 
        trainer.merge_and_save_model()
        
        logger.info("Legal tool training pipeline completed successfully!")
        logger.info(f"Model saved in: {trainer.output_dir}")
        
    except Exception as e:
        logger.error(f"Training pipeline failed: {e}")
        raise

if __name__ == "__main__":
    main()