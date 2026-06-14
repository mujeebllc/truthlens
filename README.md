# TruthLens

**Theme:** Technology for Civic Good / Open Data & Access to Information (AI for Civic Innovation Hackathon)  
**2-Line Pitch:** TruthLens is an autonomous civic misinformation detection portal that auditing statements using multi-tiered NLP veracity models, Pillow-based JPEG Error Level Analysis (ELA) image forensics, domain reliability indices, and live Google Fact Check APIs.

---

## Architecture Diagram

```
                 [ User Interface ] (frontend/index.html)
                   |            ^
                   v            |
             [   FastAPI Backend Gateway   ] (backend/main.py)
              /      |         |          \
             /       |         |           \
     [Translate] [Image ELA] [Verifier] [Cache & DB]
      langdetect   Pillow    Google API   SQLite (truthlens.db)
      opus-mt                 Local Seed  in-memory dict cache
                             /    |    \
                            /     |     \
                 DistilBERT     BART   Heuristics
                  (LIAR fine)  (Zero)   (Regex)
```

---

## Original Design vs. Implementation Mapping

| Feature from Original Design Doc | Status | Implementation Notes & Production Upgrade Path |
|:---|:---|:---|
| **Text Veracity Classifier** | Implemented (MVP) | Fine-tuned DistilBERT on LIAR dataset. Production path: larger ensemble transformer models (e.g. RoBERTa-large). |
| **Multimedia Forensics/Deepfake Detector** | Implemented (heuristic stand-in) | JPEG Error Level Analysis (ELA) standard deviation variance. Production path: trained CNN (e.g., EfficientNet-B4) on FaceForensics++ or DFDC datasets. |
| **Fact-check Repository Lookup** | Implemented (MVP) | Integrates Google Fact Check Tools API query with Jaccard-overlap local seed fallback. Production path: direct integration with multiple global IFCN fact-checking APIs. |
| **Trust Score Aggregator** | Implemented (MVP) | Custom formula combining text classifier probability, fact-check ratings, domain reputation, and image forensics. Production path: machine-learned model (e.g. XGBoost) trained on historical veracity outcomes. |
| **Source Reliability Database** | Implemented (MVP) | SQLite table pre-seeded with Ad Fontes/MBFC media credibility scores (0-100). Production path: live integration with domain trust APIs like NewsGuard. |
| **Contextual Sources & Justification** | Implemented (MVP) | Template logic falling back to Anthropic Messages API (`claude-sonnet-4-6`). Production path: Dedicated Retrieval-Augmented Generation (RAG) agent using verified sources. |
| **User Feedback Loop** | Implemented (MVP) | UI features thumbs 👍/👎 feedback buttons mapping comments to SQLite. Production path: community voting audit boards with user trust reputations. |
| **Multilingual Support** | Implemented (MVP) | Language detection using `langdetect` + translation via Helsinki-NLP models. Production path: seamless translation using translation models like NLLB-200. |
| **Database/Cache Layer** | Implemented (MVP) | Local SQLite DB + MD5 in-memory dictionary. Production path: PostgreSQL database + Redis caching server. |
| **Real-time browser scanning** | Future Work | UI elements allow inputs from URLs. Production path: Chrome/Firefox browser extension utilizing the API backend. |

---

## Dataset & Model details

### Text Classification Model
- **Dataset:** LIAR Dataset (Wang, 2017) containing ~12.8K labeled PolitiFact statements.
- **Label Collapsing Scheme:** Binary classification:
  - `pants-fire, false, barely-true` -> Class `1` (misleading/misinformation)
  - `half-true, mostly-true, true` -> Class `0` (credible)
- **Base Model:** `distilbert-base-uncased` fine-tuned for sequence classification.
- **Execution Tiers:**
  1. `finetuned-distilbert-liar`: Loaded from `backend/model/truthlens_distilbert/` if offline training succeeds.
  2. `zero-shot-bart`: Falls back to zero-shot classification via `facebook/bart-large-mnli`.
  3. `heuristic`: Local regex rules matching sensationalism, caps lock ratio, and absolute assertions.

### Image Forensics Module
Uses **Error Level Analysis (ELA)**. Resaves the target image at JPEG quality 90, calculates the absolute difference between the source and resaved image, and computes standard deviation variance. Discrepancies point to editing or compression splices.

### Multilingual Module
Detects language with `langdetect`. If `es`, `fr`, `ur`, or `ar` are found, dynamically spins up a translation pipeline using `Helsinki-NLP/opus-mt-{lang}-en` and audits the English translation.

### Fact-Check Integration
Queries the live **Google Fact Check Tools API** (set key via `GOOGLE_FACTCHECK_API_KEY` in `.env`). Falls back to a local Jaccard-overlap search on a seeded database of 10 claims if key is missing, network fails, or no match is found.

### Source Reputation Database
Seeded SQLite table with ratings (0-100) reflecting MBFC credibility ordering for major wire services, governments, and known low-credibility sites.

---

## How to Run

### Prerequisite
Python 3.11+ installed.

### Unix/Linux/macOS/Git Bash
```bash
chmod +x run.sh
./run.sh
```

### Windows (PowerShell native)
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\run.ps1
```

*Note: The first run will trigger dataset download and local fine-tuning (~15–30 min on CPU) if python ML libraries are present. If training is skipped or aborted, the system gracefully boots using the BART zero-shot or heuristic fallbacks.*

---

## API Documentation

### `POST /analyze`
Analyzes statement text.
- **Request Body:**
  ```json
  {
    "text": "Canada legalizes four-day workweek",
    "url": "https://example.com/workweek"
  }
  ```
- **Response Example:**
  ```json
  {
    "id": 1,
    "trust_score": 88,
    "label": "Likely Reliable",
    "fake_probability": 0.12,
    "explanation": "This claim closely matches a known fact-check from Snopes...",
    "factcheck_match": {
       "claim_text": "Canada legalizes four-day workweek",
       "verdict": "true",
       "explanation_snippet": "This is illustrative demo data...",
       "source_name": "Demo Fact-Check Network",
       "source_url": "https://example.com/demo-four-day-workweek",
       "origin": "seeded-demo-data"
    },
    "method": "heuristic",
    "language": "en",
    "translation_applied": false,
    "cached": false
  }
  ```

### `POST /analyze-image`
Accepts a multipart file upload (`file`) and optional form fields `claim_id` or `claim_text` for blended ELA image + text veracity analysis.

### `POST /feedback`
Records 👍/👎 audit votes.
- **Request Body:**
  ```json
  {
    "claim_id": 1,
    "user_vote": "agree",
    "comment": "Accurate prediction"
  }
  ```

### `GET /history`
Returns JSON array of the last 20 analysed claims.

### `GET /health`
Returns `{"status": "ok"}`.

---

## Known Limitations & Future Work
1. **Mock Seed Fallback:** Seeded factcheck details are illustrative for demo presentations.
2. **Fallback Mode:** Depending on the local system resources, the model classifier will downgrade to Zero-Shot BART or Offline Heuristics dynamically to avoid application crashes.
3. **Image forensics:** ELA is a stand-in, susceptible to noise from web resizing. Production requires deepfake faces/GAN classifiers.

---

**Built for AI for Civic Innovation Hackathon — Code for Pakistan x FAST NUCES Islamabad x #GreySoftware x Scrimba**
