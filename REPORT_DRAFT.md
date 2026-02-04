# Rapport: Utveckling av Finans-AI

## 1. Inledning
Finansiell analys kräver ofta genomgång av omfattande PDF-dokument såsom årsredovisningar och kvartalsrapporter. Att manuellt extrahera nyckeltal och trender från dessa dokument är tidskrävande och kan vara felbenäget.

Syftet med detta projekt, "Finans-AI", är att automatisera och demokratisera tillgången till finansiell analys. Genom att bygga en applikation som kombinerar **Retrieval-Augmented Generation (RAG)** med en modern språkmodell (LLM), möjliggör vi för användare att ladda upp rapporter och ställa frågor på naturligt språk. Systemet kan inte bara svara på frågor utan även visualisera trender genom grafer och källhänvisa direkt till specifika sidor i dokumenten.

## 2. Teori
För att lösa problemet har följande teknologier valts:

### 2.1 Retrieval-Augmented Generation (RAG)
RAG är en teknik som kombinerar styrkan hos en förtränad språkmodell (LLM) med extern data. Istället för att enbart lita på modellens inbyggda kunskap (vilket kan leda till "hallucinationer"), hämtar systemet först relevant text från de uppladdade dokumenten och skickar detta som underlag ("kontext") till modellen.

### 2.2 Vektordatabaser och Embeddings
För att datorn ska förstå semantisk likhet används **Embeddings** (i detta fall Googles `text-embedding-004`). Detta omvandlar textstycken till numeriska vektorer. Dessa lagras i **ChromaDB**, en lokal vektordatabas som möjliggör blixtsnabb sökning efter relevant information baserat på användarens fråga.

### 2.3 Large Language Models (LLM)
Vi använder Googles **Gemini 2.0 Flash** via API. Denna modell valdes för sin snabbhet, kostnadseffektivitet och stora kontextfönster, vilket gör den lämplig för att bearbeta finansiella texter.

## 3. Metod
Utvecklingsprocessen har varit iterativ och agil, där vi stegvis lagt till funktionalitet baserat på testning och användarupplevelse.

### 3.1 Databearbetning (Backend)
Applikationen är byggd i **Python** med ramverket **LangChain**. Processen ser ut som följer:
1.  **PDF-parsing:** Dokumenten läses in via `PyPDFLoader`.
2.  **Chunking:** Texten delas upp i mindre stycken (chunks) om 1000 tecken med 200 teckens överlapp. Detta är kritiskt för att inte bryta meningsbyggnad.
3.  **Metadataberikning:** Varje textstycke berikas med källfilens namn och sidnummer direkt i texten (t.ex. `[Source: rapport.pdf] [Page 5]`). Detta tvingar språkmodellen att se källan och möjliggör korrekta citeringar i svaret.

### 3.2 Visualisering och Gränssnitt
Vi valde **Streamlit** som frontend-ramverk för att snabbt kunna bygga ett interaktivt gränssnitt utan komplex webbutveckling (HTML/CSS).
*   **Prompt Engineering för grafer:** För att generera grafer instruerar vi LLM:en via en strikt system-prompt att returnera data i ett specifikt JSON-format om svaret innehåller siffror. Applikationen fångar sedan upp detta JSON-block och renderar en interaktiv **Plotly**-graf.
*   **Responsiv Design:** Vi implementerade ett valbart layout-läge där användaren kan växla mellan "Desktop (Split View)" och "Mobile (Tabs)" för att optimera läsbarheten.

### 3.3 Hantering av tekniska utmaningar
Under utvecklingen stötte vi på problem med fil-låsningar i Windows när ChromaDB försökte skriva till disk. Detta löstes genom att generera unika sessionskataloger (`session_<uuid>`) för varje analys, samt en "lazy cleanup"-funktion som städar bort gamla filer vid nästa uppstart.

## 4. Resultat och Diskussion
Resultatet är en fungerande prototyp, "Finans-AI", som klarar av att:
*   Analysera flera uppladdade PDF-filer samtidigt.
*   Generera automatiska sammanfattningar med grafer (Omsättning, Vinst, Risker).
*   Hantera konversationer med minne (chat history) som sparas lokalt.

En viktig insikt var risken för "Blank Canvas Paralysis" – att användaren inte vet vad hen ska fråga. Detta löste vi genom att implementera "Quick Start"-knappar (t.ex. "Sammanfatta", "Risker") och ett välkomstmeddelande, vilket tydligt ökade användbarheten.

Tillförlitligheten har säkrats genom "Show Sources"-funktionen, där användaren kan verifiera AI:ns påståenden mot originaltexten, vilket är avgörande i finansiella sammanhang.

## 5. Slutsatser
Projektet visar att det går att bygga kraftfulla analysverktyg med relativt enkla medel genom att kombinera moderna LLM:er med strukturerad datahantering (RAG). Valet av Streamlit och Python möjliggjorde snabb iteration, men för en produktionsmiljö skulle en mer robust databaslösning än lokala filer krävas.

## 6. Självreflektion
*   **Mest intressant:** Att se hur väl modellen kan extrahera strukturerad data (JSON) för grafer ur ostrukturerad text enbart genom instruktioner (prompt engineering).
*   **Utmanande:** Att hantera beroenden och filsystemsproblem (Windows-låsningar) samt att säkerställa att graf-datan var konsekvent (t.ex. att modellen inte blandar "miljoner" och "tusental").
*   **Framtida utveckling:** Jag skulle fokusera mer på att jämföra data över flera olika dokument/år automatiskt, kanske genom att använda "Agentic workflows" där AI:n själv kan söka upp information i flera steg.
