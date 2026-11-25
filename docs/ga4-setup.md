# GA4 Integration Setup

This guide walks you through connecting Google Analytics 4 (GA4) to FunnelLeak AI for enhanced funnel analytics. GA4 integration is **optional** — the platform works fully without it using Shopify order data alone.

---

## What GA4 Adds

With GA4 connected, FunnelLeak AI gains access to:

- **Session-level funnel data** — See where visitors drop off before they even reach a product page
- **Traffic source attribution** — Identify which channels drive the highest (and lowest) converting traffic
- **On-site behavior metrics** — Page timing, scroll depth, and engagement signals that correlate with conversion
- **Enhanced leak detection** — Cross-reference Shopify conversion data with GA4 behavioral data for more precise root-cause analysis

---

## Prerequisites

- A [Google Cloud](https://console.cloud.google.com) account
- A GA4 property tracking your Shopify store
- FunnelLeak AI running locally (see [Quick Start](../README.md#quick-start))

---

## Step 1: Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com)
2. Click the project dropdown at the top → **New Project**
3. Name it (e.g., `funnelleak-ai`) and click **Create**
4. Select the new project from the dropdown

> **Already have a Google Cloud project?** Skip to Step 2.

---

## Step 2: Enable the Analytics Data API

1. In the Cloud Console, go to **APIs & Services** → **Library**
2. Search for **Google Analytics Data API**
3. Click **Enable**

> This is the GA4 Data API (v1), not the older Universal Analytics API.

---

## Step 3: Create a Service Account

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **Service Account**
3. Enter a name: `funnelleak-ga4-reader`
4. Click **Create and Continue**
5. For the role, select **No role** (access is granted at the GA4 property level, not the GCP project level)
6. Click **Done**

---

## Step 4: Download the JSON Key File

1. In the **Credentials** page, find your new service account
2. Click the service account email to open its details
3. Go to the **Keys** tab
4. Click **Add Key** → **Create new key**
5. Select **JSON** format
6. Click **Create** — the key file downloads automatically

> ⚠️ **Store this file securely.** Never commit it to version control. Place it outside your project directory or in a path listed in `.gitignore`.

Recommended location:

```
~/.config/funnelleak/ga4-credentials.json
```

---

## Step 5: Grant Access to Your GA4 Property

1. Go to [Google Analytics](https://analytics.google.com)
2. Navigate to **Admin** (gear icon, bottom left)
3. Under your GA4 property, click **Property Access Management**
4. Click the **+** button → **Add users**
5. Enter the service account email (e.g., `funnelleak-ga4-reader@your-project.iam.gserviceaccount.com`)
6. Set the role to **Viewer** (read-only access is sufficient)
7. Click **Add**

---

## Step 6: Find Your GA4 Property ID

1. In Google Analytics, go to **Admin**
2. Under **Property Settings**, find the **Property ID**
3. It's a numeric value (e.g., `123456789`) — not the measurement ID (`G-XXXXXXX`)

---

## Step 7: Set Environment Variables

Add the following to your `.env` file:

```env
GA4_CREDENTIALS_PATH=/absolute/path/to/ga4-credentials.json
GA4_PROPERTY_ID=123456789
```

Replace with your actual file path and property ID.

---

## Step 8: Verify the Connection

1. Restart FunnelLeak AI:
   ```bash
   docker compose restart backend
   ```

2. Test the GA4 connection:
   ```bash
   curl http://localhost:8000/api/v1/analytics/ga4/status
   ```
   You should see `"status": "connected"` with your property name.

---

## Available Metrics and Dimensions

FunnelLeak AI queries the following GA4 data:

### Metrics

| Metric                     | Description                                      |
| -------------------------- | ------------------------------------------------ |
| `sessions`                 | Total sessions in the reporting period            |
| `totalUsers`               | Unique users                                     |
| `screenPageViews`          | Total page views                                 |
| `averageSessionDuration`   | Average time spent per session (seconds)         |
| `bounceRate`               | Percentage of single-page sessions               |
| `ecommerce:transactions`   | Completed purchases tracked via GA4 ecommerce    |
| `ecommerce:purchaseRevenue`| Total revenue from GA4-tracked purchases         |
| `conversions`              | Goal/event completions                           |

### Dimensions

| Dimension                 | Description                                       |
| ------------------------- | ------------------------------------------------- |
| `date`                    | Date of the session                               |
| `sessionSource`           | Traffic source (e.g., google, facebook, direct)   |
| `sessionMedium`           | Traffic medium (e.g., organic, cpc, referral)     |
| `sessionCampaignName`     | Campaign name (for paid traffic)                  |
| `pagePath`                | URL path of the page viewed                       |
| `deviceCategory`          | Device type (desktop, mobile, tablet)             |
| `country`                 | Visitor's country                                 |
| `city`                    | Visitor's city                                    |

---

## Troubleshooting

### "Permission denied" or "403" error
- Verify the service account email has **Viewer** access on the GA4 property (not just the GCP project)
- Changes to GA4 access can take up to 10 minutes to propagate

### "API not enabled" error
- Confirm you enabled the **Google Analytics Data API** (not the Admin API or Reporting API)
- Ensure it's enabled in the same GCP project as your service account

### "Property not found" error
- Use the numeric **Property ID** (e.g., `123456789`), not the Measurement ID (`G-XXXXXXX`)
- Confirm the service account has access to this specific property

### Empty data
- GA4 data is typically available with a 24–48 hour delay
- Ensure your GA4 property is actively collecting data from your Shopify store
- Verify Enhanced Ecommerce tracking is configured in GA4

---

## Security Notes

- The service account JSON key is read from disk at startup and never stored in the database
- FunnelLeak AI uses **read-only** access to GA4 (Viewer role)
- API calls are authenticated via Google's OAuth 2.0 service account flow over HTTPS
- The credentials file path should be outside the project directory and listed in `.gitignore`
