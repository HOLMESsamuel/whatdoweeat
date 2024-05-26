<script setup lang="ts">
import { useDark, useToggle } from '@vueuse/core';
const isDark = useDark();
const toggleDark = useToggle(isDark);
</script>

<template>
  <button @click="toggleDark()">dark mode</button>
  <router-view />
</template>

<style>
.dark {
  background: rgb(62, 62, 62);
  color: white;
}
</style>
