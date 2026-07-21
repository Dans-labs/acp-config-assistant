# 🎯 ACP Config Assistant (ACA)

[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)
[![UV](https://img.shields.io/badge/packaging-UV-FFD43B)](https://github.com/astral-sh/uv)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)

The **ACP Config Assistant (ACA)** is a FastAPI service that manages and provides repository configurations for the Automated Curation Platform (ACP). It serves as a central configuration hub, enabling ACP to dynamically retrieve target repository details, bridge plugins, transformers, and other essential settings.

---

## ✨ Features

- **Dynamic Configuration Management** — Store and retrieve repository configurations on-demand
- **Multiple Repository Support** — Manage configurations for multiple target repositories
- **RESTful API** — Easy-to-use REST endpoints for configuration operations
- **Metadata Transformation** — Support for metadata format conversions and transformations
- **Keycloak Integration** — Secure authentication with OAuth2 and Keycloak
- **OpenTelemetry Support** — Built-in observability with OTLP for tracing and monitoring

---

## 🛠 Installation

### Prerequisites
- Python 3.12 or newer
- [UV](https://github.com/astral-sh/uv) (recommended)

### 🚀 Quick Start

1. **Create virtual environment and install dependencies:**
   ```bash
   cd services/aca
   uv venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv sync
   ```

2. **Run the application:**
   ```bash
   python -m src.main
   ```

3. **Access the API:**
   - Swagger UI: `http://localhost:2810/docs`
   - ReDoc: `http://localhost:2810/redoc`

---

## 🎯 Running from PyCharm

### Setup

1. **Open the project in PyCharm:**
   - File → Open → `/Users/akmi/dev/work/dans/orchestrator-acp-poc`

2. **Configure Python Interpreter:**
   - PyCharm → Preferences (or File → Settings)
   - Project → Python Interpreter
   - Click ⚙️ → Add
   - Select "Existing Environment"
   - Choose: `/Users/akmi/dev/work/dans/orchestrator-acp-poc/services/aca/.venv/bin/python`
   - Click OK

3. **Install Dependencies:**
   - Open Terminal in PyCharm (View → Tool Windows → Terminal)
   - Run:
     ```bash
     cd services/aca
     uv sync
     ```

### Create Run Configuration

1. **Run → Edit Configurations...**
2. **Click + → Python**
3. **Fill in the following:**
   - **Name:** `ACA (Local)`
   - **Module name:** `src.main` (⚠️ NOT Script path)
   - **Working directory:** `/Users/akmi/dev/work/dans/orchestrator-acp-poc/services/aca`
   - **Python interpreter:** Select the ACA venv you set up above
   - **Environment variables:**
     ```
     BASE_DIR=/Users/akmi/dev/work/dans/orchestrator-acp-poc/services/aca;
     PYTHONPATH=/Users/akmi/dev/work/dans/orchestrator-acp-poc/services/aca/src;
     EXPOSE_PORT=2810;
     OTLP_GRPC_ENDPOINT=http://localhost:4317
     ```

4. **Click Apply → OK**

### Run ACA

- Click the **Run** button (▶️) or press **Ctrl+R** (macOS: **Cmd+R**)
- ACA will start on **http://localhost:2810**
- Swagger UI: **http://localhost:2810/docs**
- ReDoc: **http://localhost:2810/redoc**

### Debug Mode

- Click the **Debug** button (🐛) instead of Run to step through code
- Set breakpoints by clicking in the gutter next to line numbers

### Troubleshooting

- **ModuleNotFoundError: No module named 'src.aca'?**
  - Make sure you're using **Module name** `src.main`, NOT **Script path**
  - Verify **Working directory** is set to the `services/aca` folder

- **Port already in use?**
  - Change `EXPOSE_PORT` in environment variables to a different port (e.g., 2811)

- **Dependencies not found?**
  - Ensure Python interpreter is the ACA venv (check status bar at bottom-right)
  - Run `uv sync` again in the terminal

---

## 📚 API Endpoints

### Configuration Management
- **GET** `/list-apps` — List all available applications/configurations
- **GET** `/app/<app_name>` — Get configuration for a specific app
- **POST** `/app` — Create or update an application configuration
- **DELETE** `/app/<app_name>` — Delete an application configuration

### Health Check
- **GET** `/health` — Check service health status
- **GET** `/docs` — Interactive API documentation (Swagger UI)
- **GET** `/redoc` — Alternative API documentation (ReDoc)

---

## 🔧 Configuration Files

ACA reads configuration from TOML files located in the `conf/` directory:
- `settings.toml` — Main configuration file
- `.secrets.toml` — Secret/sensitive credentials (auto-created from `.secrets.toml.sample`)

---

## 🌐 Integration with ACP

ACA is a core component of the ORCHESTRATOR ACP stack:
- **Used by ACP** for dynamic repository configuration retrieval
- **Works with MTS** (Metadata Transformation Service) for metadata transformations
- **Integrates with RQ** for background job processing
- **Supports OpenTelemetry** for observability and monitoring

---

## 📖 Related Services

- **ACP** (Automated Curation Platform) — Main curation service
- **MTS** (Metadata Transformation Service) — Metadata transformation and conversion
- **Orchestrator** — RQ-based job orchestration service

---
