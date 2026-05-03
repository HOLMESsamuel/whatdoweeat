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

    <!-- Connected: filters + recipe list. -->
    <recipe-list
      v-else-if="status.connected"
      :recipes="recipes"
      :loading="loadingRecipes"
      @select="viewRecipe"
    />
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuth0 } from '@auth0/auth0-vue';
import { getApi } from '../services/api';
import RecipeList, { Recipe } from './RecipeList.vue';

interface DropboxStatus {
  connected: boolean;
  recipes_path?: string;
  loading: boolean;
}

const DEFAULT_PATH = '/ideaverse/Recettes/recette-templated';

export default defineComponent({
  name: 'RecipeBrowser',
  components: { RecipeList },
  setup() {
    const router = useRouter();
    const route = useRoute();
    const { user, isAuthenticated, isLoading } = useAuth0();
    const api = getApi();

    const recipes = ref<Recipe[]>([]);
    const loadingRecipes = ref(false);

    const status = ref<DropboxStatus>({ connected: false, loading: true });
    const recipesPath = ref(DEFAULT_PATH);
    const connecting = ref(false);
    const connectError = ref('');
    const appName = 'whatdoweeat';

    let userId = '';
    // `sub` may contain `|` (e.g. "auth0|abc123") which is a reserved
    // URL char — encode it whenever it goes into a path segment.
    const userPath = () => encodeURIComponent(userId);

    const fetchStatus = async () => {
      if (!userId) return;
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
      if (!userId || !status.value.connected) return;
      loadingRecipes.value = true;
      try {
        const { data } = await api.get(`/user/${userPath()}/recipes`);
        recipes.value = data || [];
      } catch (err) {
        console.error('Error fetching recipes:', err);
        recipes.value = [];
      } finally {
        loadingRecipes.value = false;
      }
    };

    const connectDropbox = async () => {
      if (!userId) return;
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
          userId = user.value.sub;
          await fetchStatus();
          if (status.value.connected) {
            await fetchRecipes();
          }
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

.connect-error {
  color: #b91c1c;
  margin-top: 12px;
  font-size: 0.9em;
}
</style>
