#!/usr/bin/env python3
"""
Create Initial Admin User for LexAI Practice Partner
"""
import os
import sys
import psycopg2
from datetime import datetime
import bcrypt
import uuid

def create_admin_user():
    """Create the initial admin user"""
    
    print("👤 Creating Initial Admin User")
    print("=" * 50)
    
    # Database connection
    DATABASE_URL = "postgres://neondb_owner:npg_9OENS6QdCUoM@ep-weathered-voice-afzm9t1s-pooler.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"
    
    try:
        # Connect to database
        print("📡 Connecting to production database...")
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Check if users table exists
        print("🔍 Checking database schema...")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'users';
        """)
        
        users_table_exists = cursor.fetchone() is not None
        
        if not users_table_exists:
            print("📋 Creating users table...")
            cursor.execute("""
                CREATE TABLE users (
                    id VARCHAR(36) PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash BYTEA NOT NULL,
                    first_name VARCHAR(100) NOT NULL,
                    last_name VARCHAR(100) NOT NULL,
                    firm_name VARCHAR(255),
                    role VARCHAR(50) DEFAULT 'user',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP WITH TIME ZONE,
                    password_updated_at TIMESTAMP WITH TIME ZONE,
                    reset_token VARCHAR(255),
                    reset_token_expires TIMESTAMP WITH TIME ZONE
                );
            """)
            print("✅ Users table created successfully")
        else:
            print("✅ Users table already exists")
        
        # Check if admin user already exists
        print("🔍 Checking for existing admin user...")
        cursor.execute("SELECT id, email FROM users WHERE email = %s", ('admin@lexai.com',))
        existing_admin = cursor.fetchone()
        
        if existing_admin:
            print(f"⚠️  Admin user already exists: {existing_admin[1]}")
            print(f"   User ID: {existing_admin[0]}")
            return True
        
        # Admin user details
        admin_data = {
            'id': str(uuid.uuid4()),
            'email': 'admin@lexai.com',
            'password': 'LexAI2025!',  # Strong temporary password
            'first_name': 'Admin',
            'last_name': 'User',
            'firm_name': 'LexAI Practice Partner',
            'role': 'admin'
        }
        
        # Hash password
        print("🔐 Hashing password...")
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(admin_data['password'].encode('utf-8'), salt)
        
        # Insert admin user
        print("👤 Creating admin user...")
        cursor.execute("""
            INSERT INTO users (
                id, email, password_hash, first_name, last_name, 
                firm_name, role, is_active, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            admin_data['id'],
            admin_data['email'],
            password_hash,
            admin_data['first_name'],
            admin_data['last_name'],
            admin_data['firm_name'],
            admin_data['role'],
            True,
            datetime.utcnow()
        ))
        
        # Create test regular user too
        print("👥 Creating test regular user...")
        test_user_id = str(uuid.uuid4())
        test_password_hash = bcrypt.hashpw('TestUser2025!'.encode('utf-8'), bcrypt.gensalt())
        
        cursor.execute("""
            INSERT INTO users (
                id, email, password_hash, first_name, last_name, 
                firm_name, role, is_active, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            test_user_id,
            'user@lexai.com',
            test_password_hash,
            'Test',
            'User',
            'Test Law Firm',
            'user',
            True,
            datetime.utcnow()
        ))
        
        # Commit changes
        conn.commit()
        
        print("✅ Admin user created successfully!")
        print("✅ Test regular user created successfully!")
        print()
        print("🔑 Login Credentials:")
        print("-" * 30)
        print("ADMIN USER:")
        print(f"  Email: {admin_data['email']}")
        print(f"  Password: {admin_data['password']}")
        print(f"  Role: {admin_data['role']}")
        print()
        print("TEST USER:")
        print("  Email: user@lexai.com")
        print("  Password: TestUser2025!")
        print("  Role: user")
        print()
        print("🚀 You can now test the authentication system at:")
        print("   https://lexai-q7mbc64og-gentler-coparent.vercel.app/login")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False

def test_user_creation():
    """Test that user creation worked"""
    
    print("\n🧪 Testing User Creation")
    print("-" * 30)
    
    DATABASE_URL = "postgres://neondb_owner:npg_9OENS6QdCUoM@ep-weathered-voice-afzm9t1s-pooler.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Count users
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        # Get user details
        cursor.execute("SELECT email, role, is_active FROM users ORDER BY created_at")
        users = cursor.fetchall()
        
        print(f"📊 Total users in database: {user_count}")
        print("\n👥 User List:")
        for email, role, is_active in users:
            status = "✅ Active" if is_active else "❌ Inactive"
            print(f"  {email:20} | {role:10} | {status}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing users: {e}")
        return False

if __name__ == "__main__":
    success = create_admin_user()
    if success:
        test_user_creation()
    
    print("\n" + "=" * 50)
    print("🎯 Next Steps:")
    print("1. Test login at: https://lexai-q7mbc64og-gentler-coparent.vercel.app/login")
    print("2. Use admin credentials to verify RBAC system")
    print("3. Test different user roles and permissions")
    print("=" * 50)