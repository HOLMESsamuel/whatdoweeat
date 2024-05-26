<template>
    <div>
      <h1>Enter List Code</h1>
      <input v-model="code" placeholder="List Code" />
      <button @click="goToList">Submit</button>
    </div>
  </template>
  
  <script lang="ts">
  import { defineComponent, ref } from 'vue';
  import { useRouter } from 'vue-router';
  
  export default defineComponent({
    setup() {
      const code = ref('');
      const router = useRouter();
  
      const goToList = () => {
        if (code.value) {
          router.push(`/list/${code.value}`);
        }
      };
  
      return {
        code,
        goToList,
      };
    },
  });
  </script>