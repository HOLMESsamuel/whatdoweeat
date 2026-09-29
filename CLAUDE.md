# CLAUDE.md

Notes for future Claude sessions. Code is the source of truth; this file
covers things you'd otherwise have to re-derive each time.
Claude always updates this file when something changes.

## Architecture

- **Frontend**: Vue 3 + TS + Vite, Auth0 SPA SDK (`@auth0/auth0-vue`),
  hash router (`createWebHashHistory`), axios client. Entry: `frontend/src/main.ts`.
- **Backend**: FastAPI + motor (async MongoDB). Auth0 JWT verified via JWKS
  in `backend/src/services/auth_service.py`.
- **Persistence**: MongoDB `whatdoweeat`. Collections: `users`,
  `grocery_lists`, `dropbox_credentials`, `meal_plans`, `recipe_cache`.
  Recipes themselves are NOT in Mongo — they're parsed from markdown
  files in the user's Dropbox by `RecipeFileService`. `recipe_cache`
  only persists the parse cache so a backend restart doesn't have to
  re-download every file.
- **Realtime**: per-grocery-list WebSocket at `/ws/{list_id}`. The
  `ConnectionManager` is a singleton; `db_service.py` mutations broadcast
  through it from `grocery_list_routes.py` so other clients refetch.

## Identity / auth conventions

- The user id everywhere is the Auth0 `sub` claim (e.g. `auth0|abc123`,
  `google-oauth2|123`). It contains `|` which is reserved in URL paths —
  always `encodeURIComponent(sub)` before sticking it in a URL. The
  pattern in components is a `userPath()` helper that does this.
- Routes shaped `/user/{user_id}/...` use `Depends(require_user_id)`,
  which 403s if the path id ≠ token `sub`. Plain auth uses
  `Depends(get_current_user)`.
- Frontend axios client is a singleton: `createApi(auth0)` is called once
  in `main.ts`; components use `getApi()`. The interceptor injects a
  fresh access token per request.
- Auth0 audience must match on both sides: `VITE_AUTH0_AUDIENCE`
  (frontend) and `AUTH0_AUDIENCE` (backend). Without audience, Auth0
  returns an opaque token instead of a JWT and backend calls 401.

## Recipes

- Read-only by design. `POST/PUT/DELETE /recipe*` return 405. Source of
  truth is markdown in the user's Obsidian vault on Dropbox.
- Per-user route: `GET /user/{user_id}/recipes` and `.../recipe/{id}`.
  Reads via the user's stored Dropbox refresh token (encrypted at rest
  via `crypto_service`, decrypted on demand).
- Single-tenant fallback: `GET /recipes` reads from `RECIPE_SOURCE=local`
  (env var `RECIPES_DIR`) — useful for dev without Dropbox.
- `_user_services` cache in `recipe_routes.py` holds one `RecipeFileService`
  per user. After credential or path changes call
  `reset_user_recipe_cache(user_id)` (OAuth callback, `PUT .../dropbox/path`
  and disconnect do), which also purges the user's Mongo `recipe_cache`:
  cache keys are bare filenames, so without the purge a same-named file
  with the same mtime in the new folder would be served from the old
  folder's parse. `_flush_pending` skips writes from a service that was
  replaced mid-request for the same reason.
- Recipe folder is per user (`dropbox_credentials.recipes_path`), chosen
  at connect time and changeable later via `DropboxFolderPicker.vue`
  (Recipes page folder bar + Profile). It's backed by
  `GET /user/{id}/dropbox/folders?path=` (subfolders of a path) and
  `PUT /user/{id}/dropbox/path`, which 404s if the folder doesn't exist.
  Paths go through `normalize_dropbox_path` (leading `/`, no trailing
  `/`, Dropbox root is `""`). Default is `DEFAULT_RECIPES_PATH` in
  `models/dropbox_credential.py`.
- Source listing failures raise instead of yielding nothing:
  `RecipeFolderNotFound` → 404 with detail, `RecipeSourceAuthError`
  (revoked token) → 409, other `RecipeSourceError` → 502 (mapping in
  `source_error_to_http`). The single-tenant `/recipes` fallback returns
  `[]` for a missing local folder. Before this, a Dropbox blip looked like "all files deleted" and
  wiped both cache tiers. Listing happens before the cache is touched.
- The Dropbox SDK is synchronous, so the `/recipes` and `/recipe/{id}`
  routes wrap `service.get_recipes()` / `service.get_recipe()` in
  `asyncio.to_thread` — without that the event loop blocks during a
  cold load and every other request stalls. Inside `_refresh`,
  stale-file downloads run through a `ThreadPoolExecutor` (size from
  `RECIPE_PARALLEL_READS`, default 16). `_lock` is only held for cache
  reads/writes, never during network I/O; a separate `_refresh_lock`
  serializes whole refreshes so concurrent cold loads download each
  file once.
- Two-tier cache: in-memory in `RecipeFileService._cache`, mirrored to
  Mongo `recipe_cache` (one doc per `(user_id, identifier)` with
  `mtime` + serialized `recipe`). Per-user routes call
  `_hydrate_from_persistent_cache` once when building a service, and
  `_flush_pending` after each request. `_refresh` tracks dirty/removed
  entries internally; routes drain them via `take_pending()`. Freshness
  still hinges on `files_list_folder` running on every request — that's
  what catches Obsidian edits, so don't add a TTL there. Per-file
  invalidation is mtime equality, so any change in `client_modified`
  busts the cache. Mongo persistence is best-effort: failures log but
  don't fail the request. Fallback (single-tenant) routes don't use the
  persistent cache.
- The recipe model includes `groceries: List[Grocery]` already populated
  by the parser, including a sub-group passed via `description` as
  `"Recipe · Subgroup"`. RecipeDetail.vue parses that with `groupOf`.
- Recipe list UI is shared via `components/RecipeList.vue` — used by
  `RecipeBrowser` (recipes page) and `Planner` (meal planner). Props:
  `recipes`, `selectedId`, `loading`, `compact`, `draggable`. Emits
  `select(recipe)`. When `draggable`, sets the recipe id on the drag
  event under MIME `application/x-recipe-id` (constant
  `RECIPE_DRAG_MIME` exported alongside the `Recipe` type); the
  planner's drop handler reads it back from `event.dataTransfer`. The
  parent owns recipe fetching; RecipeList just renders/filters.
- Frontend recipe fetching goes through `services/recipes.ts`: a
  session-level cache (`cachedRecipes`/`cachedRecipe`) plus
  `loadRecipes(userId)` that dedupes in-flight requests. Pages render the
  cached copy immediately, then revalidate; RecipeDetail renders from the
  cached list before its own fetch. Call `clearRecipeCache()` on folder
  change / disconnect. The recipes endpoint returns `[]` when Dropbox
  isn't connected, so pages fetch it in parallel with the status call.

## Grocery list

- Document shape: `{_id, user_ids: [sub, ...], name, groceries: [Grocery]}`.
  A list can have multiple users (joined by id, see ListContainer.vue).
- Grocery shape: `{id, name, quantity, description, type, color}`. `id`
  is set server-side via `generate_uuid()` on add. `type` drives the
  section grouping in the UI; `color` is the visible chip color.
- WebSocket URL on the frontend: `${VITE_WS_BACKEND_BASE_URL}/${listId}`.
  The component refetches the whole list on any message rather than
  applying diffs.

## Meal planner

- Frontend route: `/planner` → `Planner.vue`. Recipe search list +
  weekly calendar (Mon–Sun) with HTML5 drag-and-drop + click-to-place
  fallback for touch.
- Backend: `meal_plans` collection, one doc per user.
  - `GET /user/{user_id}/meal-plan` → `{user_id, meals: MealSlot[]}`
  - `PUT /user/{user_id}/meal-plan` replaces the whole plan.
  - `MealSlot = {day: 'YYYY-MM-DD', label: str, recipes: MealRecipe[]}`,
    `MealRecipe = {recipe_id, recipe_name}`. Multiple recipes per slot
    (multi-course) and free-form `label` (lets users plan things outside
    Lunch/Dinner like a Saturday baking project).
- Slot model:
  - `Lunch` and `Dinner` are built-in defaults — always rendered for
    every day, can hold many recipes, can't be renamed/deleted. Empty
    built-ins are NOT persisted (re-derived on render).
  - Custom slots are user-added via `+ Add slot`, persist even when
    empty, can be renamed (click label) or deleted (× on slot header).
  - Built-in detection is case-insensitive (`sameLabel` helper).
- `db_service._migrate_meal_plan_doc` upgrades any legacy
  `{day, slot, recipe_id, recipe_name}` entries on read by grouping by
  `(day, slot)` into the multi-recipe shape. Pass-through for new docs.
- Side effect on placement: ingredients of the placed recipe are POSTed
  to the user's **first** grocery list, with `description = recipe.name`.
  Each placement adds ingredients again (even duplicates of the same
  recipe).
- Side effect on removal: `removeIngredientsFromFirstList` deletes
  matching items. Match key is `(description == recipe.name AND
  name == ingredient.name)`, case-insensitive, picking each grocery at
  most once per call so removing one copy of a duplicated recipe only
  clears one set of ingredients. If the user edited a description or
  name the match silently misses — manual cleanup takes over. Triggered
  from `removeRecipeAt` and `removeSlot` (custom slot deletion) via the
  `cleanupForRemovedRecipe` helper, which looks up the full recipe in
  `recipes.value` (no-op if the recipe isn't loaded).

## Code conventions

- Each routes module instantiates its own `DBService(MONGO_URI, ...)` at
  module load and exposes a `get_db()` dependency. Don't try to share a
  single instance across modules; that's the existing pattern.
- Routes use `Response` + manual `status_code = 204` for "not found"
  rather than raising 404. The frontend treats 204 as not-found.
- IDs in URLs: grocery list ids are `PydanticObjectId` (Mongo ObjectId);
  recipe ids are filename-derived stable hashes (strings); user ids are
  url-encoded Auth0 `sub`.
- Comments: code has minimal comments, only on non-obvious things (auth
  caveats, Dropbox path quirks, etc.). Match that — don't add narration.

## Dev workflow

- One-shot dev startup: `./start_dev.sh` (macOS, opens two new Terminal
  tabs for backend+frontend, also runs `mongod --dbpath ./db`). Ports:
  - mongo 27017, backend 8000, frontend 5173.
- Secrets live in `backend/.env.dev` (sourced by start_dev.sh). At a
  minimum: `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, `TOKEN_ENC_KEY`,
  `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`. There's a
  `.env.dev.example`.
- Frontend env vars: `VITE_BACKEND_BASE_URL`, `VITE_WS_BACKEND_BASE_URL`,
  `VITE_AUTH0_AUDIENCE`. Set in `frontend/.env`.
- Local Python env may be missing `lingua` (used by `item_sort_service`).
  `python -c "from src.services.db_service import ..."` will fail with
  `No module named 'lingua'` — that's an env issue, not your code. Use
  `python -m py_compile <files>` for a quick syntax check that doesn't
  import deps.
- Frontend checks: `npx vue-tsc --noEmit` for types, `npx vite build` for
  a full build. Both fast (<2s typecheck, <2s build). No frontend tests.
- Backend tests: pytest in `backend/tests/`, run from the repo root
  (`python -m pytest backend/tests`; imports are `backend.src...`).
  Coverage: `models_tests/grocery_test.py` and
  `services_tests/recipe_file_service_test.py` (cache reuse, listing
  errors, pagination, path normalization, refresh coalescing). Don't
  assume a test exists for what you change.

## Things that have bitten me

- Forgetting `encodeURIComponent` on Auth0 `sub` → silent route mismatches
  because `|` becomes a literal pipe in the path.
- `_id` returned from Mongo can be either a `str` or an ObjectId-as-dict
  depending on the path; the planner normalizes with
  `typeof d._id === 'string' ? d._id : String(d._id)`.
- `start_dev.sh` does `kill_port 27017` — if you have a personal mongod
  running on 27017 outside this project, it'll die.
- The PWA service worker (`vite-plugin-pwa`, generateSW) serves the
  cached SPA shell for every navigation unless the URL matches
  `workbox.navigateFallbackDenylist` in `vite.config.ts`. `/api/` is on
  that list; without it the Dropbox OAuth redirect to
  `/api/dropbox/callback` never reached the backend and Auth0 then
  choked on the Dropbox `code`/`state` ("Invalid state"). Any new
  backend URL the browser navigates to must live under `/api/`.
  `createAuth0` also gets `skipRedirectCallback` for `/api/` paths.
- Prod certbot used `--force-renewal`, so every deploy issued a new
  cert and hit Let's Encrypt's 5-certs-per-week limit (certbot container
  exited 1). It now uses `--keep-until-expiring`.
