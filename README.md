# Finans-AI

## Om projektet
Finans-AI är ett interaktivt verktyg utvecklat för att analysera finansiella rapporter (PDF) med hjälp av generativ AI. Projektet syftar till att förenkla genomgången av tunga dokument som årsredovisningar och kvartalsrapporter. Genom att använda tekniken RAG (Retrieval Augmented Generation) kan användaren ställa frågor till sina dokument, få intelligenta sammanfattningar och visualisera ekonomiska trender direkt i webbläsaren.

## Funktioner
*   **Dokumentanalys:** Ladda upp en eller flera PDF-filer (t.ex. årsredovisningar) för analys.
*   **AI-Chatt:** Ställ frågor om intäkter, risker, VD-ord eller specifika siffror och få svar baserat på dokumentens innehåll.
*   **Transparens:** Alla svar innehåller källhänvisningar (t.ex. "[Källa: rapport.pdf] [Sida 5]") och användaren kan klicka för att läsa exakt det stycke som AI:n baserar svaret på.
*   **Automatiska Grafer:** Systemet identifierar finansiell data och genererar automatiskt interaktiva grafer (linje-, stapel- och cirkeldiagram) för att visualisera trender.
*   **Spara Analyser:** Sessioner sparas lokalt så att du kan återvända till tidigare analyser via historik-panelen.

## Installation och Start

För att köra detta projekt lokalt behöver du Python installerat på din dator.

### 1. Förbered miljö
Det rekommenderas att använda en virtuell miljö, men det är inget krav.
Öppna din terminal/kommandotolk i projektets mapp.

### 2. Installera beroenden
Installera de nödvändiga biblioteken som listas i `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 3. Konfigurera API-nyckel
Applikationen använder Google Gemini (via LangChain) och kräver en API-nyckel.
1.  Skapa en ny fil i projektets rotmapp och döp den till `.env`.
2.  Öppna filen och lägg till din nyckel på följande format:

```text
GOOGLE_API_KEY=din_google_api_nyckel_här
```

*(Om du saknar en nyckel kan du skaffa en gratis via Google AI Studio).*

### 4. Starta applikationen
Kör programmet med Streamlit:

```bash
streamlit run app.py
```

Applikationen kommer nu att starta och öppnas automatiskt i din standardwebbläsare (vanligtvis på adressen `http://localhost:8501`).

## Projektstruktur

*   **`app.py`**: Huvudapplikationen som bygger användargränssnittet med Streamlit. Här hanteras användarinteraktion, filuppladdning och rendering av chatt/grafer.
*   **`backend.py`**: "Motorn" i systemet. Här finns logiken för att läsa PDF:er, skapa vektorembäddningar (embeddings), kommunicera med AI-modellen och generera grafdata.
*   **`chat_manager.py`**: Hanterar lagring och hämtning av chatthistorik och sessioner i JSON-format.
*   **`requirements.txt`**: Lista över alla externa Python-paket som krävs.

## Teknologier
Projektet är byggt med följande teknologier:
*   **Python**
*   **Streamlit** (Frontend/UI)
*   **LangChain** (Ramverk för AI-applikationer)
*   **Google Gemini** (LLM och Embeddings)
*   **ChromaDB** (Vektordatabas för sökning i dokument)
*   **Plotly** (Grafvisualisering)
