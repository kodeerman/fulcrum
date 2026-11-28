<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useTheme } from 'vuetify'
import { chartAppearance, downloadChart } from '@/utility/chartAppearance'
import {
  BarController,
  BarElement,
  CategoryScale,
  Chart,
  LinearScale,
  Tooltip,
} from 'chart.js'

Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip)

const props = defineProps({
  result: { type: Object, required: true },
})

const canvas = ref(null)
const theme = useTheme()
let chart

function createChart(target, dark, responsive = true) {
  const appearance = chartAppearance(dark)
  const { labels, summaries, outcome, grouping } = props.result
  return new Chart(target, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: `Mean ${outcome}`,
          data: summaries.map(summary => summary.mean),
          backgroundColor: dark ? '#71b7ee' : '#23628c',
        },
      ],
    },
    options: {
      responsive,
      devicePixelRatio: responsive ? undefined : 1,
      color: appearance.text,
      animation: false,
      maintainAspectRatio: false,
      scales: {
        x: {
          ...appearance.axis,
          title: { display: true, text: grouping, color: appearance.text },
        },
        y: {
          ...appearance.axis,
          beginAtZero: true,
          title: {
            display: true,
            text: `Mean ${outcome}`,
            color: appearance.text,
          },
        },
      },
      plugins: {
        tooltip: {
          callbacks: {
            afterLabel: ({ dataIndex }) => `Count: ${summaries[dataIndex].n}`,
          },
        },
      },
    },
    plugins: [appearance.backdrop],
  })
}

function render() {
  chart?.destroy()
  chart = createChart(canvas.value, theme.global.current.value.dark)
}

onMounted(render)
watch(() => theme.global.current.value.dark, render)
onBeforeUnmount(() => chart?.destroy())

function download() {
  downloadChart(
    chart,
    createChart,
    theme.global.current.value.dark,
    'fulcrum-group-means.png',
  )
}
</script>

<template>
  <v-card variant="outlined" class="pa-5 mt-5">
    <div class="d-flex flex-wrap align-center ga-3 mb-3">
      <h3 class="text-h6 mr-auto">Group means</h3>
      <v-btn variant="outlined" @click="download">Download chart PNG</v-btn>
    </div>
    <div class="chart-frame">
      <canvas
        ref="canvas"
        role="img"
        :aria-label="`Mean ${result.outcome} by ${result.grouping}. Values are listed in the statistics table.`"
      />
    </div>
  </v-card>
</template>

<style scoped>
.chart-frame {
  height: 20rem;
}
</style>
