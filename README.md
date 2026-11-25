# FunnelLeak AI

**Revenue Recovery Intelligence for Shopify**

FunnelLeak AI identifies exactly where your Shopify store is losing revenue—and tells you how to fix it. It connects to your store and analytics, analyzes every stage of your conversion funnel using AI-powered diagnostics, and delivers prioritized, actionable recommendations with estimated revenue impact.

---

## Features (MVP)

- **Funnel Analysis Dashboard** — Visualize your full conversion funnel from session → product view → add to cart → checkout → purchase, with stage-by-stage drop-off rates
- **Leak Detection Engine** — Automatically identifies conversion problems across products, categories, and funnel stages using statistical analysis and AI
- **Revenue Impact Scoring** — Every detected leak is scored by estimated weekly revenue loss so you fix the highest-impact issues first
- **AI-Powered Recommendations** — Get specific, actionable fixes for each leak (e.g., "Product X has a 73% cart-abandonment rate—add urgency messaging and simplify checkout")
- **Product-Level Intelligence** — Deep-dive into individual product performance with conversion metrics, variant analysis, and pricing insights
- **Demo Mode** — Fully functional out of the box with 24 pre-seeded products and realistic conversion data, no Shopify account required

---

## Tech Stack

| Layer      | Technology                                    |
| ---------- | --------------------------------------------- |
| Frontend   | React 18, TypeScript, Vite, Tailwind CSS, Recharts |
| Backend    | Python 3.12, FastAPI, SQLAlchemy 2.0, Pandas  |
| Database   | PostgreSQL 16 with Alembic migrations         |
| AI         | LLM provider abstraction (OpenAI / Anthropic) with deterministic fallback |
| DevOps     | Docker Compose, hot-reload in dev             |

---

## Quick Start

### Prerequisites

- **Docker** and **Docker Compose** (recommended)
- OR: Python 3.12+, Node.js 20+, PostgreSQL 16+

### Using Docker (Recommended)

```bash
# 1. Clone the repo
git clone https://github.com/your-org/funnelleak-ai.git
cd funnelleak-ai

# 2. Copy environment config
cp .env.example .env

# 3. Start everything
docker compose up --build
```

Open [http://localhost:5173](http://localhost:5173) — the dashboard loads with demo data automatically.

### Manual Setup

#### Backend

```bash
cd backend
python -m venv venv
source venv/Scripts/activate   # Windows
# source venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

The API is now running at [http://localhost:8000](http://localhost:8000).

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

The dashboard is now running at [http://localhost:5173](http://localhost:5173).

---

## Demo Mode

Set `DEMO_MODE=true` (the default) to run FunnelLeak AI without connecting a real Shopify store.

Demo mode pre-seeds the database with **24 products** across multiple categories, each with realistic conversion data and **deliberate conversion problems** for the leak detection engine to find. This includes:

- Products with abnormally high cart-abandonment rates
- Categories with low add-to-cart rates
- Pricing outliers that suppress conversion
- Seasonal patterns and traffic anomalies

Demo mode is perfect for evaluating the platform, developing new features, or running demos without exposing real store data.

---

## API Documentation

Interactive API docs are available when the backend is running:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Project Structure

```
FunnelLeak-AI/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI route handlers
│   │   ├── core/           # Config, security, dependencies
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Business logic layer
│   │   └── main.py         # Application entry point
│   ├── alembic/            # Database migrations
│   ├── tests/              # Backend test suite
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/     # React UI components
│   │   ├── pages/          # Route-level page components
│   │   ├── hooks/          # Custom React hooks
│   │   ├── services/       # API client layer
│   │   └── types/          # TypeScript type definitions
│   ├── Dockerfile
│   └── package.json
├── docs/                   # Setup guides and API reference
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Environment Variables

See [`.env.example`](.env.example) for all available configuration options, including:

- Database connection
- Shopify API credentials and OAuth configuration
- GA4 service account and property ID
- LLM provider selection (OpenAI, Anthropic, or deterministic fallback)
- Encryption key for securing stored credentials

---

## Development Phases

| Phase | Description                        | Status         |
| ----- | ---------------------------------- | -------------- |
| 1     | Foundation & Data Models           | ✅ Complete    |
| 2     | Shopify Integration & Data Sync    | 🔲 Planned     |
| 3     | Analytics Pipeline                 | 🔲 Planned     |
| 4     | Leak Detection Engine              | 🔲 Planned     |
| 5     | AI Recommendations                 | 🔲 Planned     |
| 6     | Frontend Dashboard                 | 🔲 Planned     |
| 7     | GA4 Integration                    | 🔲 Planned     |
| 8     | Polish, Testing & Deployment       | 🔲 Planned     |

---

## Documentation

- [Shopify Integration Setup](docs/shopify-setup.md)
- [GA4 Integration Setup](docs/ga4-setup.md)
- [API Reference](docs/api-reference.md)

---

## License

MIT
