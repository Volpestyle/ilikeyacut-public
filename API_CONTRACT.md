# ilikeyacut API Contract

## Overview
This document defines the API contract between the iOS frontend and AWS serverless backend for the ilikeyacut app.
All endpoints use HTTPS with JSON payloads. The backend is hosted on AWS API Gateway with Lambda functions.

## Base URL
```
Production: https://api.ilikeyacut.app
Development: https://dev-api.ilikeyacut.app
```

## Authentication
- **Guest Mode**: Device-based tracking for 1 lifetime credit
- **OAuth Login**: Google or X authentication for 4 lifetime credits
- **Premium Users**: Subscription or bundle purchasers with extended credits
- **Admin Access**: Development-only unlimited credits (via backend script)

## Common Headers
```
Content-Type: application/json
X-API-Version: 1.0
Authorization: Bearer <token> (optional)
```

## Error Response Format
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": {} // Optional additional context
  }
}
```

## API Endpoints

### 1. POST /api/gemini-edit
**Description**: Proxy endpoint for Gemini 2.5 Flash Image API to process hairstyle transformations with credit validation and deduction.

**Credit Requirements**:
- Single-image generation: 1 credit
- Multi-angle generation (4 images): 4 credits

**Request Body**:
```json
{
  "contents": [
    {
      "inlineData": {
        "mimeType": "image/jpeg",
        "data": "base64_encoded_user_selfie"
      }
    },
    {
      "inlineData": {
        "mimeType": "image/jpeg",
        "data": "base64_encoded_reference_image"  // Optional
      }
    },
    {
      "text": "Hairstyle transformation prompt with face preservation instructions"
    }
  ],
  "options": {
    "model": "gemini-2.5-flash-image-preview",
    "variations": 1,  // 1-4 variations
    "temperature": 0.8,  // 0.0-1.0
    "maxOutputTokens": 32768
  }
}
```

**Response (200 OK)**:
```json
{
  "generatedImages": [
    "base64_encoded_result_image_1",
    "base64_encoded_result_image_2"  // If variations > 1
  ],
  "model": "gemini-2.5-flash-image-preview",
  "usage": {
    "inputTokens": 2048,
    "outputTokens": 1290,  // Per image
    "cost": 0.039  // Per image in USD
  },
  "processingTime": 1850,  // Milliseconds
  "creditsUsed": 1,
  "creditsRemaining": 167
}
```

**Response Headers**:
```
X-Credits-Limit: 168
X-Credits-Remaining: 165
X-Credits-Reset: 1704067200  // Unix timestamp (subscribers only)
```

**Error Codes**:
- `400 BAD_REQUEST`: Invalid request format or unsupported image type
- `402 PAYMENT_REQUIRED`: Insufficient credits (see error format below)
- `413 PAYLOAD_TOO_LARGE`: Image exceeds 20MB limit
- `429 RATE_LIMIT_EXCEEDED`: Too many requests (global rate limit)
- `500 INTERNAL_ERROR`: Gemini API or Lambda error
- `503 SERVICE_UNAVAILABLE`: Service temporarily unavailable

**402 Insufficient Credits Response**:
```json
{
  "error": {
    "code": "insufficient_credits",
    "message": "You need 4 credits for multi-angle generation. You have 2 credits."
  },
  "credits": {
    "required": 4,
    "available": 2,
    "userType": "free"  // guest, free, premium, or admin
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
```

### 2. GET /api/hairstyles
**Description**: Fetch hairstyle template library from DynamoDB with S3-hosted reference images. Templates are cached locally with 1-hour TTL.

**Query Parameters**:
- `limit` (number): Max templates to return (default: 50, max: 100)
- `category` (string): Filter by category (e.g., "short", "long", "trendy")
- `offset` (number): Pagination offset

**Response (200 OK)**:
```json
{
  "templates": [
    {
      "id": "classic-bob-001",
      "name": "Classic Bob Cut",
      "category": "short",
      "prompt": "Transform to a classic chin-length bob cut with subtle layering while preserving facial features completely",
      "thumbnailUrl": "https://s3.amazonaws.com/bucket/signed-url...",  // 1-hour expiry
      "referenceImageUrl": "https://s3.amazonaws.com/bucket/signed-url...",  // Optional, 1-hour expiry
      "popularity": 85,  // Usage score for sorting
      "tags": ["professional", "classic", "short"]
    }
  ],
  "totalCount": 75,
  "nextOffset": 50
}
```

### 3. GET /api/user/credits
**Description**: Fetch user's current credit balance and subscription status.

**Response (200 OK)**:
```json
{
  "userId": "google_12345",
  "credits": {
    "available": 42,
    "monthlyLimit": 168,  // Only for subscribers
    "resetDate": "2025-02-01T00:00:00Z"  // Only for subscribers
  },
  "subscription": {
    "tier": "free",  // guest, free, premium, or admin
    "status": "active",  // Only for premium
    "expiresAt": "2025-02-01T00:00:00Z"  // Only for premium
  },
  "bundles": {
    "purchased": 48,  // Total bundle credits purchased
    "remaining": 12   // Bundle credits available
  }
}
```

### 4. POST /api/purchase
**Description**: Verify in-app purchase and allocate credits.

**Request Body**:
```json
{
  "receipt": "base64_encoded_receipt",
  "productId": "com.ilikeyacut.subscription.monthly" | "com.ilikeyacut.bundle.small" | "com.ilikeyacut.bundle.large",
  "platform": "ios" | "android"
}
```

**Response (200 OK)**:
```json
{
  "success": true,
  "creditsAdded": 168,  // Or 8/48 for bundles
  "newBalance": 180,
  "purchaseType": "subscription" | "bundle",
  "expiresAt": "2025-02-01T00:00:00Z"  // Only for subscriptions
}
```

### 5. GET /api/usage-history
**Description**: Retrieve user's generation history with credit costs.

**Query Parameters**:
- `limit` (number): Max items to return (default: 50)
- `offset` (number): Pagination offset

**Response (200 OK)**:
```json
{
  "history": [
    {
      "id": "gen_12345",
      "timestamp": "2025-01-15T10:30:00Z",
      "prompt": "Classic bob cut with highlights",
      "creditCost": 4,
      "type": "multi-angle" | "single",
      "thumbnailUrl": "https://s3.amazonaws.com/bucket/signed-url...",
      "balanceAfter": 164
    }
  ],
  "totalCreditsUsed": 127,
  "currentPeriod": "2025-01"
}
```

### 6. POST /api/feedback
**Description**: Submit user feedback on generated results.

**Request Body**:
```json
{
  "sessionId": "uuid-v4",
  "rating": 4,
  "prompt": "Original prompt used for generation",
  "feedback": "Optional text feedback from user"
}
```

**Response (200 OK)**:
```json
{
  "success": true,
  "feedbackId": "feedback-uuid"
}
```

### 7. POST /api/auth/login
**Description**: Authenticate user with OAuth provider. Allocates 4 lifetime credits for new users.

**Request Body**:
```json
{
  "provider": "google" | "x",
  "authCode": "oauth_authorization_code"
}
```

**Response (200 OK)**:
```json
{
  "accessToken": "jwt-access-token",
  "refreshToken": "refresh-token",
  "expiresIn": 3600,
  "user": {
    "id": "google_12345" | "x_12345",
    "email": "user@example.com",
    "name": "User Name",
    "tier": "free",  // guest, free, premium, or admin
    "credits": {
      "available": 4,  // Or current balance
      "isNewUser": true  // If first-time login
    }
  }
}
```

### 8. POST /api/auth/guest
**Description**: Create guest session with 1 lifetime credit. Tracked by device ID.

**Request Body**:
```json
{
  "deviceId": "device-identifier-for-vendor",  // iOS: identifierForVendor
  "platform": "ios" | "android"
}
```

**Response (200 OK)**:
```json
{
  "guestToken": "guest-jwt-token",
  "expiresIn": 86400,
  "credits": {
    "available": 1,  // Or 0 if already used
    "lifetime": 1,
    "used": 0
  },
  "limitations": {
    "creditsOnly": true,
    "featuresDisabled": ["save_history", "multi_angle"]
  }
}
```

## Rate Limiting

### Credit-Based Limits
- **Guest Users**: 1 lifetime credit (tracked by device ID)
- **Free Users**: 4 lifetime credits (OAuth sign-in required)
- **Premium Subscribers**: 168 credits/month (resets on billing date)
- **Bundle Purchasers**: Credits added to balance (no expiration)
- **Admin Users**: Unlimited (development only)

### Global API Limits
- 60 requests/second burst rate
- 100,000 requests/day quota
- Enforced via AWS API Gateway Usage Plans

## Image Requirements
- **Format**: JPEG or PNG
- **Max Size**: 20MB (after base64 encoding)
- **Recommended Resolution**: 1024x1024 for optimal processing (1-3 second latency)
- **Aspect Ratio**: Square preferred, will be auto-cropped if needed
- **Multiple Images**: Supports up to 3 images as input (user photo + reference + style guide)

## Caching Strategy
- Template endpoints: `Cache-Control: public, max-age=3600`
- ETags implemented for conditional requests
- S3 signed URLs valid for 1 hour

## Security Headers
All responses include:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

## iOS Swift Integration Example
```swift
// Using URLSession with async/await and credit handling
func processHairstyle(image: Data, referenceImage: Data? = nil, prompt: String, multiAngle: Bool = false) async throws -> [Data] {
    let url = URL(string: "\(baseURL)/api/gemini-edit")!
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
    
    var contents: [[String: Any]] = [
        ["inlineData": ["mimeType": "image/jpeg", "data": image.base64EncodedString()]]
    ]
    
    // Add reference image if provided
    if let refImage = referenceImage {
        contents.append(["inlineData": ["mimeType": "image/jpeg", "data": refImage.base64EncodedString()]])
    }
    
    // Add prompt with face preservation
    let fullPrompt = multiAngle ? 
        "\(prompt). Generate four views: front facing, left profile, right profile, and back view. Preserve facial features completely." :
        "\(prompt). Preserve facial features and identity completely unchanged."
    contents.append(["text": fullPrompt])
    
    let body = [
        "contents": contents,
        "options": [
            "model": "gemini-2.5-flash-image-preview",
            "variations": multiAngle ? 4 : 1
        ]
    ]
    
    request.httpBody = try JSONSerialization.data(withJSONObject: body)
    
    do {
        let (data, response) = try await URLSession.shared.data(for: request)
        
        // Check for insufficient credits
        if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 402 {
            let errorResponse = try JSONDecoder().decode(CreditError.self, from: data)
            throw InsufficientCreditsError(errorResponse)
        }
        
        let geminiResponse = try JSONDecoder().decode(GeminiResponse.self, from: data)
        return geminiResponse.generatedImages.compactMap { Data(base64Encoded: $0) }
    } catch {
        throw error
    }
}
```

## Backend Go Lambda Example
```go
func handleGeminiEdit(ctx context.Context, request events.APIGatewayProxyRequest) (events.APIGatewayProxyResponse, error) {
    // Parse request
    var editRequest EditRequest
    json.Unmarshal([]byte(request.Body), &editRequest)
    
    // Extract user ID from JWT or device ID for guests
    userID := getUserID(request.Headers["Authorization"])
    
    // Check and deduct credits
    creditsNeeded := editRequest.Options.Variations
    if creditsNeeded == 0 {
        creditsNeeded = 1
    }
    
    remaining, err := deductCredits(ctx, userID, creditsNeeded)
    if err != nil {
        if err == ErrInsufficientCredits {
            return events.APIGatewayProxyResponse{
                StatusCode: 402,
                Headers: map[string]string{
                    "Content-Type": "application/json",
                },
                Body: buildInsufficientCreditsResponse(userID, creditsNeeded),
            }, nil
        }
        return events.APIGatewayProxyResponse{StatusCode: 500}, err
    }
    
    // Get API key from Secrets Manager
    apiKey := getSecretValue("gemini-api-key")
    
    // Initialize Gemini client and process
    client, _ := genai.NewClient(ctx, option.WithAPIKey(apiKey))
    model := client.GenerativeModel("gemini-2.5-flash-image-preview")
    
    // Generate content
    resp, _ := model.GenerateContent(ctx, editRequest.Contents...)
    
    // Extract images and build response
    var generatedImages []string
    for _, candidate := range resp.Candidates {
        for _, part := range candidate.Content.Parts {
            if part.InlineData != nil {
                generatedImages = append(generatedImages,
                    base64.StdEncoding.EncodeToString(part.InlineData.Data))
            }
        }
    }
    
    // Log usage for analytics
    logUsage(ctx, userID, creditsNeeded, editRequest.Contents[len(editRequest.Contents)-1].Text)
    
    // Return response with credit info
    return events.APIGatewayProxyResponse{
        StatusCode: 200,
        Headers: map[string]string{
            "Content-Type": "application/json",
            "X-Credits-Remaining": strconv.Itoa(remaining),
        },
        Body: json.Marshal(map[string]interface{}{
            "generatedImages": generatedImages,
            "model": "gemini-2.5-flash-image-preview",
            "creditsUsed": creditsNeeded,
            "creditsRemaining": remaining,
        }),
    }, nil
}
```

## Product IDs for In-App Purchases

### iOS (App Store)
- `com.ilikeyacut.subscription.monthly` - $9.99/month (168 credits)
- `com.ilikeyacut.bundle.small` - $0.99 (8 credits)
- `com.ilikeyacut.bundle.large` - $4.99 (48 credits)

### Android (Google Play)
- `com.ilikeyacut.subscription.monthly` - $9.99/month (168 credits)
- `com.ilikeyacut.bundle.small` - $0.99 (8 credits)
- `com.ilikeyacut.bundle.large` - $4.99 (48 credits)

## Versioning
API version specified in `X-API-Version` header. Current version: 1.0
Breaking changes will increment major version with deprecation notices.

## Admin Tools (Development Only)

### Setting Admin Access
```bash
cd backend/scripts
# Update by email
go run update-user-tier.go -email admin@example.com -tier admin
# Update by user ID
go run update-user-tier.go -user google_12345 -tier admin
```

Admin users have unlimited credits for testing and development purposes.