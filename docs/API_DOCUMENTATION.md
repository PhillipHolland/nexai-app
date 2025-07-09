# LexAI API Documentation

## 🌟 Overview

LexAI Practice Partner provides a comprehensive REST API for legal practice management with AI-powered features. This documentation covers all available endpoints, authentication, and usage examples.

## 🔐 Authentication

### Authentication Methods

1. **Session-based Authentication** (Web Interface)
2. **API Key Authentication** (Programmatic Access)
3. **JWT Tokens** (Mobile/Single Page Applications)

### Login Endpoint

```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "attorney@firm.com",
  "password": "secure_password",
  "remember_me": false
}
```

**Response:**
```json
{
  "success": true,
  "access_token": "jwt_token_here",
  "user": {
    "id": 1,
    "email": "attorney@firm.com",
    "role": "attorney",
    "first_name": "John",
    "last_name": "Doe"
  },
  "expires_in": 3600
}
```

## 📋 Core API Endpoints

### Health & Status

#### Health Check
```http
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "overall_status": "healthy",
  "checks": {
    "database": {"status": "pass", "check_time": 0.05},
    "memory": {"status": "pass", "details": "Memory usage at 45.2%"},
    "disk_space": {"status": "pass", "details": "Disk usage at 23.1%"}
  }
}
```

#### System Metrics
```http
GET /api/metrics
Authorization: Bearer {token}
```

#### Performance Data
```http
GET /api/performance
Authorization: Bearer {token}
```

## 👥 Client Management API

### List Clients
```http
GET /api/clients
Authorization: Bearer {token}
```

**Query Parameters:**
- `page` (int): Page number (default: 1)
- `limit` (int): Items per page (default: 20)
- `search` (string): Search term
- `status` (string): Filter by status

**Response:**
```json
{
  "success": true,
  "clients": [
    {
      "id": 1,
      "first_name": "Jane",
      "last_name": "Smith",
      "email": "jane@example.com",
      "phone": "+1-555-0123",
      "company": "Smith Industries",
      "client_type": "corporate",
      "created_at": "2024-01-10T09:00:00Z",
      "cases_count": 3
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 45,
    "pages": 3
  }
}
```

### Create Client
```http
POST /api/clients
Authorization: Bearer {token}
Content-Type: application/json

{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "phone": "+1-555-0124",
  "address": "123 Main St, City, State 12345",
  "company": "Doe Enterprises",
  "client_type": "individual"
}
```

### Get Client Details
```http
GET /api/clients/{client_id}
Authorization: Bearer {token}
```

### Update Client
```http
PUT /api/clients/{client_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "phone": "+1-555-9999",
  "address": "456 New St, City, State 12345"
}
```

### Delete Client
```http
DELETE /api/clients/{client_id}
Authorization: Bearer {token}
```

## 📄 Document Management API

### Upload Document
```http
POST /api/documents/upload
Authorization: Bearer {token}
Content-Type: multipart/form-data

file: [binary data]
document_type: "contract"
analysis_type: "comprehensive"
client_id: 123 (optional)
case_id: 456 (optional)
```

**Response:**
```json
{
  "success": true,
  "document_id": "doc_123456",
  "filename": "contract_analysis.pdf",
  "file_size": 2048576,
  "document_type": "contract",
  "classification": {
    "type": "contract",
    "confidence": 0.95,
    "subtypes": ["service_agreement"]
  },
  "analysis": {
    "key_terms": ["payment", "termination", "liability"],
    "pii_detected": false,
    "language": "en",
    "page_count": 12
  },
  "processing_time": 3.2,
  "bagel_insights": {
    "success": true,
    "risk_assessment": "moderate",
    "key_points": ["Review termination clause", "Verify payment terms"]
  }
}
```

### Analyze Document Text
```http
POST /api/documents/analyze
Authorization: Bearer {token}
Content-Type: application/json

{
  "text": "Contract text to analyze...",
  "document_type": "contract",
  "analysis_depth": "comprehensive"
}
```

### List Documents
```http
GET /api/documents
Authorization: Bearer {token}
```

**Query Parameters:**
- `client_id` (int): Filter by client
- `case_id` (int): Filter by case
- `document_type` (string): Filter by type
- `page`, `limit`: Pagination

## 🔍 Legal Research API

### Basic Legal Search
```http
POST /api/legal-research/search
Authorization: Bearer {token}
Content-Type: application/json

{
  "query": "contract law precedents",
  "jurisdiction": "federal",
  "court_level": "appellate",
  "date_range": "last-5-years",
  "limit": 20
}
```

### Comprehensive Legal Research
```http
POST /api/legal-research/comprehensive
Authorization: Bearer {token}
Content-Type: application/json

{
  "query": "employment discrimination cases",
  "practice_area": "employment",
  "jurisdiction": "california",
  "limit": 50
}
```

**Response:**
```json
{
  "success": true,
  "query": "employment discrimination cases",
  "results": {
    "sources": {
      "case_law": [
        {
          "title": "Smith v. ABC Corp",
          "citation": "123 F.3d 456 (9th Cir. 2020)",
          "summary": "Court ruled on workplace discrimination...",
          "relevance_score": 95,
          "court": "9th Circuit Court of Appeals",
          "date_filed": "2020-03-15",
          "url": "https://example.com/case/123"
        }
      ],
      "statutes": [],
      "secondary_sources": []
    },
    "bagel_analysis": {
      "success": true,
      "analysis": "Key precedents establish that...",
      "strategic_recommendations": ["Consider recent CA law changes"]
    }
  },
  "total_results": 45,
  "processing_time": 2.1
}
```

## 📋 Contract Analysis API

### Analyze Contract
```http
POST /api/contracts/analyze
Authorization: Bearer {token}
Content-Type: application/json

{
  "contract_text": "SERVICE AGREEMENT\n\nThis agreement...",
  "contract_type": "service",
  "analysis_depth": "comprehensive"
}
```

**Response:**
```json
{
  "success": true,
  "contract_id": "contract_789",
  "contract_type": "service",
  "overall_risk_score": 35.0,
  "key_terms": {
    "parties": ["Company A", "Company B"],
    "governing_law": "California",
    "effective_date": "2024-01-01"
  },
  "clauses": [
    {
      "clause_id": "termination_1",
      "clause_type": "termination",
      "text": "Either party may terminate with 30 days notice...",
      "risk_level": "medium",
      "concerns": ["Notice period may be insufficient"],
      "recommendations": ["Consider extending to 60 days"]
    }
  ],
  "missing_clauses": ["force_majeure", "intellectual_property"],
  "red_flags": ["Unlimited liability clause"],
  "recommendations": [
    "Add force majeure clause",
    "Limit liability exposure",
    "Have contract reviewed by legal counsel"
  ],
  "financial_terms": {
    "total_value": 50000.0,
    "payment_schedule": ["Monthly payments of $5,000"],
    "currency": "USD"
  },
  "bagel_insights": {
    "success": true,
    "strategic_analysis": "Contract favors service provider...",
    "negotiation_points": ["Payment terms", "Liability limits"]
  }
}
```

### Risk Assessment
```http
POST /api/contracts/risk-assessment
Authorization: Bearer {token}
Content-Type: application/json

{
  "contract_text": "Contract text...",
  "contract_type": "employment"
}
```

### Clause Analysis
```http
POST /api/contracts/clause-analysis
Authorization: Bearer {token}
Content-Type: application/json

{
  "contract_text": "Contract text...",
  "contract_type": "lease"
}
```

## 🌐 Spanish Translation API

### Translate Legal Text
```http
POST /api/spanish/translate
Authorization: Bearer {token}
Content-Type: application/json

{
  "text": "This contract is governed by California law",
  "target_language": "es",
  "legal_context": "contract"
}
```

**Response:**
```json
{
  "success": true,
  "original_text": "This contract is governed by California law",
  "translated_text": "Este contrato se rige por la ley de California",
  "source_language": "en",
  "target_language": "es",
  "confidence_score": 0.92,
  "legal_context": "contract",
  "warnings": [],
  "bagel_enhanced": true,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Translate Document
```http
POST /api/spanish/translate-document
Authorization: Bearer {token}
Content-Type: application/json

{
  "document_text": "EMPLOYMENT AGREEMENT\n\nThis agreement...",
  "document_type": "employment",
  "target_language": "es"
}
```

### Get UI Translations
```http
GET /api/spanish/ui-translations?language=es
Authorization: Bearer {token}
```

### Get Spanish Legal Forms
```http
GET /api/spanish/legal-forms
Authorization: Bearer {token}
```

## 🔍 Evidence Analysis API

### Upload Evidence
```http
POST /api/evidence/upload
Authorization: Bearer {token}
Content-Type: multipart/form-data

file: [binary data]
evidence_type: "document"
case_id: 123
description: "Contract signed by defendant"
```

### Legal Admissibility Check
```http
POST /api/evidence/legal-admissibility
Authorization: Bearer {token}
Content-Type: application/json

{
  "evidence_type": "document",
  "description": "Digital contract with electronic signatures",
  "source": "Email communication from client"
}
```

## 📊 Analytics API

### Practice Analytics
```http
GET /api/analytics/practice
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "analytics": {
    "overview": {
      "total_clients": 125,
      "active_cases": 45,
      "documents_processed": 320,
      "revenue_ytd": 125000.50
    },
    "monthly_trends": {
      "new_clients": [5, 7, 3, 8, 6],
      "cases_closed": [12, 15, 8, 20, 18],
      "revenue": [15000, 18000, 12000, 22000, 19000]
    },
    "practice_areas": {
      "contract": 35,
      "employment": 28,
      "corporate": 22,
      "family": 15
    }
  }
}
```

## 🔒 Security API

### Security Status
```http
GET /api/security/status
Authorization: Bearer {token}
```

## 🚨 Error Handling

### Standard Error Response Format

```json
{
  "success": false,
  "error": "Error message",
  "error_code": "VALIDATION_ERROR",
  "details": {
    "field": "email",
    "message": "Invalid email format"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### HTTP Status Codes

- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `429` - Rate Limited
- `500` - Internal Server Error

### Common Error Codes

- `AUTHENTICATION_REQUIRED` - Missing or invalid authentication
- `VALIDATION_ERROR` - Input validation failed
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `RESOURCE_NOT_FOUND` - Requested resource doesn't exist
- `PERMISSION_DENIED` - Insufficient permissions
- `SERVICE_UNAVAILABLE` - External service unavailable

## 📝 Rate Limiting

### Rate Limit Headers

All API responses include rate limiting headers:

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 995
X-RateLimit-Reset: 1642248000
```

### Rate Limits by Endpoint Type

- **Default**: 100 requests/hour
- **API**: 1000 requests/hour
- **Authentication**: 10 requests/15 minutes
- **File Upload**: 50 requests/hour
- **Search**: 200 requests/hour

## 🔧 SDKs and Libraries

### Python SDK Example

```python
import lexai

# Initialize client
client = lexai.Client(api_key="your_api_key")

# Upload and analyze document
result = client.documents.upload(
    file_path="contract.pdf",
    document_type="contract",
    analysis_type="comprehensive"
)

print(f"Analysis complete: {result.success}")
print(f"Risk score: {result.analysis.risk_score}")
```

### JavaScript SDK Example

```javascript
import LexAI from 'lexai-js';

const client = new LexAI('your_api_key');

// Translate legal text
const translation = await client.spanish.translate({
  text: 'This contract is governed by state law',
  target_language: 'es',
  legal_context: 'contract'
});

console.log(`Translation: ${translation.translated_text}`);
```

## 🔍 Webhook Events

### Webhook Configuration

```http
POST /api/webhooks
Authorization: Bearer {token}
Content-Type: application/json

{
  "url": "https://your-app.com/webhook",
  "events": ["document.analyzed", "case.updated"],
  "secret": "webhook_secret"
}
```

### Webhook Events

- `document.analyzed` - Document analysis completed
- `contract.analyzed` - Contract analysis completed
- `case.created` - New case created
- `case.updated` - Case status changed
- `client.created` - New client added
- `translation.completed` - Translation finished

### Webhook Payload Example

```json
{
  "event": "document.analyzed",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "document_id": "doc_123456",
    "client_id": 789,
    "analysis_complete": true,
    "risk_score": 35.0
  },
  "signature": "sha256=abcdef..."
}
```

## 📚 Code Examples

### Complete Workflow Example

```python
import requests
import json

# Configuration
API_BASE = "https://api.lexai.com"
API_KEY = "your_api_key"
headers = {"Authorization": f"Bearer {API_KEY}"}

# 1. Create client
client_data = {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com",
    "client_type": "individual"
}

response = requests.post(
    f"{API_BASE}/api/clients",
    headers=headers,
    json=client_data
)
client = response.json()

# 2. Upload and analyze contract
with open("contract.pdf", "rb") as f:
    files = {"file": f}
    data = {
        "document_type": "contract",
        "client_id": client["client"]["id"]
    }
    
    response = requests.post(
        f"{API_BASE}/api/documents/upload",
        headers=headers,
        files=files,
        data=data
    )
    document = response.json()

# 3. Get contract analysis
analysis = document["analysis"]
print(f"Contract risk score: {analysis['risk_score']}")
print(f"Key concerns: {analysis['red_flags']}")

# 4. Translate contract to Spanish
translation_data = {
    "document_text": document["extracted_text"],
    "document_type": "contract",
    "target_language": "es"
}

response = requests.post(
    f"{API_BASE}/api/spanish/translate-document",
    headers=headers,
    json=translation_data
)
translation = response.json()

print(f"Spanish translation completed with {translation['confidence_score']} confidence")
```

## 🛠️ Testing API Endpoints

### Using cURL

```bash
# Health check
curl -X GET "https://api.lexai.com/api/health"

# Login
curl -X POST "https://api.lexai.com/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}'

# Upload document
curl -X POST "https://api.lexai.com/api/documents/upload" \
  -H "Authorization: Bearer your_token" \
  -F "file=@contract.pdf" \
  -F "document_type=contract"

# Legal research
curl -X POST "https://api.lexai.com/api/legal-research/search" \
  -H "Authorization: Bearer your_token" \
  -H "Content-Type: application/json" \
  -d '{"query":"contract law","jurisdiction":"federal"}'
```

### Postman Collection

A comprehensive Postman collection is available at:
`https://api.lexai.com/postman/collection.json`

## 📞 Support

- **API Documentation**: https://docs.lexai.com
- **Developer Portal**: https://developers.lexai.com
- **Support Email**: api-support@lexai.com
- **Status Page**: https://status.lexai.com

---

This API documentation provides comprehensive coverage of all LexAI endpoints with practical examples for integration.