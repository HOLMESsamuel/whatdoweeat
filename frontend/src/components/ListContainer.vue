<template>
    <div class="grocery-app">
      <div class="input-group">
        <input v-on:keyup.enter="addItem" v-model="newItem.name" placeholder="Item Name" />
        <button @click="addItem">Add Item</button>
        <input v-on:keyup.enter="joinList" v-model="newItem._id" placeholder="list id" />
        <button @click="joinList">Join a list</button>
      </div>
      <button v-for="item in items" :key="item.name">
          <router-link :to="`/list/${item._id}`" class="nav-link">{{ item.name }}</router-link>
      </button>
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
      const hashedEmail = hashEmail(user.value.email);
      const items = ref<GroceryList[]>([]);
      const newItem = ref<GroceryList>({ id_list: '', name: ''});
  
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
  
  h1 {
    text-align: center;
    margin-bottom: 20px;
  }
  </style>
  