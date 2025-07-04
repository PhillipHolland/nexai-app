#!/usr/bin/env python3
"""
Test script to verify database integration works correctly.
Run this script to test the database connection and basic operations.
"""

import os
import sys
from flask import Flask
from database import init_db, get_client_data, update_client_info, add_conversation, add_document, Client, db

def test_database():
    """Test database operations"""
    app = Flask(__name__)
    
    # Use SQLite for testing if no DATABASE_URL is set
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///test_lexai.db')
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://')
    
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    print(f"Testing with database: {DATABASE_URL}")
    
    try:
        # Initialize database
        init_db(app)
        
        with app.app_context():
            print("✓ Database initialized successfully")
            
            # Test client creation
            test_client_id = "test_client"
            client_info = {
                "name": "Test Client",
                "case_number": "TEST123",
                "email": "test@example.com",
                "phone": "555-0123",
                "case_type": "Test Case",
                "notes": "This is a test client"
            }
            
            # Update client info
            update_client_info(test_client_id, client_info)
            print("✓ Client created successfully")
            
            # Test conversation
            add_conversation(test_client_id, "user", "This is a test message")
            add_conversation(test_client_id, "assistant", "This is a test response")
            print("✓ Conversations added successfully")
            
            # Test document
            add_document(test_client_id, "test_document.txt", "This is test document content")
            print("✓ Document added successfully")
            
            # Test data retrieval
            client_data = get_client_data(test_client_id)
            if client_data:
                print("✓ Client data retrieved successfully")
                print(f"  - Client name: {client_data['info']['name']}")
                print(f"  - Conversations: {len(client_data['history'])}")
                print(f"  - Documents: {len(client_data['documents'])}")
            else:
                print("✗ Failed to retrieve client data")
                return False
            
            # Test database queries
            client_count = Client.query.count()
            print(f"✓ Total clients in database: {client_count}")
            
            print("\n🎉 All database tests passed!")
            return True
            
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_database()
    if not success:
        sys.exit(1)
    print("\nDatabase integration is working correctly!")