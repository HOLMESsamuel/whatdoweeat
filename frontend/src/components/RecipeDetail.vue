<template>
  <div class="recipe-detail" v-if="recipe">
    <div class="recipe-header">
      <h1>{{ recipe.name }}</h1>
      <div class="recipe-meta">
        <span v-if="recipe.time" class="time">⏱️ {{ recipe.time }}</span>
        <span v-if="recipe.servings" class="servings">
          🍽️ {{ recipe.servings }} servings
        </span>
      </div>
      <div class="recipe-tags" v-if="recipe.tags && recipe.tags.length">
        <span v-for="tag in recipe.tags" :key="tag" class="recipe-tag">
          {{ tag }}
        </span>
      </div>
      <p v-if="recipe.remarque" class="recipe-remark">{{ recipe.remarque }}</p>
    </div>

    <div class="recipe-sections">
      <div class="ingredients-section">
        <h2>Ingredients</h2>
        <ul v-if="recipe.groceries && recipe.groceries.length" class="ingredients-list">
          <li v-for="(item, index) in recipe.groceries" :key="index">
            <span v-if="item.quantity" class="qty">{{ item.quantity }}</span>
            <span class="name">{{ item.name }}</span>
            <span v-if="hasGroup(item)" class="group">— {{ groupOf(item) }}</span>
          </li>
        </ul>
        <p v-else class="empty">No ingredients listed in the source file.</p>
      </div>

      <div class="steps-section">
        <h2>Steps</h2>
        <ol v-if="recipe.steps && recipe.steps.length" class="steps-list">
          <li v-for="(step, index) in recipe.steps" :key="index">
            {{ step }}
          </li>
        </ol>
        <p v-else class="empty">No preparation steps in the source file.</p>
      </div>
    </div>

    <div class="back-button">
      <button @click="goBack">← Back to Recipes</button>
    </div>
  </div>

  <div v-else-if="error" class="error">
    <p>Couldn't load this recipe.</p>
    <button @click="goBack">← Back to Recipes</button>
  </div>

  <div v-else class="loading">
    <p>Loading recipe...</p>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuth0 } from '@auth0/auth0-vue';
import { getApi } from '../services/api';

interface Grocery {
  id: string;
  name: string;
  quantity: string;
  description?: string;
}

interface Recipe {
  id: string;
  name: string;
  tags: string[];
  time: string;
  servings: number;
  groceries: Grocery[];
  steps: string[];
  remarque?: string;
}

export default defineComponent({
  name: 'RecipeDetail',
  setup() {
    const route = useRoute();
    const router = useRouter();
    const { user, isAuthenticated, isLoading } = useAuth0();
    const api = getApi();
    const recipe = ref<Recipe | null>(null);
    const error = ref(false);

    const fetchRecipe = async () => {
      const sub = user.value?.sub;
      if (!sub) {
        error.value = true;
        return;
      }
      const userPath = encodeURIComponent(sub);
      try {
        const response = await api.get(
          `/user/${userPath}/recipe/${route.params.id}`
        );
        // The backend returns 204 No Content (with empty body) when the
        // recipe id doesn't match anything. Treat that as an error so we
        // don't sit on the loading state forever.
        if (response.status === 204 || !response.data || !response.data.id) {
          error.value = true;
          return;
        }
        recipe.value = response.data;
      } catch (err) {
        console.error('Error fetching recipe:', err);
        error.value = true;
      }
    };

    const goBack = () => {
      router.push('/recipes');
    };

    // Recipes pulled from Obsidian sometimes carry a subgroup label in
    // each grocery's description (e.g. "Flan Pâtissier · Pour la pâte
    // sucrée"). Pull the trailing segment after " · " for display.
    const hasGroup = (item: Grocery): boolean => {
      return !!item.description && item.description.includes(' · ');
    };
    const groupOf = (item: Grocery): string => {
      if (!item.description) return '';
      const parts = item.description.split(' · ');
      return parts.length > 1 ? parts.slice(1).join(' · ') : '';
    };

    onMounted(() => {
      if (!isLoading.value && isAuthenticated.value) {
        fetchRecipe();
      } else {
        watch(
          () => isLoading.value,
          loading => {
            if (!loading && isAuthenticated.value) fetchRecipe();
          }
        );
      }
    });

    return {
      recipe,
      error,
      goBack,
      hasGroup,
      groupOf
    };
  }
});
</script>

<style scoped>
.recipe-detail {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  color: #333;
}

.recipe-header {
  text-align: center;
  margin-bottom: 30px;
}

.recipe-header h1 {
  color: #699051;
  margin-bottom: 10px;
}

.recipe-meta {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-bottom: 12px;
  color: #666;
}

.recipe-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px;
  margin-bottom: 12px;
}

.recipe-tag {
  background-color: #699051;
  color: white;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.85em;
}

.recipe-remark {
  font-style: italic;
  color: #888;
  margin: 0;
}

.recipe-sections {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

.ingredients-section,
.steps-section {
  background-color: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
}

.ingredients-section h2,
.steps-section h2 {
  color: #699051;
  margin-bottom: 15px;
  border-bottom: 2px solid #699051;
  padding-bottom: 10px;
}

.ingredients-list {
  list-style: none;
  padding: 0;
}

.ingredients-list li {
  padding: 8px 0;
  border-bottom: 1px solid #eee;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: baseline;
}

.qty {
  font-weight: 600;
  color: #445837;
  min-width: 60px;
}

.name {
  flex: 1;
}

.group {
  color: #888;
  font-size: 0.85em;
}

.steps-list {
  padding-left: 0;
}

.steps-list li {
  padding: 10px;
  margin-bottom: 8px;
  background-color: white;
  border-radius: 4px;
  border-left: 4px solid #699051;
}

.empty {
  color: #888;
  font-style: italic;
}

.back-button {
  margin-top: 30px;
  text-align: center;
}

.back-button button {
  background-color: #699051;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}

.back-button button:hover {
  background-color: #445837;
}

.loading,
.error {
  text-align: center;
  padding: 40px;
  color: #666;
}

.error button {
  margin-top: 15px;
  background-color: #699051;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
}
</style>
