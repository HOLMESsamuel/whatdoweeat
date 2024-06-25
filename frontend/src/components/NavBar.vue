<template>
  <div class="nav-container mb-3">
    <nav class="navbar navbar-expand-md" :class="isDark ? 'dark' : 'navbar-light bg-light'">
      <div class="container">
        <div class="navbar-brand logo"></div>
        
        <!-- Adjusted for left alignment on mobile -->
        <div class="d-flex justify-content-between w-100 d-md-none">
          <button
            class="navbar-toggler"
            type="button"
            data-toggle="collapse"
            data-target="#navbarNav"
            aria-controls="navbarNav"
            aria-expanded="false"
            aria-label="Toggle navigation"
          >
            <span class="navbar-toggler-icon"></span>
          </button>

          <!-- Dark mode and profile/login button outside of collapse div for mobile -->
          <div class="d-flex align-items-center">
            <button class="darkModeButton" @click.prevent="toggleDark()">
              <img class="moon" v-if="isDark" src="../assets/moon.svg" alt="dark"/>
              <img class="sun" v-if="!isDark" src="../assets/sun.svg" alt="light"/>
            </button>
            <li v-if="!isAuthenticated && !isLoading" class="nav-item list-unstyled">
              <button id="qsLoginBtn" class="btn btn-primary btn-margin" @click.prevent="login">Login</button>
            </li>
            <li class="nav-item dropdown list-unstyled" v-if="isAuthenticated">
              <a class="nav-link dropdown-toggle" href="#" id="profileDropDown" data-toggle="dropdown">
                <img :src="user?.picture" alt="User's profile picture" class="nav-user-profile rounded-circle" width="50"/>
              </a>
              <div class="dropdown-menu dropdown-menu-right">
                <div class="dropdown-header">{{ user?.name }}</div>
                <router-link to="/profile" class="dropdown-item dropdown-profile">
                  <font-awesome-icon class="mr-3" icon="user" />Profile
                </router-link>
                <a id="qsLogoutBtn" href="#" class="dropdown-item" @click.prevent="logout">
                  <font-awesome-icon class="mr-3" icon="power-off" />Log out
                </a>
              </div>
            </li>
          </div>
        </div>

        <div class="collapse navbar-collapse" id="navbarNav">
          <ul class="navbar-nav mr-auto">
            <li class="nav-item">
              <router-link to="/" class="nav-link">Home</router-link>
            </li>
            <li class="nav-item" v-if="isAuthenticated">
              <router-link to="/lists" class="nav-link">Grocery lists</router-link>
            </li>
            <li class="nav-item" v-if="isAuthenticated">
              <router-link to="/receipes" class="nav-link">Receipes</router-link>
            </li>
            <li class="nav-item" v-if="isAuthenticated">
              <router-link to="/planner" class="nav-link">Meal planner</router-link>
            </li>
          </ul>
          <ul class="navbar-nav d-none d-md-flex">
              <button
                class="darkModeButton"
                @click.prevent="toggleDark()"
              >
              <img v-if="isDark" class="moon" src = "../assets/moon.svg" alt="dark"/>
              <img v-if="!isDark" class="sun" src = "../assets/sun.svg" alt="light"/>
            </button>
          </ul>
          <ul class="navbar-nav d-none d-md-flex">
            <li v-if="!isAuthenticated && !isLoading" class="nav-item">
              <button
                id="qsLoginBtn"
                class="btn btn-primary btn-margin"
                @click.prevent="login"
              >Login</button>
            </li>

            <li class="nav-item dropdown" v-if="isAuthenticated">
              <a
                class="nav-link dropdown-toggle"
                href="#"
                id="profileDropDown"
                data-toggle="dropdown"
              >
                <img
                  v-if="user?.picture"
                  :src="user?.picture"
                  alt="User's profile picture"
                  class="nav-user-profile rounded-circle"
                  width="50"
                />
              </a>
              <div class="dropdown-menu dropdown-menu-right">
                <div class="dropdown-header">{{ user?.name }}</div>
                <router-link to="/profile" class="dropdown-item dropdown-profile">
                  <font-awesome-icon class="mr-3" icon="user" />Profile
                </router-link>
                <a id="qsLogoutBtn" href="#" class="dropdown-item" @click.prevent="logout">
                  <font-awesome-icon class="mr-3" icon="power-off" />Log out
                </a>
              </div>
            </li>
          </ul>
        </div>
      </div>
    </nav>
  </div>
</template>

<script lang="ts">
import { useAuth0 } from '@auth0/auth0-vue';
import { useDark, useToggle } from '@vueuse/core'

export default {
  name: "NavBar",
  setup() {
    const auth0 = useAuth0();
    const isDark = useDark()
    const toggleDark = useToggle(isDark)
    
    return {
      isAuthenticated: auth0.isAuthenticated,
      isLoading: auth0.isLoading,
      user: auth0.user,
      isDark,
      toggleDark,
      login() {
        auth0.loginWithRedirect();
      },
      logout() {
        auth0.logout({
          logoutParams: {
            returnTo: window.location.origin
          }
        });
      }
    }
  }
};
</script>

<style>
.navbar {
  min-height: 80px;
}

#mobileAuthNavBar {
  min-height: 125px;
  justify-content: space-between;
}

.darkModeButton {
  background: none;
  border: none;
  margin-left: 10px;
  margin-right: 10px;
}

.darkModeButton:focus {
  outline: none;
}

.moon {
  filter: invert(77%) sepia(83%) saturate(1%) hue-rotate(334deg) brightness(98%) contrast(96%);
}

.nav-item.dark {
  color: white;
}
</style>
