# ilikeyacut App: Design Document (Native Mobile)
## Executive Summary
ilikeyacut is a native mobile application that lets users take selfies and virtually try on haircuts using AI image editing. Built with SwiftUI for iOS UI and Jetpack Compose for Android UI, with SceneKit for iOS 3D elements and Filament for Android 3D rendering, it provides native performance on both iOS and Android devices. It uses Google's Gemini 2.5 Flash Image (Nano-Banana) for realistic edits that keep the user's face unchanged, leveraging platform-specific concurrency: DispatchQueue for iOS and Kotlin Coroutines for Android, ensuring smooth UI during AI processing.

The architecture uses responsive rendering frameworks (SwiftUI for iOS, Jetpack Compose for Android) for client-side interactions, with a serverless AWS backend for authentication, storage via DynamoDB and S3 (for hairstyle template assets), and secure proxying of AI requests to Gemini via Lambda. AI processing is done via Google's cloud API through secure backend proxies. Main threads on both platforms ensure zero-latency touch interactions while background threads/coroutines handle API calls.

Key goals:
- Instant camera capture on both iOS and Android
- Three equal ways to choose hairstyles: text description, source image, or library selection
- Native mobile stacks with SwiftUI/SceneKit for iOS and Jetpack Compose/Filament for Android for performance
- Serverless backend: AWS Lambda, S3, Cognito, DynamoDB
- Fluid and snappy UI response with platform-specific animations (SwiftUI for iOS, Compose animations for Android). Clean, sleek, and modern dark mode design. Geist font.
- Secure AI processing through Lambda proxy to protect API keys
- Dynamic hairstyle template library fetched from DynamoDB for easy maintenance without app redeploys
- Scalable storage of hairstyle template assets (e.g., reference images) in S3 for dynamic, visual library enhancements

## Monetization & Credit System

The app uses a **credit-based monetization model** where all features are accessible to all users, with differences only in credit allocations. This ensures a fair and transparent pricing model while maintaining profitability at small scale.

### Credit Economics
- **1 credit = 1 image generation** via Gemini API
- **Single-image generation**: 1 credit
- **Multi-angle generation**: 4 credits (4 separate API calls)

### User Tiers & Allocations
| User Type | Credits | Reset Period | Purpose |
|-----------|---------|--------------|----------|
| Guest | 1 lifetime | Never | Trial experience |
| Free (Signed-in) | 4 lifetime | Never | Test multi-angle feature |
| Premium Subscriber | 168/month | Monthly | ~1-2 generations/day |
| Bundle Purchaser | 8 or 48 | Never | On-demand usage |

### Pricing Structure
- **Monthly Subscription**: $9.99 (168 credits)
- **Small Bundle**: $0.99 (8 credits)
- **Large Bundle**: $4.99 (48 credits)

### Platform Fees & Profitability
- iOS: 30% starting, 15% after Small Business Program qualification
- Android: 15% from day one
- Break-even at 10+ users with average usage
- 50-60% margins on credit bundles

For detailed financial projections and implementation details, see:
- [RATE_LIMITING.md](./RATE_LIMITING.md) - Technical credit system implementation
- [MONEYMONEYMONEY.md](./MONEYMONEYMONEY.md) - Complete monetization strategy

## Functional Requirements
1. **User Onboarding and Authentication**:
    - Sign up/login with Google or X using platform-specific web authentication (ASWebAuthenticationSession for iOS, Chrome Custom Tabs or WebView for Android)
    - Guest mode for limited but quick use
    - Dev access backdoor only visible in development mode
2. **Camera and Photo Capture**:
    - App uses platform-specific storage for images that will be used for try-on image generation (Photos framework for iOS, MediaStore for Android)
    - Live selfie preview via native camera APIs (AVFoundation for iOS, CameraX for Android)
      - After capture, allow a preview modal with option to keep or retake; if keep selected, the image will be added to the device's photo library
    - Upload from photo library using platform-specific pickers (Photos framework for iOS, MediaStore or Document Picker for Android)
3. **Haircut Try-On**:
    - **Credit Requirements**:
      - Single-image generation: 1 credit (available to all users)
      - Multi-angle generation: 4 credits (requires sufficient balance)
      - Pre-flight validation ensures sufficient credits before starting
      - Multi-angle generations complete even if limit reached mid-process
    - Three main input methods leveraging Gemini 2.5 Flash Image's multimodal capabilities:
      - **Text description**: Direct prompt with automatic face preservation (e.g., "Transform to a short bob with red highlights while preserving facial identity")
      - **Source image**: Upload reference photo - Gemini supports character consistency across celebrity photos, anime characters, or any hairstyle reference
      - **Library selection**: 50+ pre-optimized template prompts stored in DynamoDB with S3-hosted reference images, fetched via API with signed URLs for secure access
    - **Technical Implementation**:
      - Frontend queries `/hairstyles` endpoint on app load to fetch latest templates
      - Templates cached locally with 1-hour TTL for offline support and fast UI response
      - Each template includes: ID, name, optimized prompt, optional S3 asset URL for visual preview
      - Gemini accepts up to 3 images as input, enabling hybrid combinations:
        ```swift
        // iOS Example: Combine user photo + celebrity reference + text refinement
        let contents = [
          userSelfieImage, // User's base photo
          celebrityHairImage, // Reference hairstyle
          "Apply this hairstyle but make it blonde with red highlights, shorter in the back"
        ]
        ```
        ```kotlin
        // Android Example: Combine user photo + celebrity reference + text refinement
        val contents = listOf(
          userSelfieImage, // User's base photo
          celebrityHairImage, // Reference hairstyle
          "Apply this hairstyle but make it blonde with red highlights, shorter in the back"
        )
        ```
    - **AI Processing Pipeline**:
      - Request sent to `/gemini-edit` Lambda endpoint with multipart data
      - Lambda adds API key from Secrets Manager and forwards to Gemini API
      - Gemini's built-in face preservation maintains identity without explicit masking
      - Response includes generated image with SynthID watermark
      - Typical latency: 1-3 seconds with progress indicator
    - **UI Controls & Interactions**:
      - Swipe gestures to browse generated variations using platform-specific gesture recognizers (SwiftUI DragGesture for iOS, Compose DragGesture for Android)
      - Pinch-to-zoom for detail inspection using MagnificationGesture (iOS) or ScaleGestureDetector (Android)
      - Real-time preview updates as variations generate
    - **Generation Options**:
      - **Single Image Mode**: One optimized result (default)
      - **Multi-Angle Mode**: Request specific views in prompt:
        ```swift
        // iOS Example
        "Generate four views: front facing, left profile, right profile, and back view"
        ```
    - **Iterative Refinement**:
      - Gemini supports conversational editing through chained prompts
      - Previous generation result becomes input for next refinement
      - Maintains context for progressive adjustments
      - Example flow: "Make it shorter" → "Add highlights" → "More volume on top"
    - **Save & Share Features**:
      - One-tap save to device gallery using platform-specific APIs (Photos framework for iOS, MediaStore for Android)
      - Share via native share sheets (UIActivityViewController for iOS, Intent for Android)
      - History stored locally with image+prompt cache keys
      - All requests proxied through backend for security (no client-side API keys)
4. **Customization and Editing**:
    - Iterative refinement through conversational prompts
    - Save or share edited photos
    - History of recent edits using platform-specific local storage (UserDefaults or Core Data for iOS, SharedPreferences or Room for Android)
5. **Performance and Offline Support**:
    - Cloud-based AI processing via Gemini API
    - Cache results for instant re-display
    - Queue requests when offline using platform-specific queues (DispatchQueue for iOS, WorkManager for Android), sync when connected
6. **Analytics and Feedback**:
    - Anonymous usage tracking
    - Feedback form for improvements
7. **Profile & Credit Management**:
    - **Credit Balance Display**: Real-time credit count with visual indicator
    - **Subscription Status**: Badge showing Free/Premium tier
    - **Usage History**: Detailed view of past generations with credit costs
    - **Purchase Interface**: In-app purchase overlay for subscriptions/bundles
    - **Monthly Limit Alerts**: Visual notification when approaching/reaching limits
    - **Upgrade Prompts**: Contextual CTAs when credits insufficient

## Look and Feel
The app adopts a dark mode theme throughout, featuring a minimalistic design with subtle character to engage users without overwhelming them. Inspired by sleek designs from xAI, Tesla, and Apple. The overall aesthetic is clean, modern, and classy, using mostly white text and accents on a black background for high contrast and readability.
- **Auth Entry Screen**: A fun, interactive 3D animation greets users on the onboarding screen for sign-in or guest mode. We leverage SceneKit for iOS and Filament for Android for 3D rendering.
  The shears can rotate based on touch gestures, with interaction similar to a trackball or spinning a globe, using platform-specific gesture recognizers. Upon selecting to proceed, they animate a cutting motion and fly off screen with physics-based animation using SCNAction (iOS) or Filament's animation APIs (Android).
- **General UI Elements**: Minimalist layouts with ample negative space, rounded corners, and subtle shadows for depth. Transitions between screens use platform-specific transitions for smooth fades or slides. Interactive elements like buttons and sliders have micro-animations (e.g., scale on tap) using SwiftUI .animation modifiers (iOS) or Compose Animations (Android) to add character while maintaining fast response times.
- **Profile & Credits UI**:
  - **Credit Balance Widget**: Animated circular progress indicator showing remaining credits
    - Color-coded: Green (>50%), Yellow (20-50%), Red (<20%)
    - Tappable for detailed usage breakdown
  - **Subscription Badge**: Premium users get gold badge with crown icon
    - Free users see subtle "Upgrade" CTA
  - **Purchase Button**: Shiny, animated gradient button in top-right of profile
    - Pulses subtly when credits low
  - **Usage History View**:
    - Timeline layout with thumbnail previews
    - Shows date, prompt summary, credit cost, and remaining balance
    - Swipe-to-delete for history management
  - **Purchase Overlay**:
    - Full-screen modal with blur background
    - Clear pricing tiers with benefit highlights
    - Native payment sheet integration (StoreKit 2 for iOS, Google Play Billing for Android)
    - Success animation on purchase completion



## Tech Stack
### Native Mobile
- **Frameworks**: SwiftUI for iOS UI, Jetpack Compose for Android UI; SceneKit for iOS 3D, Filament for Android 3D
- **Languages**: Swift for iOS, Kotlin for Android
- **UI Components**: SwiftUI elements (View, Image, List, ScrollView) for iOS; Compose elements (Composable, Image, LazyColumn, Scrollable) for Android
- **Styling**: SwiftUI modifiers (.background, .foregroundColor, etc.) for iOS; Compose modifiers (background, foreground, etc.) for Android
- **State Management**: @State, @ObservedObject, Combine for iOS; State, ViewModel, Flow for Android
- **Camera**: AVFoundation for iOS; CameraX for Android
- **UI Animations**: SwiftUI .animation or SceneKit SCNAction for iOS; Compose Animations or Filament animations for Android
- **Networking**: URLSession with async/await for iOS; OkHttp or Ktor with coroutines for Android, for backend API calls (e.g., to Lambda endpoints for Gemini proxy and template fetches)
- **Local Storage**: UserDefaults, FileManager, or Core Data for iOS; SharedPreferences, Files, or Room for Android, for caching and offline queue
- **Performance**: Main thread for UI, DispatchQueue for iOS background tasks, Coroutines/WorkManager for Android
### AI Integration
#### Gemini 2.5 Flash Image (Nano-Banana) - Technical Implementation
Gemini 2.5 Flash Image is Google's latest multimodal AI model specifically optimized for image generation and manipulation with native face preservation capabilities.
**Model Specifications**:
- **Model Name**: `gemini-2.5-flash-image-preview`
- **Pricing**: $0.039 per image (1290 output tokens)
- **Token Limits**: 32,768 input / 32,768 output tokens
- **Knowledge Cutoff**: June 2025
- **Response Time**: 1-3 seconds typical latency
- **Watermark**: All generated images include SynthID watermark
**API Interface**:
```swift
// iOS Swift usage (assuming GenerativeAI Swift SDK or URLSession proxy)
let model = GenerativeModel(name: "gemini-2.5-flash-image-preview", apiKey: apiKey)
// Multimodal request format
let result = try await model.generateContent([
  "Transform the hairstyle to a short bob while preserving facial features",
  GenerationContent.Part.data(mimetype: "image/jpeg", data: imageData)
])
// Extract generated image from response
let generatedImageData = result.candidates.first?.content.parts.first(where: { $0.isData })?.data
```
```kotlin
// Android Kotlin usage (assuming GenerativeAI Kotlin SDK or Retrofit proxy)
val model = GenerativeModel("gemini-2.5-flash-image-preview", apiKey)
// Multimodal request format
val result = model.generateContent(
  "Transform the hairstyle to a short bob while preserving facial features",
  GenerationContent.Part.data("image/jpeg", imageData)
)
// Extract generated image from response
val generatedImageData = result.candidates.firstOrNull()?.content?.parts?.firstOrNull { it.isData }?.data
```
**Core Capabilities**:
- **Direct Image Editing**: No preprocessing, segmentation, or masking required
- **Automatic Face Preservation**: Built-in identity retention without explicit masking
- **Conversational Generation**: Supports iterative refinement through natural language
- **Multiple Input Modes**: Text-to-image, image+text-to-image, and multi-image blending
- **Character Consistency**: Maintains subject appearance across multiple generations
- **World Knowledge**: Leverages Gemini's semantic understanding for realistic results
**Prompt Engineering Best Practices**:
- **Describe scenes narratively**: Use descriptive paragraphs over keyword lists
- **Be explicit about preservation**: "while preserving the person's face, facial features, and identity completely unchanged"
- **Use photography terms**: Specify lighting, camera angles, and lens effects for photorealistic results
- **Optimal languages**: EN, es-MX, ja-JP, zh-CN, hi-IN for best performance
- **Input limitations**: Works best with up to 3 images as input
**Three Input Methods Implementation**:
1. **Text-Only Prompts**:
```
// Direct text description with preservation instructions
let prompt = "Transform the hairstyle to a classic bob cut with auburn highlights, " +
             "while preserving the person's face and identity completely unchanged. " +
             "Photorealistic style with soft studio lighting."
```
2. **Reference Image Mode**:
```swift
// iOS Combine user photo with reference hairstyle image
let contents: [GenerationContent.Part] = [
  .data(mimetype: "image/jpeg", data: userSelfieData),
  .data(mimetype: "image/jpeg", data: referenceHairData),
  .text("Apply this hairstyle to the person, maintaining their facial features")
]
```
```kotlin
// Android Combine user photo with reference hairstyle image
val contents: List<GenerationContent.Part> = listOf(
  GenerationContent.Part.data("image/jpeg", userSelfieData),
  GenerationContent.Part.data("image/jpeg", referenceHairData),
  GenerationContent.Part.text("Apply this hairstyle to the person, maintaining their facial features")
)
```
3. **Template Library Integration**:
- Pre-optimized prompts stored in DynamoDB with metadata
- Reference images stored in S3 with signed URL access
- Cached locally for fast UI response
- Dynamic updates without app redeployment
**Performance Optimization**:
- **Caching Strategy**: Use SHA-256 hash of (image+prompt) as cache key
- **Request Batching**: Support for generating multiple variations in single request
**Backend Proxy Architecture**:
```go
// Go Lambda handler for secure Gemini forwarding
func handleGeminiEdit(request EditRequest) (EditResponse, error) {
    // Add API key from environment/Secrets Manager
    // Forward to Gemini API with rate limiting
    // Extract and return generated images
    // Log usage for analytics
}
```
**Advanced Features**:
- **Multi-angle Generation**: Generate front, side profiles, and back views
- **Variation Control**: Specify number of variations via options parameter
- **Style Transfer**: Combine multiple reference images for hybrid styles
- **Iterative Refinement**: Chain prompts for progressive edits
- **Batch Processing**: Queue multiple requests for efficient processing
### Backend (Serverless AWS, all GO lang)
We can save most user meta data to local storage. We mainly need a backend for our saved templates of hairstyles that will be updated and maintained, plus secure proxying of Gemini requests.
- **Compute**: AWS Lambda (for Gemini proxy and API endpoints)
- **API**: API Gateway for REST endpoints (e.g., /gemini-edit, /hairstyles)
- **Auth**: Cognito User Pools (optional for API protection)
- **Storage**: DynamoDB for user metadata and template structured data; S3 for hairstyle template assets (e.g., images, thumbnails)
  - S3 bucket configured for private access; Go Lambda handlers generate pre-signed URLs for secure frontend downloads
  - Integrate with DynamoDB to store asset keys/paths (e.g., DynamoDB item references S3 object key)
- **Deployment**: AWS SAM for infrastructure as code
- **Language**: Go lang for all Lambda handlers due to fast cold starts, efficient I/O for image handling, and low memory footprint
### Development Tools
- **Build Tools**: Xcode for iOS, Android Studio for Android
- **Development**: Xcode Simulator/devices for iOS; Android Emulator/devices for Android testing
- **Version Control**: GitHub
- **CI/CD**: GitHub Actions, Xcode Cloud for iOS, or Gradle for Android builds
- **Testing**: XCTest for iOS unit tests, JUnit/Espresso for Android; platform-specific debuggers
- **Analytics**: Platform-agnostic analytics service
- **IDEs**: Xcode for iOS, Android Studio for Android
- **Backend Testing**: SAM CLI for local Lambda testing

## Architecture Decisions
### Why Native Mobile with Platform-Specific UI Frameworks?
- **Native Performance**: Direct access to hardware for optimal speed on both iOS and Android
- **App Store/Google Play Integration**: Seamless deployment and updates via respective stores
- **Familiar Development**: SwiftUI for declarative UI on iOS, Jetpack Compose for Android; SceneKit for iOS 3D, Filament for Android
- **Optimized for Mobile**: Built-in support for platform features like camera and gestures
- **Hot Reload**: SwiftUI Previews for iOS, Compose Previews for Android for fast iteration
- **Separate Codebases**: Allows tailored optimizations per platform while sharing backend logic
### Why Gemini 2.5 Flash Image?
- **Simplicity**: Single API call for complex hair editing
- **Quality**: State-of-the-art image generation with face preservation
- **Speed**: Optimized for low latency (sub-2s processing)
- **Flexibility**: Supports text, image, and hybrid inputs
- **No local ML needed**: Reduces app size and complexity
### Why Backend Proxy for Gemini?
- **Security**: To secure API keys and prevent client-side exposure, all Gemini requests are proxied through a Go Lambda function
- **Control**: Enables features like logging, rate-limiting, and future integrations (e.g., cost tracking, usage analytics)
- **Minimal Overhead**: Adds minimal latency (<200ms) while providing critical security and control benefits
### Why DynamoDB for Hairstyle Templates?
- **Dynamic Maintenance**: Allows adding new styles without app updates
- **Scalability**: Easily scales beyond 50+ templates as the library grows
- **Admin Updates**: Easy backend updates without requiring frontend deployments
- **Performance**: Frontend fetches via API with local caching ensure fast UI responses and offline support
### Why S3 for Hairstyle Template Assets?
- **Binary Asset Storage**: While DynamoDB handles lightweight template metadata (e.g., prompts, IDs), S3 is ideal for storing binary assets like reference images or thumbnails
- **Visual Enhancements**: Allows visual previews in the library without bloating DynamoDB items, supports easy uploads via admin tools
- **Cost-Effective**: Low storage costs (~$0.023/GB/month) with pay-per-use model
- **Global Distribution**: Enables CDN integration via CloudFront for low-latency asset delivery worldwide
- **Future-Proof**: Supports upcoming features like user-uploaded references, high-resolution previews, or video tutorials
- **Security**: Private bucket with IAM-restricted access; Lambda generates time-limited signed URLs for secure client downloads
### API Integration Pattern
```swift
// iOS (Swift) - Background Queue
func processHairstyle(userImage: Data, options: EditOptions) async throws -> [Data] {
  // Construct multimodal content based on input method
  var contents: [GenerationContent.Part] = []
  // Always include base image
  contents.append(.data(mimetype: "image/jpeg", data: userImage))
  // Add reference image if provided
  if let referenceImage = options.referenceImage {
    contents.append(.data(mimetype: "image/jpeg", data: referenceImage))
  }
  // Add prompt with face preservation instructions
  let prompt = "\(options.prompt) while preserving the person's face, " +
               "facial features, and identity completely unchanged. " +
               "Photorealistic result with natural lighting."
  contents.append(.text(prompt))
  // 3. Send to backend proxy
  let request = try JSONEncoder().encode(EditRequest(contents: contents, options: options))
  var urlRequest = URLRequest(url: URL(string: "/api/gemini-edit")!)
  urlRequest.httpMethod = "POST"
  urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
  urlRequest.httpBody = request
  let (data, _) = try await URLSession.shared.data(for: urlRequest)
  // 4. Extract generated images from response
  let result = try JSONDecoder().decode(EditResponse.self, from: data)
  return result.generatedImages
}
```
```kotlin
// Android (Kotlin) - Coroutine
suspend fun processHairstyle(userImage: ByteArray, options: EditOptions): List<ByteArray> {
  // Construct multimodal content based on input method
  val contents = mutableListOf<GenerationContent.Part>()
  // Always include base image
  contents.add(GenerationContent.Part.data("image/jpeg", userImage))
  // Add reference image if provided
  options.referenceImage?.let {
    contents.add(GenerationContent.Part.data("image/jpeg", it))
  }
  // Add prompt with face preservation instructions
  val prompt = "${options.prompt} while preserving the person's face, " +
               "facial features, and identity completely unchanged. " +
               "Photorealistic result with natural lighting."
  contents.add(GenerationContent.Part.text(prompt))
  // 3. Send to backend proxy
  val request = Json.encodeToString(EditRequest(contents, options))
  val httpRequest = Request.Builder()
    .url("/api/gemini-edit")
    .post(request.toRequestBody("application/json".toMediaType()))
    .build()
  val response = withContext(Dispatchers.IO) { client.newCall(httpRequest).execute() }
  // 4. Extract generated images from response
  val result = Json.decodeFromString<EditResponse>(response.body.string())
  return result.generatedImages
}
// Backend (Go Lambda) - Secure Proxy
func handleGeminiEdit(ctx context.Context, request events.APIGatewayProxyRequest) (events.APIGatewayProxyResponse, error) {
    // Parse request
    var editRequest EditRequest
    json.Unmarshal([]byte(request.Body), &editRequest)
    // Get API key from Secrets Manager
    apiKey := getSecretValue("gemini-api-key")
    // Initialize Gemini client
    client, _ := genai.NewClient(ctx, option.WithAPIKey(apiKey))
    model := client.GenerativeModel("gemini-2.5-flash-image-preview")
    // Generate content
    resp, _ := model.GenerateContent(ctx, editRequest.Contents...)
    // Extract images from response parts
    var generatedImages []string
    for _, candidate := range resp.Candidates {
        for _, part := range candidate.Content.Parts {
            if part.InlineData != nil {
                generatedImages = append(generatedImages,
                    base64.StdEncoding.EncodeToString(part.InlineData.Data))
            }
        }
    }
    // Return response with generated images
    return events.APIGatewayProxyResponse{
        StatusCode: 200,
        Body: json.Marshal(map[string]interface{}{
            "generatedImages": generatedImages,
            "model": "gemini-2.5-flash-image-preview",
        }),
    }, nil
}
```

## API Endpoints (AWS API Gateway)
The backend exposes a minimal REST API for frontend integration. All endpoints use HTTPS and optional Cognito auth.
### **POST /api/gemini-edit**
Proxies requests to Gemini 2.5 Flash Image API with security, rate limiting, and credit validation.

**Credit Validation**:
- Pre-flight check ensures sufficient credits (1 for single, 4 for multi-angle)
- Deducts credits atomically before processing
- Returns clear error if insufficient credits
**Request Format**:
```json
{
  "contents": [
    {
      "inlineData": {
        "mimeType": "image/jpeg",
        "data": "base64_encoded_image"
      }
    },
    {
      "inlineData": {
        "mimeType": "image/jpeg",
        "data": "base64_reference_image" // Optional
      }
    },
    "Text prompt with preservation instructions"
  ],
  "options": {
    "model": "gemini-2.5-flash-image-preview",
    "variations": 1, // 1-4 variations
    "temperature": 0.8, // Optional: 0.0-1.0
    "maxOutputTokens": 32768
  }
}
```
**Response Format**:
```json
{
  "generatedImages": [
    "base64_encoded_result_1",
    "base64_encoded_result_2" // If variations > 1
  ],
  "model": "gemini-2.5-flash-image-preview",
  "usage": {
    "inputTokens": 2048,
    "outputTokens": 1290, // Per image
    "cost": 0.039 // Per image in USD
  },
  "processingTime": 1850 // Milliseconds
}
```
**Error Responses**:
- `400`: Invalid request format or unsupported image type
- `402`: Insufficient credits (includes upgrade options)
- `413`: Image too large (max 20MB after base64 encoding)
- `429`: Rate limit exceeded (implement exponential backoff)
- `500`: Gemini API error or Lambda timeout
- `503`: Service temporarily unavailable

**402 Error Format**:
```json
{
  "error": {
    "code": "insufficient_credits",
    "message": "You need 4 credits for multi-angle generation. You have 2 credits."
  },
  "credits": {
    "required": 4,
    "available": 2
  },
  "upgrade_options": {
    "subscription": { "credits": 168, "price": "$9.99/month" },
    "bundles": [
      { "credits": 8, "price": "$0.99" },
      { "credits": 48, "price": "$4.99" }
    ]
  }
}
```
### **GET /api/hairstyles**
Fetches hairstyle template library with optimized prompts and reference images.
**Query Parameters**:
- `limit`: Number of templates to return (default: 50, max: 100)
- `category`: Filter by style category (e.g., "short", "long", "trendy")
- `offset`: Pagination offset for large libraries
**Response Format**:
```json
{
  "templates": [
    {
      "id": "classic-bob-001",
      "name": "Classic Bob Cut",
      "category": "short",
      "prompt": "Transform to a classic chin-length bob cut with subtle layering...",
      "thumbnailUrl": "https://s3.amazonaws.com/bucket/signed-url...", // 1-hour expiry
      "referenceImageUrl": "https://s3.amazonaws.com/bucket/signed-url...", // Optional
      "popularity": 85, // Usage score for sorting
      "tags": ["professional", "classic", "short"]
    }
  ],
  "totalCount": 75,
  "nextOffset": 50
}
```
### **GET /api/user/credits**
Fetches user's current credit balance and subscription status.

**Response Format**:
```json
{
  "userId": "google_12345",
  "credits": {
    "available": 42,
    "monthlyLimit": 168,
    "resetDate": "2025-02-01T00:00:00Z"
  },
  "subscription": {
    "tier": "premium",
    "status": "active",
    "expiresAt": "2025-02-01T00:00:00Z"
  },
  "bundles": {
    "purchased": 48,
    "remaining": 12
  }
}
```

### **POST /api/purchase**
Handles in-app purchase verification and credit allocation.

**Request Format**:
```json
{
  "receipt": "base64_encoded_receipt",
  "productId": "com.ilikeyacut.subscription.monthly",
  "platform": "ios" // or "android"
}
```

### **GET /api/usage-history**
Retrieves user's generation history with credit costs.

**Response Format**:
```json
{
  "history": [
    {
      "id": "gen_12345",
      "timestamp": "2025-01-15T10:30:00Z",
      "prompt": "Classic bob cut with highlights",
      "creditCost": 4,
      "type": "multi-angle",
      "thumbnailUrl": "signed_s3_url",
      "balanceAfter": 164
    }
  ],
  "totalCreditsUsed": 127,
  "currentPeriod": "2025-01"
}
```

### **POST /api/feedback**
Collects user feedback on generated results for model improvement.
**Request Format**:
```json
{
  "sessionId": "uuid",
  "rating": 1-5,
  "prompt": "Original prompt used",
  "feedback": "Optional text feedback"
}
```
### **Rate Limiting & Caching**:
- **Rate Limits**: 60 requests/minute per IP, 1000 requests/day per user
- **Cache Headers**: `Cache-Control: public, max-age=3600` for template endpoints
- **ETags**: Implemented for template responses to minimize bandwidth
- **CloudFront CDN**: Caches S3 signed URLs at edge locations
### **Security Headers**:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

## Development Approach
### Mobile Development Workflow
1. **Setup**: Create new SwiftUI project in Xcode for iOS; new Jetpack Compose project in Android Studio for Android
2. **Development**: Use Xcode Previews/Simulator for iOS; Compose Previews/Emulator for Android for hot reload testing
3. **Debugging**: Xcode debugger and Instruments for iOS; Android Studio debugger and Profiler for Android, for inspecting elements, network, and performance
4. **Building**: Xcode for iOS bundling; Gradle for Android
5. **Deployment**: App Store Connect for iOS; Google Play Console for Android
6. **Backend Development**: Use Go for Lambda handlers; deploy via AWS SAM. Test API endpoints locally with SAM CLI before integrating with frontends. Manage S3 uploads/downloads in Go handlers using AWS SDK for Go to generate signed URLs
### Component Architecture
- **Pages**: Top-level views (SwiftUI for iOS, Composables for Android)
- **Components**: Reusable views (SwiftUI for iOS, Composables for Android)
- **Hooks**: Custom observables or functions for camera, AI processing, and state management
- **Services**: API integration layer for backend endpoints (Gemini proxy and DynamoDB fetches) and AWS; S3 integration for asset handling in backend API (e.g., include signed URLs in /hairstyles response)

## Key Implementation Files
### iOS Core Files
- **src/services/GeminiAIService.swift**: Handles calls to backend /gemini-edit endpoint with credit validation
- **src/services/HairstyleService.swift**: Fetches templates including S3 signed URLs; use SwiftUI AsyncImage for lazy-loading assets
- **src/services/ImageProcessor.swift**: UIGraphics-based image resizing and optimization
- **src/services/CreditManager.swift**: Manages credit balance, validation, and purchase flows
- **src/services/StoreKitManager.swift**: Handles StoreKit 2 integration for IAP
- **src/hooks/useCamera.swift**: Camera access using AVCaptureSession
- **src/hooks/useGeminiEdit.swift**: AI processing with queue management and credit checks
- **src/hooks/useCredits.swift**: Observable credit state management
- **src/components/CameraView.swift**: Camera preview view
- **src/components/HairstyleGallery.swift**: Template library using List view with S3-hosted thumbnails
- **src/components/CreditBalanceWidget.swift**: Animated credit display component
- **src/components/SubscriptionBadge.swift**: Premium/Free tier indicator
- **src/components/UsageHistoryView.swift**: Generation history with credit costs
- **src/components/PurchaseOverlay.swift**: Full-screen purchase interface
- **src/pages/EditScreen.swift**: Main editing interface with credit validation
- **src/pages/ProfileScreen.swift**: User profile with credit management
### Android Core Files
- **src/services/GeminiAIService.kt**: Handles calls to backend /gemini-edit endpoint with credit validation
- **src/services/HairstyleService.kt**: Fetches templates including S3 signed URLs; use Coil or Glide for lazy-loading assets
- **src/services/ImageProcessor.kt**: Bitmap-based image resizing and optimization
- **src/services/CreditManager.kt**: Manages credit balance, validation, and purchase flows
- **src/services/BillingManager.kt**: Handles Google Play Billing integration
- **src/hooks/UseCamera.kt**: Camera access using CameraX
- **src/hooks/UseGeminiEdit.kt**: AI processing with coroutine management and credit checks
- **src/hooks/UseCredits.kt**: Credit state management with Flow
- **src/components/CameraView.kt**: Camera preview composable
- **src/components/HairstyleGallery.kt**: Template library using LazyColumn with S3-hosted thumbnails
- **src/components/CreditBalanceWidget.kt**: Animated credit display composable
- **src/components/SubscriptionBadge.kt**: Premium/Free tier indicator
- **src/components/UsageHistoryView.kt**: Generation history with credit costs
- **src/components/PurchaseOverlay.kt**: Full-screen purchase interface
- **src/pages/EditScreen.kt**: Main editing interface with credit validation
- **src/pages/ProfileScreen.kt**: User profile with credit management
### Backend Go Files (AWS Lambda)
- **lambda/gemini-proxy/main.go**: Go handler for /gemini-edit: Validates credits, deducts atomically, forwards to Gemini API
- **lambda/hairstyles/main.go**: Go handler for /hairstyles: Queries DynamoDB 'HairstyleTemplates' table, generates S3 signed URLs for assets
- **lambda/credit-validator/main.go**: Validates and deducts user credits with atomic DynamoDB operations
- **lambda/purchase-handler/main.go**: Verifies IAP receipts with Apple/Google, allocates credits
- **lambda/usage-history/main.go**: Fetches user generation history from DynamoDB
- **lambda/user-credits/main.go**: Returns current credit balance and subscription status
- **lambda/s3-uploader/main.go** (optional): Admin endpoint for uploading template assets to S3
- **sam.yaml**: AWS SAM template defining Lambdas, API Gateway routes, DynamoDB tables (Users, Credits, History), S3 bucket, and IAM roles

## Mobile Optimizations
### Performance Patterns
1. **Main Thread**: Use for gesture handling (swipe gallery, pinch-to-zoom)
2. **Background Processing**: Handle API calls and image processing with DispatchQueue (iOS) or Coroutines (Android)
3. **List Virtualization**: Use SwiftUI List (iOS) or Compose LazyColumn (Android) for automatic recycling
4. **Image Optimization**: SwiftUI AsyncImage (iOS) or Coil/Glide (Android) handles lazy loading and caching
5. **Progressive Enhancement**: Start with basic features, add platform-specific enhancements
### iOS-Specific
- Leverage Metal for graphics acceleration
- Use preferredFramesPerSecond = 60 for animations
### Android-Specific
- Leverage Vulkan for graphics acceleration
- Use Choreographer for frame syncing in animations

## 3D Interactive Animations with Platform-Specific Engines
### Overview
The ilikeyacut app uses SceneKit for iOS and Filament for Android for engaging 3D animations, particularly for the auth entry screen's scissor animation. Native mobile architecture enables these engines to run efficiently with hardware acceleration on respective platforms.
### Implementation Strategy
#### 1. **Scene Container Component**
```swift
// iOS src/components/SceneKitView.swift
// Wrap SceneKit SCNView in a SwiftUI UIViewRepresentable
// Handle resize events for responsive rendering
// Manage SCNScene lifecycle
```
```kotlin
// Android src/components/FilamentView.kt
// Wrap Filament View in a Compose AndroidView
// Handle resize events for responsive rendering
// Manage Filament Scene lifecycle
```
#### 2. **Performance Optimizations**
- **Geometry LOD**: Use Level of Detail for complex models
- **Texture Compression**: Use ASTC texture compression
- **Draw Call Batching**: Merge geometries where possible
- **Frustum Culling**: Only render visible objects
- **Shadow Maps**: Use low-resolution shadows
#### 3. **Interactive Elements**
- **Touch Gestures**: Map gesture events to 3D object rotation/scaling
- **Physics**: Use platform physics engines
- **Raycasting**: Efficient object picking for user interaction
- **Animation Mixing**: Blend between animation states smoothly
### Scissor Animation Implementation
```swift
// iOS Key components for the auth screen 3D scissors
src/scenekit/ScissorScene.swift // SceneKit scene setup
src/scenekit/ScissorModel.swift // 3D scissor geometry and materials
src/scenekit/AnimationController.swift // Handle cutting animation sequence
src/hooks/useSceneKit.swift // Observable for SceneKit lifecycle
```
```kotlin
// Android Key components for the auth screen 3D scissors
src/filament/ScissorScene.kt // Filament scene setup
src/filament/ScissorModel.kt // 3D scissor geometry and materials
src/filament/AnimationController.kt // Handle cutting animation sequence
src/hooks/UseFilament.kt // State for Filament lifecycle
```
#### Animation Sequence:
1. **Idle State**: Gentle floating animation with subtle rotation
2. **User Interaction**: Rotate based on touch/drag gestures
3. **Cutting Animation**: Scissor blades close/open with metallic sound
4. **Exit Transition**: Physics-based fly-off with motion blur effect
### Platform-Specific Considerations
#### iOS Optimizations:
- Use preferredFramesPerSecond = 60 for smooth animations
- Leverage Metal's compute shaders for complex effects
- Enable multi-sampling anti-aliasing (MSAA) for better quality
#### Android Optimizations:
- Use Choreographer for 60 FPS animations
- Leverage Vulkan for rendering
- Enable hardware acceleration with anti-aliasing
### Best Practices
1. **Memory Management**:
   - Dispose of nodes, materials, and textures when unmounting
   - Use object pooling for frequently created/destroyed objects
   - Monitor context loss and handle recovery
2. **Loading Strategy**:
   - Load 3D assets progressively with loading indicators
   - Use DRACO compression for geometry
   - Implement asset caching for repeat visits
3. **Testing**:
   - Use Xcode Simulator for iOS real-time testing
   - Use Android Emulator for Android
   - Profile with Xcode Instruments (iOS) or Android Profiler (Android)
   - Test on various device tiers (low, mid, high-end)
### Integration with Mobile Architecture
The 3D integration leverages platform concurrency:
- **Main Thread**: Handles rendering loop and immediate user interactions
- **Background Processing**: Processes complex calculations, asset loading, and physics simulations (DispatchQueue for iOS, Coroutines for Android)
This separation ensures the UI remains responsive even during intensive 3D operations, maintaining our fast response time target while delivering engaging 3D experiences.

## Lessons Learned from Gemini 2.5 Flash Image Integration
1. **Narrative Prompting**: Describe scenes in full sentences rather than keyword lists - Gemini's language understanding excels with descriptive paragraphs
2. **Built-in Face Preservation**: No need for complex masking or segmentation - Gemini automatically maintains facial identity when instructed
3. **Multimodal Flexibility**: Leverage up to 3 images as input for powerful hybrid editing (user photo + reference + style guide)
4. **Optimal Resolution**: 1024x1024 provides the best balance between quality and processing speed (1-3 seconds)
5. **Character Consistency**: Gemini maintains subject appearance across multiple generations without additional training
6. **World Knowledge**: The model understands real-world concepts, enabling semantic edits beyond simple style transfer
7. **SynthID Watermarking**: All generated images include invisible watermarks for responsible AI usage
8. **Cost Efficiency**: At $0.039 per image (1290 output tokens), batch variations for better user experience
9. **Language Optimization**: Best performance with EN, es-MX, ja-JP, zh-CN, hi-IN prompts
10. **Conversational Editing**: Chain prompts for iterative refinement while maintaining context
11. **Security Architecture**: Lambda proxy adds minimal latency (<200ms) while securing API keys
12. **Caching Strategy**: Use SHA-256 hash of (image+prompt) for deterministic result caching
13. **Error Handling**: Implement exponential backoff for 429 rate limits with max 3 retries
14. **Template Library**: Pre-optimized prompts in DynamoDB with S3 reference images enable consistent quality
15. **Progressive Enhancement**: Start with single image generation, add variations based on user engagement
This native mobile architecture provides optimal performance on both iOS and Android while maintaining the same AI-powered hairstyle editing experience, enhanced with engaging 3D interactive elements and scalable asset storage via S3.
