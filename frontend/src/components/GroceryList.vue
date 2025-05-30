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
          <option value="pantry">Frozen</option>
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
              @click="removeItem(item.id)"
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
    <edit-item-modal
      :show="showEditModal"
      :item="selectedItem"
      @close="closeEditModal"
      @save="updateItem"
    />
  </div> 
</template>

<script lang="ts">
import { defineComponent, ref, onMounted, computed } from 'vue';
import axios from 'axios';
import { WebSocketService } from '../services/websocket';
import { useAuth0 } from '@auth0/auth0-vue';
import { useRoute } from 'vue-router';
import EditItemModal from './EditItemModal.vue';

interface GroceryList {
  name: string,
  groceries: GroceryItem[]
}

interface GroceryItem {
  id: string;
  name: string;
  quantity?: string;
  description?: string;
  type?: string;
  color?: string;
}

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
    const backendUrl = import.meta.env.VITE_BACKEND_BASE_URL;
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
    const colors = ['green', 'purple', 'orange'];

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
      const response = await axios.get(`${backendUrl}/grocery-list/${listId}`);
      groceryList.value = response.data;
    };

    const addItem = async () => {
      if (newItem.value.name !== "") {
        newItem.value.name = newItem.value.name.trim();
        await axios.post(`${backendUrl}/grocery-list/${listId}/grocery`, newItem.value);
        newItem.value.name = '';
        newItem.value.quantity = '';
        newItem.value.description = '';
        newItem.value.type = 'other'; // Reset to default
      }
    };

    const removeItem = async (id: string) => {
      const index = groceryList.value.groceries.findIndex(item => item.id === id);
        if (index !== -1) {
          groceryList.value.groceries.splice(index, 1);
        }
      try {
        await axios.delete(`${backendUrl}/grocery-list/${listId}/grocery/${id}`);
      } catch (error) {
        console.error('Error removing item:', error);
      }
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
      touchTimer = window.setTimeout(() => {
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
        await axios.put(`${backendUrl}/grocery-list/${listId}/grocery/${updatedItem.id}`, updatedItem);
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
