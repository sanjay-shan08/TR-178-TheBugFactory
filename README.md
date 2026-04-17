# FloorSense AI 🗺️

> An AI-powered indoor accessibility and navigation system for the visually impaired.

FloorSense AI transforms any floor plan image into a fully accessible, audio-guided navigation experience — complete with tactile SVG maps, screen-reader HTML, real-time obstacle detection, and hands-free voice control. No installation required. Works in any modern browser.

**Live Demo:** [tr-178-thebugfactory.onrender.com](https://tr-178-thebugfactory.onrender.com) *(backend)*

---

## Features

- **AI Floor Plan Analysis** — Upload any floor plan image; Groq vision extracts rooms, corridors, exits, and connections automatically
- **Tactile SVG Maps** — BANA-compliant high-contrast maps suitable for Braille displays and tactile embossing
- **Screen Reader HTML** — ARIA-landmark accessible floor plan with full keyboard navigation
- **Audio Guide** — Turn-by-turn spoken navigation powered by A* pathfinding and Web Speech API
- **Live Camera Navigation** — Real-time obstacle detection and indoor sign reading via Groq vision
- **Continuous Voice Control** — Hands-free command interface; always listening, zero button presses required
- **Step & Turn Detection** — Accelerometer and gyroscope sensor fusion for physical navigation feedback
- **PWA** — Installable Progressive Web App, works on any device without an app store

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite · Tailwind CSS · PWA |
| Backend | FastAPI (Python 3.11) |
| AI Vision | Groq API · `meta/llama-4-scout-17b-16e-instruct` |
| Pathfinding | NetworkX · A* algorithm |
| Map Rendering | Jinja2 SVG templates · BANA tactile standard |
| Voice Input | Web Speech API — SpeechRecognition (continuous) |
| Voice Output | Web Speech API — speechSynthesis |
| Deployment | Vercel (frontend) · Render (backend) |

---

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, CORS, router registration
│   │   ├── routers/
│   │   │   ├── pipeline.py          # Floor plan analysis endpoint
│   │   │   ├── live_nav.py          # Obstacle detection & OCR endpoints
│   │   │   ├── health.py            # Groq connectivity check
│   │   │   └── voice_control.py     # Whisper-based voice transcript
│   │   ├── services/
│   │   │   ├── vision_service.py    # Groq vision · floor plan parsing
│   │   │   ├── detection_service.py # Groq vision · live obstacle detection
│   │   │   ├── generators.py        # SVG · ARIA HTML · TTS text generation
│   │   │   └── graph_engine.py      # NetworkX graph · A* pathfinding
│   │   ├── models/
│   │   │   ├── schemas.py           # Pydantic v2 · FloorPlanData, Node, Edge
│   │   │   └── detection_schemas.py # Detection, BoundingBox, OCRResponse
│   │   └── templates/
│   │       └── bana_tactile.svg.jinja  # BANA-compliant SVG template
│   ├── requirements.txt
│   └── .env                         # GROQ_API_KEY, DETECTION_MODE
│
└── frontend/
    ├── src/
    │   ├── App.jsx          # Main app · floor plan mode · voice command handler
    │   ├── LiveNav.jsx      # Live navigation · camera · sensors · detection
    │   ├── VoiceBot.jsx     # Continuous speech recognition · intent matching
    │   └── api.js           # Axios instance with VITE_API_URL base URL
    ├── public/
    │   └── manifest.json    # PWA manifest
    └── vite.config.js       # Vite config · /api proxy for local dev
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- A free [Groq API key](https://console.groq.com) (no credit card required)

### 1. Clone the repo

```bash
git clone https://github.com/sanjay-shan08/TR-178-TheBugFactory.git
cd TR-178-TheBugFactory
```

### 2. Backend setup

```bash
cd backend
pip install -r requirements.txt
```

Create a `.env` file in `backend/`:

```env
GROQ_API_KEY=your_groq_api_key_here
DETECTION_MODE=real
```

Start the backend:

```bash
uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`

### 3. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`

> The Vite dev server proxies `/api/*` requests to `localhost:8000` automatically — no extra config needed for local development.

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Default |
|---|---|---|
| `GROQ_API_KEY` | Your Groq API key from console.groq.com | — |
| `DETECTION_MODE` | `real` uses Groq vision · `mock` uses static demo data | `mock` |

### Frontend (Vercel / `.env.production`)

| Variable | Description |
|---|---|
| `VITE_API_URL` | Full URL of your deployed Render backend e.g. `https://your-app.onrender.com` |

---

## Deployment

### Backend → Render

1. Create a new **Web Service** on [render.com](https://render.com)
2. Connect your GitHub repo
3. Set **Root Directory** to `backend`
4. **Build command:** `pip install -r requirements.txt`
5. **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Add environment variables: `GROQ_API_KEY` and `DETECTION_MODE=real`

### Frontend → Vercel

1. Import your repo on [vercel.com](https://vercel.com)
2. Set **Root Directory** to `frontend`
3. Add environment variable: `VITE_API_URL=https://your-render-url.onrender.com`
4. Deploy — Vercel auto-detects Vite

---

## Voice Commands

Say any of these at any time — the mic is always on:

| Command | Action |
|---|---|
| *"analyze floor plan"* | Runs the pipeline |
| *"live navigation"* | Switches to camera mode and starts navigation |
| *"play audio guide"* | Reads the navigation route aloud |
| *"show tactile map"* | Switches to the SVG tab |
| *"show screen reader"* | Switches to the ARIA HTML tab |
| *"stop speaking"* | Silences audio output |
| *"reset"* | Clears back to the upload screen |
| *"help"* | Lists all available commands |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/pipeline/process` | Analyse a floor plan image (multipart) |
| `POST` | `/api/pipeline/process-mock` | Run with built-in mock floor plan |
| `POST` | `/api/live-nav/detect` | Detect obstacles in a camera frame |
| `POST` | `/api/live-nav/ocr` | Read indoor signage from a camera frame |
| `GET` | `/api/health` | Check Groq API connectivity |

---

## Accessibility Standards

- SVG output follows [BANA Tactile Graphics Guidelines](http://www.brailleauthority.org/tg/)
- HTML output uses ARIA landmark roles (`main`, `navigation`, `region`)
- All interactive elements have `aria-label` and keyboard focus support
- Audio guide text is designed for natural speech synthesis delivery

---

## Contributing

Pull requests are welcome. For major changes please open an issue first.

---

## License

MIT

---

*Built for TENSOR'26 Hackathon · Team: The Bug Factory*
