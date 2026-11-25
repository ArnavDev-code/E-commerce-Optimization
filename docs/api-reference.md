# API Reference

Base URL: `http://localhost:8000/api/v1`

All endpoints return JSON. Errors follow the format:

```json
{
  "detail": "Human-readable error message"
}
```

> **Legend:** ✅ Implemented | 🔲 Planned

---

## Health & System

| Status | Method | Endpoint       | Description                |
| ------ | ------ | -------------- | -------------------------- |
| ✅     | GET    | `/health`      | Health check and DB status |

### `GET /health`

Returns application health and database connectivity.

**Response** `200 OK`

```json
{
  "status": "healthy",
  "database": "connected",
  "demo_mode": true,
  "version": "0.1.0"
}
```

---

## Stores

Manage connected Shopify stores.

| Status | Method | Endpoint                        | Description                     |
| ------ | ------ | ------------------------------- | ------------------------------- |
| ✅     | GET    | `/stores`                       | List all connected stores       |
| ✅     | GET    | `/stores/{store_id}`            | Get store details               |
| 🔲     | POST   | `/stores/{store_id}/sync`       | Trigger data sync               |
| 🔲     | GET    | `/stores/{store_id}/sync/status`| Check sync status               |
| 🔲     | DELETE | `/stores/{store_id}`            | Disconnect a store              |

### `GET /stores`

**Response** `200 OK`

```json
[
  {
    "id": "uuid",
    "shopify_domain": "my-store.myshopify.com",
    "store_name": "My Store",
    "sync_status": "synced",
    "last_synced_at": "2026-11-18T10:00:00Z",
    "created_at": "2026-11-15T08:00:00Z"
  }
]
```

### `POST /stores/{store_id}/sync`

Triggers an asynchronous data sync from Shopify. Returns immediately with sync job status.

**Response** `202 Accepted`

```json
{
  "sync_id": "uuid",
  "status": "in_progress",
  "started_at": "2026-11-18T10:00:00Z"
}
```

---

## Shopify OAuth

Handle Shopify app installation via OAuth 2.0.

| Status | Method | Endpoint                        | Description                     |
| ------ | ------ | ------------------------------- | ------------------------------- |
| 🔲     | GET    | `/shopify/install`              | Start OAuth flow                |
| 🔲     | GET    | `/shopify/callback`             | OAuth callback handler          |

### `GET /shopify/install`

**Query Parameters**

| Param  | Type   | Required | Description                            |
| ------ | ------ | -------- | -------------------------------------- |
| `shop` | string | Yes      | Shopify store domain (e.g., `my-store.myshopify.com`) |

**Response** `302 Redirect` to Shopify OAuth consent screen.

### `GET /shopify/callback`

Handles the OAuth callback from Shopify. Exchanges the authorization code for an access token, encrypts it, and stores it in the database.

**Query Parameters** (provided by Shopify)

| Param     | Type   | Description               |
| --------- | ------ | ------------------------- |
| `code`    | string | Authorization code        |
| `shop`    | string | Store domain              |
| `hmac`    | string | HMAC signature for verification |

**Response** `302 Redirect` to the frontend dashboard.

---

## Products

Product catalog and performance data.

| Status | Method | Endpoint                               | Description                      |
| ------ | ------ | -------------------------------------- | -------------------------------- |
| ✅     | GET    | `/stores/{store_id}/products`          | List products with metrics       |
| ✅     | GET    | `/stores/{store_id}/products/{id}`     | Get product detail               |
| 🔲     | GET    | `/stores/{store_id}/products/top`      | Top products by revenue          |
| 🔲     | GET    | `/stores/{store_id}/products/at-risk`  | Products with conversion issues  |

### `GET /stores/{store_id}/products`

**Query Parameters**

| Param       | Type    | Default | Description                          |
| ----------- | ------- | ------- | ------------------------------------ |
| `page`      | int     | 1       | Page number                          |
| `page_size` | int     | 20      | Results per page (max 100)           |
| `category`  | string  | —       | Filter by category                   |
| `sort_by`   | string  | `title` | Sort field: `title`, `revenue`, `conversion_rate` |
| `order`     | string  | `asc`   | Sort order: `asc` or `desc`          |

**Response** `200 OK`

```json
{
  "items": [
    {
      "id": "uuid",
      "shopify_product_id": "123456",
      "title": "Classic T-Shirt",
      "category": "Apparel",
      "price": 29.99,
      "sessions": 1200,
      "product_views": 980,
      "add_to_carts": 245,
      "checkouts_initiated": 147,
      "purchases": 98,
      "revenue": 2939.02,
      "conversion_rate": 0.0817,
      "cart_abandonment_rate": 0.40
    }
  ],
  "total": 24,
  "page": 1,
  "page_size": 20
}
```

---

## Funnel Analytics

Conversion funnel data and stage-by-stage analysis.

| Status | Method | Endpoint                                | Description                        |
| ------ | ------ | --------------------------------------- | ---------------------------------- |
| ✅     | GET    | `/stores/{store_id}/funnel`             | Full funnel overview               |
| ✅     | GET    | `/stores/{store_id}/funnel/stages`      | Stage-by-stage breakdown           |
| 🔲     | GET    | `/stores/{store_id}/funnel/trends`      | Funnel trends over time            |
| 🔲     | GET    | `/stores/{store_id}/funnel/by-category` | Funnel breakdown by category       |

### `GET /stores/{store_id}/funnel`

Returns the complete funnel with absolute counts and drop-off rates at each stage.

**Query Parameters**

| Param       | Type   | Default  | Description                          |
| ----------- | ------ | -------- | ------------------------------------ |
| `days`      | int    | 30       | Lookback period in days              |

**Response** `200 OK`

```json
{
  "period_days": 30,
  "stages": [
    {
      "name": "Sessions",
      "count": 15000,
      "rate": 1.0,
      "drop_off_rate": null
    },
    {
      "name": "Product Views",
      "count": 10500,
      "rate": 0.70,
      "drop_off_rate": 0.30
    },
    {
      "name": "Add to Cart",
      "count": 3150,
      "rate": 0.30,
      "drop_off_rate": 0.70
    },
    {
      "name": "Checkout Initiated",
      "count": 1890,
      "rate": 0.60,
      "drop_off_rate": 0.40
    },
    {
      "name": "Purchase",
      "count": 1134,
      "rate": 0.60,
      "drop_off_rate": 0.40
    }
  ],
  "overall_conversion_rate": 0.0756,
  "total_revenue": 67890.50
}
```

---

## Leaks

Detected conversion leaks with revenue impact analysis.

| Status | Method | Endpoint                                        | Description                        |
| ------ | ------ | ----------------------------------------------- | ---------------------------------- |
| 🔲     | GET    | `/stores/{store_id}/leaks`                      | List all detected leaks            |
| 🔲     | GET    | `/stores/{store_id}/leaks/{leak_id}`            | Get leak details                   |
| 🔲     | GET    | `/stores/{store_id}/leaks/summary`              | Leak summary with total impact     |
| 🔲     | POST   | `/stores/{store_id}/leaks/{leak_id}/dismiss`    | Dismiss a leak                     |
| 🔲     | POST   | `/stores/{store_id}/leaks/{leak_id}/resolve`    | Mark a leak as resolved            |

### `GET /stores/{store_id}/leaks`

**Query Parameters**

| Param       | Type   | Default    | Description                              |
| ----------- | ------ | ---------- | ---------------------------------------- |
| `severity`  | string | —          | Filter: `critical`, `high`, `medium`, `low` |
| `stage`     | string | —          | Filter by funnel stage                   |
| `status`    | string | `active`   | Filter: `active`, `dismissed`, `resolved` |
| `sort_by`   | string | `impact`   | Sort: `impact`, `severity`, `created_at` |

**Response** `200 OK`

```json
{
  "items": [
    {
      "id": "uuid",
      "type": "high_cart_abandonment",
      "severity": "critical",
      "funnel_stage": "Add to Cart → Checkout",
      "affected_products": ["Classic T-Shirt", "Summer Dress"],
      "current_rate": 0.73,
      "benchmark_rate": 0.45,
      "estimated_weekly_revenue_loss": 2340.00,
      "status": "active",
      "detected_at": "2026-11-17T14:30:00Z"
    }
  ],
  "total": 8,
  "total_weekly_revenue_loss": 12450.00
}
```

---

## Recommendations

AI-generated recommendations for fixing detected leaks.

| Status | Method | Endpoint                                                   | Description                     |
| ------ | ------ | ---------------------------------------------------------- | ------------------------------- |
| 🔲     | GET    | `/stores/{store_id}/recommendations`                       | List all recommendations        |
| 🔲     | GET    | `/stores/{store_id}/recommendations/{id}`                  | Get recommendation details      |
| 🔲     | POST   | `/stores/{store_id}/leaks/{leak_id}/recommendations`       | Generate recommendations for a leak |

### `GET /stores/{store_id}/recommendations`

**Query Parameters**

| Param      | Type   | Default    | Description                              |
| ---------- | ------ | ---------- | ---------------------------------------- |
| `priority` | string | —          | Filter: `high`, `medium`, `low`          |
| `status`   | string | `pending`  | Filter: `pending`, `applied`, `skipped`  |

**Response** `200 OK`

```json
{
  "items": [
    {
      "id": "uuid",
      "leak_id": "uuid",
      "priority": "high",
      "title": "Add urgency messaging to checkout",
      "description": "Products 'Classic T-Shirt' and 'Summer Dress' have cart abandonment rates 28 percentage points above your store average. Adding low-stock indicators and limited-time messaging can reduce abandonment by 15-20%.",
      "estimated_revenue_recovery": 1170.00,
      "effort": "low",
      "category": "checkout_optimization",
      "status": "pending",
      "generated_at": "2026-11-17T14:35:00Z"
    }
  ],
  "total": 12,
  "total_potential_recovery": 8900.00
}
```

---

## Analytics (GA4)

Google Analytics 4 data integration endpoints.

| Status | Method | Endpoint                                           | Description                     |
| ------ | ------ | -------------------------------------------------- | ------------------------------- |
| 🔲     | GET    | `/stores/{store_id}/analytics/ga4/status`          | GA4 connection status           |
| 🔲     | GET    | `/stores/{store_id}/analytics/ga4/traffic`         | Traffic sources and volume      |
| 🔲     | GET    | `/stores/{store_id}/analytics/ga4/behavior`        | On-site behavior metrics        |
| 🔲     | GET    | `/stores/{store_id}/analytics/ga4/conversions`     | GA4 conversion data             |

### `GET /stores/{store_id}/analytics/ga4/status`

**Response** `200 OK`

```json
{
  "status": "connected",
  "property_id": "123456789",
  "property_name": "My Shopify Store",
  "last_data_date": "2026-11-17"
}
```

---

## Dashboard

Pre-aggregated data for the frontend dashboard.

| Status | Method | Endpoint                                     | Description                        |
| ------ | ------ | -------------------------------------------- | ---------------------------------- |
| 🔲     | GET    | `/stores/{store_id}/dashboard/summary`       | Key metrics summary                |
| 🔲     | GET    | `/stores/{store_id}/dashboard/trends`        | Time-series trend data             |
| 🔲     | GET    | `/stores/{store_id}/dashboard/top-leaks`     | Top 5 leaks by revenue impact      |

### `GET /stores/{store_id}/dashboard/summary`

**Response** `200 OK`

```json
{
  "period_days": 30,
  "total_sessions": 15000,
  "total_revenue": 67890.50,
  "overall_conversion_rate": 0.0756,
  "total_leaks_detected": 8,
  "total_weekly_revenue_at_risk": 12450.00,
  "top_leak_category": "Cart Abandonment",
  "recommendations_pending": 12
}
```

---

## Pagination

All list endpoints support pagination:

| Param       | Type | Default | Description               |
| ----------- | ---- | ------- | ------------------------- |
| `page`      | int  | 1       | Page number (1-indexed)   |
| `page_size` | int  | 20      | Results per page (max 100)|

Paginated responses include:

```json
{
  "items": [],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

---

## Error Codes

| Status Code | Meaning                                          |
| ----------- | ------------------------------------------------ |
| 400         | Bad request — invalid parameters                 |
| 401         | Unauthorized — missing or invalid authentication |
| 404         | Resource not found                               |
| 422         | Validation error — request body didn't validate  |
| 429         | Rate limited — too many requests                 |
| 500         | Internal server error                            |

Error response body:

```json
{
  "detail": "Store not found"
}
```

Validation errors (422):

```json
{
  "detail": [
    {
      "loc": ["query", "page_size"],
      "msg": "ensure this value is less than or equal to 100",
      "type": "value_error"
    }
  ]
}
```
