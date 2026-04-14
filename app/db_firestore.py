from google.cloud import firestore
from datetime import datetime
import uuid


class FirestoreRepository:
    """Google Firestore repository (used on Cloud Run)."""

    def __init__(self):
        self._db = firestore.AsyncClient()
        self._scans = self._db.collection("scan_runs")
        self._leads = self._db.collection("leads")
        self._targets = self._db.collection("target_institutions")

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _doc_to_dict(doc) -> dict:
        d = doc.to_dict() or {}
        d["id"] = doc.id
        return d

    # ── ScanRun ───────────────────────────────────────────────────────────────

    async def create_scan_run(self, scan_run: dict) -> dict:
        scan_run.setdefault("id", str(uuid.uuid4()))
        scan_run.setdefault("started_at", datetime.utcnow())
        scan_run.setdefault("status", "running")
        scan_run.setdefault("total_found", 0)
        scan_run.setdefault("active_count", 0)
        doc_id = scan_run["id"]
        await self._scans.document(doc_id).set(scan_run)
        return scan_run

    async def update_scan_run(self, scan_id: str, updates: dict) -> dict:
        await self._scans.document(scan_id).update(updates)
        doc = await self._scans.document(scan_id).get()
        return self._doc_to_dict(doc)

    async def get_scan_run(self, scan_id: str) -> dict | None:
        doc = await self._scans.document(scan_id).get()
        return self._doc_to_dict(doc) if doc.exists else None

    async def list_scan_runs(self, limit: int = 20) -> list[dict]:
        query = self._scans.order_by("started_at", direction=firestore.Query.DESCENDING).limit(limit)
        docs = await query.get()
        return [self._doc_to_dict(d) for d in docs]

    # ── Leads ──────────────────────────────────────────────────────────────────

    async def create_lead(self, lead: dict) -> dict:
        lead.setdefault("id", str(uuid.uuid4()))
        lead.setdefault("first_seen_at", datetime.utcnow())
        lead.setdefault("lead_status", "new")
        await self._leads.document(lead["id"]).set(lead)
        return lead

    async def create_leads_batch(self, leads: list[dict]) -> list[dict]:
        now = datetime.utcnow()
        batch = self._db.batch()
        results = []
        for lead in leads:
            lead.setdefault("id", str(uuid.uuid4()))
            lead.setdefault("first_seen_at", now)
            lead.setdefault("lead_status", "new")
            batch.set(self._leads.document(lead["id"]), lead)
            results.append(lead)
        await batch.commit()
        return results

    async def get_lead(self, lead_id: str) -> dict | None:
        doc = await self._leads.document(lead_id).get()
        return self._doc_to_dict(doc) if doc.exists else None

    async def update_lead(self, lead_id: str, updates: dict) -> dict:
        await self._leads.document(lead_id).update(updates)
        doc = await self._leads.document(lead_id).get()
        return self._doc_to_dict(doc)

    async def list_leads(
        self,
        filters: dict,
        sort_by: str = "relevance_score",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        query = self._leads

        freshness = filters.get("freshness")
        _FETCH_CAP = 2000
        if freshness == "actionable":
            # Firestore doesn't support OR — fetch active and stale separately
            active_q = self._leads.where("freshness", "==", "active").limit(_FETCH_CAP)
            stale_q = self._leads.where("freshness", "==", "stale").limit(_FETCH_CAP)
            active_docs = await active_q.get()
            stale_docs = await stale_q.get()
            results = [self._doc_to_dict(d) for d in active_docs + stale_docs]
            results = self._apply_python_filters(results, filters)
            return self._sort_and_page(results, sort_by, offset, limit)
        elif freshness:
            query = query.where("freshness", "==", freshness)

        if filters.get("type"):
            query = query.where("type", "==", filters["type"])

        if filters.get("country"):
            query = query.where("country", "==", filters["country"])

        if filters.get("scan_run_id"):
            query = query.where("scan_run_id", "==", filters["scan_run_id"])

        # Fetch a capped set for Python-side filtering (min_score can't be done
        # server-side in Firestore). 2000 is a safe upper bound for this app's
        # data volume; revisit if the leads collection grows beyond that.
        _FETCH_CAP = 2000
        docs = await query.limit(_FETCH_CAP).get()
        results = [self._doc_to_dict(d) for d in docs]
        results = self._apply_python_filters(results, filters)
        return self._sort_and_page(results, sort_by, offset, limit)

    def _apply_python_filters(self, results: list[dict], filters: dict) -> list[dict]:
        min_score = filters.get("min_score", 0)
        if min_score:
            results = [r for r in results if (r.get("relevance_score") or 0) >= min_score]
        return results

    def _sort_and_page(self, results: list[dict], sort_by: str, offset: int, limit: int) -> list[dict]:
        reverse = sort_by in ("relevance_score", "first_seen_at")
        key_map = {
            "relevance_score": lambda r: r.get("relevance_score") or 0,
            "urgency": lambda r: {"high": 0, "medium": 1, "low": 2}.get(r.get("urgency", "low"), 2),
            "freshness": lambda r: r.get("freshness", "unknown"),
            "first_seen_at": lambda r: r.get("first_seen_at") or datetime.min,
        }
        key = key_map.get(sort_by, key_map["relevance_score"])
        results.sort(key=key, reverse=reverse)
        return results[offset: offset + limit]

    # ── Target Institutions ────────────────────────────────────────────────────

    async def create_targets_batch(self, targets: list[dict]) -> list[dict]:
        now = datetime.utcnow()
        batch = self._db.batch()
        results = []
        for target in targets:
            target.setdefault("id", str(uuid.uuid4()))
            target.setdefault("discovered_at", now)
            batch.set(self._targets.document(target["id"]), target)
            results.append(target)
        await batch.commit()
        return results

    async def get_targets_for_lead(self, lead_id: str) -> list[dict]:
        query = self._targets.where("lead_id", "==", lead_id)
        docs = await query.get()
        return [self._doc_to_dict(d) for d in docs]

    async def list_targets(self, tier: str | None = None, country: str | None = None) -> list[dict]:
        query = self._targets
        if tier:
            query = query.where("market_tier", "==", tier)
        if country:
            query = query.where("country", "==", country)
        docs = await query.limit(1000).get()
        return [self._doc_to_dict(d) for d in docs]

    async def get_existing_lead_titles(self, limit: int = 500) -> list[str]:
        query = self._leads.order_by("first_seen_at", direction=firestore.Query.DESCENDING).limit(limit)
        docs = await query.get()
        return [d.to_dict().get("title", "") for d in docs if d.to_dict().get("title")]
