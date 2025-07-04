#!/usr/bin/env python3
"""
Modern Database Management CLI for LexAI Practice Partner
Uses Click for command-line interface instead of deprecated Flask-Script
"""

import os
import sys
import click
import shutil
from datetime import datetime
from flask import Flask
from flask.cli import with_appcontext
from flask_migrate import Migrate, init, migrate, upgrade, downgrade, current, history
from database import db, User, Client, Conversation, Document
from config import get_config
from auth import AuthManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_app():
    """Create Flask app for database operations"""
    app = Flask(__name__)
    
    # Load configuration
    config_class = get_config()
    app.config.from_object(config_class)
    
    # Initialize database and migrations
    db.init_app(app)
    migrate = Migrate(app, db)
    
    return app

# Create app instance
app = create_app()

@click.group()
def cli():
    """🏛️ LexAI Database Management CLI"""
    pass

@cli.command()
@with_appcontext
def init_db():
    """Initialize migration repository"""
    click.echo("🔄 Initializing database migrations...")
    
    try:
        init()
        click.echo("✅ Migration repository initialized")
    except Exception as e:
        if "already exists" in str(e):
            click.echo("✅ Migration repository already exists")
        else:
            click.echo(f"❌ Failed to initialize migrations: {e}")
            sys.exit(1)

@cli.command()
@click.option('--message', '-m', required=True, help='Migration message')
@with_appcontext
def create_migration(message):
    """Create a new migration"""
    click.echo(f"📝 Creating migration: {message}")
    
    try:
        migrate(message=message)
        click.echo(f"✅ Migration created: {message}")
    except Exception as e:
        click.echo(f"❌ Failed to create migration: {e}")
        sys.exit(1)

@cli.command()
@with_appcontext
def upgrade_db():
    """Upgrade database to latest migration"""
    click.echo("⬆️ Upgrading database to latest version...")
    
    try:
        upgrade()
        click.echo("✅ Database upgraded successfully")
    except Exception as e:
        click.echo(f"❌ Database upgrade failed: {e}")
        sys.exit(1)

@cli.command()
@click.option('--revision', '-r', default='base', help='Target revision')
@with_appcontext
def downgrade_db(revision):
    """Downgrade database to specific revision"""
    click.echo(f"⬇️ Downgrading database to: {revision}")
    
    try:
        downgrade(revision=revision)
        click.echo(f"✅ Database downgraded to: {revision}")
    except Exception as e:
        click.echo(f"❌ Database downgrade failed: {e}")
        sys.exit(1)

@cli.command()
@with_appcontext
def migration_history():
    """Show migration history"""
    click.echo("📜 Migration History:")
    
    try:
        click.echo(f"\nCurrent revision: {current()}")
        click.echo("\nMigration history:")
        for revision in history():
            click.echo(f"  - {revision}")
    except Exception as e:
        click.echo(f"❌ Failed to show history: {e}")
        sys.exit(1)

@cli.command()
@with_appcontext
def validate_db():
    """Validate database schema matches models"""
    click.echo("🔍 Validating database schema...")
    
    try:
        # Check if all tables exist
        inspector = db.inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        expected_tables = ['users', 'clients', 'conversations', 'documents']
        missing_tables = [table for table in expected_tables if table not in existing_tables]
        
        if missing_tables:
            click.echo(f"❌ Missing tables: {missing_tables}")
            sys.exit(1)
        else:
            click.echo("✅ All expected tables exist")
            
    except Exception as e:
        click.echo(f"❌ Database validation failed: {e}")
        sys.exit(1)

@cli.command()
@click.option('--path', '-p', help='Backup file path')
@with_appcontext
def backup_db(path):
    """Create database backup"""
    if path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"backup_lexai_{timestamp}.sql"
    
    click.echo(f"💾 Creating database backup: {path}")
    
    database_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    
    if database_url.startswith('sqlite:///'):
        # SQLite backup
        db_file = database_url.replace('sqlite:///', '')
        # Handle relative paths
        if not os.path.isabs(db_file):
            db_file = os.path.join(os.getcwd(), db_file)
        
        try:
            if os.path.exists(db_file):
                shutil.copy2(db_file, path)
                click.echo(f"✅ SQLite backup created: {path}")
            else:
                click.echo(f"❌ Database file not found: {db_file}")
                sys.exit(1)
        except Exception as e:
            click.echo(f"❌ SQLite backup failed: {e}")
            sys.exit(1)
    
    elif database_url.startswith('postgresql://'):
        # PostgreSQL backup using pg_dump
        from urllib.parse import urlparse
        import subprocess
        
        parsed = urlparse(database_url)
        
        cmd = [
            'pg_dump',
            f'--host={parsed.hostname}',
            f'--port={parsed.port or 5432}',
            f'--username={parsed.username}',
            f'--dbname={parsed.path[1:]}',  # Remove leading /
            f'--file={path}',
            '--verbose',
            '--clean',
            '--no-owner',
            '--no-privileges'
        ]
        
        try:
            env = os.environ.copy()
            env['PGPASSWORD'] = parsed.password
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                click.echo(f"✅ PostgreSQL backup created: {path}")
            else:
                click.echo(f"❌ PostgreSQL backup failed: {result.stderr}")
                sys.exit(1)
                
        except Exception as e:
            click.echo(f"❌ PostgreSQL backup failed: {e}")
            sys.exit(1)
    
    else:
        click.echo(f"❌ Unsupported database type for backup: {database_url}")
        sys.exit(1)

@cli.command()
@with_appcontext
def seed_db():
    """Seed database with initial data"""
    click.echo("🌱 Seeding database with initial data...")
    
    try:
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
            click.echo(f"✅ Created admin user: {admin_email} (password: admin123)")
        
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
            
            click.echo("✅ Created sample clients")
        
        db.session.commit()
        click.echo("✅ Database seeding completed")
        
    except Exception as e:
        db.session.rollback()
        click.echo(f"❌ Database seeding failed: {e}")
        sys.exit(1)

@cli.command()
@click.confirmation_option(prompt='⚠️ This will destroy ALL data! Are you sure?')
@with_appcontext
def reset_db():
    """Reset database (DANGER: Destroys all data)"""
    click.echo("🔥 Resetting database...")
    
    try:
        # Drop all tables
        db.drop_all()
        click.echo("✅ All tables dropped")
        
        # Recreate tables
        db.create_all()
        click.echo("✅ Tables recreated")
        
        # Seed with initial data
        ctx = click.get_current_context()
        ctx.invoke(seed_db)
        
        click.echo("✅ Database reset completed")
        
    except Exception as e:
        click.echo(f"❌ Database reset failed: {e}")
        sys.exit(1)

@cli.command()
@with_appcontext
def setup_production():
    """Complete production database setup"""
    click.echo("🚀 Setting up production database...")
    
    try:
        # Check if migrations folder exists
        if not os.path.exists('migrations'):
            click.echo("📝 Initializing migrations...")
            init()
        
        # Create initial migration if needed
        inspector = db.inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if not existing_tables:
            click.echo("📝 Creating initial migration...")
            db.create_all()
            migrate(message="Initial production migration")
        
        # Upgrade to latest
        click.echo("⬆️ Upgrading to latest migration...")
        upgrade()
        
        # Seed with initial data
        click.echo("🌱 Seeding initial data...")
        ctx = click.get_current_context()
        ctx.invoke(seed_db)
        
        # Create backup
        click.echo("💾 Creating initial backup...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"production_backup_{timestamp}.sql"
        ctx.invoke(backup_db, path=backup_path)
        
        click.echo("🎉 Production database setup completed successfully!")
        click.echo(f"\n📋 Summary:")
        click.echo(f"   - Database initialized and migrated")
        click.echo(f"   - Admin user created: admin@lexai.com")
        click.echo(f"   - Sample data seeded")
        click.echo(f"   - Backup created: {backup_path}")
        
    except Exception as e:
        click.echo(f"❌ Production setup failed: {e}")
        sys.exit(1)

@cli.command()
@with_appcontext
def status():
    """Show database status"""
    click.echo("📊 Database Status:")
    
    try:
        # Check database connection
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        click.echo("✅ Database connection: OK")
        
        # Show table counts
        user_count = User.query.count()
        client_count = Client.query.count()
        conversation_count = Conversation.query.count()
        document_count = Document.query.count()
        
        click.echo(f"\n📈 Data Summary:")
        click.echo(f"   - Users: {user_count}")
        click.echo(f"   - Clients: {client_count}")
        click.echo(f"   - Conversations: {conversation_count}")
        click.echo(f"   - Documents: {document_count}")
        
        # Show migration status
        try:
            current_rev = current()
            click.echo(f"\n🔄 Migration Status:")
            click.echo(f"   - Current revision: {current_rev}")
        except:
            click.echo(f"\n🔄 Migration Status: Not initialized")
        
    except Exception as e:
        click.echo(f"❌ Status check failed: {e}")

if __name__ == '__main__':
    with app.app_context():
        cli()