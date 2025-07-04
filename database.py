from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DateTime, func
from datetime import datetime, timezone
import json

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.LargeBinary, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    firm_name = db.Column(db.String(100), nullable=True)
    role = db.Column(db.String(20), nullable=False, default='user')  # 'user', 'admin', 'premium'
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(DateTime(timezone=True), default=func.now())
    last_login = db.Column(DateTime(timezone=True), nullable=True)
    password_updated_at = db.Column(DateTime(timezone=True), nullable=True)
    reset_token = db.Column(db.String(64), nullable=True)
    reset_token_expires = db.Column(DateTime(timezone=True), nullable=True)
    
    # Subscription info
    subscription_tier = db.Column(db.String(20), default='free')  # 'free', 'professional', 'premium', 'enterprise'
    subscription_expires = db.Column(DateTime(timezone=True), nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'firm_name': self.firm_name,
            'role': self.role,
            'is_active': self.is_active,
            'subscription_tier': self.subscription_tier,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

class Client(db.Model):
    __tablename__ = 'clients'
    
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    case_number = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    case_type = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(DateTime(timezone=True), default=func.now())
    updated_at = db.Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relationships
    conversations = db.relationship('Conversation', backref='client', lazy=True, cascade='all, delete-orphan')
    documents = db.relationship('Document', backref='client', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'case_number': self.case_number,
            'email': self.email,
            'phone': self.phone,
            'case_type': self.case_type,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Conversation(db.Model):
    __tablename__ = 'conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(50), db.ForeignKey('clients.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(DateTime(timezone=True), default=func.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

class Document(db.Model):
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(50), db.ForeignKey('clients.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    text = db.Column(db.Text, nullable=True)
    upload_date = db.Column(DateTime(timezone=True), default=func.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'filename': self.filename,
            'text': self.text,
            'upload_date': self.upload_date.isoformat() if self.upload_date else None
        }

def init_db(app):
    """Initialize the database with the Flask app"""
    db.init_app(app)
    
    try:
        with app.app_context():
            # Create all tables
            db.create_all()
            
            # Add sample data if no clients exist
            if not Client.query.first():
                client1 = Client(
                    id='client1',
                    name='John Doe',
                    case_number='12345',
                    email='john.doe@example.com',
                    phone='555-1234',
                    case_type='Divorce',
                    notes='Initial consultation'
                )
                
                client2 = Client(
                    id='client2',
                    name='Jane Smith',
                    case_number='67890',
                    email='jane.smith@example.com',
                    phone='555-5678',
                    case_type='Custody',
                    notes='Follow-up meeting'
                )
                
                db.session.add(client1)
                db.session.add(client2)
                db.session.commit()
                
                print("Sample clients added to database")
    except Exception as e:
        print(f"Database initialization error: {e}")
        # Don't fail the app startup, just log the error

def get_client_data(client_id):
    """Get client data with conversations and documents"""
    client = Client.query.filter_by(id=client_id).first()
    if not client:
        return None
    
    conversations = Conversation.query.filter_by(client_id=client_id).order_by(Conversation.timestamp).all()
    documents = Document.query.filter_by(client_id=client_id).order_by(Document.upload_date).all()
    
    return {
        'info': client.to_dict(),
        'history': [conv.to_dict() for conv in conversations],
        'documents': [doc.to_dict() for doc in documents]
    }

def update_client_info(client_id, info):
    """Update client information"""
    client = Client.query.filter_by(id=client_id).first()
    if not client:
        # Create new client
        client = Client(id=client_id)
        db.session.add(client)
    
    # Update fields
    client.name = info.get('name', client.name)
    client.case_number = info.get('case_number', client.case_number)
    client.email = info.get('email', client.email)
    client.phone = info.get('phone', client.phone)
    client.case_type = info.get('case_type', client.case_type)
    client.notes = info.get('notes', client.notes)
    
    db.session.commit()
    return client.to_dict()

def add_conversation(client_id, role, content):
    """Add a conversation message"""
    conversation = Conversation(
        client_id=client_id,
        role=role,
        content=content
    )
    db.session.add(conversation)
    db.session.commit()
    return conversation.to_dict()

def clear_conversation_history(client_id):
    """Clear all conversation history for a client"""
    Conversation.query.filter_by(client_id=client_id).delete()
    db.session.commit()

def add_document(client_id, filename, text):
    """Add a document"""
    document = Document(
        client_id=client_id,
        filename=filename,
        text=text
    )
    db.session.add(document)
    db.session.commit()
    return document.to_dict()