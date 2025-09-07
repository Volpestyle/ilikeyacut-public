# ilikeyacut Service Integration Documentation

## Overview
This document describes how the iOS frontend and AWS serverless backend services work together to deliver the ilikeyacut app experience.

## Architecture Diagram
```
┌─────────────────────────────────────────────────────────────┐
│                        iOS App (SwiftUI)                     │
├─────────────────────────────────────────────────────────────┤
│  Authentication  │  Camera/Photos  │  Hairstyle Editor      │
│     Manager      │     Manager      │      Service          │
│                  │                 │                        │
│  Credit Manager  │  StoreKit IAP   │  Usage History         │
└────────┬─────────┴────────┬─────────┴──────────┬────────────┘
         │                  │                     │
         │              Local Storage             │
         │         (Keychain, Cache, Credits)    │
         │                  │                     │
    ═════╪══════════════════╪═════════════════════╪═════════
         │              HTTPS/JSON                │
         │                  │                     │
┌────────▼──────────────────▼─────────────────────▼────────────┐
│                    AWS API Gateway                            │
│            (Global Rate Limiting, Usage Plans)                │
└────────┬──────────────────┬─────────────────────┬────────────┘
         │                  │                     │
┌────────▼────────┐ ┌───────▼────────┐ ┌─────────▼────────────┐
│ Auth Lambda (Go)│ │Hairstyles      │ │ Gemini Proxy        │
│ /api/auth/*     │ │Lambda (Go)     │ │ Lambda (Go)         │
│                 │ │/api/hairstyles │ │ /api/gemini-edit    │
│                 │ │                │ │ + Credit Validation │
└────────┬────────┘ └───────┬────────┘ └─────────┬────────────┘
         │                  │                     │
     ┌───▼─────┐    ┌───────▼────────┐   ┌───────▼────────────┐
     │Purchase │    │   DynamoDB     │   │  Secrets Manager   │
     │Lambda   │    │  Tables:       │   │  (API Keys)        │
     │/api/    │    │  - Templates   │   └────────────────────┘
     │purchase │    │  - Users       │           │
     └───┬─────┘    │  - Credits     │   ┌───────▼────────────┐
         │          │  - History     │   │  Google Gemini     │
         │          └───────┬────────┘   │  2.5 Flash Image   │
         │                  │             │  ($0.039/image)    │
         │          ┌───────▼────────┐   └────────────────────┘
         │          │   S3 Bucket    │
         │          │ (Asset Storage)│
         │          └────────────────┘
         │
┌────────▼────────────────────────────────────────────────────┐
│            OAuth Providers (Google, X)                       │
│                  + Device ID Tracking                        │
└──────────────────────────────────────────────────────────────┘
```

## Service Components

### iOS Frontend Services

#### 1. **AuthenticationManager** (`/ilikeyacut-ios/ilikeyacut/Services/AuthenticationManager.swift`)
- **Purpose**: Manages user authentication state and OAuth flows
- **Integration Points**:
  - Calls `/api/auth/login` for OAuth authentication (allocates 4 lifetime credits for new users)
  - Calls `/api/auth/guest` for guest sessions (1 lifetime credit, device ID tracked)
  - Stores tokens in iOS Keychain
  - Includes auth token in all API requests
  - Tracks user tier (guest/free/premium/admin)
- **Data Flow**:
  1. Guest: Device ID → Backend tracks → 1 lifetime credit
  2. OAuth: Login → Backend validates → 4 lifetime credits (first time)
  3. Token included in `Authorization` header for all requests

#### 2. **APIService** (`/ilikeyacut-ios/ilikeyacut/Services/APIService.swift`)
- **Purpose**: Central networking layer for all backend communication
- **Features**:
  - Async/await with URLSession
  - Automatic retry with exponential backoff
  - Token refresh handling
  - Error mapping to user-friendly messages
- **Base Configuration**:
  ```swift
  baseURL: "https://api.ilikeyacut.app"  // Production
  timeout: 30 seconds
  maxRetries: 3
  ```

#### 3. **HairstyleService** (`/ilikeyacut-ios/ilikeyacut/Services/HairstyleService.swift`)
- **Purpose**: Manages hairstyle templates and AI processing with credit validation
- **Integration Points**:
  - Fetches templates from `/api/hairstyles` (includes S3 signed URLs)
  - Sends images to `/api/gemini-edit` (validates credits first)
  - Caches templates locally (1-hour TTL)
  - Handles 402 insufficient credits errors
- **Data Flow**:
  1. App launch → Fetch templates with S3 assets → Cache locally
  2. User selects input method → Check credit balance
  3. If sufficient credits → Send to backend → Deduct credits
  4. If insufficient → Show upgrade options (subscription/bundles)
  5. Display results → Update credit UI → Cache for history

#### 4. **CameraManager** (`/ilikeyacut-ios/ilikeyacut/Services/CameraManager.swift`)
- **Purpose**: Handles camera and photo library operations
- **Integration**: 
  - Captures photos for AI processing
  - Saves results to device gallery
  - No direct backend communication

#### 5. **CreditManager** (`/ilikeyacut-ios/ilikeyacut/Services/CreditManager.swift`)
- **Purpose**: Manages user credit balance and purchases
- **Integration Points**:
  - Fetches balance from `/api/user/credits`
  - Validates credit availability before generation
  - Handles StoreKit 2 purchases
  - Calls `/api/purchase` for receipt validation
- **Credit Requirements**:
  - Single-image generation: 1 credit
  - Multi-angle generation: 4 credits

#### 6. **StoreKitManager** (`/ilikeyacut-ios/ilikeyacut/Services/StoreKitManager.swift`)
- **Purpose**: Handles in-app purchases and subscriptions
- **Product IDs**:
  - `com.ilikeyacut.subscription.monthly` - $9.99 (168 credits/month)
  - `com.ilikeyacut.bundle.small` - $0.99 (8 credits)
  - `com.ilikeyacut.bundle.large` - $4.99 (48 credits)
- **Integration**:
  - StoreKit 2 for purchase flow
  - Send receipt to `/api/purchase` for validation
  - Update credit balance on success

### AWS Backend Services

#### 1. **Gemini Proxy Lambda** (`/backend/lambda/gemini-proxy/main.go`)
- **Endpoint**: `POST /api/gemini-edit`
- **Purpose**: Secure proxy for Google Gemini API with credit management
- **Flow**:
  1. Receive multimodal request from iOS app
  2. Extract user ID from JWT or device ID for guests
  3. Check credit balance (1 for single, 4 for multi-angle)
  4. If insufficient → Return 402 with upgrade options
  5. Deduct credits atomically from DynamoDB
  6. Retrieve Gemini API key from Secrets Manager
  7. Add face preservation instructions to prompt
  8. Forward to Gemini 2.5 Flash Image API ($0.039/image)
  9. Log usage to DynamoDB History table
  10. Return generated images with remaining credits
- **Headers**: Returns `X-Credits-Remaining` in response

#### 2. **Hairstyles Lambda** (`/backend/lambda/hairstyles/main.go`)
- **Endpoint**: `GET /api/hairstyles`
- **Purpose**: Serve hairstyle template library
- **Flow**:
  1. Query DynamoDB for templates
  2. Generate S3 signed URLs for assets (1-hour expiry)
  3. Return sorted templates with metadata
- **Optimization**: CloudFront CDN for asset delivery

#### 3. **Auth Lambdas** (`/backend/lambda/auth/*.go`)
- **Endpoints**: 
  - `POST /api/auth/login` - OAuth authentication (4 lifetime credits for new users)
  - `POST /api/auth/guest` - Guest sessions (1 lifetime credit, device tracked)
- **Purpose**: Handle authentication and initial credit allocation
- **Integration**: 
  - OAuth providers (Google, X) for authentication
  - DynamoDB Users table for user data
  - DynamoDB Credits table for credit tracking

#### 4. **Credit Management Lambdas** (`/backend/lambda/credits/*.go`)
- **Endpoints**:
  - `GET /api/user/credits` - Get current balance
  - `POST /api/purchase` - Validate IAP and add credits
  - `GET /api/usage-history` - Get generation history
- **Purpose**: Manage credit system and purchases
- **DynamoDB Tables**:
  - **Users**: User profiles and tiers
  - **Credits**: Credit balances and limits
  - **History**: Usage tracking and analytics
- **Credit Allocations**:
  - Guest: 1 lifetime (device ID tracked)
  - Free: 4 lifetime (OAuth required)
  - Premium: 168/month (resets on billing date)
  - Bundles: Added to balance (no expiration)

## Data Flow Scenarios

### Scenario 1: User Takes Selfie and Applies Hairstyle
```
1. iOS: Camera captures photo → Compress to 1024x1024
2. iOS: User selects hairstyle template from library
3. iOS: Check credit balance (1 for single, 4 for multi-angle)
4. iOS: If insufficient → Show purchase options (subscription/bundles)
5. iOS: APIService.processHairstyle() called with auth token
6. API Gateway: Global rate limit check → Route to Lambda
7. Lambda: Validate user credits in DynamoDB
8. Lambda: Deduct credits atomically (prevent race conditions)
9. Lambda: Add API key → Call Gemini API ($0.039/image)
10. Gemini: Process image → Return transformed result
11. Lambda: Log to History table → Return with credits remaining
12. iOS: Display result → Update credit UI → Save to cache
13. iOS: User saves → Store in Photos library
```

### Scenario 3: User Purchases Credits
```
1. iOS: User taps purchase → StoreKit 2 sheet appears
2. iOS: User completes purchase → Get receipt
3. iOS: Send receipt to /api/purchase for validation
4. Lambda: Verify with Apple/Google servers
5. Lambda: Add credits to user balance in DynamoDB
6. Lambda: Return new balance to client
7. iOS: Update credit UI → Enable generation
```

### Scenario 2: Template Library Synchronization
```
1. iOS: App launch → Check cache age
2. iOS: If expired → Fetch from /api/hairstyles
3. Lambda: Query DynamoDB → Get template data
4. Lambda: Generate S3 signed URLs for images
5. Lambda: Return template array
6. iOS: Cache templates with TTL
7. iOS: Display in gallery view
```

## Configuration Management

### iOS App Configuration
```swift
// Environment-based configuration
#if DEBUG
let apiBaseURL = "https://dev-api.ilikeyacut.app"
#else
let apiBaseURL = "https://api.ilikeyacut.app"
#endif
```

### Backend Environment Variables
```yaml
# SAM template parameters
Environment: dev|staging|prod
GeminiApiKey: stored in Secrets Manager
JWTSecret: stored in Secrets Manager
AppleSharedSecret: stored in Secrets Manager (for IAP validation)
GooglePlayKey: stored in Secrets Manager (for IAP validation)

# DynamoDB Table Names
UsersTable: ilikeyacut-users-{Environment}
CreditsTable: ilikeyacut-credits-{Environment}
HistoryTable: ilikeyacut-history-{Environment}
TemplatesTable: ilikeyacut-templates-{Environment}
```

## Security Considerations

### API Security
- **HTTPS Only**: All communication encrypted
- **API Keys**: Stored in AWS Secrets Manager, never in code
- **JWT Tokens**: Short-lived (1 hour), refresh tokens for extended sessions
- **Credit System**: Pre-flight validation prevents abuse
- **Device Tracking**: Guest users tracked by device ID to prevent abuse
- **Rate Limiting**: 
  - Global: 60 req/sec burst, 100K req/day quota
  - Credit-based: Guest (1), Free (4), Premium (168/month)
- **CORS**: Configured for mobile app bundle IDs only

### Data Privacy
- **Images**: Processed in memory, not stored on backend
- **User Data**: Minimal collection, GDPR compliant
- **Device IDs**: Used only for guest credit tracking
- **Purchase Data**: Receipt validation only, no payment info stored
- **Logs**: PII scrubbed, 7-day retention
- **S3 Assets**: Private bucket with signed URL access only (1-hour expiry)

## Monitoring & Debugging

### iOS Debug Tools
```bash
# View device logs
xcrun devicectl device log stream | grep ilikeyacut

# Network debugging
- Enable Network Link Conditioner
- Use Charles Proxy for request inspection
```

### Backend Monitoring
```bash
# View Lambda logs
sam logs -n GeminiProxyFunction --tail

# CloudWatch Metrics
- API Gateway: Request count, latency, 4xx/5xx errors
- Lambda: Invocations, duration, errors, throttles
- DynamoDB: Read/write capacity, throttled requests
```

## Error Handling

### iOS Error Recovery
```swift
// Automatic retry with exponential backoff
1st attempt: Immediate
2nd attempt: 1 second delay
3rd attempt: 3 seconds delay
Failure: Show user-friendly error with retry option
```

### Backend Error Responses
```json
// 402 - Insufficient Credits
{
  "error": {
    "code": "insufficient_credits",
    "message": "You need 4 credits for multi-angle generation. You have 2 credits."
  },
  "credits": {
    "required": 4,
    "available": 2,
    "userType": "free"
  },
  "upgrade_options": {
    "subscription": {
      "credits_per_month": 168,
      "price": "$9.99/month"
    },
    "bundles": [
      { "credits": 8, "price": "$0.99" },
      { "credits": 48, "price": "$4.99" }
    ]
  }
}

// 429 - Rate Limit
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please try again in 60 seconds.",
    "retryAfter": 60
  }
}
```

## Performance Optimization

### Frontend Optimizations
- **Image Compression**: Resize to 1024x1024 before upload
- **Caching**: 1-hour TTL for templates, indefinite for results
- **Lazy Loading**: Images loaded on-demand in gallery
- **Background Processing**: API calls on background queue

### Backend Optimizations
- **Lambda ARM**: 20% better price-performance
- **Go Runtime**: <100ms cold starts
- **DynamoDB On-Demand**: Auto-scaling, pay per request
- **CloudFront CDN**: Global edge caching for assets

## Deployment Pipeline

### iOS Deployment
```bash
# Build and deploy to device
./scripts/deploy-ios-to-device.sh

# TestFlight deployment (manual via Xcode)
1. Archive in Xcode
2. Upload to App Store Connect
3. Distribute to TestFlight
```

### Backend Deployment
```bash
# Deploy to AWS
./scripts/deploy-backend-to-aws.sh dev

# Verify deployment
curl https://dev-api.ilikeyacut.app/api/hairstyles

# Set admin access for development
cd backend/scripts
go run update-user-tier.go -email admin@example.com -tier admin
```

## Troubleshooting Guide

### Common Issues

#### 1. "Network Error" on iOS
- Check: Internet connection
- Check: Backend API status
- Check: Valid auth token
- Solution: Pull to refresh, re-login if needed

#### 2. "Insufficient Credits"
- Cause: User has exhausted credit allocation
- Solution: Purchase subscription ($9.99/month) or bundle ($0.99/$4.99)
- Dev: Set admin tier for unlimited credits

#### 3. "Rate Limit Exceeded"
- Cause: Global API limit reached (60 req/sec)
- Solution: Wait and retry with exponential backoff

#### 4. "Image Processing Failed"
- Check: Image size (<20MB after base64)
- Check: Valid image format (JPEG/PNG)
- Check: Sufficient credits (1 or 4)
- Check: Gemini API status
- Solution: Compress to 1024x1024, ensure credits available

#### 5. "Templates Not Loading"
- Check: DynamoDB Templates table exists
- Check: S3 bucket accessible
- Check: Lambda has IAM permissions for S3 signed URLs
- Solution: Run seed script, verify IAM roles

## Testing Strategy

### iOS Testing
```swift
// Unit Tests
- AuthenticationManager: Mock OAuth flows, device ID tracking
- APIService: Mock network responses, 402 error handling
- CreditManager: Test balance updates, purchase flows
- HairstyleService: Test caching, credit validation
- StoreKitManager: Mock IAP transactions

// UI Tests
- Guest flow: Launch → 1 credit → Generate → Upgrade prompt
- Purchase flow: Tap buy → StoreKit sheet → Success → Credits updated
- Camera flow: Capture → Preview → Check credits → Generate
- Template selection: Browse → Select → Validate credits → Apply
- Results: Display → Zoom → Share → Update history
```

### Backend Testing
```go
// Lambda Tests
- Credit validation and deduction
- Atomic DynamoDB operations
- IAP receipt validation
- 402 error response format
- Device ID tracking for guests
- Secrets Manager integration
- S3 signed URL generation (1-hour expiry)
- Usage history logging
```

### Integration Testing
```bash
# End-to-end test script
1. Guest mode: Get 1 credit
2. Attempt generation → Success
3. Attempt second → 402 error
4. OAuth login → Get 4 credits
5. Multi-angle generation → 4 credits deducted
6. Purchase bundle → Credits added
7. Verify history tracking
8. Test subscription flow
```

## Future Enhancements

### Planned Features
1. **Annual Subscriptions**: $99/year option (20% discount)
2. **Referral Program**: 5 credits per successful referral
3. **Team Plans**: Corporate subscriptions for salons
4. **Batch Processing**: Optimize multi-angle generation costs
5. **WebSocket Support**: Real-time progress updates
6. **Offline Mode**: Queue requests when offline
7. **Analytics Dashboard**: Usage patterns, popular styles
8. **Social Features**: Share transformations, user galleries

### Scalability Considerations
- **Database**: Consider migrating to Aurora Serverless for high traffic
- **Caching**: Add ElastiCache for session management
- **CDN**: Expand CloudFront distribution for global coverage
- **Queue**: Add SQS for async processing at scale

## Support & Maintenance

### Monitoring Checklist
- [ ] Credit usage patterns (daily)
- [ ] IAP success rates (daily)
- [ ] 402 error frequency (indicates upgrade opportunities)
- [ ] API Gateway metrics (daily)
- [ ] Lambda error rates (hourly during peak)
- [ ] DynamoDB throttling (weekly)
- [ ] Gemini API costs ($0.039/image tracking)
- [ ] S3 storage costs (monthly)
- [ ] Secrets rotation (quarterly)

### Update Process
1. Backend: Deploy with SAM (zero downtime)
2. iOS: Submit to App Store (1-2 day review)
   - Include IAP products in App Store Connect
   - Test with Sandbox accounts first
3. Templates: Update via DynamoDB console (instant)
4. Assets: Upload to S3, update DynamoDB references
5. Credit Adjustments: Use admin scripts for user tier changes

## Contact & Resources

### Documentation
- API Contract: `/docs/API_CONTRACT.md`
- Design Document: `/docs/DESIGN.md`
- Deployment Scripts: `/scripts/`

### AWS Resources
- Console: https://console.aws.amazon.com
- CloudWatch: Monitor Lambda logs and metrics
- DynamoDB: Manage hairstyle templates
- S3: Upload template assets

### Development Tools
- Xcode: iOS development and debugging
- SAM CLI: Backend development and testing
- Postman: API testing and documentation
- Charles Proxy: Network debugging