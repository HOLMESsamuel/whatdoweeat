/**
 * Session-level cache of the user's recipes.
 *
 * Recipes, Planner and a recipe's detail page all need the same list, and
 * a Dropbox round-trip on the backend takes a noticeable moment. Pages
 * render the cached copy straight away and then revalidate with
 * `loadRecipes()`; concurrent loads share a single request.
 */

import { getApi } from './api';
import type { Recipe } from '../components/RecipeList.vue';

let cache: { userId: string; recipes: Recipe[] } | null = null;
let inflight: { userId: string; promise: Promise<Recipe[]> } | null = null;

export function cachedRecipes(userId: string): Recipe[] | null {
  return cache && cache.userId === userId ? cache.recipes : null;
}

export function cachedRecipe(userId: string, id: string): Recipe | undefined {
  return cachedRecipes(userId)?.find(r => r.id === id);
}

export function loadRecipes(userId: string): Promise<Recipe[]> {
  if (inflight && inflight.userId === userId) return inflight.promise;
  const promise = getApi()
    .get(`/user/${encodeURIComponent(userId)}/recipes`)
    .then(({ data }) => {
      const recipes: Recipe[] = data || [];
      cache = { userId, recipes };
      return recipes;
    })
    .finally(() => {
      if (inflight?.promise === promise) inflight = null;
    });
  inflight = { userId, promise };
  return promise;
}

export function clearRecipeCache(): void {
  cache = null;
  inflight = null;
}

/** Error message from a failed API call, preferring the backend's detail. */
export function apiErrorMessage(err: any, fallback: string): string {
  return err?.response?.data?.detail || fallback;
}
