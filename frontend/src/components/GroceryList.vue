<template>
  <div class="grocery-app">
    <h1>{{groceryList.name}}</h1>
    <button class="shareButton" @click="copyId">
      <img class="shareButtonImage" src="../assets/share.svg" alt="share list"/>
    </button>
    <form @submit.prevent="addItem">
      <div class="input-group">
        <input v-model="newItem.name" placeholder="Item Name" required />
        <input v-model="newItem.quantity" placeholder="Quantity" />
      </div>
      <div class="input-group">
        <select v-model="newItem.type" class="type-select">
          <option value="vegetables">Vegetables/Fruits</option>
          <option value="meat">Meat</option>
          <option value="dairy">Dairy</option>
          <option value="pantry">Pantry</option>
          <option value="frozen">Frozen</option>
          <option value="other">Other</option>
        </select>
        <div class="color-picker">
          <div 
            v-for="color in colors" 
            :key="color"
            class="color-dot"
            :class="{ selected: newItem.color === color }"
            :style="{ backgroundColor: color }"
            @click="newItem.color = color"
          ></div>
        </div>
      </div>
      <div class="input-group-description">
        <textarea v-model="newItem.description" placeholder="Description"></textarea>
      </div>
      <div class="input-group-button">
        <button type="submit">Add Item</button>
      </div>
    </form>
    <div class="grocery-sections">
      <div v-for="(items, type) in groupedItems" :key="type" class="grocery-section">
        <h2 class="section-title">{{ String(type).charAt(0).toUpperCase() + String(type).slice(1) }}</h2>
        <div class="to-buy-list">
          <div v-for="item in items" :key="item.id" class="item-card">
            <button 
              @click="onItemClick(item)"
              @touchstart="startTouch(item)"
              @touchend="endTouch"
              @touchcancel="endTouch"
              @contextmenu.prevent="openEditModal(item)"
              :style="{ backgroundColor: item.color || '#FF843C' }"
            >
              <div>
                {{ item.name }} <span v-if="item.quantity">({{ item.quantity }})</span>
                <br>
                <small v-if="item.description">{{ item.description }}</small>
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="recentlyRemoved.length" class="removed-section">
      <button
        class="removed-toggle"
        :aria-expanded="showRemoved"
        @click="showRemoved = !showRemoved"
      >
        Recently removed ({{ recentlyRemoved.length }})
        <span class="removed-caret">{{ showRemoved ? '▴' : '▾' }}</span>
      </button>
      <ul v-if="showRemoved" class="removed-list">
        <li v-for="item in recentlyRemoved" :key="item.id" class="removed-item">
          <span class="removed-name">
            {{ item.name }}<span v-if="item.quantity"> ({{ item.quantity }})</span>
            <small v-if="item.description">{{ item.description }}</small>
          </span>
          <span class="removed-ago">{{ ago(item.removed_at) }}</span>
          <button class="restore-btn" @click="restoreItem(item)">↺ Restore</button>
        </li>
      </ul>
    </div>
    <div v-if="undo" class="undo-bar" role="status">
      <span>Removed {{ undo.name }}</span>
      <button class="undo-btn" @click="restoreItem(undo)">Undo</button>
    </div>
    <edit-item-modal
      :show="showEditModal"
      :item="selectedItem"
      @close="closeEditModal"
      @save="updateItem"
    />
  </div> 
</template>

<script lang="ts">
import { defineComponent, ref, onMounted, onBeforeUnmount, computed } from 'vue';
import { WebSocketService } from '../services/websocket';
import { useAuth0 } from '@auth0/auth0-vue';
import { useRoute } from 'vue-router';
import EditItemModal from './EditItemModal.vue';
import { getApi } from '../services/api';

interface GroceryList {
  name: string,
  groceries: GroceryItem[],
  removed?: RemovedItem[]
}

interface GroceryItem {
  id: string;
  name: string;
  quantity?: string;
  description?: string;
  type?: string;
  color?: string;
}

interface RemovedItem extends GroceryItem {
  removed_at: string;
}

// Matches REMOVED_TTL in backend/src/services/db_service.py.
const REMOVED_TTL_MS = 60 * 60 * 1000;
const UNDO_MS = 6000;

export default defineComponent({
  components: {
    EditItemModal
  },
  setup() {
    const route = useRoute();
    const listId = route.params.id_list;
    const { user, isAuthenticated, isLoading, logout } = useAuth0();
    const groceryList = ref<GroceryList>({ name: '', groceries: []});
    const newItem = ref<GroceryItem>({ 
      id: '', 
      name: '', 
      quantity: '', 
      description: '',
      type: 'other',
      color: 'purple'
    });
    const socket = ref<WebSocketService | null>(null);
    const api = getApi();
    const backendWsUrl = import.meta.env.VITE_WS_BACKEND_BASE_URL;
    const showEditModal = ref(false);
    const selectedItem = ref<GroceryItem>({ 
      id: '', 
      name: '', 
      quantity: '', 
      description: '',
      type: 'other',
      color: 'purple'
    });
    let touchTimer: number | null = null;
    // Set when a long press opened the edit modal, so the click that ends
    // the press doesn't also remove the item.
    let suppressClick = false;
    const colors = ['green', 'purple', 'orange'];
    const showRemoved = ref(false);
    const undo = ref<GroceryItem | null>(null);
    let undoTimer: number | null = null;
    // Ticks so "x min ago" labels and expiry stay current.
    const now = ref(Date.now());
    const clock = window.setInterval(() => (now.value = Date.now()), 30_000);
    onBeforeUnmount(() => {
      clearInterval(clock);
      if (undoTimer) clearTimeout(undoTimer);
    });

    const recentlyRemoved = computed(() =>
      (groceryList.value.removed || [])
        .filter(r => now.value - Date.parse(r.removed_at) < REMOVED_TTL_MS)
        .slice()
        .reverse()
    );

    const ago = (iso: string) => {
      const minutes = Math.floor((now.value - Date.parse(iso)) / 60_000);
      return minutes < 1 ? 'just now' : `${minutes} min ago`;
    };

    const groupedItems = computed(() => {
      const groups: { [key: string]: GroceryItem[] } = {};
      groceryList.value.groceries.forEach(item => {
        const type = item.type || 'other';
        if (!groups[type]) {
          groups[type] = [];
        }
        groups[type].push(item);
      });
      return groups;
    });

    const fetchList = async () => {
      const response = await api.get(`/grocery-list/${listId}`);
      groceryList.value = response.data;
    };

    const addItem = async () => {
      if (newItem.value.name !== "") {
        newItem.value.name = newItem.value.name.trim();
        await api.post(`/grocery-list/${listId}/grocery`, newItem.value);
        newItem.value.name = '';
        newItem.value.quantity = '';
        newItem.value.description = '';
        newItem.value.type = 'other'; // Reset to default
      }
    };

    const removeItem = async (id: string) => {
      const index = groceryList.value.groceries.findIndex(item => item.id === id);
      if (index !== -1) {
        const [item] = groceryList.value.groceries.splice(index, 1);
        groceryList.value.removed = [
          ...(groceryList.value.removed || []),
          { ...item, removed_at: new Date().toISOString() },
        ];
        undo.value = item;
        if (undoTimer) clearTimeout(undoTimer);
        undoTimer = window.setTimeout(() => (undo.value = null), UNDO_MS);
      }
      try {
        await api.delete(`/grocery-list/${listId}/grocery/${id}`);
      } catch (error) {
        console.error('Error removing item:', error);
      }
    };

    const restoreItem = async (item: GroceryItem) => {
      if (undo.value?.id === item.id) undo.value = null;
      groceryList.value.removed = (groceryList.value.removed || []).filter(
        r => r.id !== item.id
      );
      if (!groceryList.value.groceries.some(g => g.id === item.id)) {
        const { removed_at, ...restored } = item as RemovedItem;
        groceryList.value.groceries.push(restored);
      }
      try {
        await api.post(`/grocery-list/${listId}/grocery/${item.id}/restore`);
      } catch (error) {
        console.error('Error restoring item:', error);
        fetchList();
      }
    };

    const onItemClick = (item: GroceryItem) => {
      if (suppressClick) {
        suppressClick = false;
        return;
      }
      removeItem(item.id);
    };

    const connectSocket = () => {
      socket.value = new WebSocketService(`${backendWsUrl}/${listId}`);
      socket.value.connect((_event) => {
        fetchList();
      });
    };

    const copyId = async() => {
      try {
        navigator.clipboard.writeText(listId as string);
      } catch (err) {
        console.error('Failed to copy text: ', err);
      }
    }

    const startTouch = (item: GroceryItem) => {
      suppressClick = false;
      touchTimer = window.setTimeout(() => {
        suppressClick = true;
        selectedItem.value = item;
        showEditModal.value = true;
      }, 500);
    };

    const endTouch = () => {
      if (touchTimer) {
        clearTimeout(touchTimer);
        touchTimer = null;
      }
    };

    const closeEditModal = () => {
      showEditModal.value = false;
      selectedItem.value = { id: '', name: '', quantity: '', description: '', type: 'other', color: 'purple'};
    };

    const updateItem = async (updatedItem: GroceryItem) => {
      try {
        await api.put(`/grocery-list/${listId}/grocery/${updatedItem.id}`, updatedItem);
        const index = groceryList.value.groceries.findIndex(item => item.id === updatedItem.id);
        if (index !== -1) {
          groceryList.value.groceries[index] = updatedItem;
        }
      } catch (error) {
        console.error('Error updating item:', error);
      }
    };

    const openEditModal = (item: GroceryItem) => {
      selectedItem.value = item;
      showEditModal.value = true;
    };

    onMounted(() => {
      if (!isLoading.value && isAuthenticated.value) {
        fetchList();
        connectSocket();
      }
    });

    return {
      listId,
      groceryList,
      newItem,
      addItem,
      removeItem,
      restoreItem,
      onItemClick,
      recentlyRemoved,
      showRemoved,
      undo,
      ago,
      logout,
      user,
      isAuthenticated,
      isLoading,
      copyId,
      showEditModal,
      selectedItem,
      startTouch,
      endTouch,
      closeEditModal,
      updateItem,
      openEditModal,
      groupedItems,
      colors
    };
  },
});
</script>

<style scoped>
.grocery-app {
  background-color: #699051;
  color: white;
  font-family: 'Roboto', sans-serif;
  padding: 20px;
  max-width: 600px;
  margin: auto;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
}

.shareButton {
  position: relative;
  left: 93%;
  top:-42px;
  background: none;
  border: none;
}

.shareButton:focus {
  outline: none;
}

.shareButtonImage {
  filter: brightness(0) saturate(100%) invert(100%) sepia(0%) saturate(7500%) hue-rotate(124deg) brightness(101%) contrast(104%);
}

h1 {
  text-align: center;
}

.input-group {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}

.input-group input {
  flex: 1;
  padding: 10px;
  margin-right: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background-color: #445837;
  color: #fff;
}

.input-group input:last-child {
  margin-right: 0;
  flex: 0.3; /* Ensuring the quantity field is narrower */
}

.input-group-description {
  margin-bottom: 20px;
}

.input-group input::placeholder {
  color: white;
}

.input-group-description textarea::placeholder {
  color: white;
}

.input-group-description textarea {
  width: calc(100%);
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background-color: #445837;
  color: white;
  resize: none;
}

.input-group-button {
  text-align: center;
  margin-bottom: 20px;
}

.input-group-button button {
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  background-color: #445837;
  color: #fff;
  cursor: pointer;
}

.input-group-button button:hover {
  background-color: #35442a;
}

.to-buy-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.item-card button {
  background-color: #FF843C;
  padding: 10px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  color: white;
  width: 100%;
  text-align: left;
  user-select: none; /* Prevent text selection on long press */
}

.item-card button:hover {
  background-color: #FF7829;
}

@media (max-width: 800px) {
  .input-group {
    flex-direction: column;
  }

  .input-group input {
    margin-right: 0;
    margin-bottom: 10px;
  }

  .input-group input:last-child {
    flex: 1;
  }

  .input-group-description textarea {
    width: calc(100%); /* Adjusting for padding */
  }
}

.grocery-sections {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.removed-section {
  margin-top: 20px;
}

.removed-toggle {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #445837;
  color: white;
  border: none;
  border-radius: 8px;
  padding: 12px 15px;
  font-size: 1em;
  cursor: pointer;
}

.removed-list {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.removed-item {
  display: flex;
  align-items: center;
  gap: 10px;
  background-color: rgba(68, 88, 55, 0.6);
  border-radius: 6px;
  padding: 8px 10px;
}

.removed-name {
  flex: 1;
  min-width: 0;
  text-decoration: line-through;
  opacity: 0.85;
  overflow-wrap: anywhere;
}

.removed-name small {
  display: block;
  text-decoration: none;
  opacity: 0.8;
}

.removed-ago {
  font-size: 0.8em;
  opacity: 0.75;
  white-space: nowrap;
}

.restore-btn {
  background-color: white;
  color: #445837;
  border: none;
  border-radius: 4px;
  padding: 6px 10px;
  cursor: pointer;
  white-space: nowrap;
}

.undo-bar {
  position: fixed;
  left: 50%;
  bottom: 24px;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 16px;
  max-width: calc(100vw - 32px);
  box-sizing: border-box;
  padding: 10px 12px 10px 16px;
  border-radius: 8px;
  background-color: #2f3d26;
  color: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  z-index: 1000;
}

.undo-bar span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.undo-btn {
  background: none;
  border: none;
  color: #FF843C;
  font-weight: 700;
  text-transform: uppercase;
  cursor: pointer;
  padding: 4px 8px;
}

.grocery-section {
  background-color: #445837;
  border-radius: 8px;
  padding: 15px;
}

.section-title {
  margin: 0 0 15px 0;
  color: white;
  font-size: 1.2em;
}

.type-select, .color-select {
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background-color: #445837;
  color: white;
  flex: 1;
  margin-right: 10px;
}

.type-select:last-child, .color-select:last-child {
  margin-right: 0;
}

@media (max-width: 800px) {
  .type-select, .color-select {
    margin-right: 0;
    margin-bottom: 10px;
  }
}

.color-picker {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 5px;
}

.color-dot {
  width: 25px;
  height: 25px;
  border-radius: 50%;
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.2s ease;
}

.color-dot:hover {
  transform: scale(1.1);
}

.color-dot.selected {
  border-color: white;
  transform: scale(1.1);
}

@media (max-width: 800px) {
  .color-picker {
    justify-content: center;
    margin-top: 10px;
  }
}
</style>
