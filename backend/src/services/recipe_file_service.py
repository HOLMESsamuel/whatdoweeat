"""Read recipes from a folder of Obsidian-style markdown files.

The expected canonical format is:

    ---
    type: recette
    tags:
    - dessert
    - hiver
    preparation: 20min
    cuisson: 10min
    quantité: 6 personnes
    ---

    # Title

    ## Ingrédients   (or "Ingredients", "Ingrédients :", etc.)

    - [ ] 440g de farine
    - [ ] 5 œufs
    ### Garniture                <- optional sub-groups, kept as description
    - [ ] 1 burrata

    ## Préparation

    - Step one
    - Step two

The parser is tolerant of small variations (heading levels 1-3, optional
checkbox `[ ]`, accented "é", trailing colons). It deliberately ignores
sections like `## Materiel` because equipment doesn't belong on a grocery
list.

The service is structured around a `RecipeSource` protocol so a future
DropboxRecipeSource can be swapped in without changing routes/services.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Protocol, Tuple

import yaml

from ..models.grocery import Grocery
from ..models.recipe import Recipe

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Source abstraction (local folder for dev, Dropbox API for prod)
# ---------------------------------------------------------------------------

@dataclass
class FileMeta:
    """Metadata for a recipe file — cheap to enumerate."""
    identifier: str         # stable, opaque id (e.g. relative path)
    mtime: float            # modification time (seconds since epoch)


@dataclass
class SourceFile:
    """A single recipe file with its content."""
    identifier: str
    text: str
    mtime: float


class RecipeSource(Protocol):
    """Two-step interface so we don't pay to download every file on each
    request — `list_files()` returns cheap metadata, `read_file()` is only
    called when the cache says the parsed copy is stale."""

    def list_files(self) -> Iterable[FileMeta]:
        ...

    def read_file(self, identifier: str) -> str:
        ...


class LocalFolderRecipeSource:
    """Read .md files from a folder on the local filesystem."""

    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)

    def list_files(self) -> Iterable[FileMeta]:
        if not self.root.exists():
            log.warning("Recipe folder does not exist: %s", self.root)
            return
        for path in sorted(self.root.glob("*.md")):
            try:
                stat = path.stat()
            except OSError as exc:
                log.warning("Could not stat %s: %s", path, exc)
                continue
            yield FileMeta(
                identifier=str(path.relative_to(self.root)),
                mtime=stat.st_mtime,
            )

    def read_file(self, identifier: str) -> str:
        return (self.root / identifier).read_text(encoding="utf-8")


class DropboxRecipeSource:
    """Read .md files from a folder in the user's Dropbox via the API.

    Authenticates with a long-lived refresh token (set up once via the
    `scripts/get_dropbox_refresh_token.py` helper). The `client_modified`
    timestamp on each file plays the role of `mtime`, so the existing
    parse-cache invalidation logic in RecipeFileService transfers
    unchanged.
    """

    def __init__(
        self,
        app_key: str,
        app_secret: str,
        refresh_token: str,
        recipes_path: str,
    ):
        # Imported lazily so the dropbox SDK isn't a hard dep when running
        # with RECIPE_SOURCE=local.
        try:
            from dropbox import Dropbox
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "RECIPE_SOURCE=dropbox requires the `dropbox` package. "
                "Add it to requirements.txt."
            ) from exc
        self._client = Dropbox(
            app_key=app_key,
            app_secret=app_secret,
            oauth2_refresh_token=refresh_token,
        )
        # Dropbox paths must start with "/" and not have a trailing slash.
        if not recipes_path.startswith("/"):
            recipes_path = "/" + recipes_path
        self.recipes_path = recipes_path.rstrip("/")

    def list_files(self) -> Iterable[FileMeta]:
        from dropbox import files as dbx_files

        try:
            result = self._client.files_list_folder(self.recipes_path)
        except Exception as exc:  # pragma: no cover - network-dependent
            log.error("Dropbox files_list_folder failed: %s", exc)
            return
        while True:
            for entry in result.entries:
                if not isinstance(entry, dbx_files.FileMetadata):
                    continue
                if not entry.name.lower().endswith(".md"):
                    continue
                # `client_modified` mirrors the file's mtime as written by
                # the editing client (Obsidian on phone/desktop). Use that
                # rather than `server_modified` so the mtime matches what
                # local dev would see.
                yield FileMeta(
                    identifier=entry.name,
                    mtime=entry.client_modified.timestamp(),
                )
            if not result.has_more:
                break
            try:
                result = self._client.files_list_folder_continue(result.cursor)
            except Exception as exc:  # pragma: no cover
                log.error("Dropbox files_list_folder_continue failed: %s", exc)
                return

    def read_file(self, identifier: str) -> str:
        path = f"{self.recipes_path}/{identifier}"
        _meta, response = self._client.files_download(path)
        return response.content.decode("utf-8")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# Headings that indicate the ingredients section. Equipment ("Materiel") is
# intentionally excluded — it doesn't belong on a grocery list.
_ING_HEADING_RE = re.compile(
    r"^\s*#{1,3}\s*(?:ingr[eé]dient[s]?)\s*:?\s*$",
    re.IGNORECASE,
)

# Headings that indicate the preparation/steps section.
_STEPS_HEADING_RE = re.compile(
    r"^\s*#{1,3}\s*(?:pr[eé]paration|preparation|[eé]tapes|steps?|instructions?)\s*:?\s*$",
    re.IGNORECASE,
)

# Any heading at all (used to know when a section ends).
_ANY_HEADING_RE = re.compile(r"^\s*#{1,6}\s+\S")
# Subheading like `### Garniture` or `### **Assaisonnement :**` — strip
# leading/trailing `*`, `_`, and `:` decorations.
_SUBHEADING_RE = re.compile(
    r"^\s*#{3,6}\s+[\*_]*\s*(.+?)\s*[\*_:]*\s*$"
)
_LEVEL_2_OR_LESS_RE = re.compile(r"^\s*#{1,2}\s+\S")

# Bullet lines, with or without the Obsidian task checkbox. Accepts both
# `-`/`*`/`+` bullets and numbered list markers (`1.`, `1)`).
_BULLET_RE = re.compile(
    r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s*)?(.+?)\s*$"
)
# A "soft subgroup" inside a section: a non-bullet, non-blank, non-heading
# line that ends with a colon, used in some recipes instead of `### ...`
# (e.g. `Pour la pâte sucrée :`).
_SOFT_SUBGROUP_RE = re.compile(r"^\s*([^-*+#\s].{0,80}?)\s*:\s*$")

# A leading quantity: number (with optional decimal, comma, or fraction)
# followed by an optional unit / counter-word phrase.
_UNIT_WORDS = (
    r"(?:g|kg|mg|ml|cl|dl|l|L|cm|mm)\b"
    r"|(?:cuill[èe]res?\s+(?:à|a)\s+(?:soupe|caf[eé]))"
    r"|(?:c\.?\s*(?:à|a)\s*\.?\s*[sc]\.?)"
    r"|(?:sachets?|pinc[eé]es?|gousses?|tranches?|branches?|feuilles?|bouquets?|verres?|tasses?|bouillon\s+cubes?|cubes?|gros(?:ses)?|petits?)\b"
)
_QUANTITY_RE = re.compile(
    rf"^\s*(?P<qty>\d+(?:[.,/]\d+)?\s*(?:{_UNIT_WORDS})?(?:\s+(?:{_UNIT_WORDS}))*)"
    r"\s+(?P<rest>.+)$",
    re.IGNORECASE,
)
# Connecting words to strip from the start of the name and stash in description.
_CONNECTOR_RE = re.compile(r"^(de\s+|d['’]\s*)", re.IGNORECASE)


_FM_KV_RE = re.compile(r"^([A-Za-zÀ-ÿ_][\w\-]*)\s*:\s*(.*)$")
_FM_LIST_ITEM_RE = re.compile(r"^\s*-\s+(.*)$")


def _parse_frontmatter_permissive(fm_text: str) -> dict:
    """Hand-rolled fallback parser for the frontmatter format we actually
    see. Handles `key: value` (where value can itself contain colons, e.g.
    `remarque: Quantité originale: 1 moule`) and bullet-list values.
    """
    out: dict = {}
    current_key: Optional[str] = None
    current_list: Optional[list] = None
    for raw in fm_text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        list_m = _FM_LIST_ITEM_RE.match(line)
        if list_m and current_list is not None:
            current_list.append(list_m.group(1).strip())
            continue
        kv = _FM_KV_RE.match(line)
        if kv:
            key = kv.group(1).strip()
            value = kv.group(2).strip()
            if value == "":
                # Either empty string or start of a list — disambiguate by
                # peeking at whether the next non-blank line is a `- item`.
                # We can't easily peek here, so optimistically open a list;
                # if no list items follow, we'll later collapse it to "".
                current_list = []
                out[key] = current_list
                current_key = key
            else:
                out[key] = value
                current_key = key
                current_list = None
    # Collapse any opened-but-empty lists back to empty strings (e.g.
    # `preparation:` with nothing under it).
    for k, v in list(out.items()):
        if isinstance(v, list) and not v:
            out[k] = ""
    return out


def _split_frontmatter(text: str) -> Tuple[dict, str]:
    """Split YAML frontmatter from body. Returns (frontmatter_dict, body)."""
    if not text.startswith("---"):
        return {}, text
    # Find the closing delimiter on its own line.
    parts = text.split("\n")
    if len(parts) < 2:
        return {}, text
    end_idx: Optional[int] = None
    for i in range(1, len(parts)):
        if parts[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return {}, text
    fm_text = "\n".join(parts[1:end_idx])
    body = "\n".join(parts[end_idx + 1 :])
    fm: dict
    try:
        loaded = yaml.safe_load(fm_text) or {}
        fm = loaded if isinstance(loaded, dict) else {}
    except yaml.YAMLError:
        # Common cause: `remarque: Quantité originale: 1 moule` — strict
        # YAML rejects the bare colon. Fall back to a permissive parser.
        fm = _parse_frontmatter_permissive(fm_text)
    return fm, body


def _extract_section(body: str, heading_re: re.Pattern) -> List[str]:
    """Return the lines of the section whose heading matches `heading_re`,
    stopping at the next H1/H2 heading (sub-headings stay with the section)."""
    lines = body.split("\n")
    in_section = False
    out: List[str] = []
    for line in lines:
        if heading_re.match(line):
            in_section = True
            continue
        if in_section and _LEVEL_2_OR_LESS_RE.match(line):
            break
        if in_section:
            out.append(line)
    return out


def _parse_ingredient_line(raw: str) -> Tuple[str, str, str]:
    """Split an ingredient line into (quantity, name, remainder).

    Best-effort: if no leading numeric quantity is found, everything goes
    into name. The returned `remainder` is connector-words like "de" / "d'"
    that we strip from the name so they live in description rather than
    polluting matching/de-duplication on the grocery list.
    """
    m = _QUANTITY_RE.match(raw)
    if m:
        qty = m.group("qty").strip()
        rest = m.group("rest").strip()
    else:
        qty = ""
        rest = raw.strip()

    cm = _CONNECTOR_RE.match(rest)
    connector = ""
    if cm:
        connector = cm.group(0).strip()
        rest = rest[cm.end() :].strip()
    return qty, rest, connector


def _ingredients_from_section(lines: List[str], recipe_name: str) -> List[Grocery]:
    """Walk an ingredients section, honouring `### subgroup` labels and
    soft subgroups like `Pour la pâte sucrée :`."""
    current_group: Optional[str] = None
    out: List[Grocery] = []
    for line in lines:
        sub = _SUBHEADING_RE.match(line)
        if sub:
            current_group = sub.group(1).strip()
            continue
        bullet = _BULLET_RE.match(line)
        if bullet:
            raw = bullet.group(1).strip()
            if not raw:
                continue
            qty, name, _connector = _parse_ingredient_line(raw)
            if not name:
                continue
            description_bits = [recipe_name]
            if current_group:
                description_bits.append(current_group)
            out.append(
                Grocery(
                    id=str(uuid.uuid4()),
                    name=name,
                    quantity=qty,
                    description=" · ".join(description_bits),
                )
            )
            continue
        soft = _SOFT_SUBGROUP_RE.match(line)
        if soft:
            current_group = soft.group(1).strip()
    return out


def _steps_from_section(lines: List[str]) -> List[str]:
    current_group: Optional[str] = None
    out: List[str] = []
    for line in lines:
        sub = _SUBHEADING_RE.match(line)
        if sub:
            current_group = sub.group(1).strip()
            continue
        bullet = _BULLET_RE.match(line)
        if not bullet:
            continue
        text = bullet.group(1).strip()
        if not text:
            continue
        if current_group:
            out.append(f"{current_group}: {text}")
        else:
            out.append(text)
    return out


_SERVINGS_RE = re.compile(r"\b(\d+)")


def _parse_servings(value) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    m = _SERVINGS_RE.search(str(value))
    return int(m.group(1)) if m else 0


def _format_time(prep, cuisson) -> str:
    prep = (prep or "").strip() if isinstance(prep, str) else ""
    cuisson = (cuisson or "").strip() if isinstance(cuisson, str) else ""
    if prep and cuisson:
        return f"{prep} + {cuisson}"
    return prep or cuisson


def _file_id(identifier: str) -> str:
    """Stable id for a recipe — short hash of its source identifier."""
    return hashlib.sha1(identifier.encode("utf-8")).hexdigest()[:16]


def parse_recipe(source: SourceFile) -> Optional[Recipe]:
    """Parse one source file into a Recipe. Returns None if the file is
    not a recipe (i.e. doesn't have `type: recette` in frontmatter)."""
    fm, body = _split_frontmatter(source.text)
    if (fm.get("type") or "").lower() != "recette":
        return None

    # Title: prefer the first H1, fall back to the filename.
    title = ""
    for line in body.split("\n"):
        if line.startswith("# ") and not line.startswith("##"):
            title = line[2:].strip()
            break
    if not title:
        title = Path(source.identifier).stem

    ing_lines = _extract_section(body, _ING_HEADING_RE)
    step_lines = _extract_section(body, _STEPS_HEADING_RE)

    tags = fm.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    tags = [str(t).strip() for t in tags if str(t).strip()]

    return Recipe(
        id=_file_id(source.identifier),
        name=title,
        tags=tags,
        groceries=_ingredients_from_section(ing_lines, title),
        steps=_steps_from_section(step_lines),
        servings=_parse_servings(fm.get("quantité") or fm.get("quantite")),
        time=_format_time(fm.get("preparation"), fm.get("cuisson")),
        preparation=(fm.get("preparation") or None) or None,
        cuisson=(fm.get("cuisson") or None) or None,
        link=fm.get("link"),
        remarque=fm.get("remarque"),
        source_path=source.identifier,
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

# Cap on parallel reads from a RecipeSource. Dropbox handles many
# concurrent calls happily; the number is mainly chosen so we don't
# create a huge thread pool when the user has hundreds of recipes.
_MAX_PARALLEL_READS = int(os.getenv("RECIPE_PARALLEL_READS", "16"))


class RecipeFileService:
    """Caches parsed recipes per-file, invalidated by mtime.

    The cache is held in memory; an external persistence layer can call
    `hydrate()` once at startup and `take_pending()` after each refresh
    to mirror the cache to durable storage. The service itself doesn't
    talk to a database — it just exposes the dirty-tracking hooks.
    """

    def __init__(self, source: RecipeSource):
        self.source = source
        self._lock = threading.Lock()
        self._cache: dict[str, Tuple[float, Optional[Recipe]]] = {}
        # Pending writes for an external persistent store. `_dirty` holds
        # entries that need to be upserted, `_removed` holds identifiers
        # that need to be deleted. Routes drain these via take_pending().
        self._dirty: dict[str, Tuple[float, Optional[Recipe]]] = {}
        self._removed: set[str] = set()

    def _read_and_parse(self, meta: FileMeta) -> Optional[Recipe]:
        text = self.source.read_file(meta.identifier)
        return parse_recipe(
            SourceFile(
                identifier=meta.identifier,
                text=text,
                mtime=meta.mtime,
            )
        )

    def _refresh(self) -> List[Recipe]:
        # Listing is one Dropbox call; do it without the lock so concurrent
        # callers don't serialize behind each other.
        metas = list(self.source.list_files())

        with self._lock:
            cache_snapshot = dict(self._cache)

        stale: List[FileMeta] = []
        for meta in metas:
            cached = cache_snapshot.get(meta.identifier)
            if not cached or cached[0] != meta.mtime:
                stale.append(meta)

        # Download + parse stale files in parallel. Each Dropbox call is
        # mostly network wait, so threads give a real speed-up despite
        # the GIL.
        fresh: dict[str, Tuple[float, Optional[Recipe]]] = {}
        if stale:
            workers = min(_MAX_PARALLEL_READS, len(stale))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(self._read_and_parse, m): m for m in stale}
                for fut in as_completed(futures):
                    meta = futures[fut]
                    try:
                        recipe = fut.result()
                    except Exception as exc:
                        log.exception("Failed to parse %s: %s", meta.identifier, exc)
                        recipe = None
                    fresh[meta.identifier] = (meta.mtime, recipe)

        seen = {meta.identifier for meta in metas}
        with self._lock:
            for ident, entry in fresh.items():
                self._cache[ident] = entry
                self._dirty[ident] = entry
                self._removed.discard(ident)
            for stale_id in list(self._cache.keys()):
                if stale_id not in seen:
                    self._cache.pop(stale_id, None)
                    self._dirty.pop(stale_id, None)
                    self._removed.add(stale_id)
            recipes = [
                entry[1]
                for meta in metas
                if (entry := self._cache.get(meta.identifier)) and entry[1] is not None
            ]
        return recipes

    def hydrate(self, entries: dict[str, Tuple[float, Optional[Recipe]]]) -> None:
        """Populate the in-memory cache from a persisted snapshot. Call
        before the first refresh; entries don't count as dirty (they're
        already in the persistent store)."""
        with self._lock:
            self._cache.update(entries)

    def take_pending(
        self,
    ) -> Tuple[dict[str, Tuple[float, Optional[Recipe]]], set[str]]:
        """Return and clear pending upserts and deletions. Caller is
        expected to flush these to the persistent store."""
        with self._lock:
            dirty = self._dirty
            removed = self._removed
            self._dirty = {}
            self._removed = set()
        return dirty, removed

    def get_recipes(self) -> List[Recipe]:
        return self._refresh()

    def get_recipe(self, recipe_id: str) -> Optional[Recipe]:
        for recipe in self._refresh():
            if recipe.id == recipe_id:
                return recipe
        return None


def build_default_service() -> RecipeFileService:
    """Construct a RecipeFileService based on env vars.

    RECIPE_SOURCE selects the backend:
      - "local" (default): reads from RECIPES_DIR on disk.
      - "dropbox": reads from a folder in the user's Dropbox account,
        authenticated via DROPBOX_APP_KEY / DROPBOX_APP_SECRET /
        DROPBOX_REFRESH_TOKEN, with the folder path in
        DROPBOX_RECIPES_PATH.
    """
    source_kind = os.getenv("RECIPE_SOURCE", "local").lower()
    if source_kind == "dropbox":
        app_key = os.environ["DROPBOX_APP_KEY"]
        app_secret = os.environ["DROPBOX_APP_SECRET"]
        refresh_token = os.environ["DROPBOX_REFRESH_TOKEN"]
        recipes_path = os.environ["DROPBOX_RECIPES_PATH"]
        log.info("Using DropboxRecipeSource at %s", recipes_path)
        return RecipeFileService(
            DropboxRecipeSource(
                app_key=app_key,
                app_secret=app_secret,
                refresh_token=refresh_token,
                recipes_path=recipes_path,
            )
        )
    root = os.getenv("RECIPES_DIR", "/recipes")
    log.info("Using LocalFolderRecipeSource at %s", root)
    return RecipeFileService(LocalFolderRecipeSource(root))
