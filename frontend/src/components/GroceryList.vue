<template>
    <div class="grocery-app">
      <h1>Grocery List</h1>
      <div class="input-group">
        <input v-on:keyup.enter="addItem" v-model="newItem.name" placeholder="Item Name" />
        <button @click="addItem">Add Item</button>
      </div>
      <div class="to-buy-list">
        <button v-for="item in items" :key="item.name" @click="removeItem(item.name)">
          {{ item.name }}
        </button>
      </div>
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
        if(newItem && newItem.value.name != ""){
          await axios.post(`http://localhost:8000/grocery`, newItem.value);
          newItem.value.name = '';
          fetchList();
        }
      };
  
      const removeItem = async (name: string) => {
        await axios.delete(`http://localhost:8000/grocery/${name}`);
        fetchList();
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
    margin-bottom: 20px;
  }
  
  input {
    flex: 1;
    padding: 10px;
    margin-right: 10px;
    border: 1px solid #ccc;
    border-radius: 4px;
    background-color: #1e1e1e;
    color: #fff;
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
  
  .to-buy-list button {
    background-color: #da3203;
    padding: 10px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  
  .to-buy-list button:hover {
    background-color: #6f1800;
  }
  </style>
  