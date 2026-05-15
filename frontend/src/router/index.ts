import { createRouter as createVueRouter, createWebHashHistory, Router } from "vue-router";
import Home from "../views/Home.vue";
import Profile from "../views/Profile.vue";
import { createAuthGuard } from "@auth0/auth0-vue";
import { App } from 'vue';
import ListContainer from "../components/ListContainer.vue";
import GroceryList from "../components/GroceryList.vue";
import Recipe from "../views/Recipe.vue";
import RecipeDetail from "../components/RecipeDetail.vue";
import Planner from "../views/Planner.vue";

export function createRouter(app: App): Router {
  return createVueRouter({
    routes: [
      {
        path: "/",
        name: "home",
        component: Home
      },
      {
        path: "/profile",
        name: "profile",
        component: Profile,
        beforeEnter: createAuthGuard(app)
      },
      {
        path: "/lists",
        name: "lists",
        component: ListContainer,
        beforeEnter: createAuthGuard(app)
      },
      {
        path: "/lists/:id_list",
        name: "grocery list",
        component: GroceryList,
        beforeEnter: createAuthGuard(app)
      },
      {
        path: "/recipes",
        name: "recipes",
        component: Recipe,
        beforeEnter: createAuthGuard(app)
      },
      {
        path: "/recipes/:id",
        name: "recipe-detail",
        component: RecipeDetail,
        beforeEnter: createAuthGuard(app)
      },
      {
        path: "/planner",
        name: "planner",
        component: Planner,
        beforeEnter: createAuthGuard(app)
      }
    ],
    history: createWebHashHistory()
  })
}