# Touchless HCI — Camera-Based AAC System for Bedside Patients

A touchless, camera-based Augmentative and Alternative Communication (AAC) system designed for patients with severe motor impairments. The system combines hand tracking, voice/gesture confirmation, and AI-powered natural language understanding to enable patients to communicate basic needs without physical contact.

This work is part of a Computer Engineering graduation thesis at **Çukurova University**.

## Features

- **3 Interaction Modes** for comparative evaluation:
  - **Hover + Gesture** — dwell on a button, then thumbs-up to confirm / thumbs-down to cancel
  - **Hover + Voice** — dwell on a button, then say "seç" (select) / "iptal" (cancel)
  - **Single-Modal** — dwell on a button for automatic selection
- **7 communication buttons**: Water, Toilet, Emergency (SOS), TV, Light, Family Message, AI Command
- **AI-powered natural language interface** — patient speaks freely in Turkish; an LLM classifies the intent into clinical categories with urgency levels
- **Personalized gesture calibration** — adapts thumb-angle thresholds to each user's anatomy
- **Real-time caregiver web panel** with two tabs:
  - **Clinical Panel** — all patient activity with urgency-coded cards and emergency banner
  - **Family Panel** — filtered view showing only personal/communication messages
- **Two-hand support** — leftmost detected hand's index finger controls the cursor
- **SOS shortcut** — emergency button activates instantly with no confirmation step
- **CSV event logging** — every hover, selection, cancel, and AI event is logged for analysis

## Architecture

```
┌─────────────────────────────────────────┐
│         PATIENT-FACING CLIENT           │
│  ┌──────────────┐  ┌─────────────────┐  │
│  │ MediaPipe    │  │ SpeechRecognition│ │
│  │ Hand Tracking│  │ (tr-TR)          │ │
│  └──────────────┘  └─────────────────┘  │
│  ┌────────────────────────────────────┐ │
│  │  OpenCV UI + Dwell/Gesture Logic   │ │
│  └────────────────────────────────────┘ │
└──────────────┬──────────────────────────┘
               │ HTTPS / JSON
               ▼
┌─────────────────────────────────────────┐
│   Groq LLM API (LLaMA-3.1-8B-Instant)   │
│   Intent classification → JSON          │
└──────────────┬──────────────────────────┘
               │ HTTP POST
               ▼
┌─────────────────────────────────────────┐
│         CAREGIVER WEB PANEL             │
│  Flask + vanilla JS    Clinical + Family│
└─────────────────────────────────────────┘
```

## Demo Buttons

| Button | Turkish Label | Category    | Urgency |
|--------|---------------|-------------|---------|
| SU     | Su İste       | basic need  | normal  |
| WC     | Tuvalete Git  | basic need  | normal  |
| SOS    | Yardım Çağır  | emergency   | urgent  |
| TV     | TV Aç         | comfort     | low     |
| ISIK   | Işığı Aç      | comfort     | low     |
| MSJ    | Aileye Mesaj  | communication| low    |
| AI     | AI Komut      | (dynamic)   | (LLM)   |

## Installation

### Requirements

- Python 3.9 or newer
- A webcam
- A microphone
- Internet connection (for Google Speech API and Groq LLM API)

### Setup

```bash
git clone https://github.com/<your-username>/touchless-hci-aac.git
cd touchless-hci-aac
pip install -r requirements.txt
```

### Configure your LLM API key

Open `aac.py` and replace the placeholder:

```python
GROQ_API_KEY = "your-groq-api-key-here"
```

A free Groq API key can be obtained from https://console.groq.com.

## Running the System

The system has two components that run independently.

### 1. Start the caregiver web panel

```bash
python web_panel_app.py
```

The panel becomes available at `http://localhost:5000`. Phones on the same Wi-Fi can connect via `http://<your-laptop-ip>:5000`.

### 2. Start the patient client

```bash
python aac.py
```

The client opens in full-screen mode. Press `ESC` at any time to exit.

### Keyboard shortcuts (during a session)

| Key   | Action                |
|-------|-----------------------|
| `M`   | Skip to next mode     |
| `R`   | Restart current mode  |
| `Q` / `ESC` | Quit             |

## Experimental Protocol

Each participant completes the same six-task scenario in all three modes:

1. Request water (SU)
2. Go to toilet (WC)
3. Call for help (SOS)
4. Turn on TV (TV)
5. Turn on light (ISIK)
6. Send a family message (MSJ)

After each mode, participants fill out a questionnaire combining:

- **System Usability Scale (SUS)** — 10 items, 5-point Likert
- **NASA Task Load Index (NASA-TLX)** — 6 dimensions, 20-point scale
- **4 open-ended questions** about modality preference and improvements

The questionnaire is included as a Word document in this repository (`docs/SUS_NASA_Questionnaire.docx`).

## Repository Structure

```
touchless-hci-aac/
├── aac.py                          # Main patient-facing client
├── web_panel_app.py                # Caregiver Flask panel
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── LICENSE                         # MIT License
├── docs/
│   ├── SUS_NASA_Questionnaire.docx # User-study questionnaire
│   ├── Chapter1_Introduction.docx  # Thesis Introduction chapter
│   └── scenarios.md                # Five patient scenarios
├── logs/                           # Generated CSV event logs
└── messages.json                   # Panel message store
```

## Configuration Parameters

The most important tunable parameters are at the top of `aac.py`:

```python
DWELL_TIME      = 1.0   # seconds the cursor must stay on a button
GESTURE_TIMEOUT = 6.0   # max wait for gesture confirmation
GESTURE_HOLD    = 0.4   # gesture must be held continuously
VOICE_TIMEOUT   = 6.0   # max wait for voice command
PARTICIPANT_ID  = "P01" # used in the log filename
MODE_ORDER      = ["gesture", "voice", "single"]
```

## Technologies Used

- **MediaPipe Hands** — 21-landmark hand tracking
- **OpenCV** — frame capture, UI rendering, full-screen display
- **SpeechRecognition** (Google Web Speech API backend) — Turkish ASR
- **Groq Cloud** with LLaMA-3.1-8B-Instant — natural language intent classification
- **Flask** — caregiver web panel
- **Python `threading` + `queue`** — concurrent microphone/LLM management

## Limitations

- Speech recognition requires an active internet connection
- The system has not been tested with actual patients yet — participants are non-clinical volunteers
- The gesture vocabulary is binary (thumbs-up / thumbs-down) and assumes preserved thumb function
- Two-hand support detects the leftmost hand only; multi-hand cursor switching is not implemented
- The Groq LLM API call adds a network-dependent latency of approximately 1–2 seconds

## Academic Context

This implementation accompanies a graduation thesis submitted to the Department of Computer Engineering, Çukurova University, in 2026. The thesis evaluates the three interaction modes through a within-subjects user study with five participants, comparing modality preferences using SUS and NASA-TLX metrics.

## License

MIT License — see `LICENSE` for details.

## Acknowledgements

Developed under the supervision of the Çukurova University Department of Computer Engineering. Hand tracking is powered by Google's MediaPipe; speech recognition by Google's Web Speech API; natural language understanding by Meta's LLaMA-3.1 served via Groq Cloud.
