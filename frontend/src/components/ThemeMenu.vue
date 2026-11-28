<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watchEffect } from 'vue'
import { useTheme } from 'vuetify'

defineOptions({ inheritAttrs: false })

const theme = useTheme()
const storageKey = 'fulcrum-theme'
const choices = [
  { value: 'system', title: 'System', icon: 'mdi-monitor' },
  { value: 'light', title: 'Light', icon: 'mdi-weather-sunny' },
  { value: 'dark', title: 'Dark', icon: 'mdi-weather-night' },
]
const system = window.matchMedia('(prefers-color-scheme: dark)')
const followsDark = ref(system.matches)
const saved = localStorage.getItem(storageKey)
const preference = ref(
  choices.some(choice => choice.value === saved) ? saved : 'system',
)
const icon = computed(
  () => choices.find(choice => choice.value === preference.value).icon,
)

function updateSystem(event) {
  followsDark.value = event.matches
}

function choose(value) {
  preference.value = value
  localStorage.setItem(storageKey, value)
}

watchEffect(() => {
  theme.global.name.value =
    preference.value === 'system'
      ? followsDark.value
        ? 'dark'
        : 'light'
      : preference.value
})

onMounted(() => system.addEventListener('change', updateSystem))
onBeforeUnmount(() => system.removeEventListener('change', updateSystem))
</script>

<template>
  <v-menu location="bottom end">
    <template #activator="{ props }">
      <v-btn
        v-bind="{ ...$attrs, ...props }"
        :icon="icon"
        aria-label="Color theme"
        variant="text"
      />
    </template>
    <v-list density="compact" aria-label="Color theme">
      <v-list-item
        v-for="choice in choices"
        :key="choice.value"
        :active="preference === choice.value"
        :prepend-icon="choice.icon"
        :title="choice.title"
        :aria-current="preference === choice.value ? 'true' : undefined"
        @click="choose(choice.value)"
      />
    </v-list>
  </v-menu>
</template>
