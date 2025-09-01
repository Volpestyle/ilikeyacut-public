# Rate Limiting System

## User Tiers

The application implements a tiered rate limiting system with the following limits:

| Tier | Daily Limit | Description | How to Upgrade |
|------|-------------|-------------|----------------|
| Guest | 3 requests | Unauthenticated users with device tracking | Sign in with Google OAuth |
| Free | 5 requests | Authenticated users without subscription | Upgrade to paid plan |
| Paid | 100 requests | Subscribed users | Contact support for higher limits |
| Admin | Unlimited | Administrative access | Manual database update |

## Rate Limit Messages

When users exceed their rate limits, they receive tier-specific messages:

- **Guest**: "You've hit the maximum of 3 requests. Sign in to increase your limits."
- **Free User**: "You've hit your daily limit of 5 requests. Upgrade to a paid plan for more requests."
- **Paid User**: "You've hit your daily limit of 100 requests. Contact support if you need higher limits."

## Setting Admin Access

To grant yourself admin access after signing in with Google OAuth:

1. Sign in to the app with your Google account
2. Note your user ID from the JWT token or DynamoDB Users table
3. Run the update script:

```bash
cd backend/scripts

# Update by email (easiest)
go run update-user-tier.go -email your-email@gmail.com -tier admin

# Or update by user ID
go run update-user-tier.go -user google_12345 -tier admin

# Specify AWS profile if needed
go run update-user-tier.go -email your-email@gmail.com -tier admin -profile your-aws-profile
```

## Rate Limit Implementation Details

### Guest Users
- Tracked by composite key: SHA256(IP + Device ID)
- Requires X-Device-ID header from iOS app
- Additional IP-based tracking to prevent token rotation abuse

### Authenticated Users
- Tracked by user ID from JWT
- Tier determined from JWT claims or database lookup
- Support for free, paid, and admin tiers

### Technical Details
- Window: 24-hour rolling window
- Storage: DynamoDB with TTL
- Headers: Returns X-RateLimit-* headers
- Reset: Daily at midnight UTC

## API Response Headers

All API responses include rate limit information:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1704067200
Retry-After: 3600 (only on 429 responses)
```

## Error Response Format

When rate limit is exceeded (429 status):

```json
{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "You've hit your daily limit of 5 requests. Upgrade to a paid plan for more requests."
  },
  "rateLimit": {
    "limit": 5,
    "remaining": 0,
    "resetsAt": "2024-01-01T00:00:00Z",
    "retryAfter": 3600,
    "userTier": "free"
  }
}
```