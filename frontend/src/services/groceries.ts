/**
 * Sending a recipe's ingredients to a grocery list, minus pantry staples.
 *
 * Staples (salt, pepper, olive oil… editable on the Profile page) are
 * things the user always has at home, so they're skipped. An ingredient
 * is a staple when the staple appears in its name as whole words,
 * ignoring case and accents: "sel" matches "sel fin" and "fleur de sel"
 * but not "selle d'agneau"; "poivre" doesn't match "poivron".
 */

import { getApi } from './api';
import type { Recipe } from '../components/RecipeList.vue';

export interface GroceryListSummary {
  _id: string;
  name: string;
}

export interface AddResult {
  added: string[];
  skipped: string[];
}

export const normalizeIngredient = (s: string): string =>
  (s || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[’`]/g, "'")
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();

const escapeRegExp = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

export function stapleMatcher(staples: string[]): (name: string) => boolean {
  const patterns = staples
    .map(normalizeIngredient)
    .filter(Boolean)
    .map(s => new RegExp(`(^|[^a-z0-9])${escapeRegExp(s)}($|[^a-z0-9])`));
  return (name: string) => {
    const n = normalizeIngredient(name);
    return patterns.some(p => p.test(n));
  };
}

export async function fetchPantryStaples(userId: string): Promise<string[]> {
  const { data } = await getApi().get(
    `/user/${encodeURIComponent(userId)}/pantry-staples`
  );
  return data?.staples || [];
}

export async function savePantryStaples(
  userId: string,
  staples: string[]
): Promise<string[]> {
  const { data } = await getApi().put(
    `/user/${encodeURIComponent(userId)}/pantry-staples`,
    { staples }
  );
  return data?.staples || [];
}

export async function fetchGroceryLists(
  userId: string
): Promise<GroceryListSummary[]> {
  const { data } = await getApi().get(
    `/user/${encodeURIComponent(userId)}/grocery-list`
  );
  return (data || []).map((d: any) => ({
    _id: typeof d._id === 'string' ? d._id : String(d._id),
    name: d.name,
  }));
}

/** Add every non-staple ingredient of `recipe` to the list. */
export async function addRecipeToList(
  listId: string,
  recipe: Recipe,
  staples: string[]
): Promise<AddResult> {
  const api = getApi();
  const isStaple = stapleMatcher(staples);
  const result: AddResult = { added: [], skipped: [] };
  // Sequential to keep server load light and avoid race-condition log
  // spam in the websocket broadcaster.
  for (const g of recipe.groceries || []) {
    if (isStaple(g.name)) {
      result.skipped.push(g.name);
      continue;
    }
    try {
      await api.post(`/grocery-list/${listId}/grocery`, {
        id: '',
        name: g.name,
        quantity: g.quantity || '',
        description: recipe.name,
        type: 'other',
        color: '',
      });
      result.added.push(g.name);
    } catch (err) {
      console.error('Could not add grocery', g, err);
    }
  }
  return result;
}
