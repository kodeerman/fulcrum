import {
  bisectRight,
  deviation,
  extent,
  mean,
  median,
  quantileSorted,
  sum,
} from 'd3'

export const numericCell = cell => {
  const decimal = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i
  return decimal.test(cell) && Number.isFinite(Number(cell))
    ? Number(cell)
    : null
}

export const chartTypes = {
  bar: 'Bar chart',
  line: 'Line chart',
  scatter: 'Scatter plot',
  box: 'Box plot',
  histogram: 'Histogram',
}

export const aggregations = {
  mean: 'Mean',
  median: 'Median',
  sum: 'Sum',
  count: 'Count',
}
const aggregate = { mean, median, sum, count: values => values.length }

function buildHistogram(dataset, settings) {
  const values = dataset.rows
    .map(row => numericCell(row[settings.y]))
    .filter(value => value !== null)
  if (!values.length)
    throw new Error('No rows have usable values for the selected field.')
  const [min, max] = extent(values)
  const binCount = max === min ? 1 : settings.bins
  if (!Number.isInteger(binCount) || binCount < 1 || binCount > 50)
    throw new Error('Choose between 1 and 50 bins.')
  const width = (max - min) / binCount
  if (!Number.isFinite(width) || (max !== min && width <= 0))
    throw new Error('The value range is too large or too small to bin.')
  const edges = Array.from(
    { length: binCount },
    (_, index) => min + index * width,
  )
  edges.push(max)
  if (
    max !== min &&
    edges.some((edge, index) => index > 0 && edge <= edges[index - 1])
  )
    throw new Error('Choose fewer bins for this tightly spaced dataset.')

  const format = new Intl.NumberFormat(undefined, {
    maximumSignificantDigits: 8,
  })
  const points = edges.slice(0, -1).map((low, index) => ({
    x: `${format.format(low)}–${format.format(edges[index + 1])}`,
    low,
    high: edges[index + 1],
    y: 0,
  }))
  for (const value of values) {
    const index = Math.min(binCount - 1, bisectRight(edges, value) - 1)
    points[index].y++
  }
  const xLabel = dataset.fields[settings.y].title
  return {
    settings: { ...settings },
    type: 'histogram',
    points,
    excluded: dataset.rows.length - values.length,
    xLabel,
    yLabel: 'Frequency',
    title: settings.title.trim() || `Distribution of ${xLabel}`,
  }
}

export function buildChart(dataset, settings) {
  const { type, x, y, aggregation } = settings
  if (y === null || (x === null && ['line', 'scatter'].includes(type))) {
    throw new Error('Choose the fields required for this chart.')
  }
  if (type === 'histogram') return buildHistogram(dataset, settings)
  const numericX = type === 'line' || type === 'scatter'
  const errorBars =
    type === 'bar' && aggregation === 'mean' && settings.errorBars
  const groups = new Map()
  const points = []
  let excluded = 0

  for (const row of dataset.rows) {
    const xValue =
      x === null ? 'All rows' : numericX ? numericCell(row[x]) : row[x]
    const yValue = numericCell(row[y])
    if (xValue === null || xValue === '' || yValue === null) {
      excluded++
    } else if (type === 'scatter') {
      points.push({ x: xValue, y: yValue, count: 1 })
    } else {
      if (!groups.has(xValue)) groups.set(xValue, [])
      groups.get(xValue).push(yValue)
    }
  }

  if (groups.size > 100 && !numericX) {
    throw new Error('Choose a field with 100 or fewer categories.')
  }

  for (const [label, values] of groups) {
    if (type === 'box') {
      values.sort((a, b) => a - b)
      points.push({
        x: label,
        count: values.length,
        min: values[0],
        q1: quantileSorted(values, 0.25),
        median: quantileSorted(values, 0.5),
        q3: quantileSorted(values, 0.75),
        max: values.at(-1),
      })
    } else {
      points.push({
        x: label,
        y: aggregate[aggregation](values),
        count: values.length,
        ...(errorBars ? { std: deviation(values) ?? null } : {}),
      })
    }
  }

  if (!points.length)
    throw new Error('No rows have usable values for the selected fields.')
  if (
    points.some(point =>
      Object.values(point).some(
        value => typeof value === 'number' && !Number.isFinite(value),
      ),
    )
  ) {
    throw new Error('These values are too large to chart.')
  }
  if (type === 'line') points.sort((a, b) => a.x - b.x)

  const yField = dataset.fields[y].title
  const xLabel = x === null ? 'Sample' : dataset.fields[x].title
  const yLabel = ['line', 'bar'].includes(type)
    ? `${aggregations[aggregation]} of ${yField}`
    : yField
  return {
    settings: { ...settings },
    type,
    numericX,
    errorBars,
    points,
    excluded,
    xLabel,
    yLabel,
    title:
      settings.title.trim() || (x === null ? yLabel : `${yLabel} by ${xLabel}`),
  }
}
