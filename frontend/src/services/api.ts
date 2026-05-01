/**
 * Authenticated axios client.
 *
 * Every request goes through `getAccessTokenSilently()` so the backend
 * sees a fresh Auth0 access token in the Authorization header. The
 * audience must match what the backend expects (AUTH0_AUDIENCE env var
 * on the server / `audience` arg in createAuth0 on the client).
 */

import axios, { AxiosInstance } from 'axios';
import { Auth0VueClient } from '@auth0/auth0-vue';

let _client: AxiosInstance | null = null;

export function createApi(auth0: Auth0VueClient): AxiosInstance {
  if (_client) return _client;

  const client = axios.create({
    baseURL: import.meta.env.VITE_BACKEND_BASE_URL
  });

  client.interceptors.request.use(async config => {
    try {
      const token = await auth0.getAccessTokenSilently();
      config.headers = config.headers ?? {};
      (config.headers as any).Authorization = `Bearer ${token}`;
    } catch (err) {
      // No valid session — let the request proceed unauthenticated; the
      // backend will return 401 and the UI can redirect to login.
      console.warn('No access token available:', err);
    }
    return config;
  });

  _client = client;
  return client;
}

export function getApi(): AxiosInstance {
  if (!_client) {
    throw new Error(
      'API client not initialized. Call createApi(auth0) once in main.ts.'
    );
  }
  return _client;
}
