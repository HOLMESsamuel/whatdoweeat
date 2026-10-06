<template>
  <div class="container">
    <div class="row align-items-center profile-header">
      <div class="col-md-2 mb-3">
        <img
          :src="user?.picture"
          alt="User's profile picture"
          class="rounded-circle img-fluid profile-picture"
        />
      </div>
      <div class="col-md text-center text-md-left">
        <h2>{{ user?.name }}</h2>
        <p class="lead text-muted">{{ user?.email }}</p>
      </div>
    </div>

    <!-- Dropbox connection management. -->
    <div class="dropbox-section">
      <h3>Dropbox connection</h3>
      <div v-if="loading">Checking…</div>
      <div v-else-if="status.connected">
        <p>
          Connected. Reading recipes from
          <code>{{ status.recipes_path || '/' }}</code>.
        </p>
        <dropbox-folder-picker
          v-if="pickingFolder"
          :user-id="user?.sub || ''"
          :initial-path="status.recipes_path || ''"
          @saved="onFolderSaved"
          @cancel="pickingFolder = false"
        />
        <div v-else class="buttons">
          <button @click="pickingFolder = true" class="secondary-btn">
            Change folder
          </button>
          <button @click="disconnect" :disabled="busy" class="danger-btn">
            {{ busy ? 'Disconnecting…' : 'Disconnect Dropbox' }}
          </button>
        </div>
        <p v-if="message" class="message">{{ message }}</p>
      </div>
      <div v-else>
        <p>No Dropbox account connected.</p>
        <router-link to="/recipes" class="link-btn">
          Connect on the Recipes page →
        </router-link>
      </div>
    </div>

    <pantry-staples-editor v-if="user?.sub" :user-id="user.sub" />

    <div class="row">
      <highlightjs language="json" :code="JSON.stringify(user, null, 2)" />
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted, watch } from 'vue';
import { useAuth0 } from '@auth0/auth0-vue';
import { getApi } from '../services/api';
import { clearRecipeCache } from '../services/recipes';
import DropboxFolderPicker from '../components/DropboxFolderPicker.vue';
import PantryStaplesEditor from '../components/PantryStaplesEditor.vue';

export default defineComponent({
  name: "profile-view",
  components: { DropboxFolderPicker, PantryStaplesEditor },
  setup() {
    const { user, isAuthenticated, isLoading } = useAuth0();
    const api = getApi();

    const loading = ref(true);
    const busy = ref(false);
    const status = ref<{ connected: boolean; recipes_path?: string }>({
      connected: false,
    });
    const message = ref('');
    const pickingFolder = ref(false);

    let userPath = '';

    const fetchStatus = async () => {
      const sub = user.value?.sub;
      if (!sub) return;
      userPath = encodeURIComponent(sub);
      loading.value = true;
      try {
        const { data } = await api.get(`/user/${userPath}/dropbox/status`);
        status.value = data;
      } catch (err) {
        console.error('status fetch failed:', err);
      } finally {
        loading.value = false;
      }
    };

    const disconnect = async () => {
      if (!userPath) return;
      busy.value = true;
      message.value = '';
      try {
        await api.delete(`/user/${userPath}/dropbox`);
        clearRecipeCache();
        status.value = { connected: false };
        message.value = 'Disconnected. Recipes will no longer sync.';
      } catch (err: any) {
        message.value =
          err?.response?.data?.detail || 'Could not disconnect.';
      } finally {
        busy.value = false;
      }
    };

    const onFolderSaved = (path: string) => {
      status.value = { ...status.value, recipes_path: path };
      pickingFolder.value = false;
      message.value = 'Recipe folder updated.';
    };

    onMounted(() => {
      if (!isLoading.value && isAuthenticated.value) {
        fetchStatus();
      } else {
        watch(
          () => isLoading.value,
          loadingAuth => {
            if (!loadingAuth && isAuthenticated.value) fetchStatus();
          }
        );
      }
    });

    return {
      user,
      status,
      loading,
      busy,
      message,
      pickingFolder,
      disconnect,
      onFolderSaved,
    };
  }
});
</script>

<style scoped>
.dropbox-section {
  margin: 24px 0;
  padding: 20px;
  background-color: #f8f9fa;
  border-radius: 8px;
}

.dropbox-section h3 {
  margin: 0 0 12px;
  color: #445837;
}

.dropbox-section code {
  background-color: #e9ecef;
  padding: 2px 6px;
  border-radius: 3px;
}

.dropbox-section code {
  overflow-wrap: anywhere;
}

.buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.secondary-btn {
  background-color: white;
  color: #699051;
  border: 1px solid #699051;
  border-radius: 4px;
  padding: 8px 16px;
  cursor: pointer;
}

.danger-btn {
  background-color: #b91c1c;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 8px 16px;
  cursor: pointer;
}

.danger-btn:disabled {
  opacity: 0.6;
  cursor: progress;
}

.link-btn {
  color: #699051;
  text-decoration: none;
}

.message {
  margin-top: 8px;
  color: #555;
  font-size: 0.9em;
}
</style>
