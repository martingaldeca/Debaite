import glob
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Adjust imports to match project structure
# Assuming 'backend' is the root context when running uvicorn
# and 'debates' package is importable.
# If running inside valid venv and PYTHONPATH is set, this works.
from debates.base import Debate
from debates.logger import logger
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import iterate_in_threadpool

app = FastAPI(title="Debaite API")

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Welcome to Debaite API. Visit /docs for Swagger UI."}


CONFIG_DIR = Path("debate_configurations")
RESULTS_DIR = Path("debate_results")
LOGS_DIR = Path("debate_logs")

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


class DebateConfig(BaseModel):
    topic_name: str
    description: str
    allowed_positions: List[str]
    session_id: Optional[str] = None
    # We can add more overrides here if needed
    overrides: Optional[Dict[str, Any]] = None


@app.get("/configs")
def list_configs():
    configs = []
    for file_path in CONFIG_DIR.glob("*.json"):
        try:
            with open(file_path) as f:
                data = json.load(f)
                configs.append(
                    {
                        "filename": file_path.name,
                        "topic_name": data.get("topic_name", "Unknown"),
                        "description": data.get("description", ""),
                    }
                )
        except Exception:  # nosec B112
            continue
    return configs


@app.get("/config/{filename}")
def get_config(filename: str):
    path = CONFIG_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Config not found")
    with open(path) as f:
        return json.load(f)


active_debates: Dict[str, Debate] = {}


@app.post("/debates/init")
def init_debate(config: DebateConfig):
    session_id = config.session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    debate = Debate(
        topic_name=config.topic_name,
        description=config.description,
        allowed_positions=config.allowed_positions,
        session_id=session_id,
        overrides=config.overrides,
    )
    active_debates[debate.debate_id] = debate
    logger.info(f"Initialized debate {debate.debate_id}")
    return {"debate_id": debate.debate_id}


@app.post("/debates/{debate_id}/next")
def next_turn(debate_id: str):
    if debate_id not in active_debates:
        # Check if it was recently finished or just invalid
        raise HTTPException(
            status_code=404, detail=f"Debate {debate_id} not found or expired"
        )

    debate = active_debates[debate_id]
    try:
        event = debate.step()
        if event is None:
            # Debate finished naturally
            # We can optionally remove it from memory now or later
            # deb = active_debates.pop(debate_id, None)
            return {"event": None, "finished": True}

        # If event is debate_finished, we can clean up
        if event.get("type") == "debate_finished":
            active_debates.pop(debate_id, None)
            return {"event": event, "finished": True}

        return {"event": event, "finished": False}
    except Exception as e:
        logger.error(f"Error in debate step: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/debates/run")
async def run_debate(config: DebateConfig):
    # LEGACY STREAMING ENDPOINT
    session_id = config.session_id or datetime.now().strftime("%Y%m%d_%H%M%S")

    debate = Debate(
        topic_name=config.topic_name,
        description=config.description,
        allowed_positions=config.allowed_positions,
        session_id=session_id,
        overrides=config.overrides,
    )

    async def event_generator():
        # Iterate over the synchronous generator in a threadpool to avoid blocking
        async for event in iterate_in_threadpool(debate.run_generator()):
            yield {"data": json.dumps(event)}

    return EventSourceResponse(event_generator())


@app.get("/results")
def list_results_summary():
    # This might be slow if many files, but okay for MVP
    results = []
    # Search recursively for .json files in debate_results/safe_topic/session/*.json
    for path in glob.glob(str(RESULTS_DIR / "**" / "*.json"), recursive=True):
        try:
            with open(path) as f:
                data = json.load(f)
                meta = data.get("metadata", {})
                outcome = data.get("evaluation", {}).get("global_outcome", {})
                rid = meta.get("id")
                if not rid:
                    continue
                results.append(
                    {
                        "id": rid,
                        "topic": meta.get("topic"),
                        "date": meta.get("date"),
                        "winner": outcome.get("winner_name"),
                        "path": path,  # relative or absolute
                    }
                )
        except Exception:  # nosec B112
            continue
    # Sort by date
    results.sort(key=lambda x: x.get("date") or "", reverse=True)
    return results


@app.get("/results/{debate_id}")
def get_result(debate_id: str):
    # Not efficient to glob again, but acceptable for now.
    # Alternatively, client sends full path, or we index.
    # Let's search by ID which is unique.
    for path in glob.glob(
        str(RESULTS_DIR / "**" / f"{debate_id}.json"), recursive=True
    ):
        with open(path) as f:
            return json.load(f)
    raise HTTPException(status_code=404, detail="Result not found")


@app.get("/health")
def health():
    return {"status": "ok"}
