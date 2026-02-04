# Finans-AI (React + FastAPI)

Detta projekt är en AI-driven applikation för att analysera finansiella rapporter (PDF). Den består av en **FastAPI** backend och en **React** frontend.

## Förutsättningar

*   Python 3.10+
*   Node.js 18+
*   Google API Key (för Gemini-modeller)

## Installation

### 1. Backend (Python)

Gå till roten av projektet:

1.  Skapa en virtuell miljö (rekommenderas):
    ```bash
    python -m venv venv
    source venv/bin/activate  # Mac/Linux
    # venv\Scripts\activate  # Windows
    ```

2.  Installera beroenden:
    ```bash
    pip install -r requirements.txt
    ```

3.  Skapa en `.env` fil i roten (om den inte finns) och lägg till din API-nyckel:
    ```
    GOOGLE_API_KEY=din_api_nyckel_här
    ```

### 2. Frontend (React)

Gå till frontend-mappen:

```bash
cd frontend
npm install
```

## Köra Applikationen

Du behöver köra både backend och frontend samtidigt.

### Starta Backend

Från roten av projektet:

```bash
uvicorn backend.main:app --reload --port 8000
```

### Starta Frontend

Öppna en ny terminal, gå till `frontend` mappen:

```bash
cd frontend
npm run dev
```

Applikationen kommer att vara tillgänglig på `http://localhost:5173` (eller den port Vite anger).

## Struktur

*   `backend/`: Innehåller all Python-kod och API-logik.
*   `frontend/`: Innehåller React-applikationen.
*   `chroma_data/`: (Skapas automatiskt) Lagrar vektor-databasen.
*   `temp_pdf/`: (Skapas automatiskt) Tillfällig lagring av uppladdade filer.

## Funktioner

*   **Ladda upp PDF:** Ladda upp årsredovisningar eller kvartalsrapporter.
*   **Chatta:** Ställ frågor om innehållet.
*   **Visualisering:** Automatiska grafer för finansiell data (omsättning, vinst, etc).
*   **Historik:** Spara och återuppta tidigare analyser.
