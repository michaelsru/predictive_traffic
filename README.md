# Corridor Intelligence Dashboard

## Setup Instructions

### 1. Backend Setup
The backend requires Python 3.11+.
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Set your Anthropic API key:
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

Run the backend server:
```bash
python main.py
```
The FastAPI server will start on `http://localhost:8000` and the simulator thread will begin generating data.

### 2. Frontend Setup
In a new terminal, from the project root:
```bash
npm install
npm run dev
```
The Vite dev server will start (typically on `http://localhost:5173`).

### Usage
- Open the frontend in your browser.
- Use the scenario buttons (Normal, Forming, Incident) to change the simulated traffic conditions.
- Ask questions in the chat panel (e.g., "What is the current status of the corridor?").
- The LLM will analyze the live data and respond with a narrative, talking points, and map highlights.
