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
  `grocery_lists`, `dropbox_credentials`, `meal_plans`. Recipes are NOT in
  Mongo — they are parsed from markdown files in the user's Dropbox by
  `RecipeFileService`.
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
  per user. Call `invalidate_user_recipe_cache(user_id)` after credential
  or path changes (the OAuth callback does this).
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
- Backend tests: pytest in `backend/tests/` — coverage is sparse, only
  `models_tests/grocery_test.py`. Don't assume a test exists for what
  you change.

## Things that have bitten me

- Forgetting `encodeURIComponent` on Auth0 `sub` → silent route mismatches
  because `|` becomes a literal pipe in the path.
- `_id` returned from Mongo can be either a `str` or an ObjectId-as-dict
  depending on the path; the planner normalizes with
  `typeof d._id === 'string' ? d._id : String(d._id)`.
- `start_dev.sh` does `kill_port 27017` — if you have a personal mongod
  running on 27017 outside this project, it'll die.
