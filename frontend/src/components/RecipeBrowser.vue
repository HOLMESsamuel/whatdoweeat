<template>
  <div class="recipe-browser">
    <!-- Connect-Dropbox card, shown when the user hasn't linked an
         account yet OR returned with an error from the OAuth callback. -->
    <div v-if="!status.loading && !status.connected" class="connect-card">
      <h3>Connect your Dropbox</h3>
      <p class="connect-hint">
        Recipes come from a folder of markdown files in your Dropbox.
        Click below to authorize {{ appName }} to read recipes from your
        account. We only request <code>files.metadata.read</code> +
        <code>files.content.read</code>; you can revoke at any time.
      </p>
      <label class="path-input">
        <span>Folder path in your Dropbox</span>
        <input v-model="recipesPath" type="text" />
      </label>
      <button @click="connectDropbox" :disabled="connecting" class="connect-btn">
        {{ connecting ? 'Opening Dropbox…' : 'Connect Dropbox' }}
      </button>
      <p v-if="connectError" class="connect-error">{{ connectError }}</p>
    </div>

    <!-- Connected: folder bar + filters + recipe list. -->
    <template v-else-if="status.connected">
      <div class="folder-bar">
        <span>
          Reading recipes from
          <code>{{ status.recipes_path || '/' }}</code>
        </span>
        <button class="link-btn" @click="pickingFolder = !pickingFolder">
          {{ pickingFolder ? 'Close' : 'Change folder' }}
        </button>
      </div>
      <dropbox-folder-picker
        v-if="pickingFolder"
        :user-id="userId"
        :initial-path="status.recipes_path || ''"
        @saved="onFolderSaved"
        @cancel="pickingFolder = false"
      />
      <p v-if="recipesError" class="connect-error">{{ recipesError }}</p>
      <div class="idea-toolbar">
        <button
          class="inspire-btn"
          :disabled="!recipes.length"
          @click="inspiring = true"
        >
          ✨ Inspire me
        </button>
        <button
          class="shuffle-btn"
          :disabled="!recipes.length"
          title="Shuffle the order"
          @click="shuffle++"
        >
          🔀 Shuffle
        </button>
      </div>
      <p class="press-hint">
        Tap a recipe to open it, or press and hold to add its ingredients
        to your grocery list. Recipes made or planned recently are at the
        bottom.
      </p>
      <recipe-list
        :recipes="rankedRecipes"
        :loading="loadingRecipes"
        :notes="notes"
        long-press
        @select="viewRecipe"
        @long-press="addToGroceryList"
      />
      <idea-picker
        v-if="inspiring"
        title="What about…"
        :ideas="ideas"
        :page-size="1"
        :notes="notes"
        :busy="adding"
        pick-label="Add to grocery list"
        @pick="pickIdea"
        @open="viewRecipe"
        @close="inspiring = false"
      />
      <div
        v-if="toast"
        class="toast"
        :class="{ 'toast--error': toast.error }"
        role="status"
      >
        {{ toast.text }}
      </div>
    </template>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuth0 } from '@auth0/auth0-vue';
import { getApi } from '../services/api';
import {
  apiErrorMessage,
  cachedRecipes,
  loadRecipes,
} from '../services/recipes';
import RecipeList, { Recipe } from './RecipeList.vue';
import DropboxFolderPicker from './DropboxFolderPicker.vue';
import IdeaPicker from './IdeaPicker.vue';
import {
  History,
  fetchRecipeHistory,
  historyLabel,
  isoDay,
  mealIdeas,
  rankRecipes,
  recordRecipeUse,
} from '../services/suggestions';
import {
  addRecipeToList,
  fetchGroceryLists,
  fetchPantryStaples,
} from '../services/groceries';

interface DropboxStatus {
  connected: boolean;
  recipes_path?: string;
  loading: boolean;
}

const DEFAULT_PATH = '/ideaverse/Recettes/recette-templated';

export default defineComponent({
  name: 'RecipeBrowser',
  components: { RecipeList, DropboxFolderPicker, IdeaPicker },
  setup() {
    const router = useRouter();
    const route = useRoute();
    const { user, isAuthenticated, isLoading } = useAuth0();
    const api = getApi();

    const recipes = ref<Recipe[]>([]);
    const loadingRecipes = ref(false);
    const recipesError = ref('');
    const pickingFolder = ref(false);
    const toast = ref<{ text: string; error: boolean } | null>(null);
    let toastTimer: number | null = null;
    const adding = ref(false);
    const history = ref<History>({});
    const shuffle = ref(0);
    const inspiring = ref(false);

    const rankedRecipes = computed(() =>
      rankRecipes(recipes.value, { history: history.value, shuffle: shuffle.value })
    );
    const ideas = computed(() =>
      mealIdeas(recipes.value, { history: history.value, shuffle: shuffle.value })
    );
    const notes = computed(() => {
      const today = new Date();
      const out: Record<string, string> = {};
      for (const r of recipes.value) {
        const label = historyLabel(r, history.value, today);
        if (label) out[r.id] = label;
      }
      return out;
    });

    const fetchHistory = async () => {
      if (!userId.value) return;
      try {
        history.value = await fetchRecipeHistory(userId.value);
      } catch (err) {
        // Ranking still works without it, just without the recency part.
        console.error('Could not load recipe history', err);
      }
    };

    const status = ref<DropboxStatus>({ connected: false, loading: true });
    const recipesPath = ref(DEFAULT_PATH);
    const connecting = ref(false);
    const connectError = ref('');
    const appName = 'whatdoweeat';

    const userId = ref('');
    // `sub` may contain `|` (e.g. "auth0|abc123") which is a reserved
    // URL char — encode it whenever it goes into a path segment.
    const userPath = () => encodeURIComponent(userId.value);

    const fetchStatus = async () => {
      if (!userId.value) return;
      status.value.loading = true;
      try {
        const { data } = await api.get(`/user/${userPath()}/dropbox/status`);
        status.value = {
          connected: !!data.connected,
          recipes_path: data.recipes_path,
          loading: false,
        };
        if (data.recipes_path) recipesPath.value = data.recipes_path;
      } catch (err) {
        console.error('Could not fetch Dropbox status:', err);
        status.value = { connected: false, loading: false };
      }
    };

    const fetchRecipes = async () => {
      if (!userId.value) return;
      const cached = cachedRecipes(userId.value);
      if (cached) recipes.value = cached;
      loadingRecipes.value = !cached;
      recipesError.value = '';
      try {
        recipes.value = await loadRecipes(userId.value);
      } catch (err: any) {
        console.error('Error fetching recipes:', err);
        recipesError.value = apiErrorMessage(err, 'Could not load recipes.');
        if (err?.response?.status === 404) {
          // The folder is gone (moved/renamed in Dropbox).
          recipes.value = [];
          pickingFolder.value = true;
        }
      } finally {
        loadingRecipes.value = false;
      }
    };

    const onFolderSaved = async (path: string) => {
      status.value.recipes_path = path;
      pickingFolder.value = false;
      recipes.value = [];
      await fetchRecipes();
    };

    const connectDropbox = async () => {
      if (!userId.value) return;
      connecting.value = true;
      connectError.value = '';
      try {
        const { data } = await api.get(
          `/user/${userPath()}/dropbox/auth-url`,
          { params: { recipes_path: recipesPath.value } }
        );
        // Send the browser to Dropbox; it'll redirect back to the
        // backend's /dropbox/callback, which redirects to /#/recipes.
        window.location.href = data.url;
      } catch (err: any) {
        console.error('connectDropbox failed:', err);
        connectError.value =
          err?.response?.data?.detail || 'Could not start Dropbox auth.';
        connecting.value = false;
      }
    };

    const showToast = (text: string, error = false) => {
      toast.value = { text, error };
      if (toastTimer) clearTimeout(toastTimer);
      toastTimer = window.setTimeout(() => (toast.value = null), 4000);
    };

    // Fetched per press rather than cached so edits to lists or staples
    // made elsewhere (Profile, another device) apply straight away.
    const addToGroceryList = async (recipe: Recipe) => {
      if (adding.value || !userId.value) return;
      adding.value = true;
      showToast(`Adding "${recipe.name}"…`);
      try {
        const [lists, staples] = await Promise.all([
          fetchGroceryLists(userId.value),
          fetchPantryStaples(userId.value),
        ]);
        if (!lists.length) {
          showToast('Create a grocery list first.', true);
          return;
        }
        const { added, skipped } = await addRecipeToList(
          lists[0]._id,
          recipe,
          staples
        );
        let text = `Added ${added.length} ingredient(s) from "${recipe.name}" to "${lists[0].name}".`;
        if (skipped.length) text += ` Skipped: ${skipped.join(', ')}.`;
        showToast(text);
        history.value = { ...history.value, [recipe.id]: isoDay(new Date()) };
        recordRecipeUse(userId.value, recipe.id).catch(err =>
          console.error('Could not record recipe use', err)
        );
      } catch (err: any) {
        console.error('Could not add recipe to grocery list', err);
        showToast(
          apiErrorMessage(err, 'Could not add the ingredients.'),
          true
        );
      } finally {
        adding.value = false;
      }
    };

    const pickIdea = async (recipe: Recipe) => {
      await addToGroceryList(recipe);
      inspiring.value = false;
    };

    const viewRecipe = (recipe: Recipe) => {
      router.push(`/recipes/${recipe.id}`);
    };

    // If we just came back from Dropbox's OAuth redirect, surface the
    // result and refresh state.
    if (route.query.dropbox_error) {
      connectError.value = String(route.query.dropbox_error);
    }

    onMounted(async () => {
      // Wait until Auth0 has resolved so we have user.value.sub.
      const start = async () => {
        if (user.value?.sub) {
          userId.value = user.value.sub;
          // Fetch both at once: the recipes endpoint returns [] for users
          // who haven't connected, so there's no need to wait on status.
          await Promise.all([fetchStatus(), fetchRecipes(), fetchHistory()]);
        }
      };
      if (!isLoading.value && isAuthenticated.value) {
        await start();
      } else {
        watch(
          () => isLoading.value,
          async loading => {
            if (!loading && isAuthenticated.value) {
              await start();
            }
          }
        );
      }
    });

    return {
      status,
      recipesPath,
      connecting,
      connectError,
      appName,
      recipes,
      loadingRecipes,
      recipesError,
      pickingFolder,
      userId,
      onFolderSaved,
      toast,
      adding,
      addToGroceryList,
      rankedRecipes,
      ideas,
      notes,
      shuffle,
      inspiring,
      pickIdea,
      viewRecipe,
      connectDropbox,
    };
  }
});
</script>

<style scoped>
.recipe-browser {
  padding: 20px;
}

.connect-card {
  max-width: 560px;
  margin: 40px auto;
  padding: 24px;
  border-radius: 10px;
  background-color: #f8f9fa;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.connect-card h3 {
  margin: 0 0 8px;
  color: #445837;
}

.connect-hint {
  color: #555;
  margin: 0 0 16px;
  line-height: 1.45;
}

.connect-hint code {
  background-color: #eee;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 0.9em;
}

.path-input {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 16px;
}

.path-input span {
  font-size: 0.85em;
  color: #666;
}

.path-input input {
  padding: 8px 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-family: monospace;
}

.connect-btn {
  background-color: #699051;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 10px 18px;
  cursor: pointer;
  font-size: 1em;
}

.connect-btn:hover:not(:disabled) {
  background-color: #445837;
}

.connect-btn:disabled {
  opacity: 0.6;
  cursor: progress;
}

.folder-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin-bottom: 8px;
  color: #555;
  font-size: 0.9em;
}

.folder-bar code {
  background-color: #eee;
  padding: 1px 6px;
  border-radius: 3px;
  overflow-wrap: anywhere;
}

.link-btn {
  background: none;
  border: none;
  padding: 0;
  color: #699051;
  cursor: pointer;
  text-decoration: underline;
}

.idea-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.inspire-btn,
.shuffle-btn {
  border-radius: 6px;
  padding: 8px 14px;
  cursor: pointer;
  border: 1px solid #699051;
  font-size: 0.95em;
}

.inspire-btn {
  flex: 1;
  background-color: #FF843C;
  border-color: #FF843C;
  color: white;
  font-weight: 600;
}

.shuffle-btn {
  background-color: white;
  color: #445837;
}

.inspire-btn:disabled,
.shuffle-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.press-hint {
  color: #777;
  font-size: 0.85em;
  margin: 0 0 8px;
}

.toast {
  position: fixed;
  left: 50%;
  bottom: 24px;
  transform: translateX(-50%);
  width: max-content;
  max-width: calc(100vw - 32px);
  padding: 10px 16px;
  border-radius: 8px;
  background-color: #445837;
  color: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  z-index: 1000;
}

.toast--error {
  background-color: #b91c1c;
}

.connect-error {
  color: #b91c1c;
  margin-top: 12px;
  font-size: 0.9em;
}
</style>
