<template>
  <v-app-bar color="#102944" class="fulcrum-toolbar" elevation="1" :order="-1">
    <div class="toolbar-brand">
      <router-link to="/" class="fulcrum-home" aria-label="Fulcrum home">
        <span class="home-icon"
          ><v-icon icon="mdi-home-outline" size="18"
        /></span>
        <span>Fulcrum</span>
      </router-link>
    </div>

    <nav aria-label="Analysis engines" class="engine-links">
      <v-btn
        :to="{ name: 'StatsEngine', query: studyQuery }"
        :active="activeEngine === 'stats'"
        :aria-current="activeEngine === 'stats' ? 'page' : undefined"
        aria-label="Stats Engine"
        class="engine-button"
        variant="flat"
      >
        <v-icon icon="mdi-calculator-variant-outline" size="18" />
        <span class="engine-label">Stats Engine</span>
        <span class="engine-label-short" aria-hidden="true">Stats</span>
      </v-btn>
      <v-btn
        :to="{
          name: 'StatsEngine',
          query: { ...studyQuery, engine: 'charts' },
        }"
        :active="activeEngine === 'charts'"
        :aria-current="activeEngine === 'charts' ? 'page' : undefined"
        aria-label="Chart Engine"
        class="engine-button"
        variant="flat"
      >
        <v-icon icon="mdi-chart-bar" size="18" />
        <span class="engine-label">Chart Engine</span>
        <span class="engine-label-short" aria-hidden="true">Charts</span>
      </v-btn>
    </nav>

    <ThemeMenu class="toolbar-action" />

    <v-btn
      icon="mdi-help-circle-outline"
      aria-label="About Fulcrum"
      class="toolbar-action"
      variant="text"
      @click="goToAbout"
    />

    <!-- Only show if user is authenticated -->
    <template v-if="auth.isAuthenticated">
      <v-menu
        v-model="menuOpen"
        offset-y
        transition="slide-y-transition"
        @update:modelValue="onMenuToggle"
      >
        <template #activator="{ props }">
          <v-btn
            v-bind="props"
            icon="mdi-account-circle-outline"
            aria-label="Account menu"
            class="toolbar-action"
            variant="text"
          />
        </template>

        <v-slide-y-transition mode="in-out">
          <v-card style="min-width: 320px; padding: 8px">
            <v-list-item class="px-4 py-3">
              <v-row align="center" no-gutters style="width: 100%">
                <v-col cols="auto">
                  <v-avatar size="40">
                    <img
                      src="/images/unr n.jpg"
                      alt="User"
                      style="
                        width: 100%;
                        height: 100%;
                        object-fit: cover;
                        border-radius: 50%;
                      "
                    />
                  </v-avatar>
                </v-col>
                <v-col class="pl-3">
                  <span class="text-subtitle-1 font-weight-medium">
                    {{ displayName }}
                  </span>
                </v-col>
              </v-row>
            </v-list-item>

            <v-divider class="my-2" />

            <v-list>
              <v-list-item @click="goToProfile" class="px-4">
                <v-row align="center" no-gutters style="width: 100%">
                  <v-col cols="auto">
                    <v-icon>mdi-account</v-icon>
                  </v-col>
                  <v-col class="pl-3">
                    <span class="text-subtitle-2">Edit Profile</span>
                  </v-col>
                  <v-col cols="auto">
                    <v-icon>mdi-chevron-right</v-icon>
                  </v-col>
                </v-row>
              </v-list-item>

              <v-list-item @click="logOut" class="px-4">
                <v-row align="center" no-gutters style="width: 100%">
                  <v-col cols="auto">
                    <v-icon>mdi-logout</v-icon>
                  </v-col>
                  <v-col class="pl-3">
                    <span class="text-subtitle-2">Logout</span>
                  </v-col>
                  <v-col cols="auto">
                    <v-icon>mdi-chevron-right</v-icon>
                  </v-col>
                </v-row>
              </v-list-item>
            </v-list>
          </v-card>
        </v-slide-y-transition>
      </v-menu>
    </template>
  </v-app-bar>
</template>

<script>
import api from '@/axiosInstance'
import ThemeMenu from './ThemeMenu.vue'
import { auth } from '@/stores/auth'
import { useStudyStore } from '@/stores/study'

export default {
  name: 'GlobalTopBar',
  components: { ThemeMenu },
  data() {
    return {
      displayName: 'Loading...',
      auth,
      menuOpen: false,
    }
  },
  computed: {
    studyQuery() {
      return this.$route.name === 'StatsEngine' && this.$route.query.study
        ? { study: this.$route.query.study }
        : {}
    },
    activeEngine() {
      if (this.$route.name !== 'StatsEngine') return null
      return this.$route.query.engine === 'charts' ? 'charts' : 'stats'
    },
  },
  watch: {
    'auth.user': {
      handler(newUser) {
        if (newUser) {
          const fullName =
            `${newUser.first_name || ''} ${newUser.last_name || ''}`.trim()
          this.displayName = fullName || newUser.email || 'Unknown User'
        }
      },
      immediate: true,
    },
  },
  methods: {
    goToProfile() {
      this.$router.push({ name: 'UserProfile' })
    },
    goToAbout() {
      this.$router.push({ name: 'AboutPage' })
    },
    async logOut() {
      try {
        const response = await api.post('/accounts/logout')
        if (response.status === 200) {
          auth.isAuthenticated = false
          auth.user = null
          const studyStore = useStudyStore()
          studyStore.reset()
          this.$router.push({ name: 'UserLogin' })
        }
      } catch (err) {
        console.error('Error logging out:', err)
      }
    },
    onMenuToggle(isOpen) {
      if (isOpen) {
        this.fetchUserInfo()
      }
    },
    async fetchUserInfo() {
      try {
        const res = await api.get('/accounts/get_user_profile_info')
        if (res.data) {
          auth.user = res.data
        }
      } catch (err) {
        console.error('Failed to refresh user info:', err)
      }
    },
  },
}
</script>

<style scoped>
.fulcrum-toolbar {
  background-image: linear-gradient(105deg, #102944, #16436b 62%, #153552);
}

.toolbar-brand {
  flex: 1 0 auto;
  margin-inline-start: clamp(0.625rem, 2.5vw, 2rem);
}

.fulcrum-home {
  display: inline-flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.25rem;
  border-radius: 0.5rem;
  color: inherit;
  font-size: 1.15rem;
  font-weight: 700;
  text-decoration: none;
}

.home-icon {
  display: grid;
  place-items: center;
  width: 2rem;
  height: 2rem;
  border: 1px solid #ffffff38;
  border-radius: 0.5rem;
  background: #ffffff15;
}

.fulcrum-home:hover .home-icon {
  background: #ffffff2a;
}

.engine-links {
  display: flex;
  flex-shrink: 0;
  gap: 0.375rem;
  padding: 0.25rem;
  border: 1px solid #ffffff26;
  border-radius: 0.75rem;
  background: #081c3360;
  margin-inline-end: 0.625rem;
}

.engine-button {
  border-radius: 0.5rem;
  background: #ffffff1c;
  color: #fff;
  font-weight: 600;
  letter-spacing: normal;
  text-transform: none;
}

.engine-button :deep(.v-btn__content) {
  gap: 0.45rem;
}

.engine-button[aria-current='page'] {
  background: #d8eeff;
  color: #102e4c;
}

.engine-button[aria-current='page'] :deep(.v-btn__overlay) {
  opacity: 0;
}

.fulcrum-toolbar :deep(.toolbar-action) {
  width: 2.5rem;
  height: 2.5rem;
  margin-inline-end: 0.375rem;
}

.fulcrum-home:focus-visible,
.engine-button:focus-visible,
.fulcrum-toolbar :deep(.toolbar-action:focus-visible) {
  outline: 2px solid #fff;
  outline-offset: 2px;
}

.engine-label-short {
  display: none;
}

@media (max-width: 480px) {
  .fulcrum-home {
    font-size: 1rem;
  }

  .home-icon,
  .engine-button .v-icon {
    display: none;
  }

  .engine-links {
    gap: 0.25rem;
    margin-inline-end: 0.25rem;
  }

  .engine-button {
    min-width: 0;
    padding-inline: 0.5rem;
    font-size: 0.75rem;
  }

  .fulcrum-toolbar :deep(.toolbar-action) {
    width: 2.25rem;
    height: 2.25rem;
    margin-inline-end: 0.125rem;
  }
}
@media (max-width: 380px) {
  .engine-label {
    display: none;
  }

  .engine-label-short {
    display: inline;
  }
}
</style>
