# Shopify Integration Setup

This guide walks you through connecting FunnelLeak AI to your Shopify store. If you just want to explore the platform, skip this entirely and use **Demo Mode** (`DEMO_MODE=true`).

---

## Prerequisites

- A [Shopify Partner](https://partners.shopify.com) account (free to create)
- A development store or an existing Shopify store
- FunnelLeak AI running locally (see [Quick Start](../README.md#quick-start))

---

## Step 1: Create a Shopify Partner Account

1. Go to [https://partners.shopify.com](https://partners.shopify.com)
2. Click **Join now** and complete registration
3. Once logged in, you'll land on the Partner Dashboard

> **Already have a Partner account?** Skip to Step 2.

---

## Step 2: Create a New App

1. In the Partner Dashboard, navigate to **Apps** in the left sidebar
2. Click **Create app**
3. Select **Create app manually**
4. Enter the app name: `FunnelLeak AI` (or any name you prefer)
5. Set the **App URL**: `http://localhost:8000/api/v1/shopify/callback`
6. Set **Allowed redirection URL(s)**:
   ```
   http://localhost:8000/api/v1/shopify/callback
   ```
7. Click **Create app**

---

## Step 3: Get Your API Credentials

1. After creating the app, go to **App setup** → **Client credentials**
2. Copy the **API key** (also called Client ID)
3. Copy the **API secret key** (also called Client Secret)

> ⚠️ **Never commit these values to version control.** Store them in your `.env` file only.

---

## Step 4: Configure Required Scopes

FunnelLeak AI requests the following OAuth scopes:

| Scope               | Why It's Needed                                                        |
| -------------------- | ---------------------------------------------------------------------- |
| `read_products`      | Fetch product catalog, variants, pricing, images, and inventory status |
| `read_orders`        | Analyze order history to calculate conversion rates and revenue        |
| `read_inventory`     | Track inventory levels to detect stock-out–related conversion drops    |

These are **read-only** scopes. FunnelLeak AI never modifies your store data.

---

## Step 5: Set Environment Variables

Add the following to your `.env` file (copy from `.env.example` if you haven't already):

```env
SHOPIFY_API_KEY=your_api_key_here
SHOPIFY_API_SECRET=your_api_secret_key_here
SHOPIFY_SCOPES=read_products,read_orders,read_inventory
SHOPIFY_API_VERSION=2026-10
```

Make sure `DEMO_MODE` is set to `false` (or removed) if you want to use live Shopify data:

```env
DEMO_MODE=false
```

---

## Step 6: Test the OAuth Flow

1. Start FunnelLeak AI:
   ```bash
   docker compose up --build
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:8000/api/v1/shopify/install?shop=your-store.myshopify.com
   ```
   Replace `your-store` with your actual Shopify store subdomain.

3. You'll be redirected to Shopify's OAuth consent screen. Approve the requested permissions.

4. After approval, Shopify redirects back to FunnelLeak AI with an authorization code. The backend exchanges this for a permanent access token and stores it securely (encrypted at rest).

5. Verify the connection is active:
   ```bash
   curl http://localhost:8000/api/v1/stores
   ```
   You should see your store listed with `sync_status: "connected"`.

---

## Step 7: Trigger Initial Data Sync

Once connected, trigger the first data sync:

```bash
curl -X POST http://localhost:8000/api/v1/stores/{store_id}/sync
```

This pulls your product catalog and recent order history. Depending on your store size, the initial sync may take a few minutes.

---

## Troubleshooting

### "Invalid API key" error
- Double-check that `SHOPIFY_API_KEY` matches the **API key** (not the API secret) from your Partner Dashboard
- Ensure there are no leading/trailing spaces in the `.env` value

### OAuth redirect fails
- Confirm your **Allowed redirection URL** in Shopify matches exactly: `http://localhost:8000/api/v1/shopify/callback`
- If running behind a reverse proxy, update both the Shopify app config and `SHOPIFY_APP_URL` env var

### "Shop not found" error
- Use the full myshopify.com domain: `your-store.myshopify.com` (not a custom domain)

### Sync stuck or incomplete
- Check backend logs: `docker compose logs backend`
- Large stores (10k+ products) may take several minutes on first sync
- Subsequent syncs are incremental and much faster

---

## API Version

FunnelLeak AI uses Shopify API version **2026-10**. This is configured via the `SHOPIFY_API_VERSION` environment variable. When a newer stable API version is released, update this value and test for any breaking changes.

---

## Security Notes

- Access tokens are **encrypted at rest** using the `ENCRYPTION_KEY` from your `.env`
- Tokens are never logged or exposed in API responses
- All Shopify API calls use HTTPS
- FunnelLeak AI requests **read-only** scopes exclusively
