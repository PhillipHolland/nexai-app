#!/bin/bash
set -e

# Model Deployment Script
# Deploys trained Bagel RL model to serving instance

echo "🚀 Deploying trained Bagel RL model..."

# Configuration
PROJECT_ID="lexai-bagel-rl"
ZONE="us-central1-c"
TRAINING_INSTANCE="bagel-legal-trainer"
SERVER_INSTANCE="bagel-legal-server"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_training_complete() {
    log_info "Checking if training is complete..."
    
    # Check if merged model exists
    if gcloud compute ssh $TRAINING_INSTANCE --zone=$ZONE \
        --command="test -d ~/bagel-RL/merged_legal_model" 2>/dev/null; then
        log_info "Training complete - merged model found ✅"
        return 0
    else
        log_warn "Training not complete or model not merged"
        return 1
    fi
}

merge_model() {
    log_info "Merging LoRA adapters with base model..."
    
    # Merge script
    cat > merge_model.sh << 'EOF'
#!/bin/bash
set -e

cd ~/bagel-RL

echo "Merging model..."
python save_merge_model.py \
    --base_model Qwen/Qwen3-0.6B \
    --adapter_path legal_model_output/ \
    --output_dir merged_legal_model/ \
    --trust_remote_code

echo "Model merged successfully!"
ls -la merged_legal_model/
EOF
    
    # Run merge on training instance
    gcloud compute scp --zone=$ZONE merge_model.sh $TRAINING_INSTANCE:~/
    gcloud compute ssh $TRAINING_INSTANCE --zone=$ZONE \
        --command="chmod +x ~/merge_model.sh && ~/merge_model.sh"
    
    # Clean up
    rm merge_model.sh
    
    log_info "Model merge complete ✅"
}

copy_model_to_server() {
    log_info "Copying model to server instance..."
    
    # Create temporary compressed archive
    gcloud compute ssh $TRAINING_INSTANCE --zone=$ZONE \
        --command="cd ~/bagel-RL && tar -czf merged_legal_model.tar.gz merged_legal_model/"
    
    # Copy via local machine (more reliable than instance-to-instance)
    log_info "Downloading model archive..."
    gcloud compute scp --zone=$ZONE \
        $TRAINING_INSTANCE:~/bagel-RL/merged_legal_model.tar.gz ./
    
    log_info "Uploading model to server..."
    gcloud compute scp --zone=$ZONE \
        ./merged_legal_model.tar.gz $SERVER_INSTANCE:~/
    
    # Extract on server
    gcloud compute ssh $SERVER_INSTANCE --zone=$ZONE \
        --command="cd ~/ && tar -xzf merged_legal_model.tar.gz && mv merged_legal_model model_server/"
    
    # Clean up
    rm merged_legal_model.tar.gz
    gcloud compute ssh $TRAINING_INSTANCE --zone=$ZONE \
        --command="rm ~/bagel-RL/merged_legal_model.tar.gz"
    gcloud compute ssh $SERVER_INSTANCE --zone=$ZONE \
        --command="rm ~/merged_legal_model.tar.gz"
    
    log_info "Model copied to server ✅"
}

create_model_server() {
    log_info "Creating model server..."
    
    # Model server script
    cat > model_server.py << 'EOF'
from fastapi import FastAPI, HTTPException
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import json
import logging
from typing import Dict, List, Any
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="LexAI Bagel RL Legal Model Server", version="1.0.0")

# Global model variables
model = None
tokenizer = None

@app.on_event("startup")
async def load_model():
    global model, tokenizer
    
    try:
        model_path = "./merged_legal_model"
        logger.info(f"Loading model from {model_path}")
        
        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True
        )
        
        logger.info("Model loaded successfully!")
        
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise

@app.get("/health")
async def health_check():
    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.post("/v1/chat/completions")
async def chat_completions(request: Dict[str, Any]):
    try:
        if model is None or tokenizer is None:
            raise HTTPException(status_code=503, detail="Model not loaded")
        
        messages = request.get("messages", [])
        tools = request.get("tools", [])
        max_tokens = request.get("max_tokens", 512)
        temperature = request.get("temperature", 0.1)
        
        # Format prompt for tool use
        prompt = format_chat_prompt(messages, tools)
        
        # Generate response
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
        
        with torch.no_grad():
            outputs = model.generate(
                inputs.input_ids,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id
            )
        
        # Decode response
        response_text = tokenizer.decode(
            outputs[0][inputs.input_ids.shape[1]:], 
            skip_special_tokens=True
        )
        
        return {
            "id": f"chatcmpl-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "object": "chat.completion",
            "created": int(datetime.utcnow().timestamp()),
            "model": "legal-bagel-rl",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": inputs.input_ids.shape[1],
                "completion_tokens": len(outputs[0]) - inputs.input_ids.shape[1],
                "total_tokens": len(outputs[0])
            }
        }
        
    except Exception as e:
        logger.error(f"Generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def format_chat_prompt(messages: List[Dict], tools: List[Dict]) -> str:
    prompt = "You are a legal AI assistant with access to specialized legal tools.\n\n"
    
    if tools:
        prompt += "Available tools:\n"
        for tool in tools:
            prompt += f"- {tool['name']}: {tool['description']}\n"
            if 'parameters' in tool:
                prompt += f"  Parameters: {json.dumps(tool['parameters'], indent=2)}\n"
        prompt += "\n"
    
    prompt += "Conversation:\n"
    for msg in messages:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        prompt += f"{role}: {content}\n"
    
    prompt += "assistant:"
    return prompt

@app.get("/")
async def root():
    return {
        "message": "LexAI Bagel RL Legal Model Server",
        "version": "1.0.0",
        "status": "running"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
EOF
    
    # Upload server script
    gcloud compute scp --zone=$ZONE model_server.py $SERVER_INSTANCE:~/model_server/
    
    # Clean up
    rm model_server.py
    
    log_info "Model server script created ✅"
}

start_model_server() {
    log_info "Starting model server..."
    
    # Start server script
    cat > start_server.sh << 'EOF'
#!/bin/bash
set -e

cd ~/model_server

# Kill any existing server process
pkill -f "python.*model_server.py" || true

# Start server
echo "Starting model server..."
nohup python3 model_server.py > server.log 2>&1 &

# Wait a moment and check if server started
sleep 5
if pgrep -f "python.*model_server.py" > /dev/null; then
    echo "Server started successfully!"
    echo "PID: $(pgrep -f 'python.*model_server.py')"
else
    echo "Failed to start server. Check logs:"
    cat server.log
    exit 1
fi
EOF
    
    # Run start script
    gcloud compute scp --zone=$ZONE start_server.sh $SERVER_INSTANCE:~/
    gcloud compute ssh $SERVER_INSTANCE --zone=$ZONE \
        --command="chmod +x ~/start_server.sh && ~/start_server.sh"
    
    # Clean up
    rm start_server.sh
    
    log_info "Model server started ✅"
}

test_model_server() {
    log_info "Testing model server..."
    
    # Get server IP
    SERVER_IP=$(gcloud compute instances describe $SERVER_INSTANCE \
        --zone=$ZONE \
        --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    
    # Test health endpoint
    sleep 10  # Give server time to fully start
    
    if curl -f -s "http://$SERVER_IP:8000/health" > /dev/null; then
        log_info "Health check passed ✅"
    else
        log_error "Health check failed. Check server logs."
        gcloud compute ssh $SERVER_INSTANCE --zone=$ZONE \
            --command="cd ~/model_server && tail -20 server.log"
        return 1
    fi
    
    # Test chat endpoint
    TEST_RESPONSE=$(curl -s -X POST "http://$SERVER_IP:8000/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{
            "messages": [
                {"role": "user", "content": "Hello, are you working?"}
            ],
            "max_tokens": 50
        }')
    
    if echo "$TEST_RESPONSE" | grep -q "choices"; then
        log_info "Chat endpoint test passed ✅"
    else
        log_error "Chat endpoint test failed"
        echo "Response: $TEST_RESPONSE"
        return 1
    fi
    
    log_info "Model server testing complete ✅"
}

update_lexai_config() {
    log_info "Updating LexAI configuration..."
    
    # Get server IP
    SERVER_IP=$(gcloud compute instances describe $SERVER_INSTANCE \
        --zone=$ZONE \
        --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    
    # Update bagel_integration.py
    if [ -f "../bagel_integration.py" ]; then
        sed -i.bak "s|http://localhost:8000|http://$SERVER_IP:8000|g" ../bagel_integration.py
        log_info "Updated bagel_integration.py with server endpoint"
    fi
    
    # Update env file
    echo "BAGEL_MODEL_ENDPOINT=http://$SERVER_IP:8000" >> ../bagel_production.env
    
    log_info "LexAI configuration updated ✅"
}

run_evaluation() {
    log_info "Running model evaluation..."
    
    # Evaluation script
    cat > run_evaluation.sh << 'EOF'
#!/bin/bash
set -e

cd ~/bagel-RL

echo "Running model evaluation..."
python ~/bagel_config/evaluate_legal_model.py \
    --model-path merged_legal_model/ \
    --output-dir evaluation_results/ \
    --model-name legal-bagel-rl

echo "Evaluation complete!"
cat evaluation_results/evaluation_report.json
EOF
    
    # Run evaluation
    gcloud compute scp --zone=$ZONE run_evaluation.sh $TRAINING_INSTANCE:~/
    gcloud compute ssh $TRAINING_INSTANCE --zone=$ZONE \
        --command="chmod +x ~/run_evaluation.sh && ~/run_evaluation.sh"
    
    # Download evaluation results
    gcloud compute scp --zone=$ZONE \
        --recurse $TRAINING_INSTANCE:~/bagel-RL/evaluation_results/ ./
    
    # Clean up
    rm run_evaluation.sh
    
    log_info "Model evaluation complete ✅"
    log_info "Results saved to ./evaluation_results/"
}

print_deployment_info() {
    # Get server IP
    SERVER_IP=$(gcloud compute instances describe $SERVER_INSTANCE \
        --zone=$ZONE \
        --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    
    echo ""
    log_info "🎉 Model Deployment Complete!"
    echo ""
    echo "📋 Server Information:"
    echo "Model Server URL: http://$SERVER_IP:8000"
    echo "Health Check: http://$SERVER_IP:8000/health"
    echo "API Docs: http://$SERVER_IP:8000/docs"
    echo ""
    echo "🧪 Test Commands:"
    echo "curl http://$SERVER_IP:8000/health"
    echo ""
    echo "📊 Evaluation Results:"
    if [ -d "./evaluation_results" ]; then
        echo "Results saved to: ./evaluation_results/"
        if [ -f "./evaluation_results/evaluation_report.json" ]; then
            echo "Overall Score: $(cat ./evaluation_results/evaluation_report.json | grep -o '"overall_score":[0-9.]*' | cut -d':' -f2)"
        fi
    fi
    echo ""
    echo "🔗 LexAI Integration:"
    echo "Update your .env file:"
    echo "echo 'BAGEL_MODEL_ENDPOINT=http://$SERVER_IP:8000' >> .env"
    echo ""
    echo "💰 Monthly Cost: ~$140 (n1-standard-4)"
    echo "🔧 Management Commands:"
    echo "  Start server: gcloud compute instances start $SERVER_INSTANCE --zone=$ZONE"
    echo "  Stop server:  gcloud compute instances stop $SERVER_INSTANCE --zone=$ZONE"
    echo ""
}

# Main execution
main() {
    log_info "Starting model deployment pipeline..."
    
    # Check if training is complete
    if ! check_training_complete; then
        log_info "Training not complete. Merging model first..."
        merge_model
    fi
    
    copy_model_to_server
    create_model_server
    start_model_server
    test_model_server
    update_lexai_config
    run_evaluation
    print_deployment_info
    
    log_info "🚀 Model deployment pipeline complete!"
}

# Run main function
main "$@"