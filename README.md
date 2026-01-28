# CDC VIT Assessment Portal Clone

A full-stack clone of the CDC VIT Assessment Portal built with:
- **Frontend**: Vite + React + TypeScript
- **Backend**: Python FastAPI + SQLAlchemy + SQLite

## Project Structure

```
Hiring Pro/
├── frontend/          # React + TypeScript frontend
│   ├── src/
│   │   ├── components/  # Reusable UI components
│   │   ├── pages/       # Page components
│   │   ├── services/    # API services
│   │   └── types/       # TypeScript types
│   └── ...
│
└── backend/           # FastAPI backend
    ├── app/
    │   ├── models/      # SQLAlchemy models
    │   ├── schemas/     # Pydantic schemas
    │   ├── routers/     # API routes
    │   └── services/    # Business logic
    └── ...
```

## Getting Started

### Backend Setup

```bash
cd backend

# Create virtual environment (optional)
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Seed database with demo data
python seed_data.py

# Start server
uvicorn app.main:app --reload
```

Backend runs at: http://localhost:8000
API docs at: http://localhost:8000/docs

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend runs at: http://localhost:5173

## Demo Credentials

After running `seed_data.py`:
- **Email**: vinayak.shukla@gmail.com
- **Password**: password123

## Features

- ✅ JWT Authentication
- ✅ Dashboard with skill stats
- ✅ Jobs listing with filters
- ✅ Assessments & badges
- ✅ User profile
- ✅ Responsive sidebar navigation
