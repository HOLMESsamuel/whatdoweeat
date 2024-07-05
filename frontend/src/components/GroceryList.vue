<template>
  <div class="grocery-app">
    <h1>{{groceryList.name}}</h1>
    <div class="input-group">
      <input v-on:keyup.enter="addItem" v-model="newItem.name" placeholder="Item Name" required />
      <input v-on:keyup.enter="addItem" v-model="newItem.quantity" placeholder="Quantity" />
    </div>
    <div class="input-group-description">
      <textarea v-model="newItem.description" placeholder="Description"></textarea>
    </div>
    <div class="input-group-button">
      <button @click="addItem">Add Item</button>
    </div>
    <div class="to-buy-list">
      <div v-for="item in groceryList.groceries" :key="item.name" class="item-card">
        <button @click="removeItem(item.id)">
          <div>
            {{ item.name }} <span v-if="item.quantity">({{ item.quantity }})</span>
            <br>
            <small v-if="item.description">{{ item.description }}</small>
          </div>
        </button>
      </div>
    </div>
  </div> 
</template>

<script lang="ts">
import { defineComponent, ref, onMounted } from 'vue';
import axios from 'axios';
import { WebSocketService } from '../services/websocket';
import { useAuth0 } from '@auth0/auth0-vue';
import { useRoute } from 'vue-router';

interface GroceryList {
  name: string,
  groceries: GroceryItem[]
}

interface GroceryItem {
  id: string;
  name: string;
  quantity?: string;
  description?: string;
}

export default defineComponent({
  setup() {
    const route = useRoute();
    const listId = route.params.id_list;
    const { user, isAuthenticated, isLoading, logout } = useAuth0();
    const groceryList = ref<GroceryList>({ name: '', groceries: []});
    const newItem = ref<GroceryItem>({ id: '', name: '', quantity: '', description: ''});
    const socket = ref<WebSocketService | null>(null);
    const backendUrl = import.meta.env.VITE_BACKEND_BASE_URL;
    const backendWsUrl = import.meta.env.VITE_WS_BACKEND_BASE_URL;

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
      }
    };

    const removeItem = async (id: string) => {
      await axios.delete(`${backendUrl}/grocery-list/${listId}/grocery/${id}`);
    };

    const connectSocket = () => {
      socket.value = new WebSocketService(`${backendWsUrl}/${listId}`);
      socket.value.connect((_event) => {
        fetchList();
      });
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
      isLoading
    };
  },
});
</script>

<style scoped>
.grocery-app {
  background-color: #121212;
  color: #ffffff;
  font-family: 'Roboto', sans-serif;
  padding: 20px;
  max-width: 600px;
  margin: auto;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
}

h1 {
  text-align: center;
  margin-bottom: 20px;
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
  background-color: #1e1e1e;
  color: #fff;
}

.input-group input:last-child {
  margin-right: 0;
  flex: 0.3; /* Ensuring the quantity field is narrower */
}

.input-group-description {
  margin-bottom: 20px;
}

.input-group-description textarea {
  width: calc(100%);
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background-color: #1e1e1e;
  color: #fff;
  resize: none;
}

.input-group-button {
  text-align: center;
  margin-bottom: 20px;
}

button {
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  background-color: #006296;
  color: #fff;
  cursor: pointer;
}

button:hover {
  background-color: #00456a;
}

.to-buy-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.item-card button {
  background-color: #da3203;
  padding: 10px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.item-card button:hover {
  background-color: #6f1800;
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
</style>
