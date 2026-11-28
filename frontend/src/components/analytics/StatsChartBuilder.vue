<script setup>
import { computed, nextTick, ref, shallowRef, watch } from 'vue'
import StatsChartCanvas from './StatsChartCanvas.vue'
import { aggregations, buildChart, chartTypes } from '@/utility/statsChart'

const props = defineProps({
  dataset: { type: Object, required: true },
  outcome: { type: Number, default: null },
  group: { type: Number, default: null },
})
const emit = defineEmits(['download-csv'])

const plot = ref(null)
const configuration = ref(null)
const chart = shallowRef(null)
const previous = shallowRef(null)
const error = ref('')
const settings = ref({})
const number = new Intl.NumberFormat(undefined, { maximumSignificantDigits: 8 })

const numeric = computed(() =>
  props.dataset.fields.filter(field => field.numeric),
)
const numericX = computed(() =>
  ['line', 'scatter'].includes(settings.value.type),
)
const showAggregation = computed(() =>
  ['bar', 'line'].includes(settings.value.type),
)
const xFields = computed(() =>
  (numericX.value ? numeric.value : props.dataset.fields).filter(
    field => field.index !== settings.value.y,
  ),
)
const previewTitle = computed(() => {
  const { title, y, x, aggregation } = settings.value
  const outcome = props.dataset.fields[y]?.title
  if (!outcome) return 'Choose a Y field'
  const yLabel = showAggregation.value
    ? `${aggregations[aggregation]} of ${outcome}`
    : outcome
  return (
    title.trim() ||
    (x === null || !props.dataset.fields[x]
      ? yLabel
      : `${yLabel} by ${props.dataset.fields[x].title}`)
  )
})
const columns = computed(() => {
  if (!chart.value) return []
  return [
    { key: 'x', title: chart.value.xLabel },
    ...(chart.value.type === 'box'
      ? [
          { key: 'min', title: 'Minimum' },
          { key: 'q1', title: 'First quartile' },
          { key: 'median', title: 'Median' },
          { key: 'q3', title: 'Third quartile' },
          { key: 'max', title: 'Maximum' },
        ]
      : [{ key: 'y', title: chart.value.yLabel }]),
    ...(chart.value.errorBars ? [{ key: 'std', title: 'Sample SD' }] : []),
    { key: 'count', title: 'Rows' },
  ]
})
const changed = computed(
  () =>
    chart.value &&
    Object.keys(settings.value).some(
      key => settings.value[key] !== chart.value.settings[key],
    ),
)

function defaults() {
  const y = numeric.value.some(field => field.index === props.outcome)
    ? props.outcome
    : (numeric.value[0]?.index ?? null)
  const x =
    props.group !== y && props.group !== null
      ? props.group
      : (props.dataset.fields.find(
          field => field.index !== y && field.type === 'Text',
        )?.index ?? null)
  return {
    type: 'bar',
    x,
    y,
    aggregation: 'mean',
    title: '',
    axes: true,
    legend: true,
    errorBars: false,
  }
}

function reset() {
  settings.value = defaults()
  chart.value = null
  previous.value = null
  error.value = ''
}

watch(() => props.dataset, reset, { immediate: true })
watch(xFields, fields => {
  if (!fields.some(field => field.index === settings.value.x)) {
    settings.value.x = numericX.value ? (fields[0]?.index ?? null) : null
  }
})

function apply(next = settings.value) {
  error.value = ''
  try {
    const model = buildChart(props.dataset, next)
    previous.value = chart.value
    chart.value = model
    settings.value = { ...model.settings }
  } catch (err) {
    error.value = err.message
  }
}

function undo() {
  if (!previous.value) return
  chart.value = previous.value
  settings.value = { ...chart.value.settings }
  previous.value = null
  error.value = ''
}

async function focusConfiguration() {
  await nextTick()
  configuration.value?.focus()
}

function useSelection(outcome, group) {
  settings.value = { ...defaults(), y: outcome, x: group }
  apply()
}

function exportPoints() {
  emit('download-csv', 'fulcrum-chart-data.csv', [
    ['Dataset', ...columns.value.map(column => column.title)],
    ...chart.value.points.map(point => [
      props.dataset.name,
      ...columns.value.map(column => point[column.key]),
    ]),
  ])
}

const display = value =>
  value === null
    ? 'Unavailable'
    : typeof value === 'number'
      ? number.format(value)
      : value
defineExpose({ useSelection, focusConfiguration })
</script>

<template>
  <section aria-labelledby="chart-config" class="mt-5 chart-workspace">
    <v-card variant="outlined" class="pa-5">
      <h2
        id="chart-config"
        ref="configuration"
        tabindex="-1"
        class="text-h6 mb-3"
      >
        Chart configuration
      </h2>
      <form @submit.prevent="apply()">
        <div class="config-grid">
          <div class="controls">
            <label>
              Chart type
              <select v-model="settings.type">
                <option
                  v-for="(label, type) in chartTypes"
                  :key="type"
                  :value="type"
                >
                  {{ label }}
                </option>
              </select>
            </label>
            <div class="axis-grid">
              <label>
                X field
                <select v-model="settings.x">
                  <option :value="null">
                    {{ numericX ? 'Choose a numeric field' : 'All rows' }}
                  </option>
                  <option
                    v-for="field in xFields"
                    :key="field.index"
                    :value="field.index"
                  >
                    {{ field.title }}
                  </option>
                </select>
              </label>
              <label>
                Y field
                <select v-model="settings.y">
                  <option
                    v-for="field in numeric"
                    :key="field.index"
                    :value="field.index"
                  >
                    {{ field.title }}
                  </option>
                </select>
              </label>
            </div>
            <label v-if="showAggregation">
              Aggregation
              <select v-model="settings.aggregation">
                <option
                  v-for="(label, key) in aggregations"
                  :key="key"
                  :value="key"
                >
                  {{ label }}
                </option>
              </select>
            </label>
            <label>
              Chart title (optional)
              <input v-model="settings.title" type="text" maxlength="120" />
            </label>
            <div class="d-flex flex-wrap ga-4">
              <label class="toggle"
                ><input v-model="settings.axes" type="checkbox" /> Axis
                labels</label
              >
              <label class="toggle"
                ><input v-model="settings.legend" type="checkbox" />
                Legend</label
              >
              <label
                v-if="
                  settings.type === 'bar' && settings.aggregation === 'mean'
                "
                class="toggle"
              >
                <input v-model="settings.errorBars" type="checkbox" /> Error
                bars (±1 sample SD)
              </label>
            </div>
          </div>
          <aside class="settings-preview">
            <h3 class="text-subtitle-1 font-weight-medium">Preview settings</h3>
            <p class="text-body-2 mt-2">
              {{ dataset.name }} · {{ dataset.rows.length }} rows
            </p>
            <p class="mt-3 font-weight-medium">{{ previewTitle }}</p>
            <p v-if="settings.type === 'box'" class="text-body-2 mt-2">
              The box spans the first and third quartiles. The middle line is
              the median, and whiskers show the minimum and maximum.
            </p>
            <p v-else-if="settings.type === 'scatter'" class="text-body-2 mt-2">
              Each usable row contributes one X–Y pair.
            </p>
            <p v-else-if="settings.type === 'line'" class="text-body-2 mt-2">
              Repeated X values are aggregated. Points connect in ascending X
              order.
            </p>
            <p v-else class="text-body-2 mt-2">
              Each bar aggregates usable Y values for one X category.
            </p>
            <p v-if="numericX && xFields.length === 0" class="text-body-2 mt-2">
              Choose a bar chart or box plot for a dataset with only one numeric
              field.
            </p>
          </aside>
        </div>
        <p v-if="error" role="alert" class="text-error mt-4">{{ error }}</p>
        <div class="d-flex flex-wrap justify-end ga-2 mt-4">
          <v-btn variant="text" @click="reset">Reset chart</v-btn>
          <v-btn
            type="submit"
            color="primary"
            :disabled="settings.y === null || (numericX && settings.x === null)"
            >Generate chart</v-btn
          >
        </div>
      </form>
    </v-card>

    <v-card v-if="chart" variant="outlined" class="pa-5 mt-5">
      <div class="d-flex flex-wrap align-center ga-2 mb-2">
        <h2 class="text-h6 mr-auto">{{ chart.title }}</h2>
        <v-btn variant="text" @click="focusConfiguration">Edit chart</v-btn>
        <v-btn variant="text" :disabled="!previous" @click="undo"
          >Undo last chart change</v-btn
        >
        <v-btn variant="outlined" @click="plot.download()"
          >Download chart PNG</v-btn
        >
      </div>
      <p class="text-body-2 text-medium-emphasis">
        {{ chart.excluded }} of {{ dataset.rows.length }} rows excluded
      </p>
      <p v-if="changed" role="status" class="text-body-2 mt-2">
        Generate the chart to apply your current settings.
      </p>
      <StatsChartCanvas ref="plot" :model="chart" />
      <div class="d-flex flex-wrap align-center ga-2 my-2">
        <h3 class="text-subtitle-1 font-weight-medium mr-auto">Chart data</h3>
        <v-btn variant="outlined" @click="exportPoints"
          >Download chart data CSV</v-btn
        >
      </div>
      <v-data-table
        :headers="columns"
        :items="chart.points"
        :items-per-page="10"
        density="compact"
      >
        <template v-for="column in columns" #[`item.${column.key}`]="{ value }">
          {{ display(value) }}
        </template>
      </v-data-table>
    </v-card>
  </section>
</template>

<style scoped>
.config-grid,
.axis-grid {
  display: grid;
  gap: 1rem;
}
.config-grid {
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
}
.axis-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.controls {
  display: grid;
  gap: 0.875rem;
}
label {
  display: grid;
  gap: 0.3rem;
  font-size: 0.875rem;
}
select,
input[type='text'] {
  width: 100%;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.42);
  min-height: 2.75rem;
  border-radius: 4px;
  padding-inline: 0.75rem;
}
select {
  appearance: auto;
}
.toggle {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}
input[type='checkbox'] {
  appearance: auto;
}
.settings-preview {
  background: #f1f5f9;
  padding: 1rem;
  border-radius: 6px;
}
@media (max-width: 640px) {
  .config-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
