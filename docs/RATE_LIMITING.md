# Rate Limiting & Credit System

## Overview

The application uses a **credit-based access system** where all users have access to the same features, but are limited by their available credits. Each image generation request consumes credits.

**Key Principle**: 1 credit = 1 image generation request via Gemini API
- Single-image generation: 1 credit
- Multi-angle generation (4 images): 4 credits

## User Types & Credit Allocations

| User Type | Credit Allocation | Tracking Method | Reset Period |
|-----------|------------------|-----------------|--------------|
| Guest (No sign-in) | 1 credit lifetime | Device ID / IP Address | Never (lifetime limit) |
| Signed-in (Free) | 4 credits lifetime | User ID (OAuth) | Never (lifetime limit) |
| Paid Subscriber | 168 credits/month | User ID + Subscription | Monthly on billing date |
| Credit Bundle User | Varies by bundle | User ID | Never (added to balance) |

## Technical Implementation

### Credit Tracking
- **Storage**: DynamoDB RateLimitsTable
- **Keys**: 
  - Guest: `deviceID/IP + "guest-credits"`
  - Signed-in: `userId + "lifetime-credits"`
  - Subscriber: `userId + "monthly-credits"` (TTL: 30 days)
  - Bundles: Added directly to user's credit balance

### Device Tracking (iOS)
Guest users are tracked to prevent abuse:
- Primary: `UIDevice.current.identifierForVendor`
- Secondary: IDFA (with App Tracking Transparency consent)
- Fallback: IP address from API Gateway headers

### API Flow
1. User initiates generation request
2. GeminiProxyFunction checks available credits
3. If sufficient: Deduct credits → Process request
4. If insufficient: Return 429 error with upgrade prompt

### Response Headers
```
X-Credits-Limit: 168
X-Credits-Remaining: 165
X-Credits-Reset: 1704067200 (for subscribers only)
```

### Error Response (429 Status)
```json
{
  "error": {
    "code": "insufficient_credits",
    "message": "You need 4 credits for this generation. You have 2 credits remaining."
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
      {
        "credits": 8,
        "price": "$0.99"
      },
      {
        "credits": 48,
        "price": "$4.99"
      }
    ]
  }
}
```

## Setting Admin Access (Development Only)

For development and testing, admin access provides unlimited credits:

```bash
cd backend/scripts

# Update by email
go run update-user-tier.go -email your-email@gmail.com -tier admin

# Or update by user ID
go run update-user-tier.go -user google_12345 -tier admin

# Specify AWS profile if needed
go run update-user-tier.go -email your-email@gmail.com -tier admin -profile your-aws-profile
```

## Global Rate Limits

Beyond credits, API Gateway enforces global limits to prevent abuse:
- **Daily Quota**: 100,000 requests/day
- **Burst Rate**: 60 requests/second
- **Implementation**: AWS API Gateway Usage Plans

## Monitoring & Alerts

- **CloudWatch Alarms**: Trigger on unusual usage patterns (>10 generations/day/user)
- **Cost Tracking**: Monitor via AWS Cost Explorer
- **Abuse Detection**: Track multiple account creation from same device/IP

## Credit Expiration Policy

- **Guest/Free Credits**: Never expire (lifetime allocation)
- **Subscription Credits**: Reset monthly, unused credits don't roll over
- **Bundle Credits**: No expiration (permanent addition to balance)
- **Account Inactivity**: Credits may expire after 1 year of inactivity (per App Store guidelines)