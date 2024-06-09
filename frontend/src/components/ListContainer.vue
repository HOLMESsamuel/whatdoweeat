<template>
  <div class="grocery-app container">
    <div class="form-section">
      <!-- Form Section -->
      <div class="input-group">
        <div class="input-item">
          <input
            v-on:keyup.enter="addItem"
            v-model="newItem.name"
            placeholder="List name"
            class="input"
          />
          <button
            @click="addItem"
            class="button"
          >
            Create a list
          </button>
        </div>
        <div class="input-item">
          <input
            v-on:keyup.enter="joinList"
            v-model="newItem._id"
            placeholder="List id"
            class="input"
          />
          <button
            @click="joinList"
            class="button"
          >
            Join a list
          </button>
        </div>
      </div>
    </div>

    <!-- List Section -->
    <div
        v-for="item in items"
        :key="item._id"
        class="list-item"
      >
        <router-link
          :to="`/lists/${item._id}`"
          class="list-link"
        >
          {{ item.name }}
        </router-link>
        <button @click="removeItem(item._id)" class="trash-button">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-trash" viewBox="0 0 16 16">
            <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0z"/>
            <path d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4zM2.5 3h11V2h-11z"/>
          </svg>
        </button>
      </div>
  </div>
</template>
  
  <script lang="ts">
  import { defineComponent, ref, onMounted } from 'vue';
  import axios from 'axios';
  import { useAuth0 } from '@auth0/auth0-vue';
  import CryptoJS from 'crypto-js';
  
  interface GroceryList{
    _id: string,
    name: string;
  }
  
  export default defineComponent({
    setup() {

      const hashEmail = (email: string) => {
        return CryptoJS.SHA256(email).toString(CryptoJS.enc.Hex);
      };
      const backendUrl = import.meta.env.VITE_BACKEND_BASE_URL;

      const { user, isAuthenticated, isLoading, logout } = useAuth0();
      let hashedEmail = "";
      const items = ref<GroceryList[]>([]);
      const newItem = ref<GroceryList>({ _id: '', name: ''});
  
      const fetchList = async () => {
        const response = await axios.get(`${backendUrl}` + '/user/'+ `${hashedEmail}` + '/grocery-list');
        items.value = response.data;
      };
  
      const joinList = async () => {
        if (newItem.value._id !== "") {
          await axios.patch(`${backendUrl}/grocery-list/${newItem.value._id}/user/${hashedEmail}`);
          fetchList();
        }
      }
  
      const addItem = async () => {
        if (newItem.value.name !== "") {
          await axios.post(`${backendUrl}/user/${hashedEmail}/grocery-list`, newItem.value);
          newItem.value.name = '';
          fetchList();
        }
      };
  
      const removeItem = async (id: string) => {
        await axios.delete(`${backendUrl}/grocery-list/${id}`);
        fetchList();
      };

  
      onMounted(() => {
        if (!isLoading.value && isAuthenticated.value) {
          if(user && user.value && user.value.email) {
            hashedEmail = hashEmail(user.value.email);
          }
          fetchList();
          
        }
      });
  
      return {
        items,
        newItem,
        addItem,
        removeItem,
        logout,
        joinList,
        user,
        isAuthenticated,
        isLoading
      };
    },
  });
  </script>
  
<style scoped>
.container {
  max-width: 600px;
  margin: 0 auto;
  padding: 16px;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
}

.form-section, .list-section {
  margin-bottom: 16px;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.input-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input {
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
  width: 100%;
  box-sizing: border-box;
}

.button {
  padding: 8px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  width: 100%;
  text-align: center;
}

.button:hover {
  background-color: #0056b3;
}

.list-section {
  margin-top: 32px;
}

.list-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px;
  background-color: #f8f9fa;
  color: #343a40;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  margin-bottom: 8px;
}

.list-link {
  flex-grow: 1;
  text-decoration: none;
  color: inherit;
}

.trash-button {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  margin: 0;
  display: flex;
  align-items: center;
}

.trash-button:hover svg {
  fill: red;
}
</style>
  