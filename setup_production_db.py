#!/usr/bin/env python3
"""
Production Database Setup Helper
"""
import os
from dotenv import load_dotenv

def setup_production_database():
    """Guide user through production database setup"""
    
    print("🗄️  LexAI Production Database Setup")
    print("=" * 50)
    
    print("📋 Step 1: Neon PostgreSQL Database Creation")
    print("-" * 50)
    print("1. Go to: https://console.neon.tech/")
    print("2. Create new project: 'lexai-production'")
    print("3. Database name: 'lexai_database'")
    print("4. Copy the connection string")
    print()
    
    print("📝 Step 2: Environment Variables Setup")
    print("-" * 50)
    print("Add these to your .env file:")
    print()
    print("# Production Database Configuration")
    print("DATABASE_URL=postgresql://username:password@hostname/database?sslmode=require")
    print("POSTGRES_URL=postgresql://username:password@hostname/database?sslmode=require")
    print()
    print("# Optional: Redis for production")
    print("REDIS_URL=redis://your-redis-url")
    print()
    
    print("🔧 Step 3: Vercel Environment Variables")
    print("-" * 50)
    print("Set these in Vercel Dashboard:")
    print("1. Go to: https://vercel.com/dashboard")
    print("2. Select your project: lexai-app")
    print("3. Go to Settings > Environment Variables")
    print("4. Add:")
    print("   - DATABASE_URL (production value)")
    print("   - POSTGRES_URL (same as DATABASE_URL)")
    print("   - Any other production secrets")
    print()
    
    print("⚡ Step 4: Test Database Connection")
    print("-" * 50)
    print("Run these commands after setup:")
    print("1. python test_database_connection.py")
    print("2. python init_db.py (to create tables)")
    print("3. python test_rbac_with_db.py (to verify RBAC)")
    print()
    
    print("🚀 Expected Results:")
    print("-" * 50)
    print("✅ Database tables created automatically")
    print("✅ RBAC system activates (DATABASE_AVAILABLE=True)")
    print("✅ Admin user created for testing")
    print("✅ Sample data populated")
    print("✅ Production-ready security enforcement")

def check_current_config():
    """Check current database configuration"""
    load_dotenv()
    
    print("\n📊 Current Configuration Status:")
    print("-" * 50)
    
    db_url = os.getenv('DATABASE_URL')
    postgres_url = os.getenv('POSTGRES_URL') 
    redis_url = os.getenv('REDIS_URL')
    
    print(f"DATABASE_URL: {'✅ Set' if db_url else '❌ Not set'}")
    print(f"POSTGRES_URL: {'✅ Set' if postgres_url else '❌ Not set'}")
    print(f"REDIS_URL: {'✅ Set' if redis_url else '❌ Not set'}")
    
    if db_url:
        # Hide password for security
        safe_url = db_url.split('@')[1] if '@' in db_url else 'Invalid format'
        print(f"Database host: {safe_url}")
    
    return bool(db_url)

if __name__ == "__main__":
    setup_production_database()
    has_db = check_current_config()
    
    if not has_db:
        print("\n🎯 Next Action: Set up your Neon database and update .env file")
    else:
        print("\n✅ Database URL configured! Ready to test connection.")