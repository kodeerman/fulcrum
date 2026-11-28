<script setup>
import meowra from '@/assets/images/dr-meowra-swimsuit.png'
</script>

<template>
  <v-container class="meowra-page py-8">
    <v-card class="meowra-card" variant="outlined">
      <img
        :src="meowra"
        width="1254"
        height="1254"
        alt="Dr. Meowra in a swimsuit on a shaded deck by the sea"
      />
      <div class="meowra-copy">
        <h1>Dr. Meowra's day off</h1>
        <p>“Oh, you caught me on vacation!”</p>
        <v-btn
          :to="{ name: 'StatsEngine' }"
          prepend-icon="mdi-arrow-left"
          variant="outlined"
        >
          Back to Stats Engine
        </v-btn>
      </div>
    </v-card>
  </v-container>
</template>

<style scoped>
.meowra-page {
  max-width: 62rem;
}
.meowra-card {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
  background: #f3f8fc;
  color: #162b40;
  border-radius: 16px;
}
img {
  display: block;
  width: 100%;
  height: auto;
}
.meowra-copy {
  align-self: center;
  padding: clamp(1.25rem, 4vw, 3rem);
}
h1 {
  font-size: clamp(1.65rem, 4vw, 2.75rem);
  line-height: 1.12;
}
p {
  margin-block: 1rem 1.5rem;
}
@media (max-width: 660px) {
  .meowra-card {
    grid-template-columns: 1fr;
  }
}
</style>
