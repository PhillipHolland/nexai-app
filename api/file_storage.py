"""
LexAI Practice Partner - Cloud File Storage Service
Unified interface for AWS S3 and Google Cloud Storage with security and versioning
"""

import os
import hashlib
import mimetypes
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, BinaryIO, Tuple
from abc import ABC, abstractmethod
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

class FileStorageError(Exception):
    """Custom exception for file storage operations"""
    pass

class FileStorageProvider(ABC):
    """Abstract base class for file storage providers"""
    
    @abstractmethod
    def upload_file(self, file_data: bytes, key: str, content_type: str = None, metadata: Dict[str, str] = None) -> Dict[str, Any]:
        """Upload a file to storage"""
        pass
    
    @abstractmethod
    def download_file(self, key: str) -> bytes:
        """Download a file from storage"""
        pass
    
    @abstractmethod
    def delete_file(self, key: str) -> bool:
        """Delete a file from storage"""
        pass
    
    @abstractmethod
    def generate_presigned_url(self, key: str, expiration: int = 3600, operation: str = 'get') -> str:
        """Generate a presigned URL for secure file access"""
        pass
    
    @abstractmethod
    def list_files(self, prefix: str = '', limit: int = 100) -> List[Dict[str, Any]]:
        """List files with optional prefix filter"""
        pass

class AWSS3Provider(FileStorageProvider):
    """AWS S3 file storage provider"""
    
    def __init__(self, bucket_name: str, region: str = 'us-east-1'):
        self.bucket_name = bucket_name
        self.region = region
        self._client = None
        
    @property
    def client(self):
        """Lazy initialization of S3 client"""
        if self._client is None:
            try:
                import boto3
                from botocore.config import Config
                
                # Configure with retry and timeout settings
                config = Config(
                    region_name=self.region,
                    retries={'max_attempts': 3, 'mode': 'adaptive'},
                    max_pool_connections=50
                )
                
                self._client = boto3.client('s3', config=config)
                logger.info(f"✅ AWS S3 client initialized for bucket: {self.bucket_name}")
                
            except ImportError:
                raise FileStorageError("boto3 library not installed. Run: pip install boto3")
            except Exception as e:
                raise FileStorageError(f"Failed to initialize S3 client: {e}")
                
        return self._client
    
    def upload_file(self, file_data: bytes, key: str, content_type: str = None, metadata: Dict[str, str] = None) -> Dict[str, Any]:
        """Upload file to S3"""
        try:
            # Prepare upload parameters
            upload_args = {
                'Bucket': self.bucket_name,
                'Key': key,
                'Body': file_data,
                'ServerSideEncryption': 'AES256'  # Enable encryption
            }
            
            if content_type:
                upload_args['ContentType'] = content_type
            
            if metadata:
                upload_args['Metadata'] = metadata
            
            # Upload file
            response = self.client.put_object(**upload_args)
            
            # Get file info
            file_info = {
                'provider': 's3',
                'bucket': self.bucket_name,
                'key': key,
                'size': len(file_data),
                'etag': response.get('ETag', '').strip('"'),
                'content_type': content_type,
                'metadata': metadata or {},
                'uploaded_at': datetime.utcnow().isoformat(),
                'url': f"s3://{self.bucket_name}/{key}"
            }
            
            logger.info(f"✅ File uploaded to S3: {key} ({len(file_data)} bytes)")
            return file_info
            
        except Exception as e:
            logger.error(f"❌ S3 upload failed for {key}: {e}")
            raise FileStorageError(f"S3 upload failed: {e}")
    
    def download_file(self, key: str) -> bytes:
        """Download file from S3"""
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            file_data = response['Body'].read()
            
            logger.info(f"✅ File downloaded from S3: {key} ({len(file_data)} bytes)")
            return file_data
            
        except Exception as e:
            logger.error(f"❌ S3 download failed for {key}: {e}")
            raise FileStorageError(f"S3 download failed: {e}")
    
    def delete_file(self, key: str) -> bool:
        """Delete file from S3"""
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"✅ File deleted from S3: {key}")
            return True
            
        except Exception as e:
            logger.error(f"❌ S3 delete failed for {key}: {e}")
            return False
    
    def generate_presigned_url(self, key: str, expiration: int = 3600, operation: str = 'get') -> str:
        """Generate presigned URL for S3 object"""
        try:
            operation_map = {
                'get': 'get_object',
                'put': 'put_object'
            }
            
            client_method = operation_map.get(operation, 'get_object')
            
            url = self.client.generate_presigned_url(
                client_method,
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            
            logger.info(f"✅ Presigned URL generated for S3: {key} (expires in {expiration}s)")
            return url
            
        except Exception as e:
            logger.error(f"❌ S3 presigned URL generation failed for {key}: {e}")
            raise FileStorageError(f"S3 presigned URL generation failed: {e}")
    
    def list_files(self, prefix: str = '', limit: int = 100) -> List[Dict[str, Any]]:
        """List files in S3 bucket"""
        try:
            params = {
                'Bucket': self.bucket_name,
                'MaxKeys': limit
            }
            
            if prefix:
                params['Prefix'] = prefix
            
            response = self.client.list_objects_v2(**params)
            
            files = []
            for obj in response.get('Contents', []):
                files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'etag': obj['ETag'].strip('"'),
                    'storage_class': obj.get('StorageClass', 'STANDARD')
                })
            
            logger.info(f"✅ Listed {len(files)} files from S3 with prefix: {prefix}")
            return files
            
        except Exception as e:
            logger.error(f"❌ S3 list files failed: {e}")
            raise FileStorageError(f"S3 list files failed: {e}")

class GoogleCloudProvider(FileStorageProvider):
    """Google Cloud Storage provider"""
    
    def __init__(self, bucket_name: str, project_id: str = None):
        self.bucket_name = bucket_name
        self.project_id = project_id
        self._client = None
        self._bucket = None
    
    @property
    def client(self):
        """Lazy initialization of GCS client"""
        if self._client is None:
            try:
                from google.cloud import storage
                
                if self.project_id:
                    self._client = storage.Client(project=self.project_id)
                else:
                    self._client = storage.Client()  # Uses default credentials
                    
                self._bucket = self._client.bucket(self.bucket_name)
                logger.info(f"✅ Google Cloud Storage client initialized for bucket: {self.bucket_name}")
                
            except ImportError:
                raise FileStorageError("google-cloud-storage library not installed. Run: pip install google-cloud-storage")
            except Exception as e:
                raise FileStorageError(f"Failed to initialize GCS client: {e}")
                
        return self._client
    
    @property
    def bucket(self):
        """Get GCS bucket object"""
        if self._bucket is None:
            _ = self.client  # Initialize client and bucket
        return self._bucket
    
    def upload_file(self, file_data: bytes, key: str, content_type: str = None, metadata: Dict[str, str] = None) -> Dict[str, Any]:
        """Upload file to Google Cloud Storage"""
        try:
            blob = self.bucket.blob(key)
            
            # Set content type if provided
            if content_type:
                blob.content_type = content_type
            
            # Set metadata
            if metadata:
                blob.metadata = metadata
            
            # Upload file data
            blob.upload_from_string(file_data)
            
            # Get file info
            file_info = {
                'provider': 'gcs',
                'bucket': self.bucket_name,
                'key': key,
                'size': len(file_data),
                'etag': blob.etag,
                'content_type': content_type,
                'metadata': metadata or {},
                'uploaded_at': datetime.utcnow().isoformat(),
                'url': f"gs://{self.bucket_name}/{key}"
            }
            
            logger.info(f"✅ File uploaded to GCS: {key} ({len(file_data)} bytes)")
            return file_info
            
        except Exception as e:
            logger.error(f"❌ GCS upload failed for {key}: {e}")
            raise FileStorageError(f"GCS upload failed: {e}")
    
    def download_file(self, key: str) -> bytes:
        """Download file from Google Cloud Storage"""
        try:
            blob = self.bucket.blob(key)
            file_data = blob.download_as_bytes()
            
            logger.info(f"✅ File downloaded from GCS: {key} ({len(file_data)} bytes)")
            return file_data
            
        except Exception as e:
            logger.error(f"❌ GCS download failed for {key}: {e}")
            raise FileStorageError(f"GCS download failed: {e}")
    
    def delete_file(self, key: str) -> bool:
        """Delete file from Google Cloud Storage"""
        try:
            blob = self.bucket.blob(key)
            blob.delete()
            
            logger.info(f"✅ File deleted from GCS: {key}")
            return True
            
        except Exception as e:
            logger.error(f"❌ GCS delete failed for {key}: {e}")
            return False
    
    def generate_presigned_url(self, key: str, expiration: int = 3600, operation: str = 'get') -> str:
        """Generate signed URL for GCS object"""
        try:
            blob = self.bucket.blob(key)
            
            # Calculate expiration time
            expires = datetime.utcnow() + timedelta(seconds=expiration)
            
            if operation == 'get':
                url = blob.generate_signed_url(expiration=expires, method='GET')
            elif operation == 'put':
                url = blob.generate_signed_url(expiration=expires, method='PUT')
            else:
                raise ValueError(f"Unsupported operation: {operation}")
            
            logger.info(f"✅ Signed URL generated for GCS: {key} (expires in {expiration}s)")
            return url
            
        except Exception as e:
            logger.error(f"❌ GCS signed URL generation failed for {key}: {e}")
            raise FileStorageError(f"GCS signed URL generation failed: {e}")
    
    def list_files(self, prefix: str = '', limit: int = 100) -> List[Dict[str, Any]]:
        """List files in GCS bucket"""
        try:
            blobs = self.client.list_blobs(
                self.bucket_name,
                prefix=prefix,
                max_results=limit
            )
            
            files = []
            for blob in blobs:
                files.append({
                    'key': blob.name,
                    'size': blob.size,
                    'last_modified': blob.time_created.isoformat(),
                    'etag': blob.etag,
                    'content_type': blob.content_type,
                    'metadata': blob.metadata or {}
                })
            
            logger.info(f"✅ Listed {len(files)} files from GCS with prefix: {prefix}")
            return files
            
        except Exception as e:
            logger.error(f"❌ GCS list files failed: {e}")
            raise FileStorageError(f"GCS list files failed: {e}")

class LocalFileProvider(FileStorageProvider):
    """Local file system provider for development"""
    
    def __init__(self, base_path: str = 'uploads'):
        self.base_path = os.path.abspath(base_path)
        
        # Try to create directory, but handle read-only filesystem gracefully
        try:
            os.makedirs(self.base_path, exist_ok=True)
            logger.info(f"✅ Local file provider initialized: {self.base_path}")
        except (OSError, PermissionError) as e:
            # In serverless environments (like Vercel), filesystem is read-only
            # Use /tmp directory which is writable, or disable local storage
            if '/var/task' in str(e) or 'read-only file system' in str(e).lower():
                logger.warning(f"Read-only filesystem detected, using /tmp for local storage")
                self.base_path = '/tmp/uploads'
                try:
                    os.makedirs(self.base_path, exist_ok=True)
                    logger.info(f"✅ Local file provider initialized with /tmp: {self.base_path}")
                except Exception as tmp_error:
                    logger.error(f"❌ Failed to create /tmp directory: {tmp_error}")
                    # Make provider non-functional but don't crash
                    self.base_path = None
            else:
                logger.error(f"❌ Local file provider initialization failed: {e}")
                raise FileStorageError(f"Failed to initialize local storage: {e}")
    
    def _get_file_path(self, key: str) -> str:
        """Get full file path for a key"""
        if self.base_path is None:
            raise FileStorageError("Local file storage not available in this environment")
        # Ensure key doesn't escape base directory
        safe_key = secure_filename(key.replace('/', '_'))
        return os.path.join(self.base_path, safe_key)
    
    def upload_file(self, file_data: bytes, key: str, content_type: str = None, metadata: Dict[str, str] = None) -> Dict[str, Any]:
        """Save file locally"""
        try:
            file_path = self._get_file_path(key)
            
            # Create directory if needed (with error handling for read-only filesystem)
            try:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
            except (OSError, PermissionError):
                # If we can't create directories, storage is not available
                raise FileStorageError("Cannot create directories in read-only filesystem")
            
            # Write file
            with open(file_path, 'wb') as f:
                f.write(file_data)
            
            # Calculate file hash
            file_hash = hashlib.sha256(file_data).hexdigest()
            
            file_info = {
                'provider': 'local',
                'path': file_path,
                'key': key,
                'size': len(file_data),
                'hash': file_hash,
                'content_type': content_type,
                'metadata': metadata or {},
                'uploaded_at': datetime.utcnow().isoformat(),
                'url': f"file://{file_path}"
            }
            
            logger.info(f"✅ File saved locally: {key} ({len(file_data)} bytes)")
            return file_info
            
        except Exception as e:
            logger.error(f"❌ Local file save failed for {key}: {e}")
            raise FileStorageError(f"Local file save failed: {e}")
    
    def download_file(self, key: str) -> bytes:
        """Read file from local storage"""
        try:
            file_path = self._get_file_path(key)
            
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            logger.info(f"✅ File read locally: {key} ({len(file_data)} bytes)")
            return file_data
            
        except Exception as e:
            logger.error(f"❌ Local file read failed for {key}: {e}")
            raise FileStorageError(f"Local file read failed: {e}")
    
    def delete_file(self, key: str) -> bool:
        """Delete local file"""
        try:
            file_path = self._get_file_path(key)
            os.remove(file_path)
            
            logger.info(f"✅ File deleted locally: {key}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Local file delete failed for {key}: {e}")
            return False
    
    def generate_presigned_url(self, key: str, expiration: int = 3600, operation: str = 'get') -> str:
        """Generate local file URL (for development)"""
        file_path = self._get_file_path(key)
        return f"file://{file_path}"
    
    def list_files(self, prefix: str = '', limit: int = 100) -> List[Dict[str, Any]]:
        """List local files"""
        try:
            files = []
            
            for root, dirs, filenames in os.walk(self.base_path):
                for filename in filenames:
                    if prefix and not filename.startswith(prefix):
                        continue
                    
                    file_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(file_path, self.base_path)
                    stat = os.stat(file_path)
                    
                    files.append({
                        'key': relative_path,
                        'size': stat.st_size,
                        'last_modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'path': file_path
                    })
                    
                    if len(files) >= limit:
                        break
                        
                if len(files) >= limit:
                    break
            
            logger.info(f"✅ Listed {len(files)} local files with prefix: {prefix}")
            return files
            
        except Exception as e:
            logger.error(f"❌ Local file listing failed: {e}")
            raise FileStorageError(f"Local file listing failed: {e}")

class FileStorageManager:
    """Unified file storage manager"""
    
    def __init__(self, provider: FileStorageProvider):
        self.provider = provider
        self.max_file_size = 100 * 1024 * 1024  # 100MB default
        self.allowed_extensions = {
            '.pdf', '.doc', '.docx', '.txt', '.rtf',  # Documents
            '.jpg', '.jpeg', '.png', '.gif', '.bmp',  # Images
            '.xlsx', '.xls', '.csv',                  # Spreadsheets
            '.ppt', '.pptx',                         # Presentations
            '.zip', '.rar', '.7z'                    # Archives
        }
        
        logger.info(f"✅ FileStorageManager initialized with {provider.__class__.__name__}")
    
    def validate_file(self, filename: str, file_size: int) -> Tuple[bool, str]:
        """Validate file before upload"""
        # Check file size
        if file_size > self.max_file_size:
            return False, f"File too large: {file_size} bytes (max: {self.max_file_size})"
        
        # Check file extension
        _, ext = os.path.splitext(filename.lower())
        if ext not in self.allowed_extensions:
            return False, f"File type not allowed: {ext}"
        
        # Check filename
        if not filename or filename.startswith('.'):
            return False, "Invalid filename"
        
        return True, "Valid"
    
    def generate_file_key(self, user_id: str, client_id: str, filename: str, doc_type: str = 'general') -> str:
        """Generate unique file key with organization"""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        safe_filename = secure_filename(filename)
        
        # Organize by user/client/type/date
        key = f"users/{user_id}/clients/{client_id}/{doc_type}/{timestamp}_{safe_filename}"
        return key
    
    def upload_document(self, file_data: bytes, filename: str, user_id: str, client_id: str = None, 
                       doc_type: str = 'general', metadata: Dict[str, str] = None) -> Dict[str, Any]:
        """Upload document with validation and organization"""
        try:
            # Validate file
            is_valid, error_msg = self.validate_file(filename, len(file_data))
            if not is_valid:
                raise FileStorageError(error_msg)
            
            # Generate file key
            file_key = self.generate_file_key(user_id, client_id or 'general', filename, doc_type)
            
            # Detect content type
            content_type, _ = mimetypes.guess_type(filename)
            if not content_type:
                content_type = 'application/octet-stream'
            
            # Add metadata
            upload_metadata = {
                'user_id': user_id,
                'client_id': client_id or '',
                'document_type': doc_type,
                'original_filename': filename,
                'uploaded_by': 'lexai_system',
                **(metadata or {})
            }
            
            # Upload file
            file_info = self.provider.upload_file(
                file_data=file_data,
                key=file_key,
                content_type=content_type,
                metadata=upload_metadata
            )
            
            # Add additional info
            file_info.update({
                'original_filename': filename,
                'document_type': doc_type,
                'user_id': user_id,
                'client_id': client_id
            })
            
            logger.info(f"✅ Document uploaded successfully: {filename} -> {file_key}")
            return file_info
            
        except Exception as e:
            logger.error(f"❌ Document upload failed: {e}")
            raise FileStorageError(f"Document upload failed: {e}")
    
    def get_secure_download_url(self, file_key: str, expiration: int = 3600) -> str:
        """Get secure download URL for file"""
        try:
            url = self.provider.generate_presigned_url(
                key=file_key,
                expiration=expiration,
                operation='get'
            )
            
            logger.info(f"✅ Secure download URL generated: {file_key}")
            return url
            
        except Exception as e:
            logger.error(f"❌ Failed to generate download URL: {e}")
            raise FileStorageError(f"Failed to generate download URL: {e}")

def create_storage_manager(provider_type: str = None) -> FileStorageManager:
    """Factory function to create storage manager based on environment"""
    provider_type = provider_type or os.getenv('FILE_STORAGE_PROVIDER', 'local')
    
    if provider_type == 's3':
        bucket_name = os.getenv('AWS_S3_BUCKET_NAME')
        region = os.getenv('AWS_REGION', 'us-east-1')
        
        if not bucket_name:
            logger.warning("AWS_S3_BUCKET_NAME not set, falling back to local storage")
            provider = LocalFileProvider()
        else:
            provider = AWSS3Provider(bucket_name=bucket_name, region=region)
            
    elif provider_type == 'gcs':
        bucket_name = os.getenv('GCS_BUCKET_NAME')
        project_id = os.getenv('GCP_PROJECT_ID')
        
        if not bucket_name:
            logger.warning("GCS_BUCKET_NAME not set, falling back to local storage")
            provider = LocalFileProvider()
        else:
            provider = GoogleCloudProvider(bucket_name=bucket_name, project_id=project_id)
            
    else:
        # Default to local storage, but handle serverless environments
        upload_path = os.getenv('LOCAL_UPLOAD_PATH', 'uploads')
        
        # Detect serverless environment (Vercel, AWS Lambda, etc.)
        is_serverless = (
            os.getenv('VERCEL') == '1' or 
            os.getenv('AWS_LAMBDA_FUNCTION_NAME') or
            '/var/task' in os.getcwd()
        )
        
        if is_serverless:
            logger.warning("Serverless environment detected - local file storage may not work reliably")
        
        provider = LocalFileProvider(base_path=upload_path)
    
    return FileStorageManager(provider)

# Global storage manager instance
storage_manager = None

def get_storage_manager() -> FileStorageManager:
    """Get global storage manager instance"""
    global storage_manager
    if storage_manager is None:
        storage_manager = create_storage_manager()
    return storage_manager