"""
CareerCraft — your first AI agent.

M1: a single tool (read_file) running inside a basic loop.
M2: more tools (fetch_url, web_search, write_file).
M3: sharpen the system prompt into a Career Coach persona.
M4: scratchpad memory shared by tools and the model.
M5: explicit completion criteria — produce all seven deliverables
    before exiting the loop.
"""

import json
import os
import re
import sys

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

MODEL = "gpt-4o-mini"


# ============================================================
# SCRATCHPAD — shared in-memory store the tools and the model
# both read from and write to. (M4: memory.)
# ============================================================

SCRATCHPAD = {}


# ============================================================
# DELIVERABLES — the seven outputs the agent must produce.
# (M5: explicit completion criteria.)
# The loop only exits when every file in this list exists on disk.
# ============================================================

DELIVERABLES = [
    ("company_research", "output/01_company_research.md",
     "What the company does, recent news, signals about culture and stage."),
    ("jd_analysis", "output/02_jd_analysis.md",
     "Required skills, nice-to-haves, red flags from the job description."),
    ("skills_gap", "output/03_skills_gap.md",
     "What the candidate has, what is missing, how to bridge each gap."),
    ("tailored_cv", "output/04_tailored_cv.md",
     "Candidate's CV reordered and rephrased for this specific role."),
    ("cover_letter", "output/05_cover_letter.md",
     "Drafted in the candidate's voice, not a generic template."),
    ("interview_prep", "output/06_interview_prep.md",
     "Likely questions for this role, with suggested answers."),
    ("summary", "output/07_summary.md",
     "A five-line 'should I apply, and how confident am I' verdict."),
]


def _missing_deliverables():
    return [name for name, path, _ in DELIVERABLES if not os.path.exists(path)]


def _clear_deliverables():
    for _, path, _ in DELIVERABLES:
        if os.path.exists(path):
            os.remove(path)


# ============================================================
# TOOLS — the things the agent can call.
# Each tool is (a) a Python function and (b) a JSON schema the
# model sees so it knows how to call it.
# ============================================================

def read_file(path: str) -> str:
    key = f"file:{path}"
    if key in SCRATCHPAD:
        return f"[from scratchpad] {SCRATCHPAD[key]}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        SCRATCHPAD[key] = content
        return content
    except Exception as e:
        return f"ERROR reading {path}: {e}"


def _strip_html(html: str) -> str:
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def fetch_url(url: str) -> str:
    key = f"url:{url}"
    if key in SCRATCHPAD:
        return f"[from scratchpad] {SCRATCHPAD[key]}"
    try:
        r = httpx.get(
            url,
            timeout=20.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (CareerCraft v1)"},
        )
        r.raise_for_status()
        ctype = r.headers.get("content-type", "").lower()
        text = _strip_html(r.text) if "html" in ctype else r.text
        if len(text) > 50000:
            text = text[:50000] + f"\n[truncated, full length was {len(r.text)} chars]"
        SCRATCHPAD[key] = text
        return text
    except Exception as e:
        return f"ERROR fetching {url}: {e}"


def web_search(query: str, max_results: int = 5) -> str:
    cache_key = f"search:{query}|{max_results}"
    if cache_key in SCRATCHPAD:
        return f"[from scratchpad] {SCRATCHPAD[cache_key]}"
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return (
            "ERROR: TAVILY_API_KEY is not set. "
            "Sign up at https://tavily.com to get a free key, "
            "then add TAVILY_API_KEY=... to your .env file."
        )
    try:
        from tavily import TavilyClient
        tavily = TavilyClient(api_key=api_key)
        result = tavily.search(query=query, max_results=max_results)
        results = result.get("results", [])
        if not results:
            return f"No results for {query!r}."
        formatted = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            url = r.get("url", "")
            content = (r.get("content") or "")[:400]
            formatted.append(f"[{i}] {title}\n  URL: {url}\n  {content}")
        text = "\n\n".join(formatted)
        SCRATCHPAD[cache_key] = text
        return text
    except Exception as e:
        return f"ERROR searching for {query!r}: {e}"


def write_file(path: str, content: str) -> str:
    try:
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote {len(content)} chars to {path}"
    except Exception as e:
        return f"ERROR writing {path}: {e}"


# ----- Scratchpad-facing tools the model can call directly -----

def scratchpad_write(key: str, value: str) -> str:
    SCRATCHPAD[key] = value
    return f"Wrote {len(value)} chars to scratchpad[{key!r}]."


def scratchpad_read(key: str) -> str:
    if key not in SCRATCHPAD:
        return f"No scratchpad entry for {key!r}."
    return SCRATCHPAD[key]


def scratchpad_list() -> str:
    if not SCRATCHPAD:
        return "Scratchpad is empty."
    lines = ["Scratchpad contents:"]
    for k, v in SCRATCHPAD.items():
        preview = v[:80].replace("\n", " ")
        lines.append(f"  [{k}] ({len(v)} chars): {preview}...")
    return "\n".join(lines)


def deliverables_status() -> str:
    done = sum(1 for _, p, _ in DELIVERABLES if os.path.exists(p))
    total = len(DELIVERABLES)
    lines = [f"Deliverables status: {done}/{total} done"]
    for name, path, desc in DELIVERABLES:
        marker = "DONE" if os.path.exists(path) else "TODO"
        lines.append(f"  [{marker}] {name} -> {path}")
        lines.append(f"         {desc}")
    return "\n".join(lines)


TOOL_FUNCTIONS = {
    "read_file": read_file,
    "fetch_url": fetch_url,
    "web_search": web_search,
    "write_file": write_file,
    "scratchpad_write": scratchpad_write,
    "scratchpad_read": scratchpad_read,
    "scratchpad_list": scratchpad_list,
    "deliverables_status": deliverables_status,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full contents of a local text file (e.g. a CV) and return it as a string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative or absolute path to the file."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch a web page (e.g. a job description URL or a company's About page) and return its text content. HTML pages are stripped to plain text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full HTTP/HTTPS URL."},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web (via Tavily) for a query. Returns titles, URLs, and snippets. Use this to research companies, roles, recent news, or industry context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."},
                    "max_results": {"type": "integer", "description": "Max number of results (default 5).", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write text content to a local file (e.g. saving a cover letter draft to ./output/). Creates parent directories if needed. Overwrites existing files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative or absolute path to write to."},
                    "content": {"type": "string", "description": "The full text content to write."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scratchpad_write",
            "description": "Save a note to the shared scratchpad memory under a key. Use this for synthesised facts you want to remember later (e.g. 'company:acme:summary' = 'stealth ML startup, 12 people, focus on ...'). Keys should be short and descriptive.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Short identifier for this entry (e.g. 'company:acme:summary')."},
                    "value": {"type": "string", "description": "The note to store."},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scratchpad_read",
            "description": "Read a previously stored scratchpad entry by key. Use this before re-fetching or re-deriving information — the answer may already be there.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "The key to look up."},
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scratchpad_list",
            "description": "List all keys currently in the scratchpad with short previews. Useful for surveying what's already known before deciding what tool to call next.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deliverables_status",
            "description": "Show which of the seven required deliverables are DONE (file exists) and which are still TODO. Call this between work to track progress and decide what to do next.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


# ============================================================
# THE LOOP — send messages → if model wants tools, run them →
# append results → loop. Stop when all seven deliverables exist.
# ============================================================

# ----- M3: SPECIALIZATION via the system prompt -----
# Same brain, same tools, same loop. Only the persona changes.
# The prompt is built from labeled sections so you can ablate
# any one of them (comment it out of ENABLED_SECTIONS) and feel
# which one is doing the work.

ROLE = """\
You are CareerCraft, a senior career coach helping a candidate turn their CV and a
specific job description into a polished, honest application pack. You speak directly
to the candidate — frank, practical, never corporate. Your job is to help them see
their fit clearly (strong AND weak parts) and produce written deliverables that
sound like them, not like a generic AI assistant.\
"""

RULES = """\
RULES YOU MUST FOLLOW:
1. Never invent experience the candidate doesn't have. If the CV doesn't say it,
   you don't claim it. Transferable skills can be argued for — but say
   "transferable from X" rather than asserting the new skill outright.
2. Be specific over generic. Cite an actual project, role, number, or technology
   from the CV when making a claim. "Led a team of 3 on thermal-management
   subsystems" beats "leveraged engineering experience".
3. If information is missing or thin (sparse JD, stealth company, gap in CV),
   say so explicitly rather than padding with fluff.
4. Each output file is one deliverable. A cover letter is a cover letter,
   not a CV summary in disguise.
5. Use the scratchpad. Before fetching a URL, file, or search query you may
   have already done, call scratchpad_list or just re-call the same tool
   (results are auto-cached). Save synthesised facts (company summary, role
   requirements, candidate strengths) via scratchpad_write so later steps
   can reuse them instead of re-deriving.\
"""

EXAMPLES = """\
EXAMPLES — good vs. bad:

BAD cover letter opening:
  "I am writing to express my interest in the Senior Backend Engineer position
   at TechCo. With my extensive experience and passion for technology, I
   believe I would be a strong addition to your esteemed team."

GOOD cover letter opening:
  "I'm applying for the Senior Backend Engineer role because of the migration
   work mentioned in the JD — splitting your monolith without freezing feature
   work. I led the same kind of project at Acme last year: we extracted three
   services from a 5-year-old Rails app while shipping every two weeks."

BAD framing of a gap (invents experience — do NOT do this):
  "I'm a Python expert and have years of Java experience."
  (CV said: 4 years Python, no Java mentioned anywhere.)

GOOD framing of the same gap:
  "My core stack has been Python for 4 years, building backend services at
   scale. The JVM is new to me, but the patterns I've leaned on heavily —
   long-lived services, structured concurrency, observability — translate
   directly."\
"""

OUTPUT_FORMAT = """\
OUTPUT FORMAT:
- Cover letters: 3 short paragraphs, ~250 words total, first person.
  Para 1: why this specific role / this specific company.
  Para 2: strongest match between CV and JD, with one concrete example.
  Para 3: how you'd handle the closest gap, plus a clear next-step ask.
- All files written via write_file should be Markdown (.md).
- Do not wrap entire documents in code fences.\
"""

DELIVERABLES_INSTRUCTION = """\
DELIVERABLES YOU MUST PRODUCE (all 7):

You must produce every one of these as a Markdown file using write_file.
You are not finished until all seven exist on disk.

  1. output/01_company_research.md - What the company does, recent news,
     signals about culture and stage.
  2. output/02_jd_analysis.md - Required skills, nice-to-haves, red flags
     from the job description.
  3. output/03_skills_gap.md - What the candidate has, what is missing,
     how to bridge each gap.
  4. output/04_tailored_cv.md - The candidate's CV reordered and rephrased
     for this specific role.
  5. output/05_cover_letter.md - Drafted in the candidate's voice, not a
     generic template.
  6. output/06_interview_prep.md - Likely questions for this role, with
     suggested answers.
  7. output/07_summary.md - A five-line "should I apply, and how confident
     am I" verdict.

Call deliverables_status periodically to see what is still TODO. Do not
declare done until every one is marked DONE.

If a deliverable genuinely cannot be researched (e.g. the company has no
web presence at all), still write the file - but state in it what was
missing and what you would need to complete it. Don't leave the slot
empty.\
"""

SECTIONS = {
    "role": ROLE,
    "rules": RULES,
    "examples": EXAMPLES,
    "format": OUTPUT_FORMAT,
    "deliverables": DELIVERABLES_INSTRUCTION,
}

# Comment out any section name below to ablate it and see what changes.
ENABLED_SECTIONS = ["role", "rules", "examples", "format", "deliverables"]

CAREER_COACH_PROMPT = "\n\n".join(SECTIONS[k] for k in ENABLED_SECTIONS)

# The M1/M2 minimal prompt — kept so you can A/B compare against M3+.
MINIMAL_PROMPT = (
    "You are CareerCraft, an AI assistant helping with job applications. "
    "You have tools to read local files, fetch URLs, search the web, and write output files. "
    "Choose tools as needed to accomplish the task. "
    "Never invent experience the candidate doesn't have."
)

# Flip between "minimal" and "career_coach" to compare quality.
PERSONA = "career_coach"
SYSTEM_PROMPT = CAREER_COACH_PROMPT if PERSONA == "career_coach" else MINIMAL_PROMPT

MAX_ITERATIONS = 25


def run_agent_stream(user_message: str):
    """Run the agent, yielding trace lines as it goes.

    Generator. Caller can `for line in run_agent_stream(...)` to consume.
    Exits when (a) all seven DELIVERABLES exist on disk, or
    (b) MAX_ITERATIONS is reached.
    """
    SCRATCHPAD.clear()
    _clear_deliverables()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    yield "=" * 70
    yield f"USER: {user_message}"
    yield "=" * 70

    for i in range(1, MAX_ITERATIONS + 1):
        yield f"\n──── iteration {i} ────"

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0,
        )
        msg = response.choices[0].message

        if msg.tool_calls:
            yield "ASSISTANT wants to call tools:"
            messages.append(msg)
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)
                yield f"  → {tc.function.name}({args})"
                result = TOOL_FUNCTIONS[tc.function.name](**args)
                preview = result if len(result) < 300 else result[:300] + f"... [truncated, {len(result)} chars total]"
                yield f"  TOOL {tc.function.name} → {preview}"
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
            continue

        # Model returned plain text. Are all deliverables on disk?
        missing = _missing_deliverables()
        if not missing:
            yield "ASSISTANT (final, all deliverables produced):"
            yield msg.content or ""
            return

        # Not done — nudge the model to keep going.
        yield "ASSISTANT (interim — still missing deliverables):"
        yield msg.content or ""
        messages.append({"role": "assistant", "content": msg.content or ""})
        nudge = (
            f"You returned a final answer, but {len(missing)} of the seven "
            f"required deliverables are still missing on disk: "
            f"{', '.join(missing)}. Please continue producing the missing "
            "files via write_file. Call deliverables_status if you want to "
            "confirm the current state."
        )
        yield f"  → injecting nudge: {nudge}"
        messages.append({"role": "user", "content": nudge})

    yield f"\n[stopped after {MAX_ITERATIONS} iterations without all deliverables]"
    yield deliverables_status()


def run_agent(user_message: str) -> None:
    """CLI entry — consumes run_agent_stream and prints each trace line."""
    for line in run_agent_stream(user_message):
        print(line)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python careercraft.py \"<task description with paths>\"")
        print("Or run the UI:  python app.py")
        sys.exit(1)
    task = " ".join(sys.argv[1:])
    run_agent(task)

