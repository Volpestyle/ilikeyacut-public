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
Optional Cognito authentication for protected endpoints.
Guest mode available for limited functionality.

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
**Description**: Proxy endpoint for Gemini 2.5 Flash Image API to process hairstyle transformations.

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
        "data": "base64_encoded_reference_image"
      }
    },
    {
      "text": "Hairstyle transformation prompt with face preservation instructions"
    }
  ],
  "options": {
    "model": "gemini-2.5-flash-image-preview",
    "variations": 1,
    "temperature": 0.8,
    "maxOutputTokens": 32768
  }
}
```

**Response (200 OK)**:
```json
{
  "generatedImages": [
    "base64_encoded_result_image_1",
    "base64_encoded_result_image_2"
  ],
  "model": "gemini-2.5-flash-image-preview",
  "usage": {
    "inputTokens": 2048,
    "outputTokens": 1290,
    "cost": 0.039
  },
  "processingTime": 1850
}
```

**Error Codes**:
- `400 BAD_REQUEST`: Invalid request format or unsupported image type
- `413 PAYLOAD_TOO_LARGE`: Image exceeds 20MB limit
- `429 RATE_LIMIT_EXCEEDED`: Too many requests
- `500 INTERNAL_ERROR`: Gemini API or Lambda error
- `503 SERVICE_UNAVAILABLE`: Service temporarily unavailable

### 2. GET /api/hairstyles
**Description**: Fetch hairstyle template library with optimized prompts and reference images.

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
      "thumbnailUrl": "https://s3-signed-url-for-thumbnail",
      "referenceImageUrl": "https://s3-signed-url-for-reference",
      "popularity": 85,
      "tags": ["professional", "classic", "short"]
    }
  ],
  "totalCount": 75,
  "nextOffset": 50
}
```

### 3. POST /api/feedback
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

### 4. POST /api/auth/login
**Description**: Authenticate user with OAuth provider.

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
    "id": "user-uuid",
    "email": "user@example.com",
    "name": "User Name"
  }
}
```

### 5. POST /api/auth/guest
**Description**: Create guest session for limited access.

**Response (200 OK)**:
```json
{
  "guestToken": "guest-jwt-token",
  "expiresIn": 86400,
  "limitations": {
    "maxEditsPerDay": 5,
    "featuresDisabled": ["save", "history"]
  }
}
```

## Rate Limiting
- 60 requests/minute per IP
- 1000 requests/day per authenticated user
- 100 requests/day for guest users

## Image Requirements
- **Format**: JPEG or PNG
- **Max Size**: 20MB (before base64 encoding)
- **Recommended Resolution**: 1024x1024 for optimal processing
- **Aspect Ratio**: Square preferred, will be auto-cropped if needed

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
// Using URLSession with async/await
func processHairstyle(image: Data, prompt: String) async throws -> [Data] {
    let url = URL(string: "\(baseURL)/api/gemini-edit")!
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    
    let body = [
        "contents": [
            ["inlineData": ["mimeType": "image/jpeg", "data": image.base64EncodedString()]],
            ["text": prompt]
        ],
        "options": ["model": "gemini-2.5-flash-image-preview", "variations": 1]
    ]
    
    request.httpBody = try JSONSerialization.data(withJSONObject: body)
    let (data, _) = try await URLSession.shared.data(for: request)
    let response = try JSONDecoder().decode(GeminiResponse.self, from: data)
    return response.generatedImages.compactMap { Data(base64Encoded: $0) }
}
```

## Backend Go Lambda Example
```go
func handleGeminiEdit(ctx context.Context, request events.APIGatewayProxyRequest) (events.APIGatewayProxyResponse, error) {
    // Parse request
    var editRequest EditRequest
    json.Unmarshal([]byte(request.Body), &editRequest)
    
    // Get API key from Secrets Manager
    apiKey := getSecretValue("gemini-api-key")
    
    // Forward to Gemini API
    // Process response
    // Return to client
}
```

## Versioning
API version specified in `X-API-Version` header. Current version: 1.0
Breaking changes will increment major version with deprecation notices.