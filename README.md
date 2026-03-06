# AIVOA — AI-First CRM for Pharma Sales Reps

> **AIVOA** (AI Voice of Action) is a full-stack CRM built for pharmaceutical sales representatives.
> Instead of manually filling forms after every HCP visit, reps type a free-text note.
> The AI agent reads it, extracts every structured field, and auto-populates the interaction form.
> One click saves the record to Supabase — no data entry, no missed fields.

---

## Tech Stack

| Layer | Technology | Role |
|---|---|---|
| Frontend | React 18 + Vite + Redux Toolkit | SPA, state management |
| Styling | CSS Modules | Component-scoped styles |
| Backend | FastAPI + Uvicorn | REST API, async request handling |
| ORM | SQLAlchemy 2.0 async + asyncpg | Async DB, PgBouncer compatible |
| Database | PostgreSQL via Supabase | Cloud-hosted, free tier |
| AI Agent | LangGraph StateGraph | 6-node directed pipeline |
| LLM | Groq llama-3.1-8b-instant | Fast inference, free API tier |

---

## Features

- **Natural-language logging** — describe a visit in plain English; every field is extracted automatically
- **Auto form fill** — extracted data populates the React form with blue-ring highlights
- **HCP auto-creation** — if the doctor is not in the DB, a profile is created on the fly
- **Intent routing** — agent distinguishes logging, editing, history queries, follow-up suggestions, and product recommendations
- **Full interaction history** — per-HCP timeline of all past visits and calls
- **Swagger UI** — auto-generated interactive API docs at /docs

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- A free [Groq API key](https://console.groq.com)
- A free [Supabase](https://supabase.com) project (PostgreSQL)

### 1. Clone the repository

`ash
git clone https://github.com/Rudra-8124/AIVOA.git
cd AIVOA
`

### 2. Configure the backend

Create ackend/.env:

`env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
LLM_MODEL=llama-3.1-8b-instant
APP_ENV=development
CORS_ORIGINS=http://localhost:5173
`

### 3. Start the backend

`ash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
`

### 4. Start the frontend

`ash
cd frontend
npm install
npm run dev
`

Open **http://localhost:5173**

---

## How It Works

1. **Type a note** — rep writes a plain-text description of the HCP interaction in the AI Assistant panel.
2. **Agent pipeline runs** — LangGraph routes text through 6 nodes: intent classification, entity extraction, tool selection, execution, and response generation.
3. **Form auto-fills** — all extracted fields (HCP name, date, time, topics, samples, sentiment, outcomes, follow-ups) populate the form with blue-ring highlights.
4. **Save** — rep reviews and clicks **Save Interaction**; record is persisted to Supabase.

### Example prompt

`
Visited Dr. Priya Sharma at Apollo Hospital yesterday at 2:30 PM.
Discussed Cardivex efficacy and dosing. Shared brochure and Phase III reprint.
Distributed 3 samples of Cardivex 10mg. She was very positive.
Agreed to trial for 5 patients. Follow up in 2 weeks.
`

**All 9 fields extracted automatically:**

| Field | Extracted value |
|---|---|
| HCP name | Dr. Priya Sharma |
| Interaction type | in_person |
| Date | yesterday (resolved to ISO date) |
| Time | 14:30 |
| Topics discussed | Cardivex efficacy, dosing |
| Materials shared | brochure, Phase III reprint |
| Samples distributed | Cardivex 10mg x 3 |
| Sentiment | positive |
| Follow-up actions | Follow up in 2 weeks |

---

## AI Agent — 6-Node Pipeline

`
START → input_node → intent_node → entity_extraction_node
      → tool_selector_node → tool_executor_node → responder_node → END
`

| Node | What it does |
|---|---|
| input_node | Passes raw user text into the graph state |
| intent_node | Classifies the message into one of 6 intents using the LLM |
| entity_extraction_node | Extracts all structured fields (HCP, date, time, topics, etc.) |
| tool_selector_node | Maps intent to tool and builds the input payload |
| tool_executor_node | Executes the selected tool against Supabase |
| responder_node | Generates a human-readable confirmation or answer |

### 6 Intents

| Intent | When it triggers |
|---|---|
| log | Rep describes a past visit, call, or email |
| edit | Rep wants to correct a previously logged interaction |
| query_history | Rep asks to see past interactions with an HCP |
| suggest_followup | Rep explicitly asks what to do next |
| product_recommendation | Rep explicitly asks what product to recommend |
| chitchat | Greetings or out-of-scope messages |

### 5 Tools

| Tool | Description |
|---|---|
| log_interaction | Creates a new interaction record; auto-creates HCP if not found |
| edit_interaction | Updates an existing interaction by ID |
| fetch_hcp_history | Returns all interactions for an HCP |
| suggest_followup | Generates next-step suggestions based on history |
| product_recommendation | Recommends products based on HCP specialty and history |

---

## Project Structure

`
AIVOA/
├── backend/
│   ├── app/
│   │   ├── ai_agent/
│   │   │   ├── graph.py          # StateGraph definition
│   │   │   ├── nodes.py          # All 6 node functions + prompts
│   │   │   ├── groq_client.py    # Async Groq wrapper
│   │   │   └── tools/            # 5 tool implementations
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── routers/          # FastAPI route handlers
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── services/         # Business logic (HCP, Interaction)
│   │   ├── config.py         # Settings loaded from .env
│   │   ├── database.py       # Async engine + session factory
│   │   └── main.py           # App entry point, router registration
│   └── requirements.txt
└── frontend/
    └── src/
        ├── components/       # ChatPanel, InteractionForm, UI atoms
        ├── slices/           # Redux slices: interaction, agent, hcp
        ├── services/         # Axios API service functions
        └── store/            # Redux store configuration
`

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | /api/ai/chat | Send a message to the AI agent |
| POST | /api/interactions/log | Save a new interaction (form submit) |
| GET | /api/interaction/history/{hcp_id} | Get all interactions for an HCP |
| PUT | /api/interaction/edit/{id} | Update an existing interaction |
| GET | /api/hcp | List or search HCP profiles |
| POST | /api/hcp | Create a new HCP profile manually |
| GET | /health | Backend health check |

Interactive docs: **http://localhost:8000/docs**

---

## License

MIT
