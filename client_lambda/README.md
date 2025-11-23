# JAVUMBO Client Lambda

This directory contains the React frontend optimized for the serverless Lambda backend.

## Differences from `/client`

The original `/client` directory is designed for the traditional Flask/Gunicorn backend. This `client_lambda` directory is optimized for the serverless architecture with:

1. **Session Management**: Uses `useDBSession` hook to manage Lambda session lifecycle
2. **JWT Authentication**: Stores JWT tokens in localStorage, includes in all API requests
3. **API Gateway Integration**: Configured to point to API Gateway URL instead of direct backend
4. **Session Indicators**: Shows users when a session is active and changes are being batched

## Development Plan

**Week 2 Day 8**: Create session management hooks and update ReviewPage
**Week 3 Day 14**: Build and deploy to S3/CloudFront

## Structure (to be created)

```
client_lambda/
├── src/
│   ├── hooks/
│   │   └── useDBSession.js       # Session lifecycle management
│   ├── components/
│   │   └── SessionIndicator.jsx  # Visual session status
│   ├── pages/
│   │   └── ReviewPage.jsx        # Updated with session support
│   └── App.jsx
├── .env.production                # API Gateway URL
└── package.json
```

## Status

📋 **PLANNED** - Will be implemented starting Week 2 Day 8
