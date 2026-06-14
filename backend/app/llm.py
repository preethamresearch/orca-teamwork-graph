"""LLM abstraction.

`synthesize()` turns the agent's structured evidence (graph reasoning trace +
grounded chunks + work context) into a natural-language answer.

* **Live mode** — uses an Azure AI Foundry Agent Service model.
* **Local-demo mode** — composes a clear, structured answer deterministically
  from the same evidence, so the experience is fully reproducible offline.

Either way the answer is constrained to the supplied evidence (grounded), which
is what keeps Orca honest and citable.
"""
from __future__ import annotations

from .config import settings

SYSTEM_PROMPT = (
    "You are Orca, an enterprise agent that answers questions using ONLY the "
    "Teamwork Graph evidence and grounded source excerpts provided. Reason over "
    "the graph relationships, cite the sources you used by their [n] markers, and "
    "never invent people, projects, or facts not present in the evidence."
)


def synthesize(question: str, narrative: str, evidence_block: str) -> str:
    # 1) Azure AI Foundry Agent (preferred, when a model is available)
    if settings.live_foundry:
        try:
            return _synthesize_live(question, narrative, evidence_block)
        except Exception:
            pass
    # 2) NVIDIA NIM (OpenAI-compatible) — generative synthesis when Azure OpenAI quota is gated
    if settings.nvidia_api_key:
        try:
            return _synthesize_nvidia(question, narrative, evidence_block)
        except Exception:
            pass
    # 3) Local-demo: the structured reasoning narrative IS the answer
    return narrative


def _synthesize_nvidia(question: str, narrative: str, evidence_block: str) -> str:
    """Generate the answer with an NVIDIA NIM model (OpenAI-compatible chat API),
    constrained to the supplied Foundry IQ evidence + graph reasoning trace."""
    import json
    import urllib.request

    url = settings.nvidia_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.nvidia_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"Question: {question}\n\n"
                f"Graph reasoning trace:\n{narrative}\n\n"
                f"Grounded evidence:\n{evidence_block}\n\n"
                "Write a concise, well-structured answer grounded ONLY in the evidence above. "
                "Cite sources with their [n] markers. Do not invent people, projects, or facts."
            )},
        ],
        "temperature": 0.2,
        "max_tokens": 700,
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={
            "Authorization": f"Bearer {settings.nvidia_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    return data["choices"][0]["message"]["content"].strip()


def _synthesize_live(question: str, narrative: str, evidence_block: str) -> str:
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    client = AIProjectClient(endpoint=settings.ai_project_endpoint, credential=DefaultAzureCredential())
    agent = client.agents.create_agent(
        model=settings.ai_agent_model,
        name="oracle-teamwork-agent",
        instructions=SYSTEM_PROMPT,
    )
    thread = client.agents.threads.create()
    client.agents.messages.create(
        thread_id=thread.id,
        role="user",
        content=(
            f"Question: {question}\n\n"
            f"Graph reasoning trace:\n{narrative}\n\n"
            f"Grounded evidence:\n{evidence_block}\n\n"
            "Write a concise, well-structured answer. Cite sources with their [n] markers."
        ),
    )
    run = client.agents.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)
    if run.status == "failed":
        raise RuntimeError(run.last_error)
    msgs = client.agents.messages.list(thread_id=thread.id)
    for m in msgs:
        if m.role == "assistant" and m.text_messages:
            return m.text_messages[-1].text.value
    raise RuntimeError("no assistant response")
