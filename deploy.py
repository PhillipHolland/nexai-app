#!/usr/bin/env python3
"""
LexAI Practice Partner - Production Deployment Script
Handles environment validation, database setup, and production deployment
"""

import os
import sys
import secrets
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from config import validate_environment, get_config

def print_banner():
    """Print deployment banner"""
    print("=" * 70)
    print("🏛️  LexAI Practice Partner - Production Deployment")
    print("=" * 70)

def generate_secret_key():
    """Generate a secure secret key"""
    return secrets.token_urlsafe(32)

def check_requirements():
    """Check if all required dependencies are installed"""
    print("📦 Checking requirements...")
    
    try:
        import flask
        import flask_sqlalchemy
        import bcrypt
        import requests
        print("✅ All required packages are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing required package: {e}")
        print("Run: pip install -r requirements.txt")
        return False

def validate_config():
    """Validate configuration and environment variables"""
    print("🔍 Validating configuration...")
    
    validation_result = validate_environment()
    
    if validation_result['valid']:
        print("✅ Configuration is valid")
        
        if validation_result['warnings']:
            print("\n⚠️  Warnings:")
            for warning in validation_result['warnings']:
                print(f"   - {warning}")
        
        return True
    else:
        print("❌ Configuration validation failed:")
        for error in validation_result['errors']:
            print(f"   - {error}")
        return False

def setup_environment():
    """Set up environment file if it doesn't exist"""
    env_path = Path('.env')
    env_example_path = Path('.env.example')
    
    if not env_path.exists():
        print("📝 Setting up environment file...")
        
        if env_example_path.exists():
            # Copy example file
            with open(env_example_path, 'r') as example:
                content = example.read()
            
            # Generate a secure secret key
            secret_key = generate_secret_key()
            content = content.replace('your-secret-key-here', secret_key)
            
            with open(env_path, 'w') as env_file:
                env_file.write(content)
            
            print("✅ Created .env file from .env.example")
            print(f"🔑 Generated secure SECRET_KEY: {secret_key[:10]}...")
            print("\n⚠️  IMPORTANT: Please update the following in your .env file:")
            print("   - XAI_API_KEY: Your X.AI API key")
            print("   - DATABASE_URL: Your production database URL")
            print("   - Email settings (if using password reset)")
            
            return False  # Need manual configuration
        else:
            print("❌ .env.example file not found")
            return False
    else:
        print("✅ .env file already exists")
        return True

def setup_database():
    """Set up database tables"""
    print("🗄️  Setting up database...")
    
    try:
        from app import app, db
        
        with app.app_context():
            # Create all tables
            db.create_all()
            print("✅ Database tables created successfully")
            return True
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False

def setup_directories():
    """Create necessary directories"""
    print("📁 Setting up directories...")
    
    directories = [
        'logs',
        'uploads',
        'instance'
    ]
    
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created directory: {directory}")
        else:
            print(f"✅ Directory exists: {directory}")

def run_tests():
    """Run basic application tests"""
    print("🧪 Running tests...")
    
    try:
        from app import app
        
        with app.test_client() as client:
            # Test basic routes
            response = client.get('/')
            if response.status_code == 200:
                print("✅ Dashboard route working")
            else:
                print(f"❌ Dashboard route failed: {response.status_code}")
                return False
            
            # Test API health
            response = client.get('/health')
            if response.status_code in [200, 404]:  # 404 is ok if route doesn't exist yet
                print("✅ Application is responsive")
            else:
                print(f"❌ Application health check failed: {response.status_code}")
                return False
        
        return True
    except Exception as e:
        print(f"❌ Tests failed: {e}")
        return False

def create_production_script():
    """Create production startup script"""
    print("🚀 Creating production startup script...")
    
    script_content = """#!/bin/bash
# LexAI Production Startup Script

echo "🏛️  Starting LexAI Practice Partner..."

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set production environment
export FLASK_ENV=production
export FLASK_DEBUG=false

# Start with Gunicorn
gunicorn --bind 0.0.0.0:8000 --workers 4 --timeout 30 app:app
"""
    
    with open('start_production.sh', 'w') as f:
        f.write(script_content)
    
    # Make executable
    os.chmod('start_production.sh', 0o755)
    print("✅ Created start_production.sh")

def main():
    """Main deployment function"""
    print_banner()
    
    # Load environment variables
    load_dotenv()
    
    success = True
    
    # Check requirements
    if not check_requirements():
        success = False
    
    # Set up environment
    if not setup_environment():
        print("\n⚠️  Manual configuration required. Please update .env file and run again.")
        return
    
    # Reload environment after setup
    load_dotenv()
    
    # Validate configuration
    if not validate_config():
        success = False
    
    # Set up directories
    setup_directories()
    
    # Set up database
    if not setup_database():
        success = False
    
    # Run tests
    if not run_tests():
        success = False
    
    # Create production script
    create_production_script()
    
    # Final status
    print("\n" + "=" * 70)
    
    if success:
        print("🎉 Deployment preparation completed successfully!")
        print("\nNext steps:")
        print("1. Review your .env file configuration")
        print("2. For production: ./start_production.sh")
        print("3. For development: python app.py")
        print("4. Visit: http://localhost:8000 (production) or http://localhost:5002 (dev)")
    else:
        print("❌ Deployment preparation failed. Please fix the errors above.")
        sys.exit(1)
    
    print("=" * 70)

if __name__ == '__main__':
    main()