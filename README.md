# 📞 AI Pharmacy Voice Agent

<div align="center">

A real-time AI phone assistant built with **Twilio**, **Nginx**, **Python WebSockets**, and the **Deepgram Voice Agent API**.

The system handles live phone calls, streams caller audio to an AI voice agent, executes pharmacy-related backend actions through function calling, and returns spoken responses back to the caller in real time.

<br>

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Twilio](https://img.shields.io/badge/Twilio-Voice%20Calls-F22F46?style=for-the-badge&logo=twilio&logoColor=white)
![Deepgram](https://img.shields.io/badge/Deepgram-Voice%20Agent-13EF93?style=for-the-badge)
![Nginx](https://img.shields.io/badge/Nginx-Reverse%20Proxy-009639?style=for-the-badge&logo=nginx&logoColor=white)
![WebSockets](https://img.shields.io/badge/WebSockets-Real--Time-010101?style=for-the-badge)

</div>

---

## ✨ Overview

This project is a **real-time AI phone assistant** designed for a pharmacy-style customer support workflow.

A customer calls a Twilio phone number, their live audio is streamed to a Python WebSocket backend, forwarded to the **Deepgram Voice Agent API**, processed by an AI agent, and then returned as spoken audio during the same call.

The assistant can:

- answer questions about available medications;
- provide drug descriptions, prices, and predefined quantities;
- place medication orders;
- check the status of existing orders;
- ask the customer to clearly spell their full name before creating an order;
- confirm all order details before finalizing a transaction.

The current version uses a lightweight **in-memory pharmacy database** for medications and orders, making it a practical prototype for a larger voice automation system. :contentReference[oaicite:0]{index=0}

---

## 🚀 Key Features

### ☎️ Real Phone Call Integration
- Accepts live audio streams from **Twilio Media Streams**
- Processes Twilio WebSocket events such as:
  - `connected`
  - `start`
  - `media`
  - `stop`
- Tracks the `streamSid` to send AI-generated audio back to the correct live call. :contentReference[oaicite:1]{index=1}

### 🎙 Real-Time Bidirectional Audio
- Receives caller audio in real time
- Buffers and forwards inbound audio to Deepgram
- Sends synthesized AI audio back through Twilio during the same call. :contentReference[oaicite:2]{index=2}

### 🧠 AI Voice Agent
- Uses the **Deepgram Voice Agent API**
- Speech input uses:
  - μ-law audio
  - 8 kHz sample rate
  - Deepgram `nova-3`
- Reasoning uses:
  - `gpt-4o-mini`
- Speech output uses:
  - Deepgram `aura-2-thalia-en`. :contentReference[oaicite:3]{index=3}

### ⚡ Natural Interruption Handling
- Supports **barge-in**
- When the user begins speaking while the assistant is talking, the system sends a `clear` event to Twilio and stops queued audio playback, making the interaction feel more natural. :contentReference[oaicite:4]{index=4}

### 🛠 Function Calling
The voice agent can call local Python backend functions during a conversation:

| Function | Purpose |
|---|---|
| `get_drug_info` | Returns drug name, description, price, and predefined quantity |
| `place_order` | Creates a new order for a customer |
| `lookup_order` | Retrieves an existing order by order ID |

These tools are defined in `pharmacy_functions.py` and are invoked from the real-time conversation loop in `main.py`. :contentReference[oaicite:5]{index=5}

---

## 🏗 System Architecture

```text
Incoming Phone Call
        │
        ▼
Twilio Programmable Voice
        │
        ▼
Twilio Media Stream
        │
        ▼
Nginx Reverse Proxy
        │
        ▼
Python WebSocket Server
        │
        ▼
Deepgram Voice Agent API
        │
        ├── Speech-to-speech conversation
        ├── LLM reasoning with gpt-4o-mini
        ├── Text-to-speech generation
        └── Function call requests
                    │
                    ▼
        Pharmacy Backend Tools
        ├── Drug information lookup
        ├── Order creation
        └── Order status retrieval
                    │
                    ▼
AI response streamed back to caller

The repository contains the Python WebSocket backend and voice-agent logic.
Twilio phone routing and Nginx reverse-proxy configuration were used in the deployment/testing setup but are not currently included as configuration files in this repository.

🔄 How It Works
A customer calls a configured Twilio phone number.
Twilio opens a live Media Stream WebSocket connection.
Nginx exposes and forwards the external WebSocket connection to the local Python server.
The Python application receives Twilio audio events.
Caller audio is decoded from Base64 and buffered.
Audio chunks are forwarded to the Deepgram Voice Agent API.
Deepgram processes the speech and generates:
spoken audio responses;
control events;
function call requests when backend information is needed.
When a function call is requested, Python executes the matching backend tool:
medication lookup;
order placement;
order lookup.
The tool result is returned to Deepgram.
Deepgram synthesizes the final spoken answer.
The Python backend streams the audio back to Twilio so the caller hears the response live.
💊 Pharmacy Assistant Capabilities

The agent is configured to behave as a professional pharmacy assistant. It can:

1. Provide Drug Information

Example:

User: What is ibuprofen?
Agent: Ibuprofen is an anti-inflammatory medication for pain and inflammation management.
2. Place Orders

Before placing an order, the agent is instructed to:

verify that the medication exists;
ask for the customer's full name;
request clear spelling if the name is unclear;
confirm customer name, drug name, and order details before finalizing.
3. Look Up Existing Orders

The customer can ask for an order status by providing the order ID, and the system retrieves the stored order information from the in-memory orders database.

🧪 Example Conversation
Agent:
Hello! I'm your pharmacy assistant. I can help you with drug information,
placing orders, and checking order status. When placing orders, I'll need
your full name spelled out clearly and will confirm all details with you.
How can I assist you today?

User:
What is ibuprofen?

Agent:
Ibuprofen is an anti-inflammatory medication for pain and inflammation management.
Its price is $7.99, and the predefined order quantity is 20.

User:
I want to order ibuprofen.

Agent:
Certainly. Please provide your full name and spell it out clearly.

User:
Bohdan Kukuruza. B-O-H-D-A-N, K-U-K-U-R-U-Z-A.

Agent:
Thank you. To confirm: you would like to place an order for Ibuprofen
under the name Bohdan Kukuruza. Should I proceed?

User:
Yes.

Agent:
Your order has been placed successfully.

The exact medication names, prices, and quantities are defined in the in-memory pharmacy catalog in pharmacy_functions.py.

📁 Project Structure
voice-agent/
│
├── main.py                   # Real-time WebSocket server and Twilio ↔ Deepgram audio pipeline
├── config.json               # Deepgram Voice Agent settings, prompt, tools, greeting
├── pharmacy_functions.py     # Drug catalog, in-memory orders, callable backend functions
├── pyproject.toml            # Project metadata and dependencies
├── uv.lock                   # Locked dependency versions
├── .python-version           # Python version reference
├── .gitignore
└── README.md

The repository currently contains five visible commits and is implemented entirely in Python.

🔍 File Breakdown
main.py

Responsible for the real-time audio and WebSocket pipeline:

connects to the Deepgram Agent WebSocket;
loads voice-agent configuration from config.json;
receives media events from Twilio;
forwards buffered inbound audio to Deepgram;
receives text control messages and raw audio from Deepgram;
handles barge-in interruption;
executes function call requests;
streams generated audio responses back to Twilio.
config.json

Defines the assistant configuration:

input and output audio format;
Deepgram speech recognition model;
OpenAI reasoning model;
agent prompt;
function-calling schemas;
text-to-speech voice;
greeting message.
pharmacy_functions.py

Contains the lightweight backend layer:

in-memory drug catalog;
in-memory order storage;
get_drug_info;
place_order;
lookup_order;
FUNCTION_MAP used by the main WebSocket loop.
🧰 Tech Stack
Area	Technologies
Telephony	Twilio Programmable Voice, Twilio Media Streams
Reverse Proxy	Nginx
AI Voice Agent	Deepgram Voice Agent API
LLM Reasoning	OpenAI gpt-4o-mini via Deepgram agent configuration
Backend	Python, asyncio, WebSockets
Audio	μ-law, 8 kHz audio streaming
Tool Calling	Custom Python functions
Configuration	JSON, environment variables
⚙️ Local Setup
1. Clone the repository
git clone https://github.com/bohdankukuruza/voice-agent.git
cd voice-agent
2. Create and activate a virtual environment
python -m venv venv
Windows
venv\Scripts\activate
macOS / Linux
source venv/bin/activate
3. Install dependencies

Using uv:

uv sync

Or install the required runtime packages manually:

pip install websockets python-dotenv

The project uses websockets and python-dotenv in main.py.

4. Create a .env file

Create a .env file in the project root:

DEEPGRAM_API_KEY=your_deepgram_api_key

The server reads this key at startup and raises an exception if it is missing.

5. Run the Python WebSocket server
python main.py

Expected console output:

Started server.

The local WebSocket server listens on:

ws://localhost:5000

☎️ Twilio Integration

The project is designed to work with Twilio Media Streams.

Twilio should be configured to connect an incoming phone call to the WebSocket endpoint exposed through your public reverse proxy. The Python backend expects Twilio-style WebSocket messages containing:

connected
start
media
stop

The server reads the Twilio streamSid from the start event and uses it when sending generated audio back to the active call.

🌐 Nginx Reverse Proxy

During development/testing, Nginx can be used as a reverse proxy to expose the local WebSocket backend to Twilio.

Conceptually:

Public WSS endpoint
        │
        ▼
Nginx
        │
        ▼
ws://localhost:5000

This lets Twilio reach the local real-time WebSocket application from the public internet.

Note: The Nginx configuration is not currently stored in this repository.

💾 Data Storage Notes

This project currently uses in-memory Python dictionaries:

DRUG_DB stores medications;
ORDERS_DB stores generated orders;
order IDs are incremented at runtime;
orders disappear when the app restarts.

A production version would typically move this logic to a persistent database such as PostgreSQL.

🧭 Potential Improvements
Persist orders in PostgreSQL
Store real call transcripts
Add structured logging and error monitoring
Add an admin dashboard for order management
Improve medication search with fuzzy matching
Add unit tests for backend tools
Add Docker setup
Include Twilio webhook and Nginx configuration examples
Deploy the service to a cloud platform
👨‍💻 Author

Bohdan Kukuruza

<div align="center">

⭐ If you found this project interesting, feel free to star the repository.

</div> ```