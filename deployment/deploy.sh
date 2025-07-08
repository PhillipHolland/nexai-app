#!/bin/bash
set -e

# LexAI Bagel RL Deployment Script
# Automates the complete setup process

echo "🚀 Starting LexAI Bagel RL Deployment..."

# Configuration
PROJECT_ID="lexai-bagel-rl"
ZONE="us-central1-c"
TRAINING_INSTANCE="bagel-legal-trainer"
SERVER_INSTANCE="bagel-legal-server"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    log_info "Checking dependencies..."
    
    if ! command -v gcloud &> /dev/null; then
        log_error "Google Cloud CLI not found. Please install it first."
        exit 1
    fi
    
    if ! command -v git &> /dev/null; then
        log_error "Git not found. Please install it first."
        exit 1
    fi
    
    log_info "Dependencies check passed ✅"
}

setup_gcloud_project() {
    log_info "Setting up Google Cloud project..."
    
    # Check if project exists
    if gcloud projects describe $PROJECT_ID &>/dev/null; then
        log_warn "Project $PROJECT_ID already exists"
    else
        log_info "Creating project $PROJECT_ID..."
        gcloud projects create $PROJECT_ID --name="LexAI Bagel RL"
    fi
    
    # Set current project
    gcloud config set project $PROJECT_ID
    
    # Enable APIs
    log_info "Enabling required APIs..."
    gcloud services enable compute.googleapis.com
    gcloud services enable storage.googleapis.com
    gcloud services enable logging.googleapis.com
    
    log_info "Google Cloud project setup complete ✅"
}

create_service_account() {
    log_info "Creating service account..."
    
    SERVICE_ACCOUNT="bagel-rl-service@${PROJECT_ID}.iam.gserviceaccount.com"
    
    # Check if service account exists
    if gcloud iam service-accounts describe $SERVICE_ACCOUNT &>/dev/null; then
        log_warn "Service account already exists"
    else
        gcloud iam service-accounts create bagel-rl-service \
            --display-name="Bagel RL Service Account"
        
        # Grant permissions
        gcloud projects add-iam-policy-binding $PROJECT_ID \
            --member="serviceAccount:$SERVICE_ACCOUNT" \
            --role="roles/compute.admin"
        
        gcloud projects add-iam-policy-binding $PROJECT_ID \
            --member="serviceAccount:$SERVICE_ACCOUNT" \
            --role="roles/storage.admin"
    fi
    
    # Create key if it doesn't exist
    if [ ! -f "bagel-rl-key.json" ]; then
        log_info "Creating service account key..."
        gcloud iam service-accounts keys create bagel-rl-key.json \
            --iam-account=$SERVICE_ACCOUNT
    fi
    
    log_info "Service account setup complete ✅"
}

create_training_instance() {
    log_info "Creating training instance..."
    
    # Check if instance exists
    if gcloud compute instances describe $TRAINING_INSTANCE --zone=$ZONE &>/dev/null; then
        log_warn "Training instance already exists"
        return
    fi
    
    log_info "Creating GPU training instance..."
    gcloud compute instances create $TRAINING_INSTANCE \
        --zone=$ZONE \
        --machine-type=n1-standard-8 \
        --accelerator=type=nvidia-tesla-v100,count=1 \
        --image-family=pytorch-latest-gpu \
        --image-project=deeplearning-platform-release \
        --boot-disk-size=100GB \
        --boot-disk-type=pd-ssd \
        --scopes=https://www.googleapis.com/auth/cloud-platform \
        --maintenance-policy=TERMINATE \
        --metadata="install-nvidia-driver=True"
    
    log_info "Waiting for instance to be ready..."
    gcloud compute instances wait-until-running $TRAINING_INSTANCE --zone=$ZONE
    
    log_info "Training instance created ✅"
}

create_server_instance() {
    log_info "Creating server instance..."
    
    # Check if instance exists
    if gcloud compute instances describe $SERVER_INSTANCE --zone=$ZONE &>/dev/null; then
        log_warn "Server instance already exists"
        return
    fi
    
    log_info "Creating CPU inference instance..."
    gcloud compute instances create $SERVER_INSTANCE \
        --zone=$ZONE \
        --machine-type=n1-standard-4 \
        --image-family=ubuntu-2004-lts \
        --image-project=ubuntu-os-cloud \
        --boot-disk-size=50GB \
        --boot-disk-type=pd-standard \
        --scopes=https://www.googleapis.com/auth/cloud-platform
    
    log_info "Waiting for instance to be ready..."
    gcloud compute instances wait-until-running $SERVER_INSTANCE --zone=$ZONE
    
    log_info "Server instance created ✅"
}

setup_firewall() {
    log_info "Setting up firewall rules..."
    
    # Check if firewall rule exists
    if gcloud compute firewall-rules describe bagel-server-ports &>/dev/null; then
        log_warn "Firewall rule already exists"
        return
    fi
    
    gcloud compute firewall-rules create bagel-server-ports \
        --allow tcp:8000,tcp:80,tcp:443,tcp:6006 \
        --source-ranges 0.0.0.0/0 \
        --description "Allow Bagel model server access"
    
    log_info "Firewall rules created ✅"
}

setup_training_environment() {
    log_info "Setting up training environment..."
    
    # Upload configuration files
    log_info "Uploading configuration files..."
    gcloud compute scp --zone=$ZONE \
        --recurse ../bagel_config/ \
        $TRAINING_INSTANCE:~/bagel_config/
    
    # Setup script for training instance
    cat > setup_training.sh << 'EOF'
#!/bin/bash
set -e

echo "Setting up training environment on instance..."

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python dependencies
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install transformers datasets accelerate
pip install wandb tensorboard
pip install pandas numpy scipy

# Install Bagel RL
if [ ! -d "bagel-RL" ]; then
    git clone https://github.com/bagel-org/bagel-RL.git
fi
cd bagel-RL
pip install -e .

# Install BFCL
pip install bfcl

echo "Training environment setup complete!"
EOF
    
    # Run setup on training instance
    gcloud compute scp --zone=$ZONE setup_training.sh $TRAINING_INSTANCE:~/
    gcloud compute ssh $TRAINING_INSTANCE --zone=$ZONE --command="chmod +x ~/setup_training.sh && ~/setup_training.sh"
    
    # Clean up
    rm setup_training.sh
    
    log_info "Training environment setup complete ✅"
}

setup_server_environment() {
    log_info "Setting up server environment..."
    
    # Setup script for server instance
    cat > setup_server.sh << 'EOF'
#!/bin/bash
set -e

echo "Setting up server environment on instance..."

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install -y python3-pip
pip3 install fastapi uvicorn transformers torch

# Create model server directory
mkdir -p ~/model_server

echo "Server environment setup complete!"
EOF
    
    # Run setup on server instance
    gcloud compute scp --zone=$ZONE setup_server.sh $SERVER_INSTANCE:~/
    gcloud compute ssh $SERVER_INSTANCE --zone=$ZONE --command="chmod +x ~/setup_server.sh && ~/setup_server.sh"
    
    # Clean up
    rm setup_server.sh
    
    log_info "Server environment setup complete ✅"
}

start_training() {
    log_info "Starting model training..."
    
    # Training script
    cat > run_training.sh << 'EOF'
#!/bin/bash
set -e

cd ~/bagel-RL

# Copy legal configuration
cp ~/bagel_config/legal_tools_config.json configs/legal_sft_config.json
cp ~/bagel_config/train_legal_model.py ./

echo "Starting training..."
python train_legal_model.py

echo "Training started! Check progress with: tensorboard --logdir legal_model_output/ --host 0.0.0.0 --port 6006"
EOF
    
    # Run training
    gcloud compute scp --zone=$ZONE run_training.sh $TRAINING_INSTANCE:~/
    gcloud compute ssh $TRAINING_INSTANCE --zone=$ZONE --command="chmod +x ~/run_training.sh && nohup ~/run_training.sh > training.log 2>&1 &"
    
    # Clean up
    rm run_training.sh
    
    log_info "Training started! Monitor at http://TRAINING_INSTANCE_IP:6006 ✅"
}

get_instance_ips() {
    log_info "Getting instance IP addresses..."
    
    TRAINING_IP=$(gcloud compute instances describe $TRAINING_INSTANCE \
        --zone=$ZONE \
        --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    
    SERVER_IP=$(gcloud compute instances describe $SERVER_INSTANCE \
        --zone=$ZONE \
        --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    
    echo ""
    log_info "📋 Instance Information:"
    echo "Training Instance IP: $TRAINING_IP"
    echo "Server Instance IP: $SERVER_IP"
    echo "TensorBoard: http://$TRAINING_IP:6006"
    echo "Model Server: http://$SERVER_IP:8000"
    echo ""
}

create_env_file() {
    log_info "Creating environment configuration..."
    
    SERVER_IP=$(gcloud compute instances describe $SERVER_INSTANCE \
        --zone=$ZONE \
        --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    
    cat > ../bagel_production.env << EOF
# Bagel RL Production Configuration
GOOGLE_CLOUD_PROJECT_ID=$PROJECT_ID
BAGEL_MODEL_ENDPOINT=http://$SERVER_IP:8000
BAGEL_TRAINING_INSTANCE=$TRAINING_INSTANCE
BAGEL_SERVER_INSTANCE=$SERVER_INSTANCE
BAGEL_ZONE=$ZONE
GOOGLE_APPLICATION_CREDENTIALS=./deployment/bagel-rl-key.json
EOF
    
    log_info "Environment file created: bagel_production.env ✅"
}

print_next_steps() {
    log_info "🎉 Deployment Complete!"
    echo ""
    echo "📋 Next Steps:"
    echo "1. Monitor training progress:"
    echo "   gcloud compute ssh $TRAINING_INSTANCE --zone=$ZONE"
    echo "   tail -f training.log"
    echo ""
    echo "2. Access TensorBoard:"
    echo "   gcloud compute ssh $TRAINING_INSTANCE --zone=$ZONE -- -L 6006:localhost:6006"
    echo "   Open http://localhost:6006"
    echo ""
    echo "3. After training completes, deploy the model:"
    echo "   ./deploy_model.sh"
    echo ""
    echo "4. Update your .env file with:"
    echo "   cat bagel_production.env >> .env"
    echo ""
    echo "💰 Estimated monthly cost: $150-200"
    echo "⏱️  Training time: 4-8 hours"
    echo ""
}

# Main execution
main() {
    log_info "Starting LexAI Bagel RL deployment pipeline..."
    
    check_dependencies
    setup_gcloud_project
    create_service_account
    create_training_instance
    create_server_instance
    setup_firewall
    
    # Wait a bit for instances to fully initialize
    log_info "Waiting for instances to initialize..."
    sleep 60
    
    setup_training_environment
    setup_server_environment
    start_training
    get_instance_ips
    create_env_file
    print_next_steps
    
    log_info "🚀 Deployment pipeline complete!"
}

# Run main function
main "$@"