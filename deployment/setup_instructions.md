# Complete Bagel RL Legal AI Setup Instructions

## 🔧 Prerequisites

### Required Accounts & Tools
- Google Cloud Platform account with billing enabled
- Git installed locally
- Python 3.8+ installed
- Docker installed (optional but recommended)

### Required API Keys
```bash
# Add to your .env file
GOOGLE_CLOUD_PROJECT_ID="your-project-id"
GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"
BAGEL_MODEL_ENDPOINT="http://your-instance-ip:8000"
```

## 📋 Step 1: Google Cloud Setup

### 1.1 Create New Project
```bash
# Install Google Cloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init

# Create new project
gcloud projects create lexai-bagel-rl --name="LexAI Bagel RL"
gcloud config set project lexai-bagel-rl

# Enable required APIs
gcloud services enable compute.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable logging.googleapis.com
```

### 1.2 Set Up Billing & Quotas
```bash
# Link billing account (replace with your billing account ID)
gcloud billing projects link lexai-bagel-rl --billing-account=YOUR_BILLING_ACCOUNT_ID

# Request GPU quota increase (required for training)
# Go to: https://console.cloud.google.com/iam-admin/quotas
# Search for "GPUs (all regions)" and request increase to 4 GPUs
```

### 1.3 Create Service Account
```bash
# Create service account
gcloud iam service-accounts create bagel-rl-service \
    --display-name="Bagel RL Service Account"

# Grant necessary permissions
gcloud projects add-iam-policy-binding lexai-bagel-rl \
    --member="serviceAccount:bagel-rl-service@lexai-bagel-rl.iam.gserviceaccount.com" \
    --role="roles/compute.admin"

gcloud projects add-iam-policy-binding lexai-bagel-rl \
    --member="serviceAccount:bagel-rl-service@lexai-bagel-rl.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

# Create and download key
gcloud iam service-accounts keys create ~/bagel-rl-key.json \
    --iam-account=bagel-rl-service@lexai-bagel-rl.iam.gserviceaccount.com
```

## 🖥️ Step 2: Create Training Instance

### 2.1 GPU Training Instance
```bash
# Create GPU instance for training
gcloud compute instances create bagel-legal-trainer \
    --zone=us-central1-c \
    --machine-type=n1-standard-8 \
    --accelerator=type=nvidia-tesla-v100,count=1 \
    --image-family=pytorch-latest-gpu \
    --image-project=deeplearning-platform-release \
    --boot-disk-size=100GB \
    --boot-disk-type=pd-ssd \
    --scopes=https://www.googleapis.com/auth/cloud-platform \
    --maintenance-policy=TERMINATE \
    --metadata="install-nvidia-driver=True"
```

### 2.2 CPU Inference Instance  
```bash
# Create CPU instance for model serving
gcloud compute instances create bagel-legal-server \
    --zone=us-central1-c \
    --machine-type=n1-standard-4 \
    --image-family=ubuntu-2004-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=50GB \
    --boot-disk-type=pd-standard \
    --scopes=https://www.googleapis.com/auth/cloud-platform
```

### 2.3 Configure Firewall
```bash
# Allow HTTP/HTTPS traffic for model serving
gcloud compute firewall-rules create bagel-server-ports \
    --allow tcp:8000,tcp:80,tcp:443 \
    --source-ranges 0.0.0.0/0 \
    --description "Allow Bagel model server access"
```

## 📦 Step 3: Setup Training Environment

### 3.1 Connect to Training Instance
```bash
# SSH into training instance
gcloud compute ssh bagel-legal-trainer --zone=us-central1-c
```

### 3.2 Install Dependencies (on training instance)
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python dependencies
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install transformers datasets accelerate
pip install wandb tensorboard
pip install pandas numpy scipy

# Install Bagel RL
git clone https://github.com/bagel-org/bagel-RL.git
cd bagel-RL
pip install -e .

# Install BFCL for evaluation
pip install bfcl
```

### 3.3 Upload LexAI Configuration
```bash
# From your local machine, upload config files
gcloud compute scp --zone=us-central1-c \
    --recurse /Users/phillipholland/Desktop/lexai/lexai-app/bagel_config/ \
    bagel-legal-trainer:~/bagel_config/
```

## 🎯 Step 4: Training Pipeline

### 4.1 Prepare Training Data (on training instance)
```bash
cd ~/bagel-RL

# Copy our legal configuration
cp ~/bagel_config/legal_tools_config.json configs/legal_sft_config.json
cp ~/bagel_config/train_legal_model.py ./

# Generate synthetic legal dataset
python train_legal_model.py --generate-data-only
```

### 4.2 Start Training
```bash
# Run training with legal configuration
python train.py --config configs/legal_sft_config.json --output-dir legal_model_output/

# Monitor training with TensorBoard
tensorboard --logdir legal_model_output/ --host 0.0.0.0 --port 6006
```

### 4.3 Monitor Training Progress
```bash
# In new terminal/tab, tunnel TensorBoard
gcloud compute ssh bagel-legal-trainer --zone=us-central1-c -- -L 6006:localhost:6006

# Open http://localhost:6006 in your browser to view training progress
```

## 🔄 Step 5: Model Evaluation

### 5.1 Evaluate Trained Model
```bash
# Run BFCL evaluation
python ~/bagel_config/evaluate_legal_model.py \
    --model-path legal_model_output/ \
    --output-dir evaluation_results/

# View evaluation results
cat evaluation_results/evaluation_report.json
```

### 5.2 Merge and Save Model
```bash
# Merge LoRA adapters with base model
python save_merge_model.py \
    --base_model Qwen/Qwen3-0.6B \
    --adapter_path legal_model_output/ \
    --output_dir merged_legal_model/ \
    --trust_remote_code
```

## 🚀 Step 6: Model Deployment

### 6.1 Setup Model Server (on inference instance)
```bash
# SSH into server instance
gcloud compute ssh bagel-legal-server --zone=us-central1-c

# Install serving dependencies
sudo apt update
pip install fastapi uvicorn transformers torch

# Create model server directory
mkdir -p ~/model_server
```

### 6.2 Copy Trained Model
```bash
# Copy model from training instance to server instance
gcloud compute scp --zone=us-central1-c \
    --recurse bagel-legal-trainer:~/bagel-RL/merged_legal_model/ \
    bagel-legal-server:~/model_server/
```

### 6.3 Create Model Server Script
```bash
# On server instance, create server.py
cat > ~/model_server/server.py << 'EOF'
from fastapi import FastAPI
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import json
from typing import Dict, List

app = FastAPI()

# Load model and tokenizer
model_path = "./merged_legal_model"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    torch_dtype=torch.float16,
    device_map="auto"
)

@app.post("/v1/chat/completions")
async def chat_completions(request: Dict):
    messages = request.get("messages", [])
    tools = request.get("tools", [])
    
    # Format prompt for tool use
    prompt = format_chat_prompt(messages, tools)
    
    # Generate response
    inputs = tokenizer(prompt, return_tensors="pt")
    with torch.no_grad():
        outputs = model.generate(
            inputs.input_ids,
            max_new_tokens=512,
            temperature=0.1,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )
    
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": response
            }
        }]
    }

def format_chat_prompt(messages: List[Dict], tools: List[Dict]) -> str:
    prompt = "You are a legal AI assistant with access to specialized tools.\n\n"
    
    if tools:
        prompt += "Available tools:\n"
        for tool in tools:
            prompt += f"- {tool['name']}: {tool['description']}\n"
        prompt += "\n"
    
    for msg in messages:
        prompt += f"{msg['role']}: {msg['content']}\n"
    
    prompt += "assistant:"
    return prompt

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF
```

### 6.4 Start Model Server
```bash
# Start server
cd ~/model_server
python server.py

# Keep server running in background
nohup python server.py > server.log 2>&1 &
```

## 🔗 Step 7: LexAI Integration

### 7.1 Get Server IP Address
```bash
# Get external IP of server instance
gcloud compute instances describe bagel-legal-server \
    --zone=us-central1-c \
    --format="value(networkInterfaces[0].accessConfigs[0].natIP)"
```

### 7.2 Update LexAI Configuration
```bash
# Update your local .env file
echo "BAGEL_MODEL_ENDPOINT=http://EXTERNAL_IP:8000" >> .env

# Update bagel_integration.py with correct endpoint
```

### 7.3 Test Integration
```bash
# Test from your local LexAI instance
cd /Users/phillipholland/Desktop/lexai/lexai-app

# Test evidence analysis
python -c "
from bagel_integration import enhance_evidence_analysis_with_bagel
result = enhance_evidence_analysis_with_bagel({
    'type': 'image',
    'analysis_depth': 'comprehensive'
})
print(result)
"
```

## 📊 Step 8: Production Optimization

### 8.1 Auto-scaling Setup
```bash
# Create instance template
gcloud compute instance-templates create bagel-server-template \
    --machine-type=n1-standard-4 \
    --image-family=ubuntu-2004-lts \
    --image-project=ubuntu-os-cloud

# Create managed instance group
gcloud compute instance-groups managed create bagel-server-group \
    --template=bagel-server-template \
    --size=1 \
    --zone=us-central1-c
```

### 8.2 Load Balancer
```bash
# Create health check
gcloud compute health-checks create http bagel-health-check \
    --port=8000 \
    --request-path=/health

# Create backend service
gcloud compute backend-services create bagel-backend \
    --health-checks=bagel-health-check \
    --global

# Add instance group to backend
gcloud compute backend-services add-backend bagel-backend \
    --instance-group=bagel-server-group \
    --instance-group-zone=us-central1-c \
    --global
```

### 8.3 Monitoring & Logging
```bash
# Install monitoring agent on server
curl -sSO https://dl.google.com/cloudagents/add-monitoring-agent-repo.sh
sudo bash add-monitoring-agent-repo.sh
sudo apt-get update
sudo apt-get install stackdriver-agent

# Start monitoring
sudo service stackdriver-agent start
```

## 🔧 Step 9: Maintenance Scripts

### 9.1 Model Update Script
```bash
# Create update script
cat > ~/update_model.sh << 'EOF'
#!/bin/bash
set -e

echo "Updating Bagel RL legal model..."

# Stop current server
pkill -f "python server.py" || true

# Backup current model
mv ~/model_server/merged_legal_model ~/model_server/merged_legal_model.backup.$(date +%Y%m%d)

# Copy new model from training instance
gcloud compute scp --zone=us-central1-c \
    --recurse bagel-legal-trainer:~/bagel-RL/merged_legal_model/ \
    bagel-legal-server:~/model_server/

# Restart server
cd ~/model_server
nohup python server.py > server.log 2>&1 &

echo "Model updated successfully!"
EOF

chmod +x ~/update_model.sh
```

### 9.2 Backup Script
```bash
# Create backup script
cat > ~/backup_model.sh << 'EOF'
#!/bin/bash
BACKUP_BUCKET="gs://lexai-bagel-backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Create bucket if it doesn't exist
gsutil mb $BACKUP_BUCKET 2>/dev/null || true

# Backup model
gsutil -m cp -r ~/model_server/merged_legal_model $BACKUP_BUCKET/model_$DATE/

echo "Model backed up to $BACKUP_BUCKET/model_$DATE/"
EOF

chmod +x ~/backup_model.sh
```

## ✅ Step 10: Verification Checklist

- [ ] Google Cloud project created and configured
- [ ] Training instance with GPU created
- [ ] Inference instance created
- [ ] Bagel RL installed and configured
- [ ] Legal training data generated
- [ ] Model training completed successfully
- [ ] Model evaluation shows good results
- [ ] Model deployed to inference server
- [ ] LexAI integration working
- [ ] Monitoring and logging configured
- [ ] Backup procedures in place

## 🚨 Troubleshooting

### Common Issues

1. **GPU Quota Exceeded**
   ```bash
   # Request quota increase or use different zone
   gcloud compute regions list
   ```

2. **Out of Memory During Training**
   ```bash
   # Reduce batch size in config
   "batch_size": 2,
   "gradient_accumulation_steps": 8
   ```

3. **Model Server Not Responding**
   ```bash
   # Check server logs
   tail -f ~/model_server/server.log
   
   # Restart server
   pkill -f "python server.py"
   cd ~/model_server && python server.py
   ```

4. **Slow Inference**
   ```bash
   # Optimize model loading
   # Use torch.compile() for faster inference
   # Consider quantization for smaller models
   ```

## 💰 Cost Optimization

### Training Costs
- V100 GPU: ~$2.48/hour
- Training time: ~4-8 hours
- Total training cost: ~$10-20

### Serving Costs
- n1-standard-4: ~$0.19/hour
- Monthly serving: ~$140
- Consider preemptible instances for 70% savings

### Storage Costs
- Model storage: ~$0.02/GB/month
- Backup storage: ~$0.01/GB/month

Total monthly cost: ~$150-200 for full production setup

## 📝 Next Steps

1. **Fine-tune hyperparameters** based on evaluation results
2. **Collect real legal data** to improve training
3. **Implement continuous training** pipeline
4. **Add A/B testing** for model improvements
5. **Scale horizontally** with multiple inference instances

---

This completes your production-ready Bagel RL legal AI system! 🎉