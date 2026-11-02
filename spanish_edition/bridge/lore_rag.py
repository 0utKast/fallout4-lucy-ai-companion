"""Motor RAG Persistente Local en Español para Compañeros de Fallout (SQLite + Correferencia Conversacional).

- Indexa automáticamente todos los paquetes de conocimiento JSON en `bridge/lore_kb/*.json`
  dentro de una base de datos SQLite persistente (`bridge/state/lore_index.sqlite`).
- Soporta resolución de preguntas de seguimiento (`prev_query`) para que si el jugador pregunta por Cooper
  en un turno y en el siguiente dice "incluso te cortó un dedo", el motor mantenga el contexto de Cooper
  y recupere además la tarjeta específica del dedo cortado y Snip-Snip.
"""

import hashlib
import json
import re
import sqlite3
import unicodedata
from pathlib import Path

HERE = Path(__file__).parent
KB_DIR = HERE / "lore_kb"
DB_PATH = HERE / "state" / "lore_index.sqlite"


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _tokenize(text: str) -> set[str]:
    norm = _strip_accents(text)
    return {w for w in re.findall(r"[a-z0-9]{2,}", norm) if len(w) >= 2}


def _compute_kb_hash() -> str:
    h = hashlib.sha256()
    if not KB_DIR.exists():
        return ""
    for p in sorted(KB_DIR.glob("*.json")):
        h.update(p.name.encode("utf-8"))
        h.update(p.read_bytes())
    return h.hexdigest()


class PersistentLoreRAG:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._docs: list[dict] = []
        self._init_and_sync_db()

    def _init_and_sync_db(self) -> None:
        kb_hash = _compute_kb_hash()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lore_docs (
                    id TEXT PRIMARY KEY,
                    pack TEXT,
                    title TEXT,
                    keywords_en TEXT,
                    keywords_es TEXT,
                    content TEXT
                )
                """
            )
            row = conn.execute("SELECT value FROM meta WHERE key = 'kb_hash'").fetchone()
            stored_hash = row[0] if row else ""

            if stored_hash != kb_hash and KB_DIR.exists():
                conn.execute("DELETE FROM lore_docs")
                docs_loaded = 0
                for p in sorted(KB_DIR.glob("*.json")):
                    items = json.loads(p.read_text(encoding="utf-8"))
                    for item in items:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO lore_docs (id, pack, title, keywords_en, keywords_es, content)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                item["id"],
                                item.get("pack", p.stem),
                                item["title"],
                                json.dumps(item.get("keywords_en", []), ensure_ascii=False),
                                json.dumps(item.get("keywords_es", []), ensure_ascii=False),
                                item["content"],
                            ),
                        )
                        docs_loaded += 1
                conn.execute(
                    "INSERT OR REPLACE INTO meta (key, value) VALUES ('kb_hash', ?)",
                    (kb_hash,),
                )
                conn.commit()
                print(
                    f"[LoreRAG-ES] Indexados {docs_loaded} documentos canónicos en español en SQLite ({self.db_path.name}).",
                    flush=True,
                )

            rows = conn.execute(
                "SELECT id, pack, title, keywords_en, keywords_es, content FROM lore_docs"
            ).fetchall()

        self._docs = []
        for doc_id, pack, title, kw_en_json, kw_es_json, content in rows:
            kw_en = [_strip_accents(k) for k in json.loads(kw_en_json)]
            kw_es = [_strip_accents(k) for k in json.loads(kw_es_json)]
            all_kw = kw_es + kw_en
            kw_tokens = set()
            for k in all_kw:
                kw_tokens.update(_tokenize(k))
            self._docs.append(
                {
                    "id": doc_id,
                    "pack": pack,
                    "title": title,
                    "phrases": all_kw,
                    "kw_tokens": kw_tokens,
                    "content_tokens": _tokenize(title + " " + content),
                    "content": content,
                }
            )

    def _score_doc(self, doc: dict, q_norm: str, q_tokens: set[str]) -> float:
        if not q_norm:
            return 0.0
        score = 0.0
        for phrase in doc["phrases"]:
            if not phrase:
                continue
            if " " in phrase:
                if phrase in q_norm:
                    score += 14.0
            else:
                if phrase in q_tokens:
                    score += 8.0
        score += len(q_tokens & doc["kw_tokens"]) * 3.5
        score += len(q_tokens & doc["content_tokens"]) * 0.8
        return score

    def retrieve(
        self,
        query: str,
        prev_query: str = "",
        location_name: str = "",
        nearby_names: list[str] | None = None,
        top_k: int = 2,
        is_chat: bool = True,
    ) -> list[dict]:
        """Recupera las tarjetas de memoria canónica más relevantes (con soporte de seguimiento multi-turno)."""
        if not self._docs:
            return []

        combined_query = f"{query or ''} {location_name or ''} {' '.join(nearby_names or [])}".strip()
        q_norm = _strip_accents(combined_query)
        q_tokens = _tokenize(combined_query)

        prev_norm = _strip_accents(prev_query) if prev_query else ""
        prev_tokens = _tokenize(prev_query) if prev_query else set()

        scored: list[tuple[float, dict]] = []
        for doc in self._docs:
            cur_sc = self._score_doc(doc, q_norm, q_tokens)
            prev_sc = self._score_doc(doc, prev_norm, prev_tokens) * 0.35 if prev_norm else 0.0
            scored.append((cur_sc + prev_sc, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        results: list[dict] = []
        for idx, (sc, doc) in enumerate(scored[:top_k]):
            if idx == 0 and sc >= 3.0:
                results.append(doc)
            elif idx > 0 and sc >= 8.5:
                results.append(doc)

        if is_chat and not results:
            for doc in self._docs:
                if doc["id"] == "lucy_viaje_completo_t1_t2":
                    results.append(doc)
                    break

        return results


_RAG_INSTANCE: PersistentLoreRAG | None = None


def get_lore_rag() -> PersistentLoreRAG:
    global _RAG_INSTANCE
    if _RAG_INSTANCE is None:
        _RAG_INSTANCE = PersistentLoreRAG()
    return _RAG_INSTANCE
