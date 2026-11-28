import { deviation, mean, median, quantileSorted, sum } from 'd3'

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
}

export const aggregations = {
  mean: 'Mean',
  median: 'Median',
  sum: 'Sum',
  count: 'Count',
}
const aggregate = { mean, median, sum, count: values => values.length }

export function buildChart(dataset, settings) {
  const { type, x, y, aggregation } = settings
  if (y === null || (x === null && ['line', 'scatter'].includes(type))) {
    throw new Error('Choose the fields required for this chart.')
  }
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
