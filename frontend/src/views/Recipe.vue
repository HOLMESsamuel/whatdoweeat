<template>
  <div class="recipe-view">
    <div class="header">
      <h1>Recipes</h1>
      <p class="hint">
        Recipes are read from your Obsidian vault. To add or edit a recipe,
        edit the markdown file in
        <code>recette-templated/</code>.
      </p>
    </div>

    <recipe-browser />
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import RecipeBrowser from '../components/RecipeBrowser.vue';

export default defineComponent({
  name: 'RecipeView',
  components: {
    RecipeBrowser
  }
});
</script>

<style scoped>
.recipe-view {
  padding: 20px;
}

.header {
  margin-bottom: 20px;
}

.header h1 {
  margin: 0 0 8px;
  color: #699051;
}

.hint {
  color: #666;
  font-size: 0.9em;
  margin: 0;
}

.hint code {
  background-color: #f1f1f1;
  padding: 2px 6px;
  border-radius: 3px;
}
</style>
