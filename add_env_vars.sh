#!/bin/bash
echo "🚀 Adding Environment Variables to Vercel Production"
echo "================================================="

# Database variables
echo "📊 Adding DATABASE_URL..."
echo "postgres://neondb_owner:npg_9OENS6QdCUoM@ep-weathered-voice-afzm9t1s-pooler.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require" | vercel env add DATABASE_URL production

echo "📊 Adding POSTGRES_URL..."
echo "postgres://neondb_owner:npg_9OENS6QdCUoM@ep-weathered-voice-afzm9t1s-pooler.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require" | vercel env add POSTGRES_URL production

echo "🔄 Adding REDIS_URL..."
echo "redis://default:mIFwUfqGu4ZMOwSWaT4lgSpVF6gMocmA@redis-13345.c241.us-east-1-4.ec2.redns.redis-cloud.com:13345" | vercel env add REDIS_URL production

# AI and storage variables
echo "🤖 Adding XAI_API_KEY..."
echo "xai-JXfs7xIBbPhA4a4yPyCFWhjmjbGab31orEzwGnvYNih2V5nmAIlvkSSuIAv047TjBYGwu1CdU7NVtAUi" | vercel env add XAI_API_KEY production

echo "☁️ Adding FILE_STORAGE_PROVIDER..."
echo "gcs" | vercel env add FILE_STORAGE_PROVIDER production

echo "🗄️ Adding GCS_BUCKET_NAME..."
echo "lexai-465013-bucket" | vercel env add GCS_BUCKET_NAME production

echo "🌍 Adding GCP_PROJECT_ID..."
echo "lexai-465013" | vercel env add GCP_PROJECT_ID production

echo ""
echo "✅ All environment variables added!"
echo "🚀 Triggering production deployment..."
vercel --prod

echo ""
echo "🎉 Production environment setup complete!"
echo "📋 Check deployment logs for DATABASE_AVAILABLE=True"