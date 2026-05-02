"""
CareerCraft — Gradio UI wrapper.

Same agent as careercraft.py, driven from a web form:
- upload your CV (PDF, DOCX, RTF, or TXT)
- paste the JD (or upload it as a file)
- click Generate; the seven deliverables fill in across tabs as the agent
  produces them. The full trace prints to the terminal where you launched
  this app.

Run with:  .venv/bin/python app.py
Then open the URL printed in the terminal (usually http://127.0.0.1:7860).
"""

import os
import tempfile
from pathlib import Path

# Workaround: gradio_client 1.3.0 (paired with gradio 4.44.1, the last version
# that supports Python 3.9) crashes on JSONSchema's bool form of
# `additionalProperties`, which modern pydantic 2.x emits. Short-circuit any
# bool schema to "Any" before gradio gets to it. Without this, demo.launch()
# fails with "localhost not accessible" because its own /info endpoint 500s.
import gradio_client.utils as _gcu
_orig_json_schema_to_python_type = _gcu._json_schema_to_python_type
def _patched_json_schema_to_python_type(schema, defs=None):
    if isinstance(schema, bool):
        return "Any"
    return _orig_json_schema_to_python_type(schema, defs)
_gcu._json_schema_to_python_type = _patched_json_schema_to_python_type

import gradio as gr

from careercraft import DELIVERABLES, run_agent_stream


SUPPORTED_EXTS = [".pdf", ".docx", ".rtf", ".txt"]


def _extract_text(src_path: str) -> str:
    """Pull plain text out of a CV/JD file, dispatching by extension.

    Caller is expected to have already validated that the extension is one
    of SUPPORTED_EXTS — this function trusts that.
    """
    ext = Path(src_path).suffix.lower()
    if ext == ".txt":
        return open(src_path, encoding="utf-8", errors="replace").read()
    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(src_path)
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    if ext == ".docx":
        from docx import Document
        doc = Document(src_path)
        return "\n".join(p.text for p in doc.paragraphs)
    if ext == ".rtf":
        from striprtf.striprtf import rtf_to_text
        return rtf_to_text(open(src_path, encoding="utf-8", errors="replace").read())
    raise gr.Error(f"Unsupported file extension: {ext or '(none)'}")


def _save_upload_as_text(file_obj, label: str = "file") -> str:
    """Validate the upload's extension, extract text, save as .txt, return path."""
    if file_obj is None:
        return ""
    src = file_obj if isinstance(file_obj, str) else file_obj.name
    ext = Path(src).suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise gr.Error(
            f"The uploaded {label} doesn't match the supported files "
            f"({', '.join(SUPPORTED_EXTS)})"
        )
    text = _extract_text(src)
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return f.name


def _save_text(text: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return f.name


def _deliverables_view(placeholder: str):
    """Return the current contents of the seven deliverable files (or placeholder)."""
    contents = []
    for _, path, _ in DELIVERABLES:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                contents.append(fh.read())
        else:
            contents.append(placeholder)
    return tuple(contents)


def generate(cv_file, jd_text, jd_file):
    if cv_file is None:
        raise gr.Error("Please upload a CV (PDF, DOCX, RTF, or TXT).")
    if not (jd_text and jd_text.strip()) and jd_file is None:
        raise gr.Error("Please paste a job description or upload a JD file.")

    cv_path = _save_upload_as_text(cv_file, label="CV")
    jd_path = _save_upload_as_text(jd_file, label="JD") if jd_file else _save_text(jd_text)

    task = (
        f"My CV is at {cv_path}. The job description is at {jd_path}. "
        "Produce the complete application pack — all seven required "
        "deliverables — in the ./output/ folder."
    )

    placeholder = "_(in progress…)_"
    yield _deliverables_view(placeholder)

    # Drive the agent. Full trace still prints to the terminal where you ran
    # `python app.py` — only the in-browser trace component is removed.
    # Re-yield the tabs view only when something actually changed, so we don't
    # spam Gradio with redundant updates.
    last_view = None
    for _ in run_agent_stream(task):
        view = _deliverables_view(placeholder)
        if view != last_view:
            last_view = view
            yield view

    yield _deliverables_view("_(not produced)_")


with gr.Blocks(title="CareerCraft") as demo:
    gr.Markdown("# CareerCraft")

    cv_file = gr.File(label="CV", file_types=SUPPORTED_EXTS)
    jd_text = gr.Textbox(label="Job description (paste text)", lines=8)
    jd_file = gr.File(label="… or upload JD as a file", file_types=SUPPORTED_EXTS)

    run_btn = gr.Button("Generate application pack", variant="primary")

    deliverable_components = []
    with gr.Tabs():
        for name, path, desc in DELIVERABLES:
            with gr.Tab(label=name):
                gr.Markdown(f"_{desc}_\n")
                comp = gr.Markdown()
                deliverable_components.append(comp)

    run_btn.click(
        fn=generate,
        inputs=[cv_file, jd_text, jd_file],
        outputs=deliverable_components,
    )


if __name__ == "__main__":
    demo.launch(share=True)
