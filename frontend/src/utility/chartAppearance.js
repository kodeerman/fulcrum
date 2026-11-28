export function chartAppearance(dark) {
  const background = dark ? '#1b2a3c' : '#ffffff'
  const text = dark ? '#e6edf5' : '#34465a'
  const grid = dark ? '#ffffff24' : '#12243a25'
  return {
    text,
    axis: { grid: { color: grid }, ticks: { color: text } },
    backdrop: {
      id: 'plotBackground',
      beforeDraw({ ctx, width, height }) {
        ctx.save()
        ctx.fillStyle = background
        ctx.fillRect(0, 0, width, height)
        ctx.restore()
      },
    },
  }
}

export function downloadChart(chart, createChart, dark, filename) {
  let exportChart
  if (dark) {
    const canvas = document.createElement('canvas')
    canvas.width = chart.canvas.width
    canvas.height = chart.canvas.height
    exportChart = createChart(canvas, false, false)
  }

  try {
    const link = document.createElement('a')
    link.href = (exportChart || chart).toBase64Image()
    link.download = filename
    link.click()
  } finally {
    exportChart?.destroy()
  }
}
