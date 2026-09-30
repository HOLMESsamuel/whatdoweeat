<template>
  <div id="app" class="flex flex-col min-h-screen" :class="{ 'dark': isDark }">
    <nav-bar />
    <div class="container flex-grow">
      <error />
      <div v-if="accessDenied" class="alert alert-warning">
        This account isn't allowed to use What do we eat. Ask the owner to
        add you, or log in with another account.
      </div>
      <div class="mt-5">
        <router-view />
      </div>
    </div>
    <footer class="text-center p-3" :class="{ 'dark': isDark }">
      <div class="logo"></div>
      <p>
        What do we eat ?
      </p>
    </footer>
  </div>
</template>

<script lang="ts">
import NavBar from "./components/NavBar.vue";
import Error from "./components/Error.vue";
import { useDark } from '@vueuse/core';
import { accessDenied } from './services/api';

export default {
  components: {
    NavBar,
    Error
  },

  setup () {
    const isDark = useDark();

    return {
      isDark,
      accessDenied
    }
  }
};
</script>
<style scoped>
#app {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}
.flex-grow {
  flex-grow: 1;
}

.dark{
  background-color: #121212;
  color: #e0e0e0;
}
</style>