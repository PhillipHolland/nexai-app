#!/bin/bash
# LexAI Production Startup Script

echo "🏛️  Starting LexAI Practice Partner..."

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set production environment
export FLASK_ENV=production
export FLASK_DEBUG=false

# Start with Gunicorn
gunicorn --bind 0.0.0.0:8000 --workers 4 --timeout 30 app:app
