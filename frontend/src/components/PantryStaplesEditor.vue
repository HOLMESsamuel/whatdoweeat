<template>
  <div class="pantry-section">
    <h3>Pantry staples</h3>
    <p class="hint">
      Ingredients you always have at home. They're never added to your
      grocery list from a recipe, so "sel" also covers "fleur de sel" or
      "sel et poivre".
    </p>
    <div v-if="loading" class="hint">Loading…</div>
    <template v-else>
      <ul class="chips">
        <li v-for="staple in staples" :key="staple" class="chip">
          {{ staple }}
          <button
            class="chip-remove"
            :aria-label="`Remove ${staple}`"
            :disabled="saving"
            @click="remove(staple)"
          >
            ×
          </button>
        </li>
        <li v-if="!staples.length" class="hint">
          None. Every ingredient gets added.
        </li>
      </ul>
      <form class="add-row" @submit.prevent="add">
        <input
          v-model="draft"
          type="text"
          placeholder="e.g. beurre"
          :disabled="saving"
        />
        <button type="submit" :disabled="saving || !draft.trim()">Add</button>
      </form>
    </template>
    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted } from 'vue';
import { fetchPantryStaples, savePantryStaples } from '../services/groceries';
import { apiErrorMessage } from '../services/recipes';

export default defineComponent({
  name: 'PantryStaplesEditor',
  props: {
    userId: { type: String, required: true },
  },
  setup(props) {
    const staples = ref<string[]>([]);
    const draft = ref('');
    const loading = ref(true);
    const saving = ref(false);
    const error = ref('');

    const save = async (next: string[]) => {
      saving.value = true;
      error.value = '';
      try {
        staples.value = await savePantryStaples(props.userId, next);
        return true;
      } catch (err: any) {
        error.value = apiErrorMessage(err, 'Could not save your staples.');
        return false;
      } finally {
        saving.value = false;
      }
    };

    const add = async () => {
      const item = draft.value.trim();
      if (!item) return;
      const exists = staples.value.some(
        s => s.toLowerCase() === item.toLowerCase()
      );
      if (exists || (await save([...staples.value, item]))) draft.value = '';
    };

    const remove = (staple: string) =>
      save(staples.value.filter(s => s !== staple));

    onMounted(async () => {
      try {
        staples.value = await fetchPantryStaples(props.userId);
      } catch (err: any) {
        error.value = apiErrorMessage(err, 'Could not load your staples.');
      } finally {
        loading.value = false;
      }
    });

    return { staples, draft, loading, saving, error, add, remove };
  },
});
</script>

<style scoped>
.pantry-section {
  margin: 24px 0;
  padding: 20px;
  background-color: #f8f9fa;
  border-radius: 8px;
}

.pantry-section h3 {
  margin: 0 0 8px;
  color: #445837;
}

.hint {
  color: #666;
  font-size: 0.9em;
  margin: 0 0 12px;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  list-style: none;
  padding: 0;
  margin: 0 0 12px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background-color: #699051;
  color: white;
  border-radius: 999px;
  padding: 4px 6px 4px 12px;
}

.chip-remove {
  background: none;
  border: none;
  color: white;
  font-size: 1.1em;
  line-height: 1;
  padding: 0 4px;
  cursor: pointer;
}

.add-row {
  display: flex;
  gap: 8px;
  max-width: 400px;
}

.add-row input {
  flex: 1;
  min-width: 0;
  padding: 6px 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.add-row button {
  background-color: #699051;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 6px 14px;
  cursor: pointer;
}

.add-row button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error {
  color: #b91c1c;
  font-size: 0.9em;
}
</style>
