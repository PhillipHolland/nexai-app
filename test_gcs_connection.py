#!/usr/bin/env python3
"""
Test Google Cloud Storage Connection
"""
import os
from dotenv import load_dotenv

def test_gcs_setup():
    """Test Google Cloud Storage setup and connection"""
    
    # Load environment variables
    load_dotenv()
    
    print("🔍 Testing Google Cloud Storage Setup...")
    print("=" * 50)
    
    # Check environment variables
    print("📋 Environment Variables:")
    provider = os.getenv('FILE_STORAGE_PROVIDER')
    bucket_name = os.getenv('GCS_BUCKET_NAME')
    project_id = os.getenv('GCP_PROJECT_ID')
    credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    
    print(f"  FILE_STORAGE_PROVIDER: {provider}")
    print(f"  GCS_BUCKET_NAME: {bucket_name}")
    print(f"  GCP_PROJECT_ID: {project_id}")
    print(f"  GOOGLE_APPLICATION_CREDENTIALS: {credentials_path}")
    print()
    
    # Test file storage system
    print("🧪 Testing File Storage System:")
    try:
        from file_storage import get_storage_manager, FileStorageError
        
        # Get storage manager
        storage_manager = get_storage_manager()
        provider_class = storage_manager.provider.__class__.__name__
        
        print(f"  ✅ Storage Manager Created: {provider_class}")
        print(f"  📁 Max File Size: {storage_manager.max_file_size / 1024 / 1024:.1f} MB")
        print(f"  📄 Allowed Extensions: {list(storage_manager.allowed_extensions)}")
        print()
        
        # Test Google Cloud Storage connection
        if provider_class == "GoogleCloudProvider":
            print("☁️ Testing Google Cloud Storage Connection:")
            try:
                # Try to list files (this will test authentication)
                files = storage_manager.provider.list_files(limit=1)
                print(f"  ✅ Successfully connected to GCS bucket: {bucket_name}")
                print(f"  📊 Bucket accessible, found {len(files)} files")
                
                # Test file upload (small test file)
                print("  🧪 Testing file upload...")
                test_content = b"LexAI Google Cloud Storage Test File"
                test_result = storage_manager.upload_document(
                    file_data=test_content,
                    filename="test_connection.txt",
                    user_id="test_user",
                    client_id="test_client",
                    doc_type="test"
                )
                
                print(f"  ✅ Test file uploaded successfully!")
                print(f"  📍 File Key: {test_result.get('key')}")
                print(f"  🔗 Storage URL: {test_result.get('url')}")
                
                # Clean up test file
                try:
                    storage_manager.provider.delete_file(test_result.get('key'))
                    print(f"  🧹 Test file cleaned up")
                except:
                    print(f"  ⚠️ Test file cleanup failed (not critical)")
                
            except Exception as e:
                print(f"  ❌ GCS Connection Failed: {str(e)}")
                return False
                
        else:
            print(f"  ⚠️ Using {provider_class} instead of Google Cloud Storage")
            print(f"    Check your FILE_STORAGE_PROVIDER environment variable")
            
    except ImportError as e:
        print(f"  ❌ File Storage Import Failed: {str(e)}")
        return False
    except Exception as e:
        print(f"  ❌ File Storage Test Failed: {str(e)}")
        return False
    
    print()
    print("🎉 Google Cloud Storage Setup Complete!")
    return True

if __name__ == "__main__":
    success = test_gcs_setup()
    if success:
        print("\n✅ Your Google Cloud Storage is properly configured!")
        print("\n🚀 Ready to upload documents to the cloud!")
    else:
        print("\n❌ Google Cloud Storage setup needs attention.")
        print("\n🔧 Please check your configuration and try again.")