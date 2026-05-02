# CareerCraft

> An AI agent that turns a CV and a job description into a complete, tailored application pack.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Built with OpenAI](https://img.shields.io/badge/built%20with-OpenAI-412991.svg)](https://platform.openai.com/)
[![UI: Gradio](https://img.shields.io/badge/UI-Gradio-orange.svg)](https://gradio.app/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](#license)

CareerCraft is a small, single-file AI agent that reads your CV, studies a job description, researches the company on the web, and writes a polished, role-specific application pack — cover letter, tailored CV, skills-gap analysis, interview prep, and more.

It is built as a learning project: a tool-using loop on top of the OpenAI Chat Completions API ([careercraft.py](careercraft.py)) plus a thin Gradio browser UI ([app.py](app.py)).

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Deliverables](#deliverables)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [Customization](#customization)
- [Requirements](#requirements)
- [License](#license)

---

## Overview

Given a candidate's CV and a target job description, CareerCraft produces **seven Markdown deliverables** in the `./output/` folder, written in the candidate's voice with concrete examples drawn from the actual CV.

The agent uses an explicit "completion criteria" loop — it does not stop until every deliverable file exists on disk.

## Features

- **Tool-using agent loop** — the model decides which tools to call (read files, fetch URLs, search the web, write outputs).
- **Web research built in** — uses Tavily to research the company and role.
- **Shared scratchpad memory** — synthesised facts are cached so later steps reuse work instead of re-deriving it.
- **Career Coach persona** — a structured system prompt with role, rules, examples, output format, and explicit deliverables.
- **Two ways to run** — a CLI for quick use and a Gradio web UI for uploads and live tab updates.
- **Multi-format input** — CV / JD can be PDF, DOCX, RTF, or TXT.
- **Hard completion gate** — the loop only exits when all seven deliverables are written to disk.

## Deliverables

| # | File | Contents |
|---|------|----------|
| 1 | `output/01_company_research.md` | What the company does, recent news, signals about culture and stage |
| 2 | `output/02_jd_analysis.md` | Required skills, nice-to-haves, red flags from the job description |
| 3 | `output/03_skills_gap.md` | What the candidate has, what is missing, how to bridge each gap |
| 4 | `output/04_tailored_cv.md` | The candidate's CV reordered and rephrased for this specific role |
| 5 | `output/05_cover_letter.md` | Drafted in the candidate's voice, not a generic template |
| 6 | `output/06_interview_prep.md` | Likely questions for the role, with suggested answers |
| 7 | `output/07_summary.md` | A five-line "should I apply, and how confident am I" verdict |

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Rishi-Kora/CareerCraft.git
cd CareerCraft
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux
.venv\Scripts\activate            # Windows
```

### 3. Install dependencies

```bash
pip install openai httpx python-dotenv tavily-python \
            gradio==4.44.1 pypdf python-docx striprtf
```

> **Note:** `gradio` is pinned to `4.44.1` so the project keeps working on Python 3.9. See the workaround at the top of [app.py](app.py) for context.

## Configuration

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
```

| Variable | Required | How to get one |
|----------|----------|----------------|
| `OPENAI_API_KEY` | **Yes** — the agent won't start without it | https://platform.openai.com/api-keys |
| `TAVILY_API_KEY` | Optional, but needed for `web_search` | https://tavily.com (free tier available) |

## Usage

### Option A — Command Line

```bash
python careercraft.py "My CV is at ./cv.txt. The JD is at ./jd.txt. Produce the full application pack."
```

The agent prints a full trace (each iteration, every tool call, every result) and writes the seven Markdown files into `./output/`.

### Option B — Web UI

```bash
python app.py
```

Open the URL printed in the terminal (usually `http://127.0.0.1:7860`):

1. Upload a **CV** (PDF, DOCX, RTF, or TXT)
2. Paste or upload the **job description**
3. Click **Generate application pack**
4. Watch the seven tabs fill in as the agent works

The full agent trace still prints to the terminal.

## Project Structure

```
CareerCraft/
├── careercraft.py     # The agent: tools, loop, system prompt, completion gate
├── app.py             # Gradio web UI wrapper
├── cv.txt             # Sample CV (replace with your own)
├── jd.txt             # Sample job description
├── output/            # Generated deliverables land here
├── .env               # API keys (not committed)
└── README.md
```

## How It Works

### The agent loop

The loop in [`run_agent_stream`](careercraft.py) sends messages to `gpt-4o-mini`, runs any tool calls the model requests, appends the results, and continues. It exits when:

- all seven deliverable files exist on disk, **or**
- `MAX_ITERATIONS = 25` is reached

If the model declares itself "done" before all files exist, a nudge message is injected listing what's still missing.

### Tools available to the model

| Tool | Purpose |
|------|---------|
| `read_file` | Read a local text file (e.g. the CV) |
| `fetch_url` | Fetch a web page and strip it to plain text |
| `web_search` | Search the web via Tavily for company / role context |
| `write_file` | Write a deliverable to disk |
| `scratchpad_write` / `scratchpad_read` / `scratchpad_list` | Shared in-memory notes between steps |
| `deliverables_status` | Show which of the seven outputs are still TODO |

### The Career Coach persona

The system prompt is composed of labeled sections — `role`, `rules`, `examples`, `format`, `deliverables` — joined into a single string. The persona enforces guardrails such as *"never invent experience the candidate doesn't have"* and *"be specific over generic"*.

## Customization

### Ablate parts of the prompt

Edit `ENABLED_SECTIONS` in [careercraft.py](careercraft.py) to switch sections off and feel which one is doing the work:

```python
ENABLED_SECTIONS = ["role", "rules", "examples", "format", "deliverables"]
```

### Compare a minimal vs. a full persona

```python
PERSONA = "career_coach"   # or "minimal" for the M1/M2 baseline prompt
```

### Swap the model

```python
MODEL = "gpt-4o-mini"      # change to any OpenAI chat model you have access to
```

## Requirements

- **Python:** 3.9 or later
- **Accounts / keys:**
  - OpenAI API key (required)
  - Tavily API key (optional, free tier)
- **Python packages:** `openai`, `httpx`, `python-dotenv`, `tavily-python`, `gradio==4.44.1`, `pypdf`, `python-docx`, `striprtf`

## License

Released under the [MIT License](https://opensource.org/licenses/MIT). 

Feel free to fork, adapt, and use as a learning starting point for your own AI agents.
