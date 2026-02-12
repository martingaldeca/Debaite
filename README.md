
# Debaite Web App

A modern AI Debate Platform transforming the command-line experience into a real-time web application.

## Prerequisites

- Node.js (v25 recommended via `.nvmrc`)
- pnpm
- Docker and Docker Compose
- API Keys (OpenAI, Anthropic, Gemini, etc.)

## Setup

1. **Environment Variables**:
   Create a `.env` file in `backend/.env` with your API keys:
   ```bash
   OPENAI_API_KEY=sk-...
   GEMINI_API_KEY=...
   ANTHROPIC_API_KEY=...
   ```

2. **Frontend Dependencies**:
   ```bash
   cd frontend
   pnpm install
   ```

## Running the Application

To start both the backend (Docker) and frontend (Next.js) concurrently:

```bash
cd frontend
pnpm run dev
```

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000

## Features

- **Configuration**: Set up debates with specific topics and AI models.
- **Live Debate**: Watch the debate unfold in real-time with visual avatars and streaming transcript.
- **Results**: Analyze past debates, winners, and reasoning scores.

## Architecture

- **Backend**: Python FastAPI with Server-Sent Events (SSE) for streaming. Runs in Docker.
- **Frontend**: Next.js 16 (App Router), Tailwind CSS, Framer Motion, Recharts.
- **Data**: JSON-based storage for logs and results (in `backend/debate_results`).

## Tests

To run backend unit tests:
```bash
# Inside backend container or with python env
cd backend
pytest
```
