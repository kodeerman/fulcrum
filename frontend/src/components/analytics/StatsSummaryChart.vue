<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
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
let chart

onMounted(() => {
  const { labels, summaries, outcome, grouping } = props.result
  chart = new Chart(canvas.value, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: `Mean ${outcome}`,
          data: summaries.map(summary => summary.mean),
          backgroundColor: '#23628c',
        },
      ],
    },
    options: {
      animation: false,
      maintainAspectRatio: false,
      scales: {
        x: { title: { display: true, text: grouping } },
        y: {
          beginAtZero: true,
          title: { display: true, text: `Mean ${outcome}` },
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
    plugins: [
      {
        id: 'whiteBackground',
        beforeDraw({ ctx, width, height }) {
          ctx.save()
          ctx.fillStyle = '#fff'
          ctx.fillRect(0, 0, width, height)
          ctx.restore()
        },
      },
    ],
  })
})

onBeforeUnmount(() => chart?.destroy())

function downloadChart() {
  const link = document.createElement('a')
  link.href = chart.toBase64Image()
  link.download = 'fulcrum-group-means.png'
  link.click()
}
</script>

<template>
  <v-card variant="outlined" class="pa-5 mt-5">
    <div class="d-flex flex-wrap align-center ga-3 mb-3">
      <h3 class="text-h6 mr-auto">Group means</h3>
      <v-btn variant="outlined" @click="downloadChart"
        >Download chart PNG</v-btn
      >
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
