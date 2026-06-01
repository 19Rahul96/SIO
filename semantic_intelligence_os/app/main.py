"""FastAPI entrypoint for the Semantic Intelligence OS.

Serves both the 14-layer pipeline API and (when built) the React SPA from a single
process, so the whole platform is hosted on one port.

API routes are mounted twice:
  - at root  (`/ingest`, `/graph`, ...) so the Vite dev proxy (which strips `/sio`) works
  - under `/sio` (`/sio/ingest`, ...) so the production-built SPA can call same-origin
The built SPA is served at `/` with assets under `/assets`.
"""
from __future__ import annotations

from pathlib import Path

from typing import List

from fastapi import APIRouter, Body, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .layers import s00_db, s10_ontology, s12_graph, s13_graph_consistency
from .pipeline import run_pipeline
from .storage.jsonstore import read_json

api = APIRouter()


def _read(stage: str, sid: str):
    data = read_json(settings.dir(stage) / f"{sid}.json", None)
    if data is None:
        raise HTTPException(404, f"no {stage} artifact for {sid}")
    return data


@api.get("/health")
def health():
    return {"service": "semantic-intelligence-os", "governance_mode": settings.governance_mode.value}


# ---------------------------------------------------------------------------
# Observatory aggregate endpoints (declared BEFORE /eda/{source_id} so the
# static /eda/<name> routes win over the param route). Every endpoint returns
# {empty: true, reason} when nothing has been ingested — no fake data.
# ---------------------------------------------------------------------------
EMPTY_REASON = "No data ingested yet — upload files or connect a database to populate this view."


def _read_all(stage: str, exclude: set[str] | None = None) -> list[dict]:
    exclude = exclude or set()
    out = []
    for p in sorted((settings.data_root / stage).glob("*.json")):
        if p.name in exclude or p.name.endswith("_triples.json"):
            continue
        d = read_json(p, None)
        if isinstance(d, dict):
            out.append(d)
    return out


def _components(node_ids: list[str], edges: list[dict]) -> int:
    parent = {n: n for n in node_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e in edges:
        a, b = e.get("source"), e.get("target")
        if a in parent and b in parent:
            parent[find(a)] = find(b)
    return len({find(n) for n in node_ids})


def _eda_scoped(stage: str, source_id: str = "") -> list[dict]:
    """All per-source artifacts in a stage dir, or just one when source_id is given."""
    arts = _read_all(stage)
    return [a for a in arts if a.get("source_id") == source_id] if source_id else arts


def _scoped_graph(source_id: str = "") -> dict:
    """Full canonical graph, or the subgraph whose nodes/edges carry source_id in provenance."""
    graph = s12_graph.get_graph()
    if not source_id:
        return graph
    nodes = {nid: n for nid, n in graph.get("nodes", {}).items() if source_id in (n.get("provenance") or [])}
    edges = {eid: e for eid, e in graph.get("edges", {}).items()
             if source_id in (e.get("provenance") or []) and e["source"] in nodes and e["target"] in nodes}
    return {"nodes": nodes, "edges": edges}


@api.get("/sources")
def list_sources():
    """Ingested sources for the scope selector (id, filename, time, kind)."""
    items = []
    for rec in _read_all("sources"):
        if "fingerprint" not in rec:  # skip *_run.json reports (only source records have a fingerprint)
            continue
        items.append({"source_id": rec["source_id"], "filename": rec.get("filename"),
                      "uploaded_at": rec.get("uploaded_at"), "ext": rec.get("ext")})
    items.sort(key=lambda x: x.get("uploaded_at") or "", reverse=True)
    return {"sources": items, "count": len(items)}


def _graph_stats(source_id: str = "") -> dict:
    graph = _scoped_graph(source_id)
    nodes = graph.get("nodes", {})
    edges = [e for e in graph.get("edges", {}).values() if not e.get("suppressed")]
    if not nodes:
        return {"empty": True, "reason": EMPTY_REASON}
    n = len(nodes)
    incident = set()
    for e in edges:
        incident.add(e["source"])
        incident.add(e["target"])
    orphan = [nid for nid in nodes if nid not in incident]
    max_edges = n * (n - 1) / 2 if n > 1 else 1
    return {
        "empty": False,
        "node_count": n,
        "edge_count": len(edges),
        "density": round(len(edges) / max_edges, 4) if max_edges else 0.0,
        "connected_components": _components(list(nodes.keys()), edges),
        "avg_path_length": None,  # deferred (expensive on large graphs)
        "orphan_count": len(orphan),
        "low_confidence_edges": sum(1 for e in edges if e.get("confidence", 0) < settings.band_low),
    }


@api.get("/eda/summary")
def eda_summary(source_id: str = Query(default="")):
    gs = _graph_stats(source_id)
    if gs.get("empty"):
        return gs
    edas = _eda_scoped("eda", source_id)
    vlist = _eda_scoped("validation", source_id)
    cons = read_json(settings.dir("graph") / "consistency_report.json", {})
    halluc = [v.get("hallucination_risk") for v in vlist if v.get("hallucination_risk") is not None]
    # When scoped to one source, prefer its own validation trust; else use global consistency.
    trust = (vlist[0].get("graph_trust_score") if (source_id and vlist) else cons.get("graph_trust_score"))
    band = (vlist[0].get("trust_band") if (source_id and vlist) else cons.get("trust_band"))
    return {
        "empty": False,
        "graph": gs,
        "sources_count": len(edas),
        "graph_trust_score": trust,
        "trust_band": band,
        "avg_hallucination_risk": round(sum(halluc) / len(halluc), 4) if halluc else None,
        "ontology_violations": (None if source_id else cons.get("ontology_violations", {}).get("count")),
    }


@api.get("/eda/columns")
def eda_columns(source_id: str = Query(default="")):
    cols, sources = [], []
    for eda in _eda_scoped("eda", source_id):
        num = eda.get("numeric", {})
        if num.get("is_tabular"):
            sources.append(eda["source_id"])
            for c in num.get("columns", []):
                cols.append({**c, "source_id": eda["source_id"]})
    if not cols:
        return {"empty": True, "reason": "No numeric/tabular columns found in ingested data."}
    return {"empty": False, "sources": sources, "columns": cols}


@api.get("/eda/validation")
def eda_validation(source_id: str = Query(default="")):
    agg = {"invalid_dates": 0, "type_mismatches": 0, "enum_violations": 0, "null_key_violations": 0, "duplicates": 0}
    per_source, found = [], False
    for eda in _eda_scoped("eda", source_id):
        ck = eda.get("numeric", {}).get("consistency_checks")
        if ck:
            found = True
            for k in agg:
                agg[k] += ck.get(k, 0)
            per_source.append({"source_id": eda["source_id"], **ck})
    if not found:
        return {"empty": True, "reason": "No tabular data to validate."}
    return {"empty": False, "totals": agg, "per_source": per_source}


@api.get("/eda/correlation")
def eda_correlation(source_id: str = Query(default="")):
    options = []
    latest = None
    for eda in _eda_scoped("eda", source_id):
        corr = eda.get("numeric", {}).get("correlation")
        if corr and corr.get("available"):
            options.append(eda["source_id"])
            latest = {"source_id": eda["source_id"], **corr}
    if not latest:
        return {"empty": True, "reason": "At least 2 numeric columns required to compute correlations."}
    return {"empty": False, "sources": options, **latest}


@api.get("/eda/outliers")
def eda_outliers(source_id: str = Query(default="")):
    cols = []
    for eda in _eda_scoped("eda", source_id):
        for c in eda.get("numeric", {}).get("columns", []):
            if c.get("is_numeric"):
                cols.append({
                    "column": c["column"], "source_id": eda["source_id"],
                    "outliers_iqr_count": c.get("outliers_iqr_count", 0),
                    "outliers_zscore_count": c.get("outliers_zscore_count", 0),
                    "outliers": c.get("outliers", []),
                    "box": c.get("box"), "zscore_bins": c.get("zscore_bins"),
                })
    if not cols:
        return {"empty": True, "reason": "No numeric data available."}
    return {"empty": False, "columns": cols}


@api.get("/eda/confidence")
def eda_confidence(source_id: str = Query(default="")):
    if source_id:
        per = read_json(settings.dir("confidence") / f"{source_id}.json", None)
        if not per or not per.get("entities"):
            return {"empty": True, "reason": "No confidence data for this source."}
        return {"empty": False, "layers": per["layers"], "entities": per["entities"]}
    matrix = read_json(settings.dir("confidence") / "matrix.json", None)
    if not matrix or not matrix.get("entities"):
        return {"empty": True, "reason": "No confidence data available. Ingest data and run the full pipeline to populate this view."}
    return {"empty": False, "layers": matrix["layers"], "entities": list(matrix["entities"].values())}


@api.get("/eda/extraction")
def eda_extraction(source_id: str = Query(default="")):
    arts = _eda_scoped("extraction", source_id)
    if not arts:
        return {"empty": True, "reason": "No extraction data available. Upload files or connect a database to see extraction quality."}
    lineage, pdf = [], []
    for a in arts:
        lineage.extend(a.get("lineage", []))
        if a.get("pdf_quality", {}).get("pdf_enabled"):
            pdf.append({"source_id": a["source_id"], **a["pdf_quality"]})
    return {"empty": False, "lineage": lineage, "pdf_quality": pdf,
            "parser_confidence": [{"source_id": a["source_id"], "confidence": a.get("parser_confidence"), "needs_ocr": a.get("needs_ocr")} for a in arts]}


@api.get("/graph/stats")
def graph_stats(source_id: str = Query(default="")):
    return _graph_stats(source_id)


@api.get("/graph/entities")
def graph_entities(filter: str = Query(default=""), source_id: str = Query(default="")):
    graph = _scoped_graph(source_id)
    nodes = graph.get("nodes", {})
    if not nodes:
        return {"empty": True, "reason": EMPTY_REASON}
    registry = read_json(settings.dir("canonical") / "registry.json", {"nodes": {}})["nodes"]
    degree: dict[str, int] = {nid: 0 for nid in nodes}
    for e in graph.get("edges", {}).values():
        if e.get("suppressed"):
            continue
        if e["source"] in degree:
            degree[e["source"]] += 1
        if e["target"] in degree:
            degree[e["target"]] += 1
    items = []
    for nid, node in nodes.items():
        if filter == "orphan" and degree[nid] != 0:
            continue
        reg = registry.get(nid, {})
        items.append({
            "canonical_id": nid,
            "label": node.get("label"),
            "entity_type": node.get("entity_type"),
            "degree_centrality": degree[nid],
            "confidence": reg.get("confidence"),
            "source_count": len(node.get("provenance", [])),
        })
    items.sort(key=lambda x: -x["degree_centrality"])
    return {"empty": False, "count": len(items), "entities": items}


@api.get("/graph/relationships")
def graph_relationships(source_id: str = Query(default="")):
    graph = _scoped_graph(source_id)
    edges = graph.get("edges", {})
    if not edges:
        return {"empty": True, "reason": EMPTY_REASON}
    rels = [{
        "source": e["source"], "target": e["target"], "relation": e["relation"],
        "confidence": e.get("confidence"), "suppressed": e.get("suppressed", False),
        "governance": e.get("governance"),
    } for e in edges.values()]
    return {"empty": False, "count": len(rels), "relationships": rels}


@api.get("/metrics/aggregate")
def metrics_aggregate(source_id: str = Query(default="")):
    gs = _graph_stats(source_id)
    if gs.get("empty"):
        return {"empty": True, "reason": EMPTY_REASON}
    cons = read_json(settings.dir("graph") / "consistency_report.json", {})
    vlist = _eda_scoped("validation", source_id)
    # Metadata coverage: mean column semantic-label confidence across (scoped) tabular sources.
    confs = []
    for md in _eda_scoped("metadata", source_id):
        for c in md.get("columns", []):
            sc = c.get("audit", {}).get("confidence", {}).get("score")
            if sc is not None:
                confs.append(sc)
    halluc = [v.get("hallucination_risk") for v in vlist if v.get("hallucination_risk") is not None]
    recall = [v.get("retrieval_metrics", {}).get("recall_at_5") for v in vlist if v.get("retrieval_metrics")]
    graph_trust = (vlist[0].get("graph_trust_score") if (source_id and vlist) else cons.get("graph_trust_score"))
    return {
        "empty": False,
        "graph_trust": graph_trust,
        "metadata_coverage": round(sum(confs) / len(confs), 4) if confs else None,
        "hallucination_risk": round(sum(halluc) / len(halluc), 4) if halluc else None,
        "retrieval_accuracy": round(sum(recall) / len(recall), 4) if recall else None,
        "retrieval_accuracy_proxy": True,
    }


@api.post("/ingest")
async def ingest(
    files: List[UploadFile] = File(...),
    role: str = Form(""),
    domain: str = Form(""),
):
    """Ingest one or many files (also covers folder uploads, which arrive as many files).

    Each file runs the full 14-layer pipeline and merges into the shared canonical graph.
    Returns the last source's report (for per-source tabs) plus an ``ingested`` summary list.
    """
    reports = []
    for f in files:
        raw = await f.read()
        reports.append(run_pipeline(filename=f.filename, raw=raw, role=role, domain=domain))
    if not reports:
        raise HTTPException(400, "no files provided")
    last = dict(reports[-1])
    last["ingested"] = [
        {"source_id": r["source_id"], "filename": r["filename"],
         "entities": r.get("summary", {}).get("entities"),
         "relationships": r.get("summary", {}).get("relationships")}
        for r in reports
    ]
    last["ingested_count"] = len(reports)
    return last


@api.post("/db/test")
def db_test(payload: dict = Body(...)):
    """Validate a database connection (engine/host/port/dbname/user/password)."""
    return s00_db.test_connection(payload)


@api.post("/ingest/database")
def ingest_database(payload: dict = Body(...)):
    """Connect to a database, introspect its schema, and run it through the pipeline."""
    role = payload.pop("role", "") if isinstance(payload, dict) else ""
    domain = payload.pop("domain", "") if isinstance(payload, dict) else ""
    try:
        text, label = s00_db.schema_corpus(payload)
    except ModuleNotFoundError as exc:
        raise HTTPException(400, f"missing driver: {exc}. Install sqlalchemy + dialect driver")
    except Exception as exc:
        raise HTTPException(400, f"database connection failed: {exc}")
    report = run_pipeline(filename=f"{label}.txt", raw=text.encode("utf-8"), role=role, domain=domain)
    report["source_kind"] = "database"
    return report


@api.get("/run/{source_id}")
def run_report(source_id: str):
    data = read_json(settings.dir("sources") / f"{source_id}_run.json", None)
    if data is None:
        raise HTTPException(404, "run not found")
    return data


@api.get("/lineage/{source_id}")
def lineage(source_id: str):
    return _read("lineage", source_id)


@api.get("/metadata/{source_id}")
def metadata(source_id: str):
    return _read("metadata", source_id)


@api.get("/eda/{source_id}")
def eda(source_id: str):
    return _read("eda", source_id)


@api.get("/validation/{source_id}")
def validation(source_id: str):
    return _read("validation", source_id)


@api.get("/governance/{source_id}")
def governance(source_id: str):
    return _read("governance", source_id)


@api.get("/ontology")
def ontology():
    return s10_ontology.load_ontology()


@api.post("/ontology/predicate")
def add_predicate(predicate: str = Form(...), allowed_pairs: str = Form(...)):
    """allowed_pairs: semicolon-separated 'srcType,dstType' tuples."""
    pairs = [p.split(",") for p in allowed_pairs.split(";") if "," in p]
    return s10_ontology.update_ontology(predicate, pairs)


@api.get("/graph")
def graph():
    return s12_graph.get_graph()


@api.get("/graph/consistency")
def graph_consistency():
    return s13_graph_consistency.validate_graph()


@api.get("/wiki/pages")
def wiki_pages():
    return read_json(settings.dir("wiki") / "index.json", {"pages": {}})


@api.get("/wiki/page/{canonical_id}")
def wiki_page(canonical_id: str):
    page = read_json(settings.dir("wiki") / f"{canonical_id}.json", None)
    if page is None:
        raise HTTPException(404, "page not found")
    return page


app = FastAPI(title="Semantic Intelligence OS", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
app.include_router(api)                 # root: /ingest, /graph, ...  (dev proxy)
app.include_router(api, prefix="/sio")  # prod: /sio/ingest, ...      (built SPA)

# Serve the built React SPA when present (frontend/dist).
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if (_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/")
    def spa_index():
        return FileResponse(str(_DIST / "index.html"))
else:
    @app.get("/")
    def root_info():
        return {"service": "semantic-intelligence-os", "spa": "not built", "api": "/sio/health"}
