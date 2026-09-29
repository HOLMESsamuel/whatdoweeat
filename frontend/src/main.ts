import App from "./App.vue";
import { createApp } from "vue";
import { createRouter } from "./router";
import { createAuth0 } from "@auth0/auth0-vue";
import { library } from "@fortawesome/fontawesome-svg-core";
import { faLink, faUser, faPowerOff } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";
import authConfig from "../auth_config.json";
import hljs from 'highlight.js/lib/core';
import json from 'highlight.js/lib/languages/json';
import hljsVuePlugin from "@highlightjs/vue-plugin";
import "highlight.js/styles/github.css";
import './style.css';
import { createApi } from './services/api';

hljs.registerLanguage('json', json);

const app = createApp(App);

library.add(faLink, faUser, faPowerOff);

// The audience must match the API's "Identifier" set in the Auth0
// dashboard, and AUTH0_AUDIENCE on the backend. Without it Auth0 hands
// out an opaque ID token instead of a JWT access token.
const audience = (import.meta as any).env.VITE_AUTH0_AUDIENCE as string | undefined;
if (!audience) {
  console.warn(
    'VITE_AUTH0_AUDIENCE is not set — backend calls will fail JWT '
    + 'verification. Add it to .env (frontend) and AUTH0_AUDIENCE on the backend.'
  );
}

const auth0 = createAuth0({
  domain: authConfig.domain,
  clientId: authConfig.clientId,
  authorizationParams: {
    redirect_uri: window.location.origin,
    audience,
    scope: 'openid profile email offline_access',
  },
  cacheLocation: 'localstorage',
  useRefreshTokens: true,
}, {
  // `code`/`state` on a backend URL belong to the Dropbox OAuth flow, not
  // Auth0; handling them here fails with "Invalid state".
  skipRedirectCallback: window.location.pathname.startsWith('/api/'),
});

// Initialise the singleton axios client so any component can `import
// { getApi }` without needing to handle auth itself.
createApi(auth0);

app
  .use(hljsVuePlugin)
  .use(createRouter(app))
  .use(auth0)
  .component("font-awesome-icon", FontAwesomeIcon)
  .mount("#app");
