# iOS Token Lifecycle Implementation Guide

## Overview
This guide documents the current JWT token lifecycle management in the iOS app, with different behaviors for guest vs authenticated users.

## Token Behavior by User Type

### Guest Users (Current Implementation)
- **Storage**: iOS Keychain (persisted) - stored with key `"guest_token"`
- **Token Lifetime**: 15 minutes from creation
- **On App Close**: Token preserved in Keychain
- **On App Launch**: Auto-restore session if token not expired
- **On Token Expiry**: Token cleared, must tap "Continue as Guest" again
- **Rate Limiting**: 5 edits per day per device (tracked by IP + Device ID)

### Authenticated Users (Partial Implementation)
- **Storage**: iOS Keychain (persisted) - stored with key `"access_token"`
- **Lifetime**: Depends on OAuth provider
- **On App Close**: Token preserved
- **On App Launch**: Auto-restore session if token not expired
- **On Token Expiry**: Token cleared, must re-authenticate
- **Refresh Token**: Stored with key `"refresh_token"` (not yet used for auto-refresh)

## Required Headers for All Requests

### Current Implementation (APIService.swift)
```swift
// Headers are set in processHairstyle and other API methods:
if let token = authToken {
    request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

    // Add device ID header for guest users (required by backend for rate limiting)
    if isGuestUser {
        request.setValue(deviceID, forHTTPHeaderField: "X-Device-ID")
    }
}
```

**Note**: X-Device-ID is only required for guest users. Device ID is persisted in UserDefaults.

## Core Implementation

### 1. AuthenticationManager (Current Implementation)

```swift
class AuthenticationManager: NSObject, ObservableObject {
    @Published var isAuthenticated = false
    @Published var currentUser: User?
    @Published var authToken: String?
    private let apiService = APIService.shared

    // Guest sign-in stores token in Keychain
    private func signInAsGuest() {
        Task {
            do {
                let response = try await apiService.createGuestSession()

                await MainActor.run {
                    self.authToken = response.guestToken
                    self.apiService.setAuthToken(response.guestToken, isGuest: true)
                    self.currentUser = User(
                        id: UUID().uuidString,
                        email: nil,
                        name: "Guest",
                        isGuest: true
                    )
                    self.isAuthenticated = true

                    // Store guest token in Keychain (PERSISTED)
                    KeychainHelper.shared.save(response.guestToken, forKey: "guest_token")
                }
            } catch {
                // Handle error
            }
        }
    }

    // Check existing auth on app launch
    func checkExistingAuth() {
        if let token = KeychainHelper.shared.load(forKey: "access_token") {
            // Check if token is expired using JWTDecoder
            if JWTDecoder.isTokenExpired(token) {
                KeychainHelper.shared.delete(forKey: "access_token")
                isAuthenticated = false
                return
            }
            // Set up authenticated session
            authToken = token
            apiService.setAuthToken(token, isGuest: false)
            isAuthenticated = true

        } else if let guestToken = KeychainHelper.shared.load(forKey: "guest_token") {
            // Check if guest token is expired
            if JWTDecoder.isTokenExpired(guestToken) {
                KeychainHelper.shared.delete(forKey: "guest_token")
                isAuthenticated = false
                return
            }
            // Restore guest session
            authToken = guestToken
            apiService.setAuthToken(guestToken, isGuest: true)
            let guestId = JWTDecoder.getSubject(guestToken) ?? UUID().uuidString
            currentUser = User(id: guestId, email: nil, name: "Guest", isGuest: true)
            isAuthenticated = true
        }
    }
}
```

### 2. JWT Token Decoder (JWTDecoder.swift)

```swift
struct JWTDecoder {
    /// Decodes a JWT token and returns its claims
    static func decode(_ token: String) -> [String: Any]? {
        let segments = token.split(separator: ".")
        guard segments.count == 3 else { return nil }

        let payloadSegment = String(segments[1])
        let paddedPayload = padBase64String(payloadSegment)

        guard let payloadData = Data(base64Encoded: paddedPayload) else { return nil }
        return try? JSONSerialization.jsonObject(with: payloadData) as? [String: Any]
    }

    /// Checks if a JWT token is expired
    static func isTokenExpired(_ token: String) -> Bool {
        guard let claims = decode(token),
              let exp = claims["exp"] as? TimeInterval else {
            return true
        }

        let expirationDate = Date(timeIntervalSince1970: exp)
        let now = Date()

        // Add 5-minute buffer for clock skew
        let bufferTime: TimeInterval = 5 * 60
        let adjustedExpirationDate = expirationDate.addingTimeInterval(-bufferTime)

        return now > adjustedExpirationDate
    }
}
```

### 3. API Service (APIService.swift)

```swift
class APIService {
    static let shared = APIService()

    private var authToken: String?
    private var isGuestUser: Bool = false
    private let deviceID: String

    private init() {
        // Generate or retrieve persistent device ID
        if let savedDeviceID = UserDefaults.standard.string(forKey: "deviceID") {
            self.deviceID = savedDeviceID
        } else {
            let newDeviceID = UUID().uuidString
            UserDefaults.standard.set(newDeviceID, forKey: "deviceID")
            self.deviceID = newDeviceID
        }
    }

    func setAuthToken(_ token: String?, isGuest: Bool = false) {
        self.authToken = token
        self.isGuestUser = isGuest
    }

    func makeAuthenticatedRequest(
        endpoint: String,
        method: String = "POST",
        body: Data? = nil,
        completion: @escaping (Result<Data, Error>) -> Void
    ) {
        // Check for valid token
        guard let token = AuthManager.shared.getCurrentToken() else {
            // Token expired or missing - notify UI to show auth screen
            NotificationCenter.default.post(
                name: .authenticationRequired,
                object: nil
            )
            completion(.failure(APIError.authenticationRequired))
            return
        }

        // Build request with required headers
        guard let url = URL(string: "\(GuestAuthService.baseURL)\(endpoint)") else {
            completion(.failure(APIError.invalidURL))
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.httpBody = body

        // Set required headers
        let headers = APIHeaders.getHeaders(
            token: token,
            deviceID: AuthManager.shared.deviceID
        )
        headers.forEach { request.setValue($0.value, forHTTPHeaderField: $0.key) }

        // Make request
        URLSession.shared.dataTask(with: request) { data, response, error in
            if let httpResponse = response as? HTTPURLResponse {
                switch httpResponse.statusCode {
                case 401:
                    // Token invalid/expired
                    AuthManager.shared.clearSession()
                    NotificationCenter.default.post(
                        name: .authenticationRequired,
                        object: nil
                    )
                    completion(.failure(APIError.unauthorized))

                case 400:
                    // Might be missing X-Device-ID
                    if let data = data,
                       let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data),
                       errorResponse.error.message.contains("X-Device-ID") {
                        completion(.failure(APIError.missingDeviceID))
                    } else {
                        completion(.failure(APIError.badRequest))
                    }

                case 429:
                    // Rate limited
                    self.handleRateLimit(response: httpResponse, data: data)
                    completion(.failure(APIError.rateLimited))

                case 200...299:
                    // Success
                    if let data = data {
                        completion(.success(data))
                    } else {
                        completion(.failure(APIError.noData))
                    }

                default:
                    completion(.failure(APIError.serverError(statusCode: httpResponse.statusCode)))
                }
            } else if let error = error {
                completion(.failure(error))
            } else {
                completion(.failure(APIError.unknown))
            }
        }.resume()
    }

    private func handleRateLimit(response: HTTPURLResponse, data: Data?) {
        // Extract rate limit info
        let remaining = response.allHeaderFields["X-RateLimit-Remaining"] as? String
        let resetTime = response.allHeaderFields["X-RateLimit-Reset"] as? String
        let retryAfter = response.allHeaderFields["Retry-After"] as? String

        // Notify UI about rate limit
        NotificationCenter.default.post(
            name: .rateLimitExceeded,
            object: nil,
            userInfo: [
                "remaining": remaining ?? "0",
                "resetTime": resetTime ?? "",
                "retryAfter": retryAfter ?? "3600"
            ]
        )
    }
}
```

### 4. App Lifecycle Integration

```swift
class AppDelegate: UIResponder, UIApplicationDelegate {

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {

        // Check for existing session
        if AuthManager.shared.isTokenValid() {
            // Token still valid (app was in background, not closed)
            navigateToMainApp()
        } else {
            // No valid token - show auth screen
            navigateToAuthScreen()
        }

        return true
    }

    func applicationWillTerminate(_ application: UIApplication) {
        // Guest tokens are automatically cleared (memory only)
        // No action needed
    }
}

// SceneDelegate for iOS 13+
class SceneDelegate: UIResponder, UIWindowSceneDelegate {

    func sceneDidBecomeActive(_ scene: UIScene) {
        // Check token validity when app becomes active
        if !AuthManager.shared.isTokenValid() {
            navigateToAuthScreen()
        }
    }
}
```

### 5. View Controller Integration

```swift
class MainViewController: UIViewController {

    override func viewDidLoad() {
        super.viewDidLoad()

        // Listen for auth events
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleAuthRequired),
            name: .authenticationRequired,
            object: nil
        )

        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleRateLimit),
            name: .rateLimitExceeded,
            object: nil
        )
    }

    @objc private func handleAuthRequired() {
        DispatchQueue.main.async {
            // Show auth screen
            let authVC = AuthViewController()
            authVC.modalPresentationStyle = .fullScreen
            self.present(authVC, animated: true)
        }
    }

    @objc private func handleRateLimit(_ notification: Notification) {
        guard let userInfo = notification.userInfo,
              let retryAfter = userInfo["retryAfter"] as? String,
              let seconds = Int(retryAfter) else { return }

        DispatchQueue.main.async {
            let hours = seconds / 3600
            let minutes = (seconds % 3600) / 60

            var message = "You've reached your daily limit of 5 hairstyle edits."
            if hours > 0 {
                message += " Try again in \(hours) hour\(hours > 1 ? "s" : "")."
            } else if minutes > 0 {
                message += " Try again in \(minutes) minute\(minutes > 1 ? "s" : "")."
            }

            let alert = UIAlertController(
                title: "Daily Limit Reached",
                message: message,
                preferredStyle: .alert
            )
            alert.addAction(UIAlertAction(title: "OK", style: .default))
            self.present(alert, animated: true)
        }
    }
}
```

### 6. Error Types

```swift
enum APIError: Error {
    case authenticationRequired
    case unauthorized
    case rateLimited
    case missingDeviceID
    case badRequest
    case serverError(statusCode: Int)
    case noData
    case invalidURL
    case unknown

    var localizedDescription: String {
        switch self {
        case .authenticationRequired:
            return "Please sign in to continue"
        case .unauthorized:
            return "Your session has expired. Please sign in again."
        case .rateLimited:
            return "You've reached your daily limit. Try again tomorrow."
        case .missingDeviceID:
            return "Device identification required"
        case .badRequest:
            return "Invalid request"
        case .serverError(let code):
            return "Server error (\(code))"
        case .noData:
            return "No data received"
        case .invalidURL:
            return "Invalid URL"
        case .unknown:
            return "An unknown error occurred"
        }
    }
}

struct ErrorResponse: Codable {
    let error: ErrorDetail
}

struct ErrorDetail: Codable {
    let code: String
    let message: String
}
```

### 7. Notification Names

```swift
extension Notification.Name {
    static let authenticationRequired = Notification.Name("authenticationRequired")
    static let rateLimitExceeded = Notification.Name("rateLimitExceeded")
    static let sessionExpired = Notification.Name("sessionExpired")
}
```

## Testing Checklist

- [x] Guest sign in generates new token each time
- [x] Token IS persisted in Keychain after app close
- [x] App auto-restores guest session if token not expired (15 min window)
- [x] X-Device-ID header is sent with guest requests only
- [x] 401 errors are returned for expired/invalid tokens
- [x] 400 errors returned for missing Device ID on guest requests
- [x] 429 rate limit errors with proper headers
- [x] Token expiry (15 minutes for guests) handled locally
- [x] Rate limit persists across multiple guest sessions (same device)
- [x] Local JWT validation without API call on app launch

## Security Notes

1. **Guest tokens ARE stored**: Currently persisted in Keychain (may change)
2. **Device ID for guests only**: Required for guest rate limiting
3. **Handle 401 gracefully**: Clear token and show auth screen
4. **Rate limits are enforced**: 5 edits/day per device, tracked by IP + Device ID hash
5. **Token expiration**: 15 minutes for guests, checked locally before API calls
6. **Clock skew buffer**: 5-minute buffer when checking expiration locally

## Rate Limiting Behavior

- **Tracked by**: SHA256(IP Address + Device ID) for guests, User ID for authenticated
- **Limit**: 5 successful API calls per day for guests
- **Reset**: Every 24 hours rolling window
- **Cannot bypass**: Getting new token doesn't reset count (tied to device)
- **Required header**: X-Device-ID must be present for guest requests only
- **Backend validation**: Returns 400 if X-Device-ID missing for guest users

## Current Backend Responses

### Guest Token Creation (/api/auth/guest)
```json
{
    "guestToken": "eyJ...",
    "expiresIn": 900,  // 15 minutes
    "limitations": {
        "maxEditsPerDay": 5,
        "featuresDisabled": ["save", "history", "premium_templates"]
    }
}
```

### Error Responses
- **401 Unauthorized**: "Invalid or expired token" or "Authentication required"
- **400 Bad Request**: "X-Device-ID header is required for guest users"
- **429 Too Many Requests**: Includes rate limit headers
