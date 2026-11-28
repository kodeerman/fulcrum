<script setup>
import { computed, nextTick, ref, shallowRef, watch } from 'vue'
import Papa from 'papaparse'
import { useRoute, useRouter } from 'vue-router'
import StatsChartBuilder from '@/components/analytics/StatsChartBuilder.vue'
import { numericCell } from '@/utility/statsChart'
import StatsSummaryChart from '@/components/analytics/StatsSummaryChart.vue'

const props = defineProps({
  studyLabel: { type: String, default: '' },
  studyRows: { type: Array, default: () => [] },
})

const MAX_ROWS = 50_000
const MAX_BYTES = 5 * 1024 * 1024
const sources = [
  ['manual', 'Manual entry', 'Enter a single numeric sample.'],
  ['csv', 'Upload CSV', 'Choose a file with column headers.'],
  ['paste', 'Paste a table', 'Paste CSV or spreadsheet cells with headers.'],
  ...(props.studyLabel
    ? [['study', 'Study data', 'Use participant metrics from Study Analytics.']]
    : []),
]

const route = useRoute()
const router = useRouter()
const workspace = ref(route.query.engine === 'charts' ? 'charts' : 'stats')
const chartBuilder = ref(null)
const previewHeading = ref(null)
const analysisHeading = ref(null)
const dropActive = ref(false)
const source = ref(props.studyLabel ? 'study' : 'manual')
const values = ref('')
const pasted = ref('')
const draft = shallowRef(null)
const dataset = shallowRef(null)
const outcome = ref(null)
const group = ref(null)
const test = ref(null)
const result = ref(null)
const error = ref('')
const pending = ref(false)
const reading = ref(false)
const formatNumber = new Intl.NumberFormat(undefined, {
  maximumSignificantDigits: 8,
})
const measures = [
  ['n', 'Count'],
  ['mean', 'Mean'],
  ['median', 'Median'],
  ['mode', 'Mode'],
  ['min', 'Minimum'],
  ['max', 'Maximum'],
  ['range', 'Range'],
  ['variance', 'Sample variance'],
  ['std', 'Sample standard deviation'],
  ['q1', 'First quartile'],
  ['q3', 'Third quartile'],
  ['iqr', 'Interquartile range'],
]
const comparisonMeasures = [
  ['mean_difference', 'Mean difference (first − second)'],
  ['t_stat', 't statistic'],
  ['f_stat', 'F statistic'],
  ['df', 'Degrees of freedom'],
  ['df_between', 'Between-group df'],
  ['df_within', 'Within-group df'],
  ['p_value', 'p-value'],
]

const chartDataset = computed(() => {
  if (source.value !== 'manual') return dataset.value
  const cells = values.value.split(/[\s,]+/).filter(Boolean)
  if (
    cells.length > MAX_ROWS ||
    !cells.length ||
    cells.some(cell => numericCell(cell) === null)
  )
    return null
  return {
    name: 'Manual sample',
    fields: [{ title: 'Value', index: 0, numeric: true, type: 'Numeric' }],
    rows: cells.map(cell => [cell]),
  }
})

watch(
  () => route.query.engine,
  engine => {
    if (route.name === 'StatsEngine')
      workspace.value = engine === 'charts' ? 'charts' : 'stats'
  },
)

function setWorkspace(next) {
  if (route.name === 'StatsEngine') {
    const query = { ...route.query }
    if (next === 'charts') query.engine = 'charts'
    else delete query.engine
    return router.push({ name: 'StatsEngine', query })
  }
  workspace.value = next
}

async function showChart() {
  await setWorkspace('charts')
  await nextTick()
  chartBuilder.value?.useSelection(
    source.value === 'manual' ? 0 : outcome.value,
    group.value,
  )
}

const numericFields = computed(
  () => dataset.value?.fields.filter(field => field.numeric) ?? [],
)
const groupingFields = computed(
  () =>
    dataset.value?.fields.filter(field => field.index !== outcome.value) ?? [],
)
const analysis = computed(() => {
  const samples = new Map()
  let skipped = 0
  if (!dataset.value || outcome.value === null) return { samples, skipped }
  for (const row of dataset.value.rows) {
    const value = numericCell(row[outcome.value])
    const label = group.value === null ? 'All rows' : row[group.value]
    if (value === null || !label) {
      skipped++
      continue
    }
    if (!samples.has(label)) samples.set(label, [])
    samples.get(label).push(value)
  }
  return { samples, skipped }
})
const tests = computed(() => {
  const samples = [...analysis.value.samples.values()]
  if (samples.length < 2 || samples.some(sample => sample.length < 2)) return []
  const options = [{ title: 'One-way ANOVA', value: 'anova' }]
  if (samples.length === 2)
    options.unshift({ title: 'Welch’s t-test', value: 'welch' })
  return options
})

watch([outcome, group], () => {
  if (outcome.value === group.value) group.value = null
  test.value = null
})
watch([values, outcome, group, test], () => {
  result.value = null
  error.value = ''
})
watch(pasted, () => {
  draft.value = null
  error.value = ''
})

function display(value) {
  if (Array.isArray(value))
    return value.length ? value.map(display).join(', ') : 'None'
  return value === null ? 'Unavailable' : formatNumber.format(value)
}

function reset() {
  values.value = ''
  pasted.value = ''
  draft.value = null
  dataset.value = null
  outcome.value = null
  group.value = null
  test.value = null
  result.value = null
  error.value = ''
}

function chooseSource(next) {
  if (next === source.value) return
  reset()
  source.value = next
}

function prepare(name, headers, rows) {
  if (!rows.length)
    throw new Error('Include at least one data row below the headers.')
  if (rows.length > MAX_ROWS) throw new Error('Use at most 50,000 data rows.')
  const fields = headers.map((title, index) => {
    let numeric = 0
    let missing = 0
    for (const row of rows) {
      if (!row[index]) missing++
      else if (numericCell(row[index]) !== null) numeric++
    }
    const type =
      numeric === 0
        ? 'Text'
        : numeric + missing === rows.length
          ? 'Numeric'
          : 'Mixed'
    return { title, index, numeric: numeric > 0, type, missing }
  })
  draft.value = { name, fields, rows }
}

function previewTable(raw, name, delimiter) {
  draft.value = null
  error.value = ''
  try {
    if (new Blob([raw]).size > MAX_BYTES)
      throw new Error('Use a table no larger than 5 MB.')
    const parsed = Papa.parse(raw, {
      delimiter,
      delimitersToGuess: [',', '\t', ';'],
      skipEmptyLines: 'greedy',
    })
    const parseError = parsed.errors.find(
      item => item.code !== 'UndetectableDelimiter',
    )
    if (parseError) throw new Error(parseError.message)
    const [first, ...body] = parsed.data
    const headers = first?.map(cell => cell.trim()) ?? []
    if (
      !headers.length ||
      headers.some(header => !header) ||
      new Set(headers).size !== headers.length
    ) {
      throw new Error('Give each column a unique, nonblank header.')
    }
    const invalid = body.findIndex(row => row.length !== headers.length)
    if (invalid !== -1)
      throw new Error(
        `Data row ${invalid + 1} has a different number of columns than the header.`,
      )
    prepare(
      name,
      headers,
      body.map(row => row.map(cell => cell.trim())),
    )
  } catch (err) {
    error.value = err.message
  }
}

function previewFile(event) {
  const file = event.target.files[0]
  event.target.value = ''
  readCsv(file)
}

function dropFile(event) {
  dropActive.value = false
  if (reading.value) return
  if (event.dataTransfer.files.length !== 1) {
    draft.value = null
    error.value = 'Drop one CSV file at a time.'
    return
  }
  readCsv(event.dataTransfer.files[0])
}

async function readCsv(file) {
  if (!file || reading.value) return
  draft.value = null
  error.value = ''
  reading.value = true
  try {
    if (file.size > MAX_BYTES)
      throw new Error('Choose a CSV file no larger than 5 MB.')
    previewTable(await file.text(), file.name, ',')
  } catch (err) {
    error.value = err.message
  } finally {
    reading.value = false
  }
}

watch(draft, async data => {
  if (!data) return
  await nextTick()
  previewHeading.value?.focus()
})

function previewStudy() {
  draft.value = null
  error.value = ''
  const headers = ['Trial count', 'Average completion time (s)']
  const rows = props.studyRows.map(row => [
    String(row.trialCount ?? ''),
    row.completionTime > 0 ? String(row.completionTime) : '',
  ])
  try {
    prepare(props.studyLabel, headers, rows)
  } catch (err) {
    error.value = err.message
  }
}

async function importTable() {
  dataset.value = draft.value
  draft.value = null
  outcome.value =
    numericFields.value.find(field => field.type === 'Numeric')?.index ??
    numericFields.value[0]?.index ??
    null
  group.value = null
  test.value = null
  result.value = null
  await nextTick()
  if (workspace.value === 'charts') chartBuilder.value?.focusConfiguration()
  else analysisHeading.value?.focus()
}

function submitManual(event) {
  if (/^dr\.?\s+meowra$/i.test(values.value.trim())) {
    event.preventDefault()
    const { href } = router.resolve({ name: 'DrMeowra' })
    window.open(href, '_blank', 'noopener')
    return
  }

  if (event.type === 'submit' && workspace.value === 'stats') calculate()
}

async function calculate() {
  if (pending.value) return
  result.value = null
  error.value = ''
  const manual = source.value === 'manual'
  const { samples, skipped } = analysis.value
  if (!manual && (samples.size === 0 || samples.size > 500)) {
    error.value =
      'Choose fields that yield between 1 and 500 groups with usable values.'
    return
  }
  const payload = manual
    ? { values: values.value }
    : { samples: [...samples.values()], test: test.value }
  pending.value = true
  try {
    const response = await fetch('/api/stats/describe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!response.headers.get('content-type')?.includes('application/json')) {
      throw new Error('The stats service is unavailable. Try again.')
    }
    const data = await response.json()
    if (!response.ok)
      throw new Error(
        data.error || 'The stats service could not calculate results.',
      )
    result.value = {
      name: manual ? 'Manual sample' : dataset.value.name,
      outcome: manual ? 'Value' : dataset.value.fields[outcome.value].title,
      grouping:
        group.value === null ? '' : dataset.value.fields[group.value].title,
      labels: manual ? ['All values'] : [...samples.keys()],
      summaries: manual ? [data] : data.summaries,
      comparison: data.comparison,
      test: tests.value.find(option => option.value === test.value)?.title,
      skipped: manual ? 0 : skipped,
    }
  } catch (err) {
    error.value = err.message
  } finally {
    pending.value = false
  }
}

function downloadCsv(name, rows) {
  const blob = new Blob(
    [
      Papa.unparse(rows, {
        escapeFormulae: true,
      }),
    ],
    { type: 'text/csv;charset=utf-8' },
  )
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function exportData() {
  downloadCsv('fulcrum-dataset.csv', [
    dataset.value.fields.map(field => field.title),
    ...dataset.value.rows,
  ])
}

function exportStats() {
  const {
    name,
    outcome,
    grouping,
    skipped,
    labels,
    summaries,
    comparison,
    test,
  } = result.value
  const columns = comparisonMeasures.filter(
    ([key]) => comparison && key in comparison,
  )
  const metadata = ['Dataset', 'Outcome', 'Group field', 'Excluded rows']
  const rows = [
    [
      ...metadata,
      'Group',
      ...measures.map(([, label]) => label),
      'Test',
      ...columns.map(([, label]) => label),
    ],
    ...summaries.map((summary, index) => [
      name,
      outcome,
      grouping,
      skipped,
      labels[index],
      ...measures.map(([key]) =>
        Array.isArray(summary[key]) ? summary[key].join(', ') : summary[key],
      ),
      '',
      ...columns.map(() => ''),
    ]),
  ]
  if (comparison)
    rows.push([
      name,
      outcome,
      grouping,
      skipped,
      labels.join(' vs '),
      ...measures.map(() => ''),
      test,
      ...columns.map(([key]) => comparison[key]),
    ])
  downloadCsv('fulcrum-statistics.csv', rows)
}
</script>

<template>
  <v-container class="stats-page py-8">
    <header class="mb-6">
      <h1 class="text-h4 mb-2">
        {{ workspace === 'charts' ? 'Chart Display Engine' : 'Stats Engine' }}
      </h1>
      <p class="text-medium-emphasis">
        {{
          workspace === 'charts'
            ? 'Plot a dataset by choosing the fields to show on each axis.'
            : 'Summarize a numeric sample or compare groups in a dataset.'
        }}
      </p>
    </header>

    <div
      class="d-flex flex-wrap ga-2 mb-5"
      role="group"
      aria-label="Analysis workspace"
    >
      <v-btn
        :variant="workspace === 'stats' ? 'tonal' : 'outlined'"
        :aria-pressed="workspace === 'stats'"
        @click="setWorkspace('stats')"
      >
        Stats Engine
      </v-btn>
      <v-btn
        :variant="workspace === 'charts' ? 'tonal' : 'outlined'"
        :aria-pressed="workspace === 'charts'"
        @click="setWorkspace('charts')"
      >
        Chart Display Engine
      </v-btn>
    </div>

    <section aria-labelledby="stats-source">
      <h2 id="stats-source" class="text-h6 mb-3">Data source</h2>
      <div class="source-grid mb-5">
        <v-btn
          v-for="[key, label, description] in sources"
          :key="key"
          :variant="source === key ? 'tonal' : 'outlined'"
          :color="source === key ? 'primary' : undefined"
          :aria-pressed="source === key"
          :disabled="pending || reading"
          class="source-button"
          @click="chooseSource(key)"
        >
          <strong>{{ label }}</strong>
          <span>{{ description }}</span>
        </v-btn>
      </div>
    </section>

    <v-card variant="outlined" class="pa-5">
      <form
        v-if="source === 'manual'"
        @submit.prevent="submitManual"
      >
        <v-textarea
          v-model="values"
          @keydown.enter.exact="submitManual"
          label="Numbers"
          hint="Separate numbers with commas, spaces, or new lines."
          maxlength="100000"
          persistent-hint
          :readonly="pending"
          variant="outlined"
          rows="4"
        />
        <v-btn
          v-if="workspace === 'stats'"
          class="mt-4"
          color="primary"
          type="submit"
          :loading="pending"
          >Calculate</v-btn
        >
        <v-btn
          class="mt-4 ml-2"
          variant="text"
          :disabled="pending"
          @click="reset"
          >Reset</v-btn
        >
      </form>
      <div v-else-if="dataset" class="d-flex flex-wrap align-center ga-3">
        <div class="mr-auto">
          <h2 class="text-h6">{{ dataset.name }}</h2>
          <p class="text-medium-emphasis">
            {{ dataset.rows.length }} rows · {{ dataset.fields.length }} columns
          </p>
        </div>
        <v-btn variant="outlined" @click="exportData">Download data CSV</v-btn>
        <v-btn variant="text" :disabled="pending" @click="reset"
          >Replace dataset</v-btn
        >
      </div>
      <div v-else-if="source === 'csv'">
        <div
          class="csv-drop"
          :class="{ 'csv-drop--active': dropActive }"
          @dragover.prevent="dropActive = !reading"
          @dragleave="dropActive = false"
          @drop.prevent="dropFile"
        >
          <label class="d-block font-weight-medium mb-2" for="stats-file">
            Drop a CSV here or choose a file
          </label>
          <input
            id="stats-file"
            type="file"
            accept=".csv,text/csv"
            aria-describedby="stats-file-help"
            :disabled="reading"
            @change="previewFile"
          />
          <p id="stats-file-help" class="text-body-2 text-medium-emphasis mt-2">
            Use a comma-separated file with headers in the first row. Maximum 5
            MB.
          </p>
        </div>
        <p v-if="reading" role="status" class="mt-2">Reading file…</p>
      </div>
      <form
        v-else-if="source === 'paste'"
        @submit.prevent="previewTable(pasted, 'Pasted table', '')"
      >
        <v-textarea
          v-model="pasted"
          label="Table with column headers"
          variant="outlined"
          rows="5"
        />
        <v-btn color="primary" type="submit" :disabled="!pasted.trim()"
          >Preview table</v-btn
        >
      </form>
      <div v-else>
        <p class="mb-3">
          Use trial counts and average completion times for the participant rows
          loaded in Study Analytics.
        </p>
        <v-btn
          color="primary"
          :disabled="!studyRows.length"
          @click="previewStudy"
          >Preview study data</v-btn
        >
        <p v-if="!studyRows.length" class="text-medium-emphasis mt-2">
          No participant rows are available yet.
        </p>
      </div>
    </v-card>

    <v-alert
      v-if="error"
      type="error"
      variant="tonal"
      class="mt-5"
      role="alert"
      >{{ error }}</v-alert
    >

    <v-card v-if="draft" variant="outlined" class="pa-5 mt-5">
      <h2 ref="previewHeading" tabindex="-1" class="text-h6">
        Preview {{ draft.name }}
      </h2>
      <p class="text-medium-emphasis mb-3">
        Showing up to 5 of {{ draft.rows.length }} rows.
      </p>
      <v-table density="compact">
        <thead>
          <tr>
            <th v-for="field in draft.fields" :key="field.index" scope="col">
              {{ field.title }}
              <div class="text-caption">
                {{ field.type }} · {{ field.missing }} blank
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in draft.rows.slice(0, 5)" :key="index">
            <td v-for="(cell, col) in row" :key="col">{{ cell || '—' }}</td>
          </tr>
        </tbody>
      </v-table>
      <v-alert
        v-if="!draft.fields.some(field => field.numeric)"
        type="warning"
        variant="tonal"
        class="mt-3"
      >
        Add a column with numeric values before importing.
      </v-alert>
      <v-btn
        class="mt-4"
        color="primary"
        :disabled="reading || !draft.fields.some(field => field.numeric)"
        @click="importTable"
      >
        Import dataset
      </v-btn>
      <v-btn class="mt-4 ml-2" variant="text" @click="draft = null"
        >Cancel preview</v-btn
      >
    </v-card>

    <StatsChartBuilder
      v-if="chartDataset"
      v-show="workspace === 'charts'"
      ref="chartBuilder"
      :dataset="chartDataset"
      :outcome="outcome"
      :group="group"
      @download-csv="downloadCsv"
    />
    <p
      v-else-if="workspace === 'charts' && source === 'manual'"
      class="text-medium-emphasis mt-4"
    >
      Enter a sample of finite numbers to configure a chart.
    </p>

    <v-card
      v-if="dataset && workspace === 'stats'"
      variant="outlined"
      class="pa-5 mt-5"
    >
      <h2 ref="analysisHeading" tabindex="-1" class="text-h6 mb-3">
        Analysis settings
      </h2>
      <form @submit.prevent="calculate">
        <div class="settings-grid">
          <label class="settings-field">
            Numeric outcome
            <select id="stats-outcome" v-model="outcome" :disabled="pending">
              <option
                v-for="field in numericFields"
                :key="field.index"
                :value="field.index"
              >
                {{ field.title }}
              </option>
            </select>
          </label>
          <label class="settings-field">
            Group by (optional)
            <select id="stats-group" v-model="group" :disabled="pending">
              <option :value="null">No grouping</option>
              <option
                v-for="field in groupingFields"
                :key="field.index"
                :value="field.index"
              >
                {{ field.title }}
              </option>
            </select>
          </label>
          <label class="settings-field">
            Comparison test (optional)
            <select
              id="stats-test"
              v-model="test"
              :disabled="pending || !tests.length"
            >
              <option :value="null">No comparison</option>
              <option
                v-for="option in tests"
                :key="option.value"
                :value="option.value"
              >
                {{ option.title }}
              </option>
            </select>
          </label>
        </div>
        <p class="text-body-2 mb-2">
          {{ analysis.skipped }} of {{ dataset.rows.length }} rows excluded.
          Rows need a finite numeric outcome and, when grouping, a nonblank
          group.
        </p>
        <p v-if="group !== null && !tests.length" class="text-body-2 mb-2">
          Comparison tests require at least two groups with at least two values
          each.
        </p>
        <p v-if="test" class="text-body-2 mb-2">
          Use independent observations and check that the outcome is
          approximately normal within each group.
          {{
            test === 'anova'
              ? 'One-way ANOVA also assumes similar group variances.'
              : 'Welch’s test allows unequal group variances.'
          }}
        </p>
        <v-btn
          class="mt-3"
          color="primary"
          type="submit"
          :loading="pending"
          :disabled="!analysis.samples.size"
          >Calculate</v-btn
        >
      </form>
    </v-card>

    <p v-if="pending" role="status" class="mt-4">Calculating statistics…</p>

    <section
      v-if="result && workspace === 'stats'"
      class="mt-7"
      aria-labelledby="stats-results"
      aria-live="polite"
    >
      <div class="d-flex flex-wrap align-center ga-3 mb-3">
        <div class="mr-auto">
          <h2 id="stats-results" class="text-h6">Descriptive statistics</h2>
          <p class="text-medium-emphasis">
            {{ result.name }} · {{ result.outcome
            }}<span v-if="result.grouping"> by {{ result.grouping }}</span>
          </p>
        </div>
        <v-btn v-if="chartDataset" variant="outlined" @click="showChart"
          >Visualize selection</v-btn
        >
        <v-btn variant="outlined" @click="exportStats"
          >Download statistics CSV</v-btn
        >
      </div>
      <v-table>
        <thead v-if="result.grouping">
          <tr>
            <th scope="col">Measure</th>
            <th v-for="label in result.labels" :key="label" scope="col">
              {{ label }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="[key, label] in measures" :key="key">
            <th scope="row">{{ label }}</th>
            <td v-for="(summary, index) in result.summaries" :key="index">
              {{ display(summary[key]) }}
            </td>
          </tr>
        </tbody>
      </v-table>
      <v-card v-if="result.comparison" variant="outlined" class="pa-5 mt-5">
        <h3 class="text-h6 mb-2">{{ result.test }}</h3>
        <v-table density="compact">
          <tbody>
            <template v-for="[key, label] in comparisonMeasures" :key="key">
              <tr v-if="key in result.comparison">
                <th scope="row">{{ label }}</th>
                <td>{{ display(result.comparison[key]) }}</td>
              </tr>
            </template>
          </tbody>
        </v-table>
        <p class="text-body-2 mt-3">
          {{
            result.comparison.p_value === null
              ? 'The test could not estimate a p-value for these samples. Check the variation within groups.'
              : 'Use the group summaries to judge the size and practical importance of differences.'
          }}
        </p>
      </v-card>
      <StatsSummaryChart
        v-if="result.grouping && result.labels.length <= 30"
        :result="result"
      />
    </section>
  </v-container>
</template>

<style scoped>
.stats-page {
  max-width: 70rem;
}
.csv-drop {
  border: 1px dashed rgba(var(--v-theme-on-surface), 0.42);
  border-radius: 8px;
  padding: 1rem;
}
.csv-drop--active {
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.08);
}
.source-grid,
.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 13rem), 1fr));
  gap: 0.75rem;
}
.settings-grid {
  margin-bottom: 1rem;
}
.settings-field {
  display: grid;
  gap: 0.25rem;
  font-size: 0.875rem;
}
.settings-field select {
  appearance: auto;
  min-height: 2.75rem;
  width: 100%;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.42);
  border-radius: 4px;
  padding-inline: 0.75rem;
}
.settings-field select:disabled {
  opacity: 0.55;
}
.source-button {
  height: auto;
  min-height: 5rem;
  text-transform: none;
  letter-spacing: normal;
}
.source-button :deep(.v-btn__content) {
  align-items: flex-start;
  flex-direction: column;
  gap: 0.25rem;
  padding-block: 0.75rem;
  text-align: left;
  white-space: normal;
}
.source-button span {
  font-weight: 400;
}
</style>
