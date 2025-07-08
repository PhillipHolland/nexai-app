#!/bin/bash
set -e

# CPU-Only LexAI Bagel RL Deployment Script
# For immediate deployment without GPU quota

echo "🚀 Starting CPU-Only LexAI Bagel RL Deployment..."

# Configuration
PROJECT_ID="lexai-bagel-rl"
ZONE="us-central1-c"
TRAINING_INSTANCE="bagel-legal-trainer-cpu"
SERVER_INSTANCE="bagel-legal-server"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Create CPU training instance (no GPU quota needed)
create_cpu_training_instance() {
    log_step "Creating CPU training instance (no GPU quota required)..."
    
    if gcloud compute instances describe $TRAINING_INSTANCE --zone=$ZONE &>/dev/null; then
        log_warn "Training instance already exists"
        return
    fi
    
    log_info "Creating CPU-optimized training instance..."
    gcloud compute instances create $TRAINING_INSTANCE \
        --zone=$ZONE \
        --machine-type=n1-standard-16 \
        --image-family=pytorch-latest-cpu \
        --image-project=deeplearning-platform-release \
        --boot-disk-size=100GB \
        --boot-disk-type=pd-ssd \
        --preemptible \
        --scopes=https://www.googleapis.com/auth/cloud-platform \
        --metadata="startup-script=#!/bin/bash
        echo 'CPU training instance starting...'
        echo 'sudo shutdown -h +720' | at now
        " \
        --labels="purpose=bagel-training-cpu,environment=development"
    
    log_info "Waiting for instance to be ready..."
    gcloud compute instances wait-until-running $TRAINING_INSTANCE --zone=$ZONE
    
    log_info "CPU training instance created ✅"
}

# Create server instance
create_server_instance() {
    log_step "Creating server instance..."
    
    if gcloud compute instances describe $SERVER_INSTANCE --zone=$ZONE &>/dev/null; then
        log_warn "Server instance already exists"
        return
    fi
    
    gcloud compute instances create $SERVER_INSTANCE \
        --zone=$ZONE \
        --machine-type=n1-standard-4 \
        --image-family=ubuntu-2004-lts \
        --image-project=ubuntu-os-cloud \
        --boot-disk-size=50GB \
        --boot-disk-type=pd-standard \
        --scopes=https://www.googleapis.com/auth/cloud-platform \
        --labels="purpose=bagel-serving,environment=development"
    
    gcloud compute instances wait-until-running $SERVER_INSTANCE --zone=$ZONE
    log_info "Server instance created ✅"
}

# Setup CPU training environment
setup_cpu_training() {
    log_step "Setting up CPU training environment..."
    
    # Upload configs
    gcloud compute scp --zone=$ZONE \
        --recurse ../bagel_config/ \
        $TRAINING_INSTANCE:~/bagel_config/
    
    # Setup script
    cat > setup_cpu_training.sh << 'EOF'
#!/bin/bash
set -e

echo "Setting up CPU training environment..."

# Install dependencies
sudo apt update && sudo apt upgrade -y
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install transformers datasets accelerate
pip install tensorboard pandas numpy scipy

# Install Bagel RL
git clone https://github.com/bagel-org/bagel-RL.git
cd bagel-RL
pip install -e .

echo "CPU training environment ready!"
EOF
    
    gcloud compute scp --zone=$ZONE setup_cpu_training.sh $TRAINING_INSTANCE:~/
    gcloud compute ssh $TRAINING_INSTANCE --zone=$ZONE \
        --command="chmod +x ~/setup_cpu_training.sh && ~/setup_cpu_training.sh"
    
    rm setup_cpu_training.sh
    log_info "CPU training environment setup complete ✅"
}

# Start CPU training
start_cpu_training() {
    log_step "Starting CPU training (will take 12-24 hours)..."
    
    cat > run_cpu_training.sh << 'EOF'
#!/bin/bash
set -e

cd ~/bagel-RL

# Create CPU-optimized config
cat > configs/legal_cpu_config.json << 'CPUCONF'
{
  "model_config": {
    "base_model": "Qwen/Qwen3-0.6B",
    "training_type": "lora",
    "max_length": 2048,
    "learning_rate": 5e-5,
    "num_epochs": 2,
    "batch_size": 1,
    "gradient_accumulation_steps": 16,
    "dataloader_num_workers": 8,
    "fp16": false
  },
  "dataset_config": {
    "type": "legal_basic",
    "sources": ["legal_research", "evidence_analysis"],
    "synthetic_generation": true,
    "real_data_mixing": 0.2
  }
}
CPUCONF

echo "Starting CPU training..."
tensorboard --logdir legal_model_output/ --host 0.0.0.0 --port 6006 &

python train.py --config configs/legal_cpu_config.json --output-dir legal_model_output/

echo "CPU training completed!"
EOF
    
    gcloud compute scp --zone=$ZONE run_cpu_training.sh $TRAINING_INSTANCE:~/
    gcloud compute ssh $TRAINING_INSTANCE --zone=$ZONE \
        --command="chmod +x ~/run_cpu_training.sh && nohup ~/run_cpu_training.sh > training.log 2>&1 &"
    
    rm run_cpu_training.sh
    log_info "CPU training started! Monitor at TensorBoard ✅"
}

# Get IPs and create summary
get_instance_info() {
    TRAINING_IP=$(gcloud compute instances describe $TRAINING_INSTANCE \
        --zone=$ZONE \
        --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    
    SERVER_IP=$(gcloud compute instances describe $SERVER_INSTANCE \
        --zone=$ZONE \
        --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    
    echo ""
    log_info "🎉 CPU-Only Deployment Complete!"
    echo ""
    echo "📋 Instance Information:"
    echo "Training Instance IP: $TRAINING_IP"
    echo "Server Instance IP: $SERVER_IP"
    echo "TensorBoard: http://$TRAINING_IP:6006"
    echo ""
    echo "⏱️ Training Timeline:"
    echo "• CPU training: 12-24 hours (vs 4-8 hours on GPU)"
    echo "• Auto-shutdown: 12 hours"
    echo "• Cost: ~$0.75/hour (~$18 total)"
    echo ""
    echo "🔧 Monitor Progress:"
    echo "gcloud compute ssh $TRAINING_INSTANCE --zone=$ZONE --command='tail -f training.log'"
    echo ""
    echo "🚀 When ready for GPU:"
    echo "1. Request GPU quota at: https://console.cloud.google.com/iam-admin/quotas"
    echo "2. Run ./deploy_enhanced.sh for full GPU deployment"
    echo ""
}

# Main execution
main() {
    log_info "Starting CPU-only deployment..."
    
    create_cpu_training_instance
    create_server_instance
    
    sleep 60  # Wait for initialization
    
    setup_cpu_training
    start_cpu_training
    get_instance_info
    
    log_info "CPU deployment complete! 🎉"
}

main "$@"