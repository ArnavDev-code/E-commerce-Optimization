# Google Analytics 4 Integration Guide

## Overview

FunnelLeak AI uses the **Google Analytics 4 Data API v1beta** via OAuth 2.0 to ingest session counts, traffic source breakdowns, and device category segmentations.

> **Data separation rule:** GA4 is authoritative for traffic, sessions, and funnel stage counts. Shopify is authoritative for all commerce data (orders, revenue, COGS, inventory). These two sources are **never merged or double-counted**.

---

## 1. Prerequisites

| Requirement | Detail |
|---|---|
| Google Account | Must have access to your store's GA4 property |
| GA4 Property | GA4 (not Universal Analytics) must be active on your Shopify storefront |
| FunnelLeak Account | Must be a registered merchant with an active Shopify store connected |

---

## 2. Create a Google Cloud OAuth 2.0 Client

### Step-by-step

1. Open [Google Cloud Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials).
2. Select or create a project.
3. Click **Create Credentials → OAuth client ID**.
4. Set **Application type** to **Web application**.
5. Add the following **Authorized redirect URIs**:
   - Development: `http://localhost:8000/api/integrations/ga4/callback`
   - Production: `https://your-domain.com/api/integrations/ga4/callback`
6. Click **Create** and note your **Client ID** and **Client Secret**.

### Enable Required APIs

In the same project, navigate to **APIs & Services → Library** and enable:
- **Google Analytics Admin API** — for property discovery
- **Google Analytics Data API** — for `runReport` metric queries

---

## 3. Configure Environment Variables

Add the following to your `.env` file:

```dotenv
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/integrations/ga4/callback
GOOGLE_OAUTH_SCOPES=https://www.googleapis.com/auth/analytics.readonly
```

The scope `analytics.readonly` grants read-only access to GA4 reporting data. No write permissions are requested or used.

---

## 4. Connect GA4 from the FunnelLeak UI

1. Log in to FunnelLeak AI and navigate to **Integrations**.
2. In the **Google Analytics 4** card, click **Connect Google Account**.
3. You are redirected to Google's OAuth consent screen. Grant access.
4. After granting access, you are redirected back to FunnelLeak with the connection active.
5. Click **Select Property** and expand your Google Analytics account.
6. Choose the GA4 property that tracks your Shopify storefront.
7. Click **Use This Property**.
8. Click **Sync Now** to import the last 30 days of GA4 data.

---

## 5. What Data is Imported

Each sync run calls `properties/{id}:runReport` and imports the following:

| Dimension | Metrics Collected |
|---|---|
| `overall` (daily totals) | sessions, totalUsers, screenPageViews, itemsViewed, itemsAddedToCart, itemsCheckedOut, ecommercePurchases, purchaseRevenue |
| `deviceCategory` (mobile/desktop/tablet) | sessions, totalUsers, screenPageViews |
| `sessionDefaultChannelGroup` (Organic/Paid/etc.) | sessions, totalUsers, screenPageViews |

> **Important:** If ecommerce events are not configured in your GA4 property, funnel step counts (itemsViewed, itemsAddedToCart, etc.) will be zero. FunnelLeak will fall back to basic session metrics in that case.

---

## 6. Analytics Engine Source Attribution

When GA4 is connected and a property is selected:

| Data Type | Source |
|---|---|
| Sessions, traffic sources, device breakdown | **GA4** (via `GA4Metric` table) |
| Orders, revenue, AOV | **Shopify** (via `Order` table) — always authoritative |
| Product views and add-to-cart events | **Shopify Web Pixel** when available, else **GA4** |
| COGS and gross margin | **Manual entry** or Shopify cost data |

You can explicitly request a data source on analytics endpoints with `?data_source=ga4` or `?data_source=pixel`.

---

## 7. Token Refresh and Expiry

- Access tokens expire after 1 hour.
- FunnelLeak automatically refreshes the access token using the stored refresh token before API calls.
- If the refresh token becomes invalid (user revokes access or long inactivity), the connection status changes to `expired`. Reconnect from the Integrations page.

---

## 8. Disconnecting

Clicking **Disconnect** in the Integrations page:
1. Calls `POST /api/integrations/ga4/disconnect`
2. Revokes the access token at `https://oauth2.googleapis.com/revoke`
3. Clears all stored encrypted credentials from the database
4. Preserves previously imported `GA4Metric` records (historical data)

To also delete historical GA4 data, contact your FunnelLeak administrator.

---

## 9. Privacy & Security

| Aspect | Detail |
|---|---|
| Scope | `analytics.readonly` — no write access |
| Token storage | Encrypted at rest using AES-256 (Fernet) keyed on `ENCRYPTION_KEY` |
| Data isolation | All credentials and metrics are scoped to the authenticated merchant's store |
| Token transmission | Tokens are never logged, returned in API responses, or included in error messages |
