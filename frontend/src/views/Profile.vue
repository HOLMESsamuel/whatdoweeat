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
          <code>{{ status.recipes_path }}</code>.
        </p>
        <button @click="disconnect" :disabled="busy" class="danger-btn">
          {{ busy ? 'Disconnecting…' : 'Disconnect Dropbox' }}
        </button>
        <p v-if="message" class="message">{{ message }}</p>
      </div>
      <div v-else>
        <p>No Dropbox account connected.</p>
        <router-link to="/recipes" class="link-btn">
          Connect on the Recipes page →
        </router-link>
      </div>
    </div>

    <div class="row">
      <highlightjs language="json" :code="JSON.stringify(user, null, 2)" />
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted, watch } from 'vue';
import { useAuth0 } from '@auth0/auth0-vue';
import { getApi } from '../services/api';

export default defineComponent({
  name: "profile-view",
  setup() {
    const { user, isAuthenticated, isLoading } = useAuth0();
    const api = getApi();

    const loading = ref(true);
    const busy = ref(false);
    const status = ref<{ connected: boolean; recipes_path?: string }>({
      connected: false,
    });
    const message = ref('');

    let userId = '';
    let userPath = '';

    const fetchStatus = async () => {
      const sub = user.value?.sub;
      if (!sub) return;
      userId = sub;
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
        status.value = { connected: false };
        message.value = 'Disconnected. Recipes will no longer sync.';
      } catch (err: any) {
        message.value =
          err?.response?.data?.detail || 'Could not disconnect.';
      } finally {
        busy.value = false;
      }
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

    return { user, status, loading, busy, message, disconnect };
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
