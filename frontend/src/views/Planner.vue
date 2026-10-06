<template>
  <div class="planner-view">
    <div class="header">
      <h1>Meal Planner</h1>
      <p class="hint">
        Drag a recipe onto a slot, or tap a recipe and then a slot. Tap an
        empty slot for ideas. Ingredients are automatically added to your
        first grocery list.
      </p>
    </div>

    <div v-if="loading" class="loading">Loading…</div>

    <div v-else-if="!dropboxConnected" class="empty-state">
      <p>
        Connect your Dropbox in
        <router-link to="/recipes">Recipes</router-link>
        first to load your recipes.
      </p>
    </div>

    <div v-else-if="groceryLists.length === 0" class="empty-state">
      <p>
        Create a
        <router-link to="/lists">grocery list</router-link>
        first — added recipes drop their ingredients into your first list.
      </p>
    </div>

    <div v-else class="planner-layout">
      <!-- Recipe list panel -->
      <aside class="recipes-panel">
        <recipe-list
          :recipes="rankedRecipes"
          :selected-id="selectedRecipe?.id || ''"
          :loading="loadingRecipes"
          :notes="notes"
          compact
          draggable
          @select="onRecipeClick"
        />
      </aside>

      <!-- Calendar panel -->
      <section class="calendar-panel">
        <div class="week-controls">
          <button class="nav-btn" @click="shiftWeek(-1)">← Prev</button>
          <h2 class="week-label">{{ weekLabel }}</h2>
          <button class="nav-btn" @click="shiftWeek(1)">Next →</button>
          <button class="nav-btn today-btn" @click="goToday">Today</button>
        </div>

        <p v-if="selectedRecipe" class="hint-selected">
          Selected: <strong>{{ selectedRecipe.name }}</strong> — tap a slot to
          place it, or
          <button class="link-btn" @click="selectedRecipe = null">
            cancel
          </button>
        </p>

        <p v-if="addStatus" class="status">{{ addStatus }}</p>

        <div class="calendar">
          <div
            v-for="day in weekDays"
            :key="day.iso"
            class="day-column"
          >
            <div class="day-header">
              <div class="day-name">{{ day.name }}</div>
              <div class="day-date">{{ day.dayNum }}</div>
            </div>
            <div
              v-for="slot in slotsForDay(day.iso)"
              :key="slot.label"
              class="meal-slot"
              :class="{
                'meal-slot--drag-over': dragOver?.day === day.iso && dragOver?.label === slot.label,
                'meal-slot--filled': slot.recipes.length > 0,
                'meal-slot--placeable': !!selectedRecipe,
              }"
              @dragover.prevent="onDragOver(day.iso, slot.label)"
              @dragleave="onDragLeave"
              @drop.prevent="onDrop(day.iso, slot.label, $event)"
              @click="onSlotClick(day.iso, slot.label)"
            >
              <div class="slot-header">
                <span
                  class="slot-label"
                  :class="{ 'slot-label--clickable': slot.isCustom }"
                  :title="slot.isCustom ? 'Click to rename' : ''"
                  @click.stop="slot.isCustom && renameSlot(day.iso, slot.label)"
                >{{ slot.label }}</span>
                <button
                  v-if="slot.isCustom"
                  class="remove-slot-btn"
                  title="Remove this slot"
                  @click.stop="removeSlot(day.iso, slot.label)"
                >×</button>
              </div>
              <div
                v-for="(r, idx) in slot.recipes"
                :key="`${r.recipe_id}-${idx}`"
                class="slot-recipe"
              >
                <span>{{ r.recipe_name }}</span>
                <button
                  class="remove-btn"
                  title="Remove from plan"
                  @click.stop="removeRecipeAt(day.iso, slot.label, idx)"
                >×</button>
              </div>
            </div>
            <button
              class="add-slot-btn"
              title="Add a custom slot for this day"
              @click="addCustomSlot(day.iso)"
            >+ Add slot</button>
          </div>
        </div>
      </section>
      <idea-picker
        v-if="ideaTarget"
        :title="`Ideas for ${ideaTarget.dayName} ${ideaTarget.label.toLowerCase()}`"
        :ideas="slotIdeas"
        :notes="notes"
        pick-label="Place here"
        @pick="pickIdea"
        @open="openRecipe"
        @close="ideaTarget = null"
      />
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, onMounted, watch } from 'vue';
import { useAuth0 } from '@auth0/auth0-vue';
import { getApi } from '../services/api';
import { cachedRecipes, loadRecipes } from '../services/recipes';
import { useRouter } from 'vue-router';
import IdeaPicker from '../components/IdeaPicker.vue';
import {
  History,
  fetchRecipeHistory,
  historyLabel,
  mealIdeas,
  rankRecipes,
} from '../services/suggestions';
import {
  GroceryListSummary,
  addRecipeToList,
  fetchGroceryLists as fetchUserGroceryLists,
  fetchPantryStaples,
} from '../services/groceries';
import RecipeList, { Recipe, RECIPE_DRAG_MIME } from '../components/RecipeList.vue';

// Recipe is re-exported by RecipeList; use it via the import above.

interface MealRecipe {
  recipe_id: string;
  recipe_name: string;
}

interface MealSlotEntry {
  day: string;
  label: string;
  recipes: MealRecipe[];
}

interface MealPlan {
  user_id?: string;
  meals: MealSlotEntry[];
}

interface DisplaySlot {
  label: string;
  recipes: MealRecipe[];
  isCustom: boolean;
}

const BUILTIN_LABELS = ['Lunch', 'Dinner'];

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

const sameLabel = (a: string, b: string) =>
  a.trim().toLowerCase() === b.trim().toLowerCase();

function startOfWeek(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  // getDay(): Sun=0, Mon=1 ... — shift so Monday is start.
  const dow = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - dow);
  return d;
}

function isoDate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export default defineComponent({
  name: 'PlannerView',
  components: { RecipeList, IdeaPicker },
  setup() {
    const { user, isAuthenticated, isLoading } = useAuth0();
    const api = getApi();

    const recipes = ref<Recipe[]>([]);
    const plan = ref<MealPlan>({ meals: [] });
    const groceryLists = ref<GroceryListSummary[]>([]);
    const dropboxConnected = ref(false);
    const loading = ref(true);
    const loadingRecipes = ref(false);

    const selectedRecipe = ref<Recipe | null>(null);
    const router = useRouter();
    const history = ref<History>({});
    const ideaTarget = ref<{ day: string; dayName: string; label: string } | null>(null);
    const dragOver = ref<{ day: string; label: string } | null>(null);
    const addStatus = ref('');
    let statusTimer: number | null = null;

    const weekStart = ref(startOfWeek(new Date()));

    let userId = '';
    const userPath = () => encodeURIComponent(userId);

    const slotsForDay = (day: string): DisplaySlot[] => {
      const dayMeals = plan.value.meals.filter(m => m.day === day);
      const out: DisplaySlot[] = [];
      // Built-in labels first, always shown.
      for (const label of BUILTIN_LABELS) {
        const existing = dayMeals.find(m => sameLabel(m.label, label));
        out.push({
          label,
          recipes: existing?.recipes || [],
          isCustom: false,
        });
      }
      // Then custom slots, preserved in plan order.
      for (const m of dayMeals) {
        if (BUILTIN_LABELS.some(b => sameLabel(b, m.label))) continue;
        out.push({ label: m.label, recipes: m.recipes, isCustom: true });
      }
      return out;
    };

    const weekDays = computed(() => {
      const out: { iso: string; name: string; dayNum: number }[] = [];
      for (let i = 0; i < 7; i++) {
        const d = new Date(weekStart.value);
        d.setDate(d.getDate() + i);
        out.push({
          iso: isoDate(d),
          name: DAY_NAMES[i],
          dayNum: d.getDate(),
        });
      }
      return out;
    });

    const weekLabel = computed(() => {
      const start = new Date(weekStart.value);
      const end = new Date(weekStart.value);
      end.setDate(end.getDate() + 6);
      const fmt = (d: Date) =>
        d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
      return `${fmt(start)} – ${fmt(end)}, ${end.getFullYear()}`;
    });

    const flashStatus = (msg: string) => {
      addStatus.value = msg;
      if (statusTimer) clearTimeout(statusTimer);
      statusTimer = window.setTimeout(() => {
        addStatus.value = '';
      }, 3500);
    };

    const fetchRecipes = async () => {
      const cached = cachedRecipes(userId);
      if (cached) recipes.value = cached;
      loadingRecipes.value = !cached;
      try {
        recipes.value = await loadRecipes(userId);
      } catch (err) {
        console.error('Could not fetch recipes', err);
        if (!cached) recipes.value = [];
      } finally {
        loadingRecipes.value = false;
      }
    };

    const fetchDropboxStatus = async () => {
      try {
        const { data } = await api.get(`/user/${userPath()}/dropbox/status`);
        dropboxConnected.value = !!data.connected;
      } catch {
        dropboxConnected.value = false;
      }
    };

    const fetchPlan = async () => {
      try {
        const { data } = await api.get(`/user/${userPath()}/meal-plan`);
        plan.value = { meals: data?.meals || [] };
      } catch (err) {
        console.error('Could not fetch meal plan', err);
        plan.value = { meals: [] };
      }
    };

    const fetchGroceryLists = async () => {
      try {
        groceryLists.value = await fetchUserGroceryLists(userId);
      } catch (err) {
        console.error('Could not fetch grocery lists', err);
        groceryLists.value = [];
      }
    };

    const savePlan = async () => {
      try {
        await api.put(`/user/${userPath()}/meal-plan`, plan.value);
      } catch (err) {
        console.error('Could not save meal plan', err);
      }
    };

    const addIngredientsToFirstList = async (recipe: Recipe) => {
      if (groceryLists.value.length === 0) return { added: [], skipped: [] };
      let staples: string[] = [];
      try {
        staples = await fetchPantryStaples(userId);
      } catch (err) {
        console.error('Could not load pantry staples', err);
      }
      return addRecipeToList(groceryLists.value[0]._id, recipe, staples);
    };

    // Best-effort cleanup: for each ingredient in `recipe`, remove ONE
    // matching grocery from the first list where description matches the
    // recipe name. One-per-ingredient avoids over-deleting when the same
    // recipe is on the calendar twice. Edits the user made (renaming the
    // item, changing the description) silently skip — manual cleanup
    // takes over from there.
    const removeIngredientsFromFirstList = async (
      recipe: Recipe
    ): Promise<number> => {
      if (groceryLists.value.length === 0) return 0;
      const listId = groceryLists.value[0]._id;
      const items = recipe.groceries || [];
      if (items.length === 0) return 0;
      let listGroceries: { id: string; name: string; description?: string }[] = [];
      try {
        const { data } = await api.get(`/grocery-list/${listId}`);
        listGroceries = data?.groceries || [];
      } catch (err) {
        console.error('Could not load list for ingredient cleanup', err);
        return 0;
      }
      const norm = (s: string | undefined) => (s || '').trim().toLowerCase();
      const recipeKey = norm(recipe.name);
      const consumed = new Set<string>();
      let removed = 0;
      for (const ing of items) {
        const target = listGroceries.find(
          g =>
            !consumed.has(g.id) &&
            norm(g.description) === recipeKey &&
            norm(g.name) === norm(ing.name)
        );
        if (!target) continue;
        consumed.add(target.id);
        try {
          await api.delete(`/grocery-list/${listId}/grocery/${target.id}`);
          removed++;
        } catch (err) {
          console.error('Could not delete grocery', target, err);
        }
      }
      return removed;
    };

    const cleanupForRemovedRecipe = async (mealRecipe: MealRecipe) => {
      const recipe = recipes.value.find(r => r.id === mealRecipe.recipe_id);
      if (!recipe) return 0;
      return removeIngredientsFromFirstList(recipe);
    };

    const placeRecipe = async (recipe: Recipe, day: string, label: string) => {
      let slot = plan.value.meals.find(
        m => m.day === day && sameLabel(m.label, label)
      );
      if (!slot) {
        slot = { day, label, recipes: [] };
        plan.value.meals.push(slot);
      }
      slot.recipes.push({ recipe_id: recipe.id, recipe_name: recipe.name });
      if (day > (history.value[recipe.id] || '')) {
        history.value = { ...history.value, [recipe.id]: day };
      }
      await savePlan();
      const { added, skipped } = await addIngredientsToFirstList(recipe);
      flashStatus(
        `Added "${recipe.name}" to ${label} — ${added.length} ingredient(s) sent to "${groceryLists.value[0]?.name}".` +
          (skipped.length ? ` Skipped: ${skipped.join(', ')}.` : '')
      );
    };

    const removeRecipeAt = async (day: string, label: string, idx: number) => {
      const slot = plan.value.meals.find(
        m => m.day === day && sameLabel(m.label, label)
      );
      if (!slot) return;
      const [removed] = slot.recipes.splice(idx, 1);
      // Empty built-in slots aren't persisted (they re-appear as defaults).
      // Empty custom slots stick around as a labeled bucket.
      const isBuiltin = BUILTIN_LABELS.some(b => sameLabel(b, label));
      if (slot.recipes.length === 0 && isBuiltin) {
        plan.value.meals = plan.value.meals.filter(
          m => !(m.day === day && sameLabel(m.label, label))
        );
      }
      await savePlan();
      if (!removed) return;
      const cleared = await cleanupForRemovedRecipe(removed);
      flashStatus(
        cleared
          ? `Removed "${removed.recipe_name}" — ${cleared} ingredient(s) cleared from "${groceryLists.value[0]?.name}".`
          : `Removed "${removed.recipe_name}" — no matching ingredients to clear.`
      );
    };

    const addCustomSlot = async (day: string) => {
      const raw = window.prompt('Slot label (e.g. "Snack", "Cake")') || '';
      const label = raw.trim();
      if (!label) return;
      // No-op if it's a built-in (already shown) or a duplicate for the day.
      if (BUILTIN_LABELS.some(b => sameLabel(b, label))) return;
      if (plan.value.meals.some(m => m.day === day && sameLabel(m.label, label))) {
        return;
      }
      plan.value.meals.push({ day, label, recipes: [] });
      await savePlan();
    };

    const renameSlot = async (day: string, oldLabel: string) => {
      if (BUILTIN_LABELS.some(b => sameLabel(b, oldLabel))) return;
      const raw = window.prompt('Rename slot', oldLabel) || '';
      const newLabel = raw.trim();
      if (!newLabel || sameLabel(newLabel, oldLabel)) return;
      if (BUILTIN_LABELS.some(b => sameLabel(b, newLabel))) return;
      if (
        plan.value.meals.some(
          m => m.day === day && sameLabel(m.label, newLabel)
        )
      ) {
        return;
      }
      const slot = plan.value.meals.find(
        m => m.day === day && sameLabel(m.label, oldLabel)
      );
      if (!slot) return;
      slot.label = newLabel;
      await savePlan();
    };

    const removeSlot = async (day: string, label: string) => {
      if (BUILTIN_LABELS.some(b => sameLabel(b, label))) return;
      const slot = plan.value.meals.find(
        m => m.day === day && sameLabel(m.label, label)
      );
      const removedRecipes = slot ? [...slot.recipes] : [];
      plan.value.meals = plan.value.meals.filter(
        m => !(m.day === day && sameLabel(m.label, label))
      );
      await savePlan();
      let total = 0;
      for (const r of removedRecipes) {
        total += await cleanupForRemovedRecipe(r);
      }
      if (removedRecipes.length > 0) {
        flashStatus(
          `Removed slot "${label}" — ${total} ingredient(s) cleared from "${groceryLists.value[0]?.name}".`
        );
      }
    };

    // -- drag & drop ---------------------------------------------------
    // RecipeList sets the recipe id on dataTransfer; we read it back on
    // drop and look up the full recipe locally.

    const onDragOver = (day: string, label: string) => {
      dragOver.value = { day, label };
    };

    const onDragLeave = () => {
      // Only clear if leaving the slot — kept simple: drop event will
      // still fire when target is correct.
    };

    const onDrop = async (day: string, label: string, event: DragEvent) => {
      dragOver.value = null;
      const recipeId = event.dataTransfer?.getData(RECIPE_DRAG_MIME) || '';
      if (!recipeId) return;
      const recipe = recipes.value.find(r => r.id === recipeId);
      if (!recipe) return;
      await placeRecipe(recipe, day, label);
    };

    // -- click-to-place (mobile) ---------------------------------------

    const onRecipeClick = (recipe: Recipe) => {
      selectedRecipe.value =
        selectedRecipe.value?.id === recipe.id ? null : recipe;
    };

    const rankedRecipes = computed(() =>
      rankRecipes(recipes.value, { history: history.value })
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

    // Meals not made recently and not already on the displayed week.
    const slotIdeas = computed(() => {
      const thisWeek = new Set<string>();
      const days = new Set(weekDays.value.map(d => d.iso));
      for (const m of plan.value.meals) {
        if (days.has(m.day)) m.recipes.forEach(r => thisWeek.add(r.recipe_id));
      }
      return mealIdeas(recipes.value, { history: history.value, exclude: thisWeek });
    });

    const pickIdea = async (recipe: Recipe) => {
      const target = ideaTarget.value;
      ideaTarget.value = null;
      if (target) await placeRecipe(recipe, target.day, target.label);
    };

    const openRecipe = (recipe: Recipe) => router.push(`/recipes/${recipe.id}`);

    const onSlotClick = async (day: string, label: string) => {
      if (!selectedRecipe.value) {
        // Empty slot, nothing selected: offer ideas instead of doing nothing.
        const slot = slotsForDay(day).find(s => sameLabel(s.label, label));
        if (slot && !slot.recipes.length && recipes.value.length) {
          const dayName = weekDays.value.find(d => d.iso === day)?.name || '';
          ideaTarget.value = { day, dayName, label };
        }
        return;
      }
      const recipe = selectedRecipe.value;
      selectedRecipe.value = null;
      await placeRecipe(recipe, day, label);
    };

    const shiftWeek = (delta: number) => {
      const d = new Date(weekStart.value);
      d.setDate(d.getDate() + delta * 7);
      weekStart.value = d;
    };

    const goToday = () => {
      weekStart.value = startOfWeek(new Date());
    };

    const init = async () => {
      if (!user.value?.sub) return;
      userId = user.value.sub;
      loading.value = true;
      // The recipes endpoint returns [] when Dropbox isn't connected, so
      // it can run alongside the status check instead of after it.
      await Promise.all([
        fetchDropboxStatus(),
        fetchPlan(),
        fetchGroceryLists(),
        fetchRecipeHistory(userId)
          .then(h => (history.value = h))
          .catch(err => console.error('Could not load recipe history', err)),
        fetchRecipes(),
      ]);
      loading.value = false;
    };

    onMounted(() => {
      if (!isLoading.value && isAuthenticated.value) {
        init();
      } else {
        watch(
          () => isLoading.value,
          loading => {
            if (!loading && isAuthenticated.value) init();
          }
        );
      }
    });

    return {
      loading,
      dropboxConnected,
      groceryLists,
      recipes,
      loadingRecipes,
      weekDays,
      weekLabel,
      slotsForDay,
      selectedRecipe,
      dragOver,
      addStatus,
      onDragOver,
      onDragLeave,
      onDrop,
      onRecipeClick,
      rankedRecipes,
      notes,
      slotIdeas,
      ideaTarget,
      pickIdea,
      openRecipe,
      onSlotClick,
      removeRecipeAt,
      addCustomSlot,
      renameSlot,
      removeSlot,
      shiftWeek,
      goToday,
    };
  },
});
</script>

<style scoped>
.planner-view {
  padding: 20px;
}

.header h1 {
  margin: 0 0 8px;
  color: #699051;
}

.hint {
  color: #666;
  font-size: 0.9em;
  margin: 0 0 20px;
}

.loading,
.empty-state {
  text-align: center;
  padding: 30px;
  color: #888;
}

.planner-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 20px;
}

@media (max-width: 900px) {
  .planner-layout {
    grid-template-columns: 1fr;
  }
}

/* Recipe panel */
.recipes-panel {
  background-color: #f8f9fa;
  border-radius: 8px;
  padding: 15px;
  max-height: calc(100vh - 180px);
  overflow-y: auto;
  position: sticky;
  top: 20px;
  align-self: start;
}

@media (max-width: 900px) {
  .recipes-panel {
    position: static;
    max-height: 50vh;
  }
}

/* Calendar */
.calendar-panel {
  min-width: 0;
}

.week-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.week-label {
  margin: 0;
  flex: 1;
  text-align: center;
  color: #445837;
  font-size: 1.1em;
}

.nav-btn {
  background-color: #699051;
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9em;
}

.nav-btn:hover {
  background-color: #445837;
}

.today-btn {
  background-color: #FF843C;
}

.hint-selected {
  background-color: #fff3e6;
  border: 1px solid #FF843C;
  color: #4a3a2a;
  padding: 8px 12px;
  border-radius: 4px;
  margin-bottom: 10px;
  font-size: 0.9em;
}

.link-btn {
  background: none;
  border: none;
  color: #FF843C;
  text-decoration: underline;
  cursor: pointer;
  padding: 0;
  font: inherit;
}

.status {
  background-color: #eaf2e3;
  border: 1px solid #699051;
  color: #2e4422;
  padding: 8px 12px;
  border-radius: 4px;
  margin-bottom: 10px;
  font-size: 0.9em;
}

.calendar {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 6px;
}

@media (max-width: 700px) {
  .calendar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.day-column {
  display: flex;
  flex-direction: column;
  gap: 6px;
  background-color: #f1f3ee;
  border-radius: 6px;
  padding: 6px;
  min-width: 0;
}

.day-header {
  text-align: center;
  padding: 4px 0;
}

.day-name {
  font-size: 0.8em;
  color: #666;
  text-transform: uppercase;
}

.day-date {
  font-size: 1.1em;
  font-weight: 600;
  color: #445837;
}

.meal-slot {
  background-color: white;
  border: 2px dashed #cfd8c5;
  border-radius: 4px;
  padding: 8px 6px;
  min-height: 70px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
  transition: background-color 0.15s, border-color 0.15s;
}

.meal-slot:hover {
  border-color: #699051;
}

.meal-slot--drag-over {
  background-color: #fff3e6;
  border-color: #FF843C;
}

.meal-slot--placeable {
  border-color: #FF843C;
}

.meal-slot--filled {
  background-color: #699051;
  border-style: solid;
  border-color: #445837;
  color: white;
}

.slot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
}

.slot-label {
  font-size: 0.7em;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: inherit;
  opacity: 0.85;
}

.slot-label--clickable {
  cursor: text;
  text-decoration: underline dotted;
  text-underline-offset: 2px;
}

.remove-slot-btn {
  background: none;
  border: none;
  color: inherit;
  opacity: 0.7;
  cursor: pointer;
  padding: 0 4px;
  font-size: 1em;
  line-height: 1;
}

.remove-slot-btn:hover {
  color: #FF843C;
  opacity: 1;
}

.slot-recipe {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 4px;
  font-size: 0.85em;
  word-break: break-word;
  background-color: rgba(255, 255, 255, 0.12);
  padding: 3px 6px;
  border-radius: 3px;
}

.meal-slot:not(.meal-slot--filled) .slot-recipe {
  background-color: rgba(0, 0, 0, 0.04);
}

.remove-btn {
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  padding: 0 4px;
  font-size: 1.1em;
  line-height: 1;
}

.remove-btn:hover {
  color: #FF843C;
}

.add-slot-btn {
  background: none;
  border: 1px dashed #b6c2a8;
  border-radius: 4px;
  padding: 4px 6px;
  color: #5b6b4d;
  font-size: 0.75em;
  cursor: pointer;
  margin-top: 2px;
}

.add-slot-btn:hover {
  background-color: #eaf2e3;
  border-color: #699051;
  color: #445837;
}
</style>
