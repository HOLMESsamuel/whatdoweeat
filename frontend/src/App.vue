<template>
  <div id="app" class="flex flex-col min-h-screen">
    <nav-bar />
    <div class="container flex-grow">
      <error />
      <div class="mt-5">
        <router-view />
      </div>
    </div>
    <footer class="bg-light text-center p-3">
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

export default {
  components: {
    NavBar,
    Error
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
</style>