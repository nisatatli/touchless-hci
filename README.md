# Touchless HCI — Camera-Based AAC System for Bedside Patients

A touchless, camera-based AAC system for patients with motor impairments. Combines hand tracking, voice and gesture confirmation, and AI-powered natural language understanding so patients can communicate without physical contact.

Graduation thesis project, Computer Engineering, Çukurova University.

## Features

- **3 interaction modes:** Hover + Gesture, Hover + Voice, Single-modal hover
- **7 buttons:** Water, Toilet, SOS, TV, Light, Family Message, AI Command
- **Personalized gesture calibration** (thumb angle per user)
- **LLM-based intent classification** (LLaMA-3.1 via Groq Cloud) for free-form Turkish speech
- **Caregiver web panel** with clinical and family tabs
- **CSV event logging** for analysis

## Requirements

- Python 3.9+
- Webcam and microphone
- Internet connection (for speech recognition and LLM)

## Setup

```bash
git clone https://github.com/nisatatli/touchless-hci.git
cd touchless-hci
pip install -r requirements.txt
```

Get a free API key from https://console.groq.com and paste it into `aac.py`:

```python
GROQ_API_KEY = "your-key-here"
```

## Usage

Run the caregiver panel and the patient client in separate terminals:

```bash
python web_panel_app.py    # opens at http://localhost:5000
python aac.py              # full-screen patient interface
```

Press `ESC` to exit, `M` to skip to next mode, `R` to restart.

## Repository Structure
touchless-hci/
├── aac.py

├── web_panel_app.py

├── requirements.txt

├── LICENSE

└── README.md

## Technologies

MediaPipe (hand tracking) · OpenCV · SpeechRecognition (Google Web Speech API) · Groq Cloud + LLaMA-3.1-8B-Instant · Flask

## License

MIT
