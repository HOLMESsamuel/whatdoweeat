/**
 * Ranking recipes as cooking ideas.
 *
 * The goal is "what should we eat", so the default view is meals (not
 * desserts or snacks), in an order that changes every day, with recipes
 * eaten or planned recently pushed to the bottom and out-of-season ones
 * pushed down a little.
 *
 * Desserts aren't tagged consistently, so `isSweet` falls back on the
 * ingredients and the name when tags don't settle it.
 */

import { getApi } from './api';
import { normalizeIngredient, stapleMatcher } from './groceries';
import type { Recipe } from '../components/RecipeList.vue';

export type Category = 'meal' | 'sweet';

const MEAL_TAGS = [
  'plat', 'plats', 'plat principal', 'repas', 'dejeuner', 'diner',
  'entree', 'soupe', 'salade',
];
const SWEET_TAGS = [
  'dessert', 'desserts', 'gouter', 'snack', 'snacks', 'apero', 'aperitif',
  'patisserie', 'gateau', 'gateaux', 'biscuit', 'biscuits', 'boisson',
  'petit dejeuner', 'petit-dejeuner', 'brunch sucre', 'sucre',
];
const SWEET_INGREDIENTS = stapleMatcher([
  'sucre', 'cassonade', 'vergeoise', 'sucre glace', 'chocolat', 'cacao',
  'levure chimique', 'sirop d\'erable', 'confiture', 'pepites de chocolat',
]);
// Any of these means a savory dish, whatever else is in it.
const SAVORY_INGREDIENTS = stapleMatcher([
  'oignon', 'oignons', 'ail', 'echalote', 'echalotes', 'poulet', 'boeuf',
  'veau', 'porc', 'agneau', 'canard', 'dinde', 'lardons', 'jambon',
  'chorizo', 'saucisse', 'saucisses', 'viande', 'poisson', 'saumon', 'thon',
  'cabillaud', 'crevettes', 'moules', 'bouillon', 'poireau', 'poireaux',
  'courgette', 'courgettes', 'aubergine', 'aubergines', 'poivron',
  'poivrons', 'tomate', 'tomates', 'pomme de terre', 'pommes de terre',
  'lentilles', 'pois chiches', 'parmesan', 'gruyere', 'emmental', 'comte',
  'mozzarella', 'feta', 'persil', 'coriandre', 'basilic', 'ciboulette',
  'curry', 'cumin', 'paprika', 'sauce soja', 'moutarde', 'champignons',
  'epinards', 'brocoli', 'chou',
]);
const SWEET_NAMES = stapleMatcher([
  'gateau', 'cake au chocolat', 'cookie', 'cookies', 'brownie', 'brownies',
  'muffin', 'muffins', 'madeleine', 'madeleines', 'financier', 'financiers',
  'tiramisu', 'mousse au chocolat', 'creme brulee', 'clafoutis', 'flan',
  'cheesecake', 'compote', 'panna cotta', 'fondant', 'sable', 'sables',
  'crumble', 'tarte tatin', 'crepes', 'gaufres', 'pancakes',
]);

const hasTag = (recipe: Recipe, tags: string[]) =>
  (recipe.tags || []).some(t => tags.includes(normalizeIngredient(t)));

export function recipeCategory(recipe: Recipe): Category {
  if (hasTag(recipe, MEAL_TAGS)) return 'meal';
  if (hasTag(recipe, SWEET_TAGS)) return 'sweet';
  const names = (recipe.groceries || []).map(g => g.name);
  if (names.some(SAVORY_INGREDIENTS)) return 'meal';
  if (names.some(SWEET_INGREDIENTS) || SWEET_NAMES(recipe.name)) return 'sweet';
  return 'meal';
}

// -- Seasons ----------------------------------------------------------

const SEASONS = ['printemps', 'ete', 'automne', 'hiver'] as const;
type Season = (typeof SEASONS)[number];

export function seasonOf(day: Date): Season {
  const m = day.getMonth(); // 0 = January
  if (m >= 2 && m <= 4) return 'printemps';
  if (m >= 5 && m <= 7) return 'ete';
  if (m >= 8 && m <= 10) return 'automne';
  return 'hiver';
}

function recipeSeasons(recipe: Recipe): Season[] {
  return (recipe.tags || [])
    .map(normalizeIngredient)
    .filter((t): t is Season => (SEASONS as readonly string[]).includes(t));
}

const SEASON_EDGE_DAYS = 21;

/**
 * +1 when a season-specific recipe is in season, -1 when it isn't, 0 for
 * untagged / all-season recipes. Within three weeks of a season change
 * both neighbouring seasons count, so a winter soup is fine in early
 * December and late November alike.
 */
export function seasonFit(recipe: Recipe, today: Date): number {
  const seasons = recipeSeasons(recipe);
  if (!seasons.length || seasons.length === SEASONS.length) return 0;
  const shift = (days: number) =>
    seasonOf(new Date(today.getTime() + days * 86_400_000));
  const current = [shift(-SEASON_EDGE_DAYS), shift(0), shift(SEASON_EDGE_DAYS)];
  return seasons.some(s => current.includes(s)) ? 1 : -1;
}

// -- History ----------------------------------------------------------

export type History = Record<string, string>; // recipe_id -> YYYY-MM-DD

export const RECENT_DAYS = 21;
const FORGOTTEN_DAYS = 60;

export const isoDay = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

/** Days since last use; negative when planned in the future. */
export function daysSince(day: string, today: Date): number {
  const [y, m, d] = day.split('-').map(Number);
  const then = new Date(y, m - 1, d);
  const now = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((now.getTime() - then.getTime()) / 86_400_000);
}

export function isRecent(recipe: Recipe, history: History, today: Date) {
  const last = history[recipe.id];
  return !!last && daysSince(last, today) < RECENT_DAYS;
}

/** Short label for a recipe card, or '' when there's nothing to say. */
export function historyLabel(recipe: Recipe, history: History, today: Date) {
  const last = history[recipe.id];
  if (!last) return '';
  const days = daysSince(last, today);
  if (days < 0) return 'Planned';
  if (days === 0) return 'Today';
  if (days < 14) return `${days} day${days > 1 ? 's' : ''} ago`;
  if (days < 60) return `${Math.round(days / 7)} weeks ago`;
  return `Not made in ${Math.round(days / 30)} months`;
}

export async function fetchRecipeHistory(userId: string): Promise<History> {
  const { data } = await getApi().get(
    `/user/${encodeURIComponent(userId)}/recipe-history`
  );
  return data?.last_used || {};
}

export async function recordRecipeUse(userId: string, recipeId: string) {
  await getApi().post(`/user/${encodeURIComponent(userId)}/recipe-history`, {
    recipe_id: recipeId,
    day: isoDay(new Date()),
  });
}

// -- Ranking ----------------------------------------------------------

// FNV-1a: a stable pseudo-random number in [0, 1) per (seed, recipe), so
// the order holds for a day instead of jumping on every render.
function seededRandom(seed: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0) / 0x100000000;
}

export interface RankOptions {
  history: History;
  today?: Date;
  /** Bump to reshuffle; the day is always part of the seed. */
  shuffle?: number;
}

function recencyScore(recipe: Recipe, history: History, today: Date) {
  const last = history[recipe.id];
  if (!last) return 0;
  const days = daysSince(last, today);
  if (days < RECENT_DAYS) return -10;
  return days > FORGOTTEN_DAYS ? 0.25 : 0;
}

/**
 * Daily shuffle, then: recently used recipes sink to the bottom; season
 * and long-forgotten recipes nudge the rest (each worth a fraction of
 * the random spread, so the order still varies).
 */
export function rankRecipes(recipes: Recipe[], opts: RankOptions): Recipe[] {
  const today = opts.today || new Date();
  const seed = `${isoDay(today)}:${opts.shuffle || 0}`;
  const score = (r: Recipe) =>
    seededRandom(`${seed}:${r.id}`) +
    0.35 * seasonFit(r, today) +
    recencyScore(r, opts.history, today);
  return recipes
    .map(r => ({ r, s: score(r) }))
    .sort((a, b) => b.s - a.s)
    .map(x => x.r);
}

/** Meal ideas for "Inspire me" / the planner: ranked, meals, not recent. */
export function mealIdeas(
  recipes: Recipe[],
  opts: RankOptions & { exclude?: Set<string> }
): Recipe[] {
  const today = opts.today || new Date();
  return rankRecipes(recipes, opts).filter(
    r =>
      recipeCategory(r) === 'meal' &&
      !isRecent(r, opts.history, today) &&
      !opts.exclude?.has(r.id)
  );
}
