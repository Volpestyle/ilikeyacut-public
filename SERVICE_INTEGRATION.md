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
└────────┬─────────┴────────┬─────────┴──────────┬────────────┘
         │                  │                     │
         │              Local Storage             │
         │            (Keychain, Cache)           │
         │                  │                     │
    ═════╪══════════════════╪═════════════════════╪═════════
         │              HTTPS/JSON                │
         │                  │                     │
┌────────▼──────────────────▼─────────────────────▼────────────┐
│                    AWS API Gateway                            │
│                  (Rate Limiting, CORS)                        │
└────────┬──────────────────┬─────────────────────┬────────────┘
         │                  │                     │
┌────────▼────────┐ ┌───────▼────────┐ ┌─────────▼────────────┐
│ Auth Lambda (Go)│ │Hairstyles      │ │ Gemini Proxy        │
│ /api/auth/*     │ │Lambda (Go)     │ │ Lambda (Go)         │
│                 │ │/api/hairstyles │ │ /api/gemini-edit    │
└────────┬────────┘ └───────┬────────┘ └─────────┬────────────┘
         │                  │                     │
         │          ┌───────▼────────┐   ┌───────▼────────────┐
         │          │   DynamoDB     │   │  Secrets Manager   │
         │          │  (Templates)   │   │  (API Keys)        │
         │          └───────┬────────┘   └────────────────────┘
         │                  │                     │
         │          ┌───────▼────────┐   ┌───────▼────────────┐
         │          │   S3 Bucket    │   │  Google Gemini     │
         │          │ (Asset Storage)│   │  2.5 Flash Image   │
         │          └────────────────┘   └────────────────────┘
         │
┌────────▼────────────────────────────────────────────────────┐
│                    Amazon Cognito                           │
│                  (User Authentication)                      │
└──────────────────────────────────────────────────────────────┘
```

## Service Components

### iOS Frontend Services

#### 1. **AuthenticationManager** (`/ilikeyacut-ios/ilikeyacut/Services/AuthenticationManager.swift`)
- **Purpose**: Manages user authentication state and OAuth flows
- **Integration Points**:
  - Calls `/api/auth/login` for OAuth authentication
  - Calls `/api/auth/guest` for guest sessions
  - Stores tokens in iOS Keychain
  - Includes auth token in all API requests
- **Data Flow**:
  1. User initiates login → OAuth flow → Backend validates
  2. Backend returns JWT token → Store in Keychain
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
- **Purpose**: Manages hairstyle templates and AI processing
- **Integration Points**:
  - Fetches templates from `/api/hairstyles`
  - Sends images to `/api/gemini-edit`
  - Caches templates locally (1-hour TTL)
- **Data Flow**:
  1. App launch → Fetch templates → Cache locally
  2. User selects input method → Prepare multimodal request
  3. Send to backend → Display results → Cache for history

#### 4. **CameraManager** (`/ilikeyacut-ios/ilikeyacut/Services/CameraManager.swift`)
- **Purpose**: Handles camera and photo library operations
- **Integration**: 
  - Captures photos for AI processing
  - Saves results to device gallery
  - No direct backend communication

### AWS Backend Services

#### 1. **Gemini Proxy Lambda** (`/backend/lambda/gemini-proxy/main.go`)
- **Endpoint**: `POST /api/gemini-edit`
- **Purpose**: Secure proxy for Google Gemini API
- **Flow**:
  1. Receive multimodal request from iOS app
  2. Retrieve Gemini API key from Secrets Manager
  3. Add face preservation instructions to prompt
  4. Forward to Gemini 2.5 Flash Image API
  5. Return generated images to client
- **Security**: API key never exposed to client

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
  - `POST /api/auth/login` - OAuth authentication
  - `POST /api/auth/guest` - Guest sessions
- **Purpose**: Handle authentication flows
- **Integration**: Cognito User Pools for user management

## Data Flow Scenarios

### Scenario 1: User Takes Selfie and Applies Hairstyle
```
1. iOS: Camera captures photo → Compress to 1024x1024
2. iOS: User selects hairstyle template from library
3. iOS: APIService.processHairstyle() called
4. API Gateway: Rate limit check → Route to Lambda
5. Lambda: Add API key → Call Gemini API
6. Gemini: Process image → Return transformed result
7. Lambda: Log usage → Return to client
8. iOS: Display result → Save to cache
9. iOS: User saves → Store in Photos library
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
```

## Security Considerations

### API Security
- **HTTPS Only**: All communication encrypted
- **API Keys**: Stored in AWS Secrets Manager, never in code
- **JWT Tokens**: Short-lived (1 hour), refresh tokens for extended sessions
- **Rate Limiting**: 60 req/min per IP, 1000 req/day per user
- **CORS**: Configured for mobile app bundle IDs only

### Data Privacy
- **Images**: Processed in memory, not stored on backend
- **User Data**: Minimal collection, GDPR compliant
- **Logs**: PII scrubbed, 7-day retention
- **S3 Assets**: Private bucket with signed URL access only

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
```

## Troubleshooting Guide

### Common Issues

#### 1. "Network Error" on iOS
- Check: Internet connection
- Check: Backend API status
- Check: Valid auth token
- Solution: Pull to refresh, re-login if needed

#### 2. "Rate Limit Exceeded"
- Cause: Too many requests
- Solution: Wait 60 seconds, implement request batching

#### 3. "Image Processing Failed"
- Check: Image size (<20MB)
- Check: Valid image format (JPEG/PNG)
- Check: Gemini API status
- Solution: Compress image, retry with smaller size

#### 4. "Templates Not Loading"
- Check: DynamoDB table exists
- Check: S3 bucket accessible
- Check: Lambda has proper IAM permissions
- Solution: Run seed script, check AWS console

## Testing Strategy

### iOS Testing
```swift
// Unit Tests
- AuthenticationManager: Mock OAuth flows
- APIService: Mock network responses
- HairstyleService: Test caching logic

// UI Tests
- Camera flow: Capture → Preview → Save
- Template selection: Browse → Select → Apply
- Results: Display → Zoom → Share
```

### Backend Testing
```go
// Lambda Tests
- Input validation
- Error handling
- Secrets Manager integration
- DynamoDB queries
- S3 signed URL generation
```

### Integration Testing
```bash
# End-to-end test script
1. Authenticate user
2. Fetch templates
3. Process test image
4. Verify result
5. Submit feedback
```

## Future Enhancements

### Planned Features
1. **Batch Processing**: Multiple variations in single request
2. **WebSocket Support**: Real-time progress updates
3. **Offline Mode**: Queue requests when offline
4. **Analytics**: Usage tracking, popular styles
5. **Social Features**: Share transformations, user galleries

### Scalability Considerations
- **Database**: Consider migrating to Aurora Serverless for high traffic
- **Caching**: Add ElastiCache for session management
- **CDN**: Expand CloudFront distribution for global coverage
- **Queue**: Add SQS for async processing at scale

## Support & Maintenance

### Monitoring Checklist
- [ ] API Gateway metrics (daily)
- [ ] Lambda error rates (hourly during peak)
- [ ] DynamoDB throttling (weekly)
- [ ] S3 storage costs (monthly)
- [ ] Secrets rotation (quarterly)

### Update Process
1. Backend: Deploy with SAM (zero downtime)
2. iOS: Submit to App Store (1-2 day review)
3. Templates: Update via DynamoDB console (instant)
4. Assets: Upload to S3, update DynamoDB references

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