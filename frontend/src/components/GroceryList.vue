<template>
    <div>
      <h1>Grocery List</h1>
      <input v-model="newItem.name" placeholder="Item Name" />
      <button @click="addItem">Add Item</button>
      <ul>
        <li v-for="item in items" :key="item.name">
          {{ item.name }}
          <button @click="removeItem(item.name)">Remove</button>
        </li>
      </ul>
      
    </div>
  </template>
  
  <script lang="ts">
  import { defineComponent, ref, onMounted } from 'vue';
  import axios from 'axios';
  import { useRoute } from 'vue-router';
  import { WebSocketService } from '../services/websocket';
  
  interface GroceryItem {
    name: string;
  }
  
  export default defineComponent({
    setup() {
      const items = ref<GroceryItem[]>([]);
      const newItem = ref<GroceryItem>({ name: ''});
      const route = useRoute();
      const code = route.params.code as string;
      const socket = new WebSocketService(`ws://localhost:8000/ws/${code}`);
  
      const fetchList = async () => {
        const response = await axios.get(`http://localhost:8000/grocery`);
        items.value = response.data;
      };
  
      const addItem = async () => {
        await axios.post(`http://localhost:8000/grocery`, newItem.value);
        newItem.value.name = '';
      };
  
      const removeItem = async (name: string) => {
        await axios.delete(`http://localhost:8000/grocery/${name}`);
      };
  
      onMounted(() => {
        fetchList();
        socket.connect((event) => {
          fetchList();
        });
      });
  
      return {
        items,
        newItem,
        addItem,
        removeItem,
      };
    },
  });
  </script>
  