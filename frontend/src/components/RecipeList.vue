<template>
  <div class="recipe-list-component">
    <div class="filters-section">
      <div class="category-chips" role="group" aria-label="Kind of recipe">
        <button
          v-for="c in categoryOptions"
          :key="c.value"
          type="button"
          class="category-chip"
          :class="{ 'category-chip--active': category === c.value }"
          :aria-pressed="category === c.value"
          @click="category = c.value"
        >
          {{ c.label }} ({{ c.count }})
        </button>
      </div>
      <input
        v-model="searchQuery"
        :placeholder="searchPlaceholder"
        class="search-input"
      />
      <select v-model="selectedTag" class="filter-select">
        <option value="">All tags ({{ inCategory.length }})</option>
        <option
          v-for="tag in availableTags"
          :key="tag.name"
          :value="tag.name"
        >
          {{ tag.name }} ({{ tag.count }})
        </option>
      </select>
    </div>

    <div v-if="loading" class="state-text">Loading recipes…</div>
    <div v-else-if="filteredRecipes.length === 0" class="state-text">
      {{ emptyText }}
    </div>
    <div v-else class="items" :class="{ 'items--compact': compact }">
      <div
        v-for="recipe in filteredRecipes"
        :key="recipe.id"
        class="recipe-item"
        :class="{
          'recipe-item--selected': !!selectedId && recipe.id === selectedId,
          'recipe-item--compact': compact,
          'recipe-item--draggable': draggable,
          'recipe-item--pressing': pressingId === recipe.id,
        }"
        :draggable="draggable"
        @dragstart="onDragStart(recipe, $event)"
        @pointerdown="onPointerDown(recipe, $event)"
        @pointermove="onPointerMove"
        @pointerup="cancelPress"
        @pointerleave="cancelPress"
        @pointercancel="cancelPress"
        @contextmenu="onContextMenu"
        @click="onClick(recipe)"
      >
        <span class="recipe-name-row">
          <span class="recipe-name">{{ recipe.name }}</span>
          <span v-if="notes[recipe.id]" class="recipe-note">
            {{ notes[recipe.id] }}
          </span>
        </span>
        <span v-if="recipe.tags && recipe.tags.length" class="recipe-tags">
          <span v-for="tag in recipe.tags" :key="tag" class="recipe-tag">
            {{ tag }}
          </span>
        </span>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, onBeforeUnmount, watch, PropType } from 'vue';
import { Category, recipeCategory } from '../services/suggestions';
import { normalizeIngredient } from '../services/groceries';

interface Grocery {
  id: string;
  name: string;
  quantity: string;
  description?: string;
}

export interface Recipe {
  id: string;
  name: string;
  tags: string[];
  time: string;
  servings: number;
  groceries: Grocery[];
}

interface TagBucket {
  name: string;
  count: number;
}

// Custom MIME for the dragged recipe id. The drop target reads it back
// out of dataTransfer — that's how we avoid sharing a "currently
// dragging" ref between this component and the planner.
export const RECIPE_DRAG_MIME = 'application/x-recipe-id';

const LONG_PRESS_MS = 500;
// A finger drifting further than this is scrolling, not pressing.
const LONG_PRESS_SLOP_PX = 10;

export default defineComponent({
  name: 'RecipeList',
  props: {
    recipes: { type: Array as PropType<Recipe[]>, required: true },
    selectedId: { type: String, default: '' },
    loading: { type: Boolean, default: false },
    compact: { type: Boolean, default: false },
    draggable: { type: Boolean, default: false },
    searchPlaceholder: {
      type: String,
      default: 'Search by name, tag or ingredient...',
    },
    emptyText: { type: String, default: 'No recipes match.' },
    // Emit `long-press` after holding a recipe; the click that ends the
    // press is swallowed so it doesn't also `select`.
    longPress: { type: Boolean, default: false },
    // Small per-recipe label shown next to the name, e.g. "3 days ago".
    notes: {
      type: Object as PropType<Record<string, string>>,
      default: () => ({}),
    },
    defaultCategory: {
      type: String as PropType<Category | 'all'>,
      default: 'meal',
    },
  },
  emits: ['select', 'long-press'],
  setup(props, { emit }) {
    const searchQuery = ref('');
    const selectedTag = ref('');
    const category = ref<Category | 'all'>(props.defaultCategory);

    const categories = computed(() => {
      const out = new Map<string, Category>();
      for (const r of props.recipes) out.set(r.id, recipeCategory(r));
      return out;
    });

    const categoryOptions = computed(() => {
      const count = (c: Category) =>
        props.recipes.filter(r => categories.value.get(r.id) === c).length;
      return [
        { value: 'meal' as const, label: 'Meals', count: count('meal') },
        { value: 'sweet' as const, label: 'Sweet & snacks', count: count('sweet') },
        { value: 'all' as const, label: 'All', count: props.recipes.length },
      ];
    });

    watch(category, () => (selectedTag.value = ''));

    const inCategory = computed(() =>
      category.value === 'all'
        ? props.recipes
        : props.recipes.filter(r => categories.value.get(r.id) === category.value)
    );

    const availableTags = computed<TagBucket[]>(() => {
      const counts = new Map<string, number>();
      for (const r of inCategory.value) {
        for (const tag of r.tags || []) {
          counts.set(tag, (counts.get(tag) || 0) + 1);
        }
      }
      return Array.from(counts.entries())
        .map(([name, count]) => ({ name, count }))
        .sort((a, b) =>
          b.count !== a.count
            ? b.count - a.count
            : a.name.localeCompare(b.name)
        );
    });

    // Every word of the query must appear in the name, tags or
    // ingredients ("poulet citron"), ignoring case and accents.
    const filteredRecipes = computed(() => {
      const words = normalizeIngredient(searchQuery.value)
        .split(' ')
        .filter(Boolean);
      const tag = selectedTag.value;
      return inCategory.value.filter(r => {
        const matchesTag = !tag || (r.tags || []).includes(tag);
        if (!matchesTag) return false;
        if (!words.length) return true;
        const haystack = normalizeIngredient(
          [r.name, ...(r.tags || []), ...(r.groceries || []).map(g => g.name)]
            .join(' ')
        );
        return words.every(w => haystack.includes(w));
      });
    });

    const pressingId = ref('');
    let pressTimer: number | null = null;
    let pressStart = { x: 0, y: 0 };
    let suppressClick = false;

    const cancelPress = () => {
      if (pressTimer !== null) clearTimeout(pressTimer);
      pressTimer = null;
      pressingId.value = '';
    };

    const onPointerDown = (recipe: Recipe, event: PointerEvent) => {
      if (!props.longPress || event.button !== 0) return;
      cancelPress();
      suppressClick = false;
      pressStart = { x: event.clientX, y: event.clientY };
      pressingId.value = recipe.id;
      pressTimer = window.setTimeout(() => {
        pressTimer = null;
        pressingId.value = '';
        suppressClick = true;
        navigator.vibrate?.(30);
        emit('long-press', recipe);
      }, LONG_PRESS_MS);
    };

    const onPointerMove = (event: PointerEvent) => {
      if (pressTimer === null) return;
      const dx = event.clientX - pressStart.x;
      const dy = event.clientY - pressStart.y;
      if (dx * dx + dy * dy > LONG_PRESS_SLOP_PX * LONG_PRESS_SLOP_PX) {
        cancelPress();
      }
    };

    // Mobile browsers open a context menu on long touch.
    const onContextMenu = (event: Event) => {
      if (props.longPress) event.preventDefault();
    };

    const onClick = (recipe: Recipe) => {
      if (suppressClick) {
        suppressClick = false;
        return;
      }
      emit('select', recipe);
    };

    onBeforeUnmount(cancelPress);

    const onDragStart = (recipe: Recipe, event: DragEvent) => {
      cancelPress();
      if (!event.dataTransfer) return;
      event.dataTransfer.effectAllowed = 'copy';
      event.dataTransfer.setData(RECIPE_DRAG_MIME, recipe.id);
      event.dataTransfer.setData('text/plain', recipe.name);
    };

    return {
      searchQuery,
      selectedTag,
      category,
      categoryOptions,
      inCategory,
      availableTags,
      filteredRecipes,
      onDragStart,
      pressingId,
      onPointerDown,
      onPointerMove,
      cancelPress,
      onContextMenu,
      onClick,
    };
  },
});
</script>

<style scoped>
.recipe-list-component {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.filters-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.category-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.category-chip {
  border: 1px solid #699051;
  background-color: white;
  color: #445837;
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 0.85em;
  cursor: pointer;
}

.category-chip--active {
  background-color: #699051;
  color: white;
}

.recipe-name-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.recipe-note {
  flex-shrink: 0;
  font-size: 0.75em;
  opacity: 0.85;
  white-space: nowrap;
}

.search-input,
.filter-select {
  padding: 8px 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background-color: #445837;
  color: white;
  box-sizing: border-box;
  width: 100%;
}

.search-input::placeholder {
  color: #cfd8c5;
}

.state-text {
  text-align: center;
  padding: 20px;
  color: #888;
}

.items {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.items--compact {
  gap: 8px;
}

.recipe-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  background-color: #699051;
  padding: 15px;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  transition: background-color 0.2s, transform 0.05s;
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
  -webkit-tap-highlight-color: transparent;
}

.recipe-item--pressing {
  background-color: #445837;
  transform: scale(0.97);
  transition: background-color 0.5s, transform 0.5s;
}

.recipe-item--compact {
  padding: 10px 12px;
  border-radius: 6px;
  gap: 4px;
}

.recipe-item--draggable {
  cursor: grab;
}

.recipe-item--draggable:active {
  cursor: grabbing;
  transform: scale(0.98);
}

.recipe-item:hover {
  background-color: #445837;
}

.recipe-item--selected {
  outline: 3px solid #FF843C;
  outline-offset: 1px;
}

.recipe-name {
  font-size: 1.1em;
}

.recipe-item--compact .recipe-name {
  font-size: 0.95em;
}

.recipe-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.recipe-item--compact .recipe-tags {
  gap: 4px;
}

.recipe-tag {
  background-color: rgba(255, 255, 255, 0.18);
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.8em;
}

.recipe-item--compact .recipe-tag {
  padding: 1px 6px;
  font-size: 0.7em;
}
</style>
