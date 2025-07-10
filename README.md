# LexAI Practice Partner

A sophisticated AI-powered legal assistant built with Flask, designed specifically for family law practitioners. Features advanced privacy protection through data anonymization and integrates with Grok-3 for intelligent legal support.

## Features

- **AI-Powered Legal Assistant**: Uses Grok-3 for intelligent responses on family law matters
- **Client Management**: Comprehensive client profiles with case history tracking
- **Document Processing**: Upload and process legal documents with text extraction
- **Advanced Privacy**: Sophisticated tokenization system to protect client confidentiality
- **Professional UI**: Clean, responsive interface optimized for legal professionals
- **Persistent Storage**: PostgreSQL database with Neon integration for Vercel deployment

## Setup Instructions

### 1. Prerequisites

- Python 3.8+
- PostgreSQL database (Neon recommended for production)
- X.AI API key for Grok-3 access

### 2. Local Development

1. Clone the repository and navigate to the project directory
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

5. Run the application:
   ```bash
   python app.py
   ```

### 3. Neon Database Setup

1. Create a Neon account at [neon.tech](https://neon.tech)
2. Create a new database project
3. Copy the connection string (it should look like):
   ```
   postgresql://username:password@ep-cool-darkness-123456.us-east-1.aws.neon.tech/neondb?sslmode=require
   ```
4. Add this to your `.env` file as `DATABASE_URL`

### 4. Vercel Deployment

1. Install Vercel CLI:
   ```bash
   npm install -g vercel
   ```

2. Deploy to Vercel:
   ```bash
   vercel
   ```

3. Set environment variables in Vercel dashboard:
   - `XAI_API_KEY`: Your X.AI API key
   - `DATABASE_URL`: Your Neon database connection string

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `XAI_API_KEY` | X.AI API key for Grok-3 access | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `FLASK_ENV` | Flask environment (development/production) | No |
| `FLASK_DEBUG` | Flask debug mode (True/False) | No |

## Database Schema

The application uses three main tables:

- **clients**: Store client information and case details
- **conversations**: Store chat history between lawyers and AI
- **documents**: Store uploaded documents with extracted text

## Privacy & Security

- **Data Anonymization**: All client data is tokenized before sending to AI
- **Secure File Handling**: Files stored in temporary directories
- **Environment-based Secrets**: API keys managed through environment variables
- **Database Encryption**: Neon provides automatic encryption at rest

## Usage

1. **Client Management**: Add and manage client profiles with case information
2. **Document Upload**: Upload legal documents for AI analysis
3. **AI Consultation**: Use pre-built prompts or custom queries for legal assistance
4. **Conversation History**: Review past interactions with AI for each client

## API Endpoints

- `GET /api/client/<client_id>`: Get client data
- `POST /api/client/<client_id>`: Update client information
- `POST /api/new_conversation/<client_id>`: Start new conversation
- `POST /api/upload`: Upload document
- `POST /api/chat`: Send message to AI

## Legal Compliance

This application is designed with legal professional standards in mind:

- Client confidentiality through advanced anonymization
- Audit trails through conversation history
- Secure document handling
- Professional-grade UI suitable for client interactions

## Support

For issues or questions, please check the application logs or contact support.# Test change
