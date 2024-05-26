import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router';
import LandingPage from '../components/LandingPage.vue';
import GroceryList from '../components/GroceryList.vue';

const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    name: 'LandingPage',
    component: LandingPage,
  },
  {
    path: '/list/:code',
    name: 'GroceryList',
    component: GroceryList,
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;