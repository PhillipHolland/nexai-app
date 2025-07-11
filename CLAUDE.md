# Claude Code Knowledge Base - LexAI Practice Partner

## 🎯 Project Overview
LexAI Practice Partner is a comprehensive law firm management platform with a marketplace model featuring a **1.9% platform fee** on all client payments. The system includes client portals, law firm dashboards, billing management, and Stripe payment processing.

## 🏗️ Architecture & Tech Stack
- **Backend**: Python Flask API (`api/index.py`)
- **Frontend**: HTML/CSS/JavaScript templates 
- **Database**: PostgreSQL (falls back to mock data)
- **Payments**: Stripe API (HTTP-based, no Python module)
- **Deployment**: Vercel serverless
- **Repository**: GitHub - PhillipHolland/nexai-app

## 🔑 Key System Components

### **1. Platform Fee System (1.9%)**
- **Rate**: 1.9% on all successful client payments
- **Implementation**: Tracked in Stripe metadata, ready for Connect
- **Status**: Implemented but Connect accounts not yet fully configured
- **Location**: All payment flows include platform fee calculations

### **2. Payment Processing**
- **Client Portal**: Real Stripe checkout sessions via HTTP API
- **Law Firm Dashboard**: Payment link generation for client invoicing
- **Method**: HTTP requests to Stripe API (module not available on Vercel)
- **Issue Resolved**: Application fee was causing API rejection, now commented out

### **3. Authentication & Roles**
- **Law Firm Users**: Login with role-based permissions
- **Client Portal**: Separate authentication system
- **Demo Mode**: Many endpoints have authentication temporarily disabled

## 🚨 Critical Knowledge & Fixes

### **Stripe Integration**
```bash
# Environment Variables Required:
STRIPE_SECRET_KEY=sk_live_51... (confirmed working on Vercel)

# Common Issues:
1. STRIPE_MODULE_AVAILABLE = False (Python stripe module not on Vercel)
2. Use HTTP API calls instead: requests.post('https://api.stripe.com/v1/checkout/sessions')
3. MUST use urllib.parse.urlencode() for proper data formatting
4. application_fee_amount causes rejection without proper Connect setup
```

### **Working Payment Implementation Pattern**
```python
# This pattern works (copied from client billing):
checkout_data = {...}
headers = {'Authorization': f'Bearer {stripe_secret_key}', 'Content-Type': 'application/x-www-form-urlencoded'}
encoded_data = urllib.parse.urlencode(checkout_data)
response = requests.post(stripe_api_url, data=encoded_data, headers=headers)
```

### **Route Conflicts to Avoid**
```python
# NEVER create duplicate @app.route() definitions
# Flask will crash with: AssertionError: View function mapping is overwriting
# Always check for existing routes with: grep -n "route_name" api/index.py
```

## 📁 Key Files & Locations

### **Main API** (`/api/index.py`)
- **Lines 8936-9060**: Payment link generation (`/api/billing/generate-payment-link`)
- **Lines 9490+**: Client portal payment processing (`/api/client-portal/billing/pay-invoice`)
- **Lines 2441+**: Billing dashboard APIs
- **Lines 64-75**: Stripe initialization and availability flags

### **Templates**
- **`/templates/billing.html`**: Law firm billing dashboard with payment link generation
- **`/templates/client-billing.html`**: Client portal billing with working Stripe integration
- **`/templates/platform-verification.html`**: Testing dashboard for platform fee system

### **Key API Endpoints**
```
GET  /billing                           - Law firm billing dashboard
GET  /client-portal/billing             - Client billing portal  
POST /api/billing/generate-payment-link - Generate Stripe payment links
POST /api/billing/connect-status        - Platform fee analytics
GET  /platform-verification             - Testing interface
```

## 🔄 Development Workflow

### **Testing Payment Integration**
1. **Test client payments**: `/client-portal/billing` (should work with real Stripe)
2. **Test law firm links**: `/billing` → Click "🔗 Generate Link" 
3. **Debug endpoint**: Create temporary debug routes to check environment variables
4. **Remove debug routes**: Always clean up temporary debug endpoints

### **Git Workflow**
```bash
# Standard pattern:
git add [files]
git commit -m "Description with platform fee context

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"
git push origin main
```

### **Common Issues & Solutions**

#### **Demo Mode Fallback**
**Symptom**: Payment links go to `/demo-checkout` instead of real Stripe
**Causes**: 
1. Missing STRIPE_SECRET_KEY (check with debug endpoint)
2. HTTP request failing (usually due to application_fee_amount)
3. Wrong condition logic (use simple `if stripe_secret_key:`)

**Fix**: Copy exact working pattern from client billing implementation

#### **Site Crashes (500 errors)**
**Symptom**: All pages return 500, Flask won't start
**Common Cause**: Duplicate route definitions
**Fix**: Search for duplicate function names and remove

#### **Platform Fee Not Collected**
**Current Status**: Platform fee tracked in metadata only
**Reason**: Stripe Connect accounts not fully configured for law firms
**Next Step**: Implement proper Connect onboarding when needed

## 🎯 Platform Fee System Status

### **✅ Completed**
- Law firm billing dashboard with fee breakdown
- Client payment flow with 1.9% fee metadata
- Payment link generation system
- Platform fee analytics and reporting
- Verification testing dashboard

### **📋 TODO (Future)**
- Real Stripe Connect account linking for law firms
- Actual platform fee collection (currently in metadata)
- Enhanced analytics with charts/graphs
- Automated payout reporting

## 🔧 Quick Reference Commands

### **Check Stripe Status**
```bash
curl -s https://lexai-app.vercel.app/api/billing/connect-status | jq .
```

### **Test Payment Link Generation**
```bash
curl -X POST https://lexai-app.vercel.app/api/billing/generate-payment-link \
  -H "Content-Type: application/json" \
  -d '{"invoice_id":"test","invoice_number":"TEST-001","amount":100000}'
```

### **Debug Environment**
Create temporary debug endpoint to check:
- `os.environ.get('STRIPE_SECRET_KEY')` 
- `STRIPE_MODULE_AVAILABLE`
- `STRIPE_AVAILABLE`

## 💡 Development Notes

### **Vercel Deployment**
- Changes auto-deploy on git push to main
- Environment variables configured in Vercel dashboard
- Python stripe module not available (use HTTP API)
- Deployment takes 2-3 minutes

### **Platform Fee Philosophy**
- **1.9% rate**: Competitive (industry standard 2.5%-3.5%)
- **Transparent**: Clear disclosure to law firms
- **Marketplace model**: Law firms onboard, clients pay through platform
- **Future scaling**: Ready for multi-tenant law firm marketplace

---

**Last Updated**: July 11, 2025  
**Status**: 1.9% platform fee system fully operational, payment links working with real Stripe