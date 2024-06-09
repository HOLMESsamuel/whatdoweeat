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
    <div class="list-section">
      <router-link
        v-for="item in items"
        :key="item._id"
        :to="`/list/${item._id}`"
        class="list-item"
      >
        {{ item.name }}
      </router-link>
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

      const { user, isAuthenticated, isLoading, logout } = useAuth0();
      let hashedEmail = "";
      const items = ref<GroceryList[]>([]);
      const newItem = ref<GroceryList>({ _id: '', name: ''});
  
      const fetchList = async () => {
        const response = await axios.get(`http://localhost:8000/user/${hashedEmail}/grocery-list`);
        items.value = response.data;
      };
  
      const joinList = async () => {
        if (newItem.value._id !== "") {
          await axios.patch(`http://localhost:8000/grocery-list/${newItem.value._id}/user/${hashedEmail}`);
          fetchList();
        }
      }
  
      const addItem = async () => {
        if (newItem.value.name !== "") {
          await axios.post(`http://localhost:8000/user/${hashedEmail}/grocery-list`, newItem.value);
          newItem.value.name = '';
          fetchList();
        }
      };
  
      const removeItem = async (name: string) => {
        await axios.delete(`http://localhost:8000/grocery/${name}`);
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
  display: block;
  padding: 8px;
  background-color: #f8f9fa;
  color: #343a40;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  margin-bottom: 8px;
  text-decoration: none;
}

.list-item:hover {
  background-color: #e2e6ea;
}
</style>
  