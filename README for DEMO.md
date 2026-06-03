# Time Series Forecasting Accelerator Agent - DEMO

A production-ready pipeline for forecasting multiple time series on **Microsoft Fabric** or locally.

# 🚀 Demo Setup Guide to Run it LOCALLY

This guide explains how to:
- Clone a GitHub repository  
- Create a Python 3.11.14 environment  
- Install project dependencies from `requirements.txt`  

---

## ✅ Prerequisites

- VS Code installed
- GitHub Copilot extension installed
- GitHub account (personal or enterprise)
- Copilot access (free, individual, or business)

Make sure you have the following installed:

- **Git**
- **Python 3.11.14**
- **pip** (comes with Python)

Verify installation:

```bash
git --version
python --version
pip --version
```

# 📥 1. Clone the Repository
- Clone the repo from Github https://github.com/mmbellani/time-series-forecasting-agent
- Load it in Vs Code or use the command line
  
```bash
git clone [https://github.com/mmbellani/time-series-forecasting-agent](https://github.com/mmbellani/time-series-forecasting-agent.git)
cd time-series-forecasting-agent
```

# 🐍 2. Create Python 3.11.14 Virtual Environment
```bash
python3.11 -m venv .venv
```

## Activate the environment
```bash
.venv\Scripts\activate
```
✅ After activation, your terminal should show (.venv).

# ⬆️ 3. Upgrade pip
```bash
pip install --upgrade pip
```

# 📦 4. Install Dependencies
```bash
pip install -r requirements.txt
```

# 🚀 5. Install the GitHub Copilot extension in VS Code
```bash
Ctrl + Shift + X → search “GitHub Copilot” → Install
Ctrl + Shift + P →  GitHub Copilot: Sign in
```
## Complete browser authentication

- A browser window opens
- Log in to GitHub
- Authorise VS Code

✅ You’ll be redirected back automatically when done
(Also optionally install GitHub Copilot Chat)

# 6. 🧠 Start the Pipeline
- Open Github Copilot Chat with View/Command Palette or 
```bash
  CTRL + P → Chat → Open Chat
```
- Select model Claude Opus 4.6 or higher so that you can interact with the agent
- Start Phase 01 by selecting teh agent time-series-forecaster and then prompt /tsf-01 
  