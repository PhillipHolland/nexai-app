#!/usr/bin/env python3
"""
Test production database connection
"""
import os
import sys
from dotenv import load_dotenv

def test_database_connection():
    """Test connection to production database"""
    
    print("🧪 Testing Production Database Connection")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL not found in environment variables")
        print("   Please set up your Neon database first")
        return False
    
    print(f"📡 Connecting to database...")
    print(f"   Host: {db_url.split('@')[1].split('/')[0] if '@' in db_url else 'Unknown'}")
    
    try:
        # Test basic connection
        import psycopg2
        
        # Parse connection string
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Test query
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        
        print(f"✅ Database connection successful!")
        print(f"   PostgreSQL version: {version.split(' ')[0]} {version.split(' ')[1]}")
        
        # Test database info
        cursor.execute("SELECT current_database(), current_user;")
        db_name, user = cursor.fetchone()
        print(f"   Database: {db_name}")
        print(f"   User: {user}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except ImportError:
        print("⚠️  psycopg2 not installed, testing with SQLAlchemy...")
        
        try:
            from sqlalchemy import create_engine, text
            
            engine = create_engine(db_url)
            with engine.connect() as conn:
                result = conn.execute(text("SELECT version()"))
                version = result.fetchone()[0]
                
            print(f"✅ Database connection successful!")
            print(f"   PostgreSQL version: {version.split(' ')[0]} {version.split(' ')[1]}")
            
            return True
            
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Check your DATABASE_URL is correct")
        print("2. Ensure your IP is allowlisted in Neon")
        print("3. Verify database exists and is running")
        return False

def test_flask_app_database():
    """Test database connection through Flask app"""
    
    print("\n🔗 Testing Flask App Database Integration")
    print("-" * 50)
    
    try:
        # Add current directory to path
        sys.path.append('.')
        sys.path.append('api')
        
        # Import Flask app components
        from api.index import app, DATABASE_AVAILABLE, db
        
        print(f"DATABASE_AVAILABLE: {DATABASE_AVAILABLE}")
        
        if not DATABASE_AVAILABLE:
            print("❌ Database models not available in Flask app")
            print("   Check imports and database configuration")
            return False
        
        with app.app_context():
            try:
                # Test database connection
                from sqlalchemy import text
                result = db.session.execute(text("SELECT 1"))
                print("✅ Flask app database connection working!")
                
                # Check if tables exist
                inspector = db.inspect(db.engine)
                tables = inspector.get_table_names()
                
                if tables:
                    print(f"✅ Found {len(tables)} existing tables:")
                    for table in tables[:5]:  # Show first 5
                        print(f"   - {table}")
                    if len(tables) > 5:
                        print(f"   ... and {len(tables) - 5} more")
                else:
                    print("⚠️  No tables found - run init_db.py to create them")
                
                return True
                
            except Exception as e:
                print(f"❌ Flask database test failed: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Flask app import failed: {e}")
        return False

def show_next_steps(db_connected, flask_working):
    """Show next steps based on test results"""
    
    print("\n🎯 Next Steps:")
    print("-" * 50)
    
    if not db_connected:
        print("🔴 CRITICAL: Fix database connection first")
        print("1. Verify Neon database is created and running")
        print("2. Check DATABASE_URL format and credentials")
        print("3. Ensure IP allowlist includes your current IP")
        
    elif not flask_working:
        print("🟡 Database connected but Flask integration needs work")
        print("1. Check Flask app database imports")
        print("2. Verify SQLAlchemy configuration")
        print("3. Run: python init_db.py")
        
    else:
        print("✅ Database connection working!")
        if db_connected and flask_working:
            print("🚀 Ready for next steps:")
            print("1. Run: python init_db.py (create tables & sample data)")
            print("2. Test RBAC activation")
            print("3. Deploy to production")

if __name__ == "__main__":
    db_ok = test_database_connection()
    flask_ok = test_flask_app_database() if db_ok else False
    show_next_steps(db_ok, flask_ok)