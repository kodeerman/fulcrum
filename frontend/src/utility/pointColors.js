const lightPalette = [
  '#2379bd',
  '#7857bd',
  '#148575',
  '#aa4e22',
  '#a33265',
  '#476683',
]
const darkPalette = [
  '#71b7ee',
  '#bda3fa',
  '#56c6b3',
  '#ffab80',
  '#f68ab5',
  '#a9c8df',
]

export const supportsPointColors = type =>
  ['bar', 'box', 'scatter'].includes(type)

export function pointColor(model, index, dark) {
  const palette = dark ? darkPalette : lightPalette
  const category = model.type === 'bar' || model.type === 'box'
  return (
    model.points[index]?.color || palette[category ? index % palette.length : 0]
  )
}

export const paletteSize = lightPalette.length
