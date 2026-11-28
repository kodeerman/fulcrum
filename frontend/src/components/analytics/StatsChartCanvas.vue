<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import {
  BarController,
  BarElement,
  CategoryScale,
  Chart,
  Legend,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  ScatterController,
  Title,
  Tooltip,
} from 'chart.js'

Chart.register(
  BarController,
  BarElement,
  CategoryScale,
  Legend,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  ScatterController,
  Title,
  Tooltip,
)

const props = defineProps({ model: { type: Object, required: true } })
const canvas = ref(null)
let chart

const palette = [
  '#2379bd',
  '#7857bd',
  '#148575',
  '#aa4e22',
  '#a33265',
  '#476683',
]

function render() {
  chart?.destroy()

  const { type, title, points, numericX, errorBars, xLabel, yLabel, settings } =
    props.model
  const box = type === 'box'
  const groupLegend =
    !numericX && points.length > 1 && points.length <= palette.length
  const colors = groupLegend ? palette.slice(0, points.length) : palette[0]
  const data = numericX
    ? points.map(({ x, y }) => ({ x, y }))
    : points.map(point => (box ? [point.q1, point.q3] : point.y))

  const extent = box
    ? points.map(point => [point.min, point.max])
    : errorBars
      ? points.map(point => [
          point.y - (point.std ?? 0),
          point.y + (point.std ?? 0),
        ])
      : []
  const min = Math.min(...extent.map(([low]) => low))
  const max = Math.max(...extent.map(([, high]) => high))

  chart = new Chart(canvas.value, {
    type: box ? 'bar' : type,
    data: {
      labels: numericX ? undefined : points.map(point => point.x),
      datasets: [
        {
          label: box ? 'Interquartile range' : yLabel,
          data,
          backgroundColor: colors,
          borderColor: palette[0],
          maxBarThickness: 68,
          pointRadius: points.length > 1000 ? (type === 'line' ? 0 : 2) : 4,
        },
      ],
    },
    options: {
      animation: false,
      maintainAspectRatio: false,
      scales: {
        x: {
          type: numericX ? 'linear' : 'category',
          title: { display: settings.axes, text: xLabel },
        },
        y: {
          beginAtZero: type === 'bar',
          suggestedMin: Number.isFinite(min) ? min : undefined,
          suggestedMax: Number.isFinite(max) ? max : undefined,
          title: { display: settings.axes, text: yLabel },
        },
      },
      plugins: {
        title: { display: true, text: title },
        legend: {
          display: settings.legend,
          onClick() {},
          labels: groupLegend
            ? {
                generateLabels: () =>
                  points.map((point, index) => ({
                    text: `${point.x} (n=${point.count})`,
                    fillStyle: colors[index],
                    strokeStyle: colors[index],
                  })),
              }
            : undefined,
        },
        tooltip: {
          callbacks: {
            label: ({ dataIndex, formattedValue }) => {
              const point = points[dataIndex]
              return box
                ? [
                    `Median: ${point.median}`,
                    `Min–max: ${point.min}–${point.max}`,
                    `Rows: ${point.count}`,
                  ]
                : [
                    `${yLabel}: ${formattedValue}`,
                    `Rows: ${point.count}`,
                    ...(errorBars
                      ? [`Sample SD: ${point.std ?? 'Unavailable'}`]
                      : []),
                  ]
            },
          },
        },
      },
    },
    plugins: [
      {
        id: 'statsChartDrawing',
        beforeDraw({ ctx, width, height }) {
          ctx.save()
          ctx.fillStyle = '#fff'
          ctx.fillRect(0, 0, width, height)
          ctx.restore()
        },
        afterDatasetsDraw(instance) {
          if (!box && !errorBars) return
          const { ctx, scales } = instance
          ctx.save()
          ctx.strokeStyle = '#162536'
          ctx.lineWidth = 2
          const bars = instance.getDatasetMeta(0).data
          points.forEach((point, index) => {
            if (errorBars && point.std === null) return
            const { x, width } = bars[index]
            const pixel = value => scales.y.getPixelForValue(value)
            const cap = Math.min(width / 4, 12)
            const low = box ? point.min : point.y - point.std
            const high = box ? point.max : point.y + point.std
            if (!Number.isFinite(low) || !Number.isFinite(high)) return
            ctx.beginPath()
            const segments = box
              ? [
                  [low, point.q1],
                  [point.q3, high],
                ]
              : [[low, high]]
            for (const [start, end] of segments) {
              ctx.moveTo(x, pixel(start))
              ctx.lineTo(x, pixel(end))
            }
            for (const value of [low, high]) {
              ctx.moveTo(x - cap, pixel(value))
              ctx.lineTo(x + cap, pixel(value))
            }
            if (box) {
              ctx.moveTo(x - width / 2, pixel(point.median))
              ctx.lineTo(x + width / 2, pixel(point.median))
            }
            ctx.stroke()
          })
          ctx.restore()
        },
      },
    ],
  })
}

onMounted(render)
watch(() => props.model, render)
onBeforeUnmount(() => chart?.destroy())

function download() {
  const link = document.createElement('a')
  link.href = chart.toBase64Image()
  link.download = `fulcrum-${props.model.type}-chart.png`
  link.click()
}

defineExpose({ download })
</script>

<template>
  <div class="plot">
    <canvas
      ref="canvas"
      role="img"
      :aria-label="model.title + '. Values are listed in the chart data table.'"
    />
  </div>
</template>

<style scoped>
.plot {
  height: clamp(19rem, 50vw, 29rem);
  min-width: 0;
}
</style>
