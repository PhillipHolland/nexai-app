"""
Database Migration Management for LexAI Practice Partner
Handles database schema versioning, migrations, and production deployments
"""

import os
import sys
from flask import Flask
from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager
from database import db
from config import get_config
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_migration_app():
    """Create Flask app specifically for migrations"""
    app = Flask(__name__)
    
    # Load configuration
    config_class = get_config()
    app.config.from_object(config_class)
    
    # Initialize database
    db.init_app(app)
    
    # Initialize Flask-Migrate
    migrate = Migrate(app, db)
    
    return app, migrate

# Create app and migration objects
app, migrate = create_migration_app()
manager = Manager(app)
manager.add_command('db', MigrateCommand)

def init_migrations():
    """Initialize migration repository"""
    print("🔄 Initializing database migrations...")
    
    with app.app_context():
        from flask_migrate import init
        try:
            init()
            print("✅ Migration repository initialized")
            return True
        except Exception as e:
            if "already exists" in str(e):
                print("✅ Migration repository already exists")
                return True
            else:
                print(f"❌ Failed to initialize migrations: {e}")
                return False

def create_migration(message):
    """Create a new migration"""
    print(f"📝 Creating migration: {message}")
    
    with app.app_context():
        from flask_migrate import migrate as create_migrate
        try:
            create_migrate(message=message)
            print(f"✅ Migration created: {message}")
            return True
        except Exception as e:
            print(f"❌ Failed to create migration: {e}")
            return False

def upgrade_database():
    """Upgrade database to latest migration"""
    print("⬆️  Upgrading database to latest version...")
    
    with app.app_context():
        from flask_migrate import upgrade
        try:
            upgrade()
            print("✅ Database upgraded successfully")
            return True
        except Exception as e:
            print(f"❌ Database upgrade failed: {e}")
            return False

def downgrade_database(revision='base'):
    """Downgrade database to specific revision"""
    print(f"⬇️  Downgrading database to: {revision}")
    
    with app.app_context():
        from flask_migrate import downgrade
        try:
            downgrade(revision=revision)
            print(f"✅ Database downgraded to: {revision}")
            return True
        except Exception as e:
            print(f"❌ Database downgrade failed: {e}")
            return False

def show_migration_history():
    """Show migration history"""
    print("📜 Migration History:")
    
    with app.app_context():
        from flask_migrate import current, history
        try:
            print(f"\nCurrent revision: {current()}")
            print("\nMigration history:")
            for revision in history():
                print(f"  - {revision}")
            return True
        except Exception as e:
            print(f"❌ Failed to show history: {e}")
            return False

def validate_database():
    """Validate database schema matches models"""
    print("🔍 Validating database schema...")
    
    with app.app_context():
        try:
            # Import all models to ensure they're registered
            from database import User, Client, Conversation, Document
            
            # Check if all tables exist
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            expected_tables = ['users', 'clients', 'conversations', 'documents']
            missing_tables = [table for table in expected_tables if table not in existing_tables]
            
            if missing_tables:
                print(f"❌ Missing tables: {missing_tables}")
                return False
            else:
                print("✅ All expected tables exist")
                return True
                
        except Exception as e:
            print(f"❌ Database validation failed: {e}")
            return False

def backup_database(backup_path=None):
    """Create database backup"""
    if backup_path is None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"backup_lexai_{timestamp}.sql"
    
    print(f"💾 Creating database backup: {backup_path}")
    
    database_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    
    if database_url.startswith('sqlite:///'):
        # SQLite backup
        import shutil
        db_file = database_url.replace('sqlite:///', '')
        try:
            shutil.copy2(db_file, backup_path)
            print(f"✅ SQLite backup created: {backup_path}")
            return True
        except Exception as e:
            print(f"❌ SQLite backup failed: {e}")
            return False
    
    elif database_url.startswith('postgresql://'):
        # PostgreSQL backup using pg_dump
        from urllib.parse import urlparse
        parsed = urlparse(database_url)
        
        cmd = [
            'pg_dump',
            f'--host={parsed.hostname}',
            f'--port={parsed.port or 5432}',
            f'--username={parsed.username}',
            f'--dbname={parsed.path[1:]}',  # Remove leading /
            f'--file={backup_path}',
            '--verbose',
            '--clean',
            '--no-owner',
            '--no-privileges'
        ]
        
        try:
            import subprocess
            env = os.environ.copy()
            env['PGPASSWORD'] = parsed.password
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ PostgreSQL backup created: {backup_path}")
                return True
            else:
                print(f"❌ PostgreSQL backup failed: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ PostgreSQL backup failed: {e}")
            return False
    
    else:
        print(f"❌ Unsupported database type for backup: {database_url}")
        return False

def seed_database():
    """Seed database with initial data"""
    print("🌱 Seeding database with initial data...")
    
    with app.app_context():
        try:
            from database import User, Client
            from auth import AuthManager
            
            # Create admin user if it doesn't exist
            admin_email = 'admin@lexai.com'
            admin_user = User.query.filter_by(email=admin_email).first()
            
            if not admin_user:
                admin_password = AuthManager.hash_password('admin123')
                admin_user = User(
                    email=admin_email,
                    password_hash=admin_password,
                    first_name='Admin',
                    last_name='User',
                    firm_name='LexAI Practice Partner',
                    role='admin',
                    is_active=True
                )
                db.session.add(admin_user)
                print(f"✅ Created admin user: {admin_email}")
            
            # Create sample clients if none exist
            if Client.query.count() == 0:
                sample_clients = [
                    Client(
                        id='demo_client_1',
                        name='John Smith',
                        email='john.smith@email.com',
                        phone='(555) 123-4567',
                        case_type='Family Law',
                        notes='Divorce proceedings - initial consultation completed'
                    ),
                    Client(
                        id='demo_client_2',
                        name='Sarah Johnson',
                        email='sarah.johnson@email.com',
                        phone='(555) 987-6543',
                        case_type='Personal Injury',
                        notes='Auto accident case - gathering medical records'
                    ),
                    Client(
                        id='demo_client_3',
                        name='Tech Startup LLC',
                        email='legal@techstartup.com',
                        phone='(555) 456-7890',
                        case_type='Corporate Law',
                        notes='Business formation and IP protection'
                    )
                ]
                
                for client in sample_clients:
                    db.session.add(client)
                
                print("✅ Created sample clients")
            
            db.session.commit()
            print("✅ Database seeding completed")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Database seeding failed: {e}")
            return False

def reset_database():
    """Reset database (WARNING: Destroys all data)"""
    print("⚠️  WARNING: This will destroy ALL data in the database!")
    response = input("Type 'CONFIRM' to proceed: ")
    
    if response != 'CONFIRM':
        print("❌ Database reset cancelled")
        return False
    
    print("🔥 Resetting database...")
    
    with app.app_context():
        try:
            # Drop all tables
            db.drop_all()
            print("✅ All tables dropped")
            
            # Recreate tables
            db.create_all()
            print("✅ Tables recreated")
            
            # Seed with initial data
            seed_database()
            
            print("✅ Database reset completed")
            return True
            
        except Exception as e:
            print(f"❌ Database reset failed: {e}")
            return False

def production_setup():
    """Complete production database setup"""
    print("🚀 Setting up production database...")
    
    success = True
    
    # Initialize migrations
    if not init_migrations():
        success = False
    
    # Validate database
    if not validate_database():
        print("📝 Database schema needs updates, creating migration...")
        if not create_migration("Initial production migration"):
            success = False
    
    # Upgrade to latest
    if not upgrade_database():
        success = False
    
    # Seed with initial data
    if not seed_database():
        success = False
    
    # Create backup
    if not backup_database():
        print("⚠️  Backup failed, but continuing...")
    
    if success:
        print("🎉 Production database setup completed successfully!")
    else:
        print("❌ Production database setup encountered errors")
    
    return success

if __name__ == '__main__':
    if len(sys.argv) == 1:
        # Interactive mode
        print("🏛️  LexAI Database Migration Manager")
        print("=" * 50)
        print("1. Initialize migrations")
        print("2. Create migration")
        print("3. Upgrade database")
        print("4. Show migration history")
        print("5. Validate database")
        print("6. Backup database")
        print("7. Seed database")
        print("8. Reset database (DANGER)")
        print("9. Production setup")
        print("0. Exit")
        
        while True:
            choice = input("\nSelect option (0-9): ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                init_migrations()
            elif choice == '2':
                message = input("Migration message: ").strip()
                create_migration(message)
            elif choice == '3':
                upgrade_database()
            elif choice == '4':
                show_migration_history()
            elif choice == '5':
                validate_database()
            elif choice == '6':
                backup_path = input("Backup file path (optional): ").strip() or None
                backup_database(backup_path)
            elif choice == '7':
                seed_database()
            elif choice == '8':
                reset_database()
            elif choice == '9':
                production_setup()
            else:
                print("❌ Invalid option")
    else:
        # Command line mode
        manager.run()