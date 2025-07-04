# 🗄️ LexAI Practice Partner - Database Schema Documentation

## Overview

The LexAI Practice Partner platform uses a relational database schema designed for scalability, security, and legal practice management efficiency.

## 📊 Entity Relationship Diagram

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    Users    │    │   Clients   │    │Conversations│
│             │    │             │    │             │
│ id (PK)     │    │ id (PK)     │    │ id (PK)     │
│ email       │    │ name        │    │ client_id   │
│ password_hash│    │ case_number │    │ role        │
│ first_name  │    │ email       │    │ content     │
│ last_name   │    │ phone       │    │ timestamp   │
│ firm_name   │    │ case_type   │    │             │
│ role        │    │ notes       │    └─────────────┘
│ is_active   │    │ created_at  │
│ created_at  │    │ updated_at  │
│ last_login  │    │             │
│             │    └─────────────┘
└─────────────┘
                            │
                            │
                            ▼
                   ┌─────────────┐
                   │ Documents   │
                   │             │
                   │ id (PK)     │
                   │ client_id   │
                   │ filename    │
                   │ text        │
                   │ upload_date │
                   │             │
                   └─────────────┘
```

## 📋 Table Specifications

### Users Table

**Purpose:** User authentication and authorization

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY, AUTO_INCREMENT | Unique user identifier |
| email | String(120) | UNIQUE, NOT NULL, INDEX | User email address |
| password_hash | LargeBinary | NOT NULL | Bcrypt hashed password |
| first_name | String(50) | NOT NULL | User's first name |
| last_name | String(50) | NOT NULL | User's last name |
| firm_name | String(100) | NULLABLE | Law firm name |
| role | String(20) | NOT NULL, DEFAULT 'user' | User role (user, admin, premium) |
| is_active | Boolean | NOT NULL, DEFAULT true | Account status |
| created_at | DateTime | DEFAULT now() | Account creation timestamp |
| last_login | DateTime | NULLABLE | Last login timestamp |
| password_updated_at | DateTime | NULLABLE | Password change timestamp |
| reset_token | String(64) | NULLABLE | Password reset token |
| reset_token_expires | DateTime | NULLABLE | Reset token expiration |
| subscription_tier | String(20) | DEFAULT 'free' | Subscription level |
| subscription_expires | DateTime | NULLABLE | Subscription expiration |

**Indexes:**
- `ix_users_email` on `email`
- `ix_users_role` on `role`
- `ix_users_is_active` on `is_active`

### Clients Table

**Purpose:** Client information and case management

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | String(50) | PRIMARY KEY | Unique client identifier |
| name | String(100) | NOT NULL | Client full name |
| case_number | String(50) | NULLABLE | Case reference number |
| email | String(100) | NULLABLE | Client email address |
| phone | String(20) | NULLABLE | Client phone number |
| case_type | String(50) | NULLABLE | Type of legal case |
| notes | Text | NULLABLE | Case notes and details |
| created_at | DateTime | DEFAULT now() | Client creation timestamp |
| updated_at | DateTime | DEFAULT now(), ON UPDATE now() | Last update timestamp |

**Indexes:**
- `ix_clients_name` on `name`
- `ix_clients_case_type` on `case_type`
- `ix_clients_updated_at` on `updated_at`

### Conversations Table

**Purpose:** AI chat history and legal consultations

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY, AUTO_INCREMENT | Unique conversation identifier |
| client_id | String(50) | FOREIGN KEY, NOT NULL | Reference to clients.id |
| role | String(20) | NOT NULL | Message role (user, assistant) |
| content | Text | NOT NULL | Message content |
| timestamp | DateTime | DEFAULT now() | Message timestamp |

**Foreign Keys:**
- `fk_conversations_client_id` → `clients.id` (CASCADE DELETE)

**Indexes:**
- `ix_conversations_client_id` on `client_id`
- `ix_conversations_timestamp` on `timestamp`
- `ix_conversations_role` on `role`

### Documents Table

**Purpose:** Document storage and processing

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY, AUTO_INCREMENT | Unique document identifier |
| client_id | String(50) | FOREIGN KEY, NOT NULL | Reference to clients.id |
| filename | String(255) | NOT NULL | Original filename |
| text | Text | NULLABLE | Extracted text content |
| upload_date | DateTime | DEFAULT now() | Upload timestamp |

**Foreign Keys:**
- `fk_documents_client_id` → `clients.id` (CASCADE DELETE)

**Indexes:**
- `ix_documents_client_id` on `client_id`
- `ix_documents_upload_date` on `upload_date`
- `ix_documents_filename` on `filename`

## 🔐 Security Considerations

### Password Security
- Passwords are hashed using bcrypt with salt
- Minimum 8 characters with complexity requirements
- Password reset tokens expire after 1 hour
- Account lockout after failed attempts

### Data Protection
- Sensitive client data encrypted at rest
- Audit logging for data access
- GDPR compliance for EU clients
- Regular security audits

### Access Control
- Role-based permissions (user, admin, premium)
- Session-based authentication
- CSRF protection enabled
- Rate limiting on API endpoints

## 📈 Performance Optimizations

### Indexing Strategy
```sql
-- Primary indexes for frequent queries
CREATE INDEX ix_clients_updated_at ON clients(updated_at DESC);
CREATE INDEX ix_conversations_client_timestamp ON conversations(client_id, timestamp DESC);
CREATE INDEX ix_users_active_role ON users(is_active, role);
```

### Query Optimization
- Use of connection pooling
- Prepared statements for security
- Pagination for large result sets
- Caching for frequently accessed data

## 🔄 Migration History

### Version 1.0.0 - Initial Schema
- Created users table with authentication
- Created clients table for case management
- Created conversations table for AI chat history
- Created documents table for file management
- Added necessary indexes and foreign keys

### Future Migrations Planned
- Billing and subscription tables
- Advanced case management features
- Document versioning system
- Audit logging tables
- Performance analytics tables

## 📊 Data Relationships

### One-to-Many Relationships
- `clients` → `conversations` (One client has many conversations)
- `clients` → `documents` (One client has many documents)

### Cascade Behaviors
- Delete client → Delete all related conversations and documents
- User deactivation → Preserve all client data
- Document deletion → Remove file from storage

## 🧪 Sample Data Structure

### User Record
```json
{
  "id": 1,
  "email": "lawyer@firm.com",
  "first_name": "John",
  "last_name": "Doe",
  "firm_name": "Doe & Associates",
  "role": "admin",
  "is_active": true,
  "subscription_tier": "premium"
}
```

### Client Record
```json
{
  "id": "client_123",
  "name": "Jane Smith",
  "case_number": "2024-FAM-001",
  "email": "jane@email.com",
  "case_type": "Family Law",
  "notes": "Divorce proceedings initiated..."
}
```

### Conversation Record
```json
{
  "id": 1,
  "client_id": "client_123",
  "role": "user",
  "content": "I need help with custody arrangements",
  "timestamp": "2024-07-04T10:30:00Z"
}
```

## 🛠️ Database Administration

### Backup Strategy
```bash
# Daily automated backups
python manage.py backup-db --path "backups/daily_$(date +%Y%m%d).sql"

# Weekly full backups with retention
python manage.py backup-db --path "backups/weekly_$(date +%Y%m%d).sql"
```

### Maintenance Tasks
```bash
# Update statistics
python manage.py analyze-db

# Vacuum database (PostgreSQL)
python manage.py vacuum-db

# Check integrity
python manage.py validate-db
```

### Monitoring Queries
```sql
-- Active connections
SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'active';

-- Table sizes
SELECT schemaname,tablename,pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size 
FROM pg_tables WHERE schemaname='public';

-- Slow queries
SELECT query, mean_time, calls FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;
```

## 📋 Migration Best Practices

### Before Migration
1. Create database backup
2. Test migration on staging environment
3. Verify rollback procedures
4. Check application compatibility

### During Migration
1. Use transactions for atomic changes
2. Monitor performance impact
3. Maintain backward compatibility
4. Log all changes

### After Migration
1. Validate schema integrity
2. Update application configuration
3. Run integration tests
4. Monitor application health

---

**Note:** This schema is designed for scalability and can be extended with additional tables for billing, analytics, and advanced features as the platform grows.