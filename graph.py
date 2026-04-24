import re, hashlib, uuid
from models import GraphState

# --- Nodes ---

def validator_node(state: GraphState) -> GraphState:
    valid, dead = [], []
    email_re = re.compile(r"[^@]+@[^@]+\.[^@]+")
    
    for r in state.records:
        r["first_name"] = r.get("first_name", "").strip().title()
        r["email"] = r.get("email", "").strip().lower()
        
        if not r["email"] or not email_re.match(r["email"]):
            r["status"] = "dead_letter"
            dead.append(r)
        else:
            valid.append(r)
    
    return GraphState(records=valid, processed=[], failed=dead)


def categorizer_node(state: GraphState) -> GraphState:
    clinical, analytics, manual = [], [], []
    
    for r in state.records:
        initial = r["first_name"][0] if r["first_name"] else ""
        
        if not initial.isalpha():
            manual.append({**r, "_route": "manual"})
        elif initial.upper() <= "F":
            clinical.append({**r, "_route": "clinical"})
        else:
            analytics.append({**r, "_route": "analytics"})
    
    # Flatten back — LangGraph will route via conditional edges
    return GraphState(
        records=clinical + analytics + manual,
        processed=state.processed,
        failed=state.failed
    )


def clinical_node(state: GraphState) -> GraphState:
    processed = list(state.processed)
    remaining = []
    
    for r in state.records:
        if r.get("_route") == "clinical":
            length = len(r.get("last_name", ""))
            r["occupation"] = "Doctor"
            r["specialty_code"] = (length * 7) % 10
            r["status"] = "processed"
            r.pop("_route", None)
            processed.append(r)
        else:
            remaining.append(r)
    
    return GraphState(records=remaining, processed=processed, failed=state.failed)


def analytics_node(state: GraphState) -> GraphState:
    processed = list(state.processed)
    remaining = []
    
    for r in state.records:
        if r.get("_route") == "analytics":
            email_hash = hashlib.md5(r["email"].encode()).hexdigest()
            r["occupation"] = "Scientist"
            r["uuid"] = str(uuid.UUID(email_hash))
            r["status"] = "processed"
            r.pop("_route", None)
            processed.append(r)
        else:
            remaining.append(r)
    
    return GraphState(records=remaining, processed=processed, failed=state.failed)


def manual_node(state: GraphState) -> GraphState:
    processed = list(state.processed)
    
    for r in state.records:
        r["occupation"] = "Unknown"
        r["status"] = "pending_review"
        r.pop("_route", None)
        processed.append(r)
    
    return GraphState(records=[], processed=processed, failed=state.failed)


def aggregator_node(state: GraphState) -> GraphState:
    # All records should already be in processed/failed by now
    return state


# --- Graph Assembly ---

from langgraph.graph import StateGraph, END
from typing import TypedDict

# LangGraph needs TypedDict, not Pydantic — thin adapter
class State(TypedDict):
    records: list[dict]
    processed: list[dict]
    failed: list[dict]

def _wrap(fn):
    """Wrap Pydantic-based node for LangGraph TypedDict state."""
    def wrapper(state: State) -> State:
        result = fn(GraphState(**state))
        return result.model_dump()
    return wrapper

def build_graph():
    g = StateGraph(State)
    
    g.add_node("validator", _wrap(validator_node))
    g.add_node("categorizer", _wrap(categorizer_node))
    g.add_node("clinical", _wrap(clinical_node))
    g.add_node("analytics", _wrap(analytics_node))
    g.add_node("manual", _wrap(manual_node))
    g.add_node("aggregator", _wrap(aggregator_node))
    
    g.set_entry_point("validator")
    g.add_edge("validator", "categorizer")
    
    # All three transformation nodes run in sequence (simplest approach)
    g.add_edge("categorizer", "clinical")
    g.add_edge("clinical", "analytics")
    g.add_edge("analytics", "manual")
    g.add_edge("manual", "aggregator")
    g.add_edge("aggregator", END)
    
    return g.compile()

graph = build_graph()