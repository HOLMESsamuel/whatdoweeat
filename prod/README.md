# Production setup (Hostinger)

The prod stack runs from `/root/whatdoweeat` on Hostinger and pulls
images from Docker Hub. **Recipes are per-user**: each user connects
their own Dropbox account from inside the app, the backend stores their
refresh token encrypted in Mongo, and reads from *their* Dropbox via
the API at request time. The shared `whatdoweeat` Dropbox app is just
the OAuth bridge — what each user authorizes is their own data.

## One-time setup

### 1. Auth0 — create an API and grab its identifier

In the Auth0 dashboard:

1. *Applications → APIs → + Create API*. Name it `whatdoweeat`,
   identifier `https://api.whatdoweeat` (any URL-shaped string works
   as long as it's stable).
2. The identifier is what goes in `AUTH0_AUDIENCE` (backend) and
   `VITE_AUTH0_AUDIENCE` (frontend). They must match.

### 2. Dropbox — create a shared app

At <https://www.dropbox.com/developers/apps>:

1. *Create app* → "Scoped access" → "Full Dropbox" → name it (e.g.
   `whatdoweeat`).
2. Under *Permissions*, enable `files.metadata.read` and
   `files.content.read`. Submit.
3. Under *OAuth 2 → Redirect URIs*, add:
   - `https://whatdoweeat.fr/api/dropbox/callback`  (prod)
   - `http://localhost:8000/dropbox/callback`        (optional, for dev)
4. Note the App key and App secret from *Settings*.

### 3. Generate the token-encryption key

On your laptop:

```bash
python scripts/generate_enc_key.py
```

It prints one line. Save it.

### 4. Drop everything into `/root/whatdoweeat/prod/.env`

```bash
ssh root@your-host
cd /root/whatdoweeat/prod
cp .env.example .env
vim .env   # paste the values from steps 1–3
```

Required vars (see `.env.example` for full descriptions):

```
AUTH0_DOMAIN
AUTH0_AUDIENCE
DROPBOX_APP_KEY
DROPBOX_APP_SECRET
DROPBOX_TOKEN_ENC_KEY
BACKEND_PUBLIC_URL
FRONTEND_PUBLIC_URL
```

### 5. Per-user: each user clicks "Connect Dropbox" in the app

Once the stack is up, every user goes through their own one-click flow:

- Open `/recipes` in the app.
- Adjust the path field if their recipes folder isn't at the default.
- Click *Connect Dropbox* → Dropbox auth page → click Allow → bounced
  back to `/recipes` with their recipes loaded.
- They can change the folder later with *Change folder* (Recipes page
  or Profile), which opens a Dropbox folder browser, and disconnect at
  any time from the *Profile* page.

## How updates flow

The cron job (`30 2 * * *`) runs `update-script.sh`, which:

1. `git pull`s the latest compose / scripts from `master`.
2. Pulls the latest backend + frontend images from Docker Hub.
3. Recreates any container whose image changed.
4. Prunes dangling images.

CI in `.github/workflows/build-push-docker-image.yml` publishes those
images on every push to `master`.

## Bringing the stack up by hand

```bash
cd /root/whatdoweeat/prod
docker compose -f prod-docker-compose.yml pull
docker compose -f prod-docker-compose.yml up -d
docker compose -f prod-docker-compose.yml logs -f backend
```

## Rotating the encryption key

If `DROPBOX_TOKEN_ENC_KEY` is ever leaked, rotate it. The trade-off:
every user's stored token becomes unreadable, so they all have to
click *Connect Dropbox* again. There's no in-place re-encryption.

```bash
# 1. Generate a new key on your laptop:
python scripts/generate_enc_key.py
# 2. Update prod/.env with the new value.
# 3. Wipe the dropbox_credentials collection so users get a clean
#    slate (otherwise their existing entries decrypt to gibberish):
docker compose exec mongodb mongosh whatdoweeat --eval \
  'db.dropbox_credentials.drop()'
# 4. Restart the backend.
docker compose -f prod-docker-compose.yml up -d backend
```

## Single-user / self-hosted alternative

The backend still supports a single-tenant fallback through the
`/recipes` (no user prefix) endpoint, configured by `RECIPE_SOURCE`,
`RECIPES_DIR` and the local-folder env vars. Nothing in the per-user
flow uses it, but it's there if you (or someone) want to deploy
whatdoweeat for a single user without the OAuth setup. The
`docker-compose.yml` in the repo root demonstrates the local-folder
mount.
