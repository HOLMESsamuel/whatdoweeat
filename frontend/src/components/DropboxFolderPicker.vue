<template>
  <div class="folder-picker">
    <form class="path-row" @submit.prevent="open(typedPath)">
      <input v-model="typedPath" type="text" placeholder="/path/to/recipes" />
      <button type="submit" class="secondary-btn">Go</button>
    </form>

    <div class="breadcrumbs">
      <button class="crumb" @click="open('')">Dropbox</button>
      <template v-for="crumb in crumbs" :key="crumb.path">
        <span class="sep">/</span>
        <button class="crumb" @click="open(crumb.path)">{{ crumb.name }}</button>
      </template>
    </div>

    <div v-if="loading" class="muted">Loading folders…</div>
    <ul v-else class="folder-list">
      <li v-if="!folders.length" class="muted">No subfolders</li>
      <li v-for="folder in folders" :key="folder.path">
        <button class="folder" @click="open(folder.path)">
          📁 {{ folder.name }}
        </button>
      </li>
    </ul>

    <p v-if="notice" class="muted">{{ notice }}</p>
    <p v-if="error" class="error">{{ error }}</p>

    <div class="actions">
      <button
        class="primary-btn"
        :disabled="saving || loading || !!error"
        @click="save"
      >
        {{ saving ? 'Saving…' : `Use ${current || '/'}` }}
      </button>
      <button class="secondary-btn" @click="$emit('cancel')">Cancel</button>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, onMounted } from 'vue';
import { getApi } from '../services/api';
import { apiErrorMessage, clearRecipeCache } from '../services/recipes';

interface Folder {
  name: string;
  path: string;
}

export default defineComponent({
  name: 'DropboxFolderPicker',
  props: {
    userId: { type: String, required: true },
    initialPath: { type: String, default: '' },
  },
  emits: ['saved', 'cancel'],
  setup(props, { emit }) {
    const api = getApi();
    const current = ref('');
    const typedPath = ref(props.initialPath);
    const folders = ref<Folder[]>([]);
    const loading = ref(false);
    const saving = ref(false);
    const error = ref('');
    const notice = ref('');

    const userPath = () => encodeURIComponent(props.userId);

    const crumbs = computed(() => {
      const out: Folder[] = [];
      let acc = '';
      for (const name of current.value.split('/').filter(Boolean)) {
        acc += `/${name}`;
        out.push({ name, path: acc });
      }
      return out;
    });

    const open = async (path: string) => {
      loading.value = true;
      error.value = '';
      notice.value = '';
      try {
        const { data } = await api.get(`/user/${userPath()}/dropbox/folders`, {
          params: { path },
        });
        current.value = data.path;
        typedPath.value = data.path || '/';
        folders.value = data.folders || [];
      } catch (err: any) {
        error.value = apiErrorMessage(err, 'Could not list Dropbox folders.');
      } finally {
        loading.value = false;
      }
    };

    const save = async () => {
      saving.value = true;
      error.value = '';
      try {
        const { data } = await api.put(`/user/${userPath()}/dropbox/path`, {
          recipes_path: current.value,
        });
        clearRecipeCache();
        emit('saved', data.recipes_path);
      } catch (err: any) {
        error.value = apiErrorMessage(err, 'Could not save the folder.');
      } finally {
        saving.value = false;
      }
    };

    onMounted(async () => {
      await open(props.initialPath);
      // The saved folder may have been moved or renamed; start from the
      // root so the user can pick a new one.
      if (error.value && props.initialPath) {
        const missing = error.value;
        await open('');
        if (!error.value) notice.value = missing;
      }
    });

    return {
      current,
      typedPath,
      folders,
      crumbs,
      loading,
      saving,
      error,
      notice,
      open,
      save,
    };
  },
});
</script>

<style scoped>
.folder-picker {
  margin: 12px 0;
  padding: 16px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background-color: #fff;
}

.path-row {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}

.path-row input {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-family: monospace;
}

.breadcrumbs {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px;
  margin-bottom: 8px;
}

.crumb {
  background: none;
  border: none;
  padding: 2px 4px;
  color: #699051;
  cursor: pointer;
}

.sep {
  color: #999;
}

.folder-list {
  list-style: none;
  padding: 0;
  margin: 0 0 12px;
  max-height: 260px;
  overflow-y: auto;
}

.folder {
  width: 100%;
  text-align: left;
  background: none;
  border: none;
  border-radius: 4px;
  padding: 6px 8px;
  cursor: pointer;
}

.folder:hover {
  background-color: #f1f5ee;
}

.muted {
  color: #888;
  font-size: 0.9em;
  padding: 6px 8px;
}

.error {
  color: #b91c1c;
  font-size: 0.9em;
}

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.primary-btn,
.secondary-btn {
  border-radius: 4px;
  padding: 8px 14px;
  cursor: pointer;
  border: 1px solid #699051;
}

.primary-btn {
  background-color: #699051;
  color: white;
  max-width: 100%;
  overflow-wrap: anywhere;
}

.secondary-btn {
  background-color: white;
  color: #699051;
}

.primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
