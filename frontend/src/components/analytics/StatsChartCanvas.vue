<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { extent as valueExtent } from 'd3'
import { useTheme } from 'vuetify'
import { chartAppearance, downloadChart } from '@/utility/chartAppearance'
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
const theme = useTheme()
let chart

const palette = [
  '#2379bd',
  '#7857bd',
  '#148575',
  '#aa4e22',
  '#a33265',
  '#476683',
]

function createChart(target, dark, responsive = true) {
  const appearance = chartAppearance(dark)
  const lineColor = dark ? '#ffaa82' : '#ae4a24'

  const {
    type,
    title,
    points,
    numericX,
    errorBars,
    xLabel,
    yLabel,
    settings,
    regression,
  } = props.model
  const box = type === 'box'
  const histogram = type === 'histogram'
  const fitX = regression ? valueExtent(points, point => point.x) : []
  const groupLegend =
    !numericX &&
    !histogram &&
    points.length > 1 &&
    points.length <= palette.length
  const colorsForTheme = dark
    ? ['#71b7ee', '#bda3fa', '#56c6b3', '#ffab80', '#f68ab5', '#a9c8df']
    : palette
  const colors = groupLegend
    ? colorsForTheme.slice(0, points.length)
    : colorsForTheme[0]
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

  return new Chart(target, {
    type: box || histogram ? 'bar' : type,
    data: {
      labels: numericX ? undefined : points.map(point => point.x),
      datasets: [
        {
          label: box ? 'Interquartile range' : yLabel,
          data,
          backgroundColor: colors,
          borderColor: colorsForTheme[0],
          maxBarThickness: histogram ? undefined : 68,
          categoryPercentage: histogram ? 1 : undefined,
          barPercentage: histogram ? 1 : undefined,
          borderWidth: histogram ? 1 : undefined,
          pointRadius: points.length > 1000 ? (type === 'line' ? 0 : 2) : 4,
        },
        ...(regression
          ? [
              {
                type: 'line',
                label: 'Linear regression',
                data: fitX.map(x => ({
                  x,
                  y: regression.intercept + regression.slope * x,
                })),
                borderColor: lineColor,
                borderWidth: 2,
                pointRadius: 0,
              },
            ]
          : []),
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
          type: numericX ? 'linear' : 'category',
          title: {
            display: settings.axes,
            text: xLabel,
            color: appearance.text,
          },
        },
        y: {
          ...appearance.axis,
          beginAtZero: type === 'bar' || histogram,
          suggestedMin: Number.isFinite(min) ? min : undefined,
          suggestedMax: Number.isFinite(max) ? max : undefined,
          title: {
            display: settings.axes,
            text: yLabel,
            color: appearance.text,
          },
        },
      },
      plugins: {
        title: { display: true, text: title, color: appearance.text },
        legend: {
          display: settings.legend,
          onClick() {},
          labels: groupLegend
            ? {
                color: appearance.text,
                generateLabels: () =>
                  points.map((point, index) => ({
                    text: `${point.x} (n=${point.count})`,
                    fillStyle: colors[index],
                    strokeStyle: colors[index],
                    fontColor: appearance.text,
                  })),
              }
            : { color: appearance.text },
        },
        tooltip: {
          callbacks: {
            label: ({ datasetIndex, dataIndex, formattedValue }) => {
              if (datasetIndex === 1)
                return `Linear regression: ${formattedValue}`
              if (histogram) return `Frequency: ${formattedValue}`
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
      appearance.backdrop,
      {
        id: 'statsChartDrawing',
        afterDatasetsDraw(instance) {
          if (!box && !errorBars) return
          const { ctx, scales } = instance
          ctx.save()
          ctx.strokeStyle = appearance.text
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

function render() {
  chart?.destroy()
  chart = createChart(canvas.value, theme.global.current.value.dark)
}

onMounted(render)
watch([() => props.model, () => theme.global.current.value.dark], render)
onBeforeUnmount(() => chart?.destroy())

function download() {
  downloadChart(
    chart,
    createChart,
    theme.global.current.value.dark,
    `fulcrum-${props.model.type}-chart.png`,
  )
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
