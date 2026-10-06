<template>
  <div class="idea-backdrop" @click.self="$emit('close')">
    <div class="idea-sheet" role="dialog" :aria-label="title">
      <div class="idea-header">
        <h3>{{ title }}</h3>
        <button class="close-btn" aria-label="Close" @click="$emit('close')">×</button>
      </div>

      <p v-if="!ideas.length" class="muted">
        No ideas left: every meal was made or planned in the last
        {{ recentDays }} days.
      </p>
      <div v-else class="idea-cards" :class="{ 'idea-cards--single': pageSize === 1 }">
        <div v-for="recipe in page" :key="recipe.id" class="idea-card">
          <div class="idea-name-row">
            <span class="idea-name">{{ recipe.name }}</span>
            <span v-if="notes[recipe.id]" class="idea-note">{{ notes[recipe.id] }}</span>
          </div>
          <div v-if="recipe.time || recipe.tags.length" class="idea-meta">
            <span v-if="recipe.time">⏱ {{ recipe.time }}</span>
            <span v-for="tag in recipe.tags" :key="tag" class="idea-tag">{{ tag }}</span>
          </div>
          <p v-if="pageSize === 1 && ingredientPreview(recipe)" class="idea-ingredients">
            {{ ingredientPreview(recipe) }}
          </p>
          <div class="idea-actions">
            <button class="primary-btn" :disabled="busy" @click="$emit('pick', recipe)">
              {{ pickLabel }}
            </button>
            <button class="secondary-btn" @click="$emit('open', recipe)">Open</button>
          </div>
        </div>
      </div>

      <button v-if="ideas.length > pageSize" class="more-btn" @click="next">
        {{ pageSize === 1 ? 'Another idea' : 'More ideas' }} ↻
      </button>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, watch, PropType } from 'vue';
import type { Recipe } from './RecipeList.vue';
import { RECENT_DAYS } from '../services/suggestions';

export default defineComponent({
  name: 'IdeaPicker',
  props: {
    ideas: { type: Array as PropType<Recipe[]>, required: true },
    title: { type: String, required: true },
    pageSize: { type: Number, default: 3 },
    pickLabel: { type: String, required: true },
    notes: {
      type: Object as PropType<Record<string, string>>,
      default: () => ({}),
    },
    busy: { type: Boolean, default: false },
  },
  emits: ['pick', 'open', 'close'],
  setup(props) {
    const start = ref(0);
    watch(() => props.ideas, () => (start.value = 0));

    // Wraps around so "Another idea" never dead-ends.
    const page = computed(() => {
      const n = props.ideas.length;
      const count = Math.min(props.pageSize, n);
      return Array.from({ length: count }, (_, i) => props.ideas[(start.value + i) % n]);
    });

    const next = () => {
      start.value = (start.value + props.pageSize) % props.ideas.length;
    };

    const ingredientPreview = (recipe: Recipe) =>
      (recipe.groceries || []).slice(0, 8).map(g => g.name).join(', ');

    return { page, next, ingredientPreview, recentDays: RECENT_DAYS };
  },
});
</script>

<style scoped>
.idea-backdrop {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 900;
}

@media (min-width: 640px) {
  .idea-backdrop {
    align-items: center;
  }
}

.idea-sheet {
  width: 100%;
  max-width: 520px;
  max-height: 85vh;
  overflow-y: auto;
  background-color: white;
  border-radius: 12px 12px 0 0;
  padding: 16px;
  box-sizing: border-box;
}

@media (min-width: 640px) {
  .idea-sheet {
    border-radius: 12px;
  }
}

.idea-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.idea-header h3 {
  margin: 0;
  color: #445837;
  font-size: 1.15em;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.6em;
  line-height: 1;
  color: #666;
  cursor: pointer;
}

.idea-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.idea-card {
  background-color: #f1f5ee;
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.idea-cards--single .idea-card {
  padding: 18px;
}

.idea-name-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}

.idea-name {
  font-weight: 600;
  color: #2f3d26;
}

.idea-cards--single .idea-name {
  font-size: 1.3em;
}

.idea-note {
  font-size: 0.8em;
  color: #6b7a5f;
  white-space: nowrap;
}

.idea-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 0.85em;
  color: #555;
}

.idea-tag {
  background-color: #dfe8d6;
  border-radius: 999px;
  padding: 1px 8px;
}

.idea-ingredients {
  margin: 0;
  font-size: 0.9em;
  color: #555;
}

.idea-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.primary-btn,
.secondary-btn,
.more-btn {
  border-radius: 4px;
  padding: 8px 14px;
  cursor: pointer;
  border: 1px solid #699051;
}

.primary-btn {
  background-color: #699051;
  color: white;
}

.primary-btn:disabled {
  opacity: 0.6;
  cursor: progress;
}

.secondary-btn {
  background-color: white;
  color: #699051;
}

.more-btn {
  width: 100%;
  margin-top: 12px;
  background-color: white;
  color: #445837;
}

.muted {
  color: #777;
}
</style>
