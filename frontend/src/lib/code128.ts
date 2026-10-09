/**
 * Bağımlılıksız (vendored) Code128-B kodlayıcı.
 *
 * Neden dependency değil: bu ortamda `npm install` proje-kapsamlı kurulumlarda
 * enjekte edilen `--allow-scripts` bayrağı yüzünden reddediliyor (jsbarcode/react-barcode
 * kurulamadı). Kargo barkodu LİNEER olmalı (Code128) → küçük, doğrulanabilir bir
 * Code128-B kodlayıcı burada vendored. Order ID (rakam/harf) taranabilir barkoda dönüşür.
 *
 * Standart Code128 desen tablosu (index 0..106); her desen ardışık bar/boşluk genişlikleri,
 * bar ile başlar. 103=Start A, 104=Start B, 105=Start C, 106=Stop (7 elemanlı).
 */
const PATTERNS: string[] = [
  '212222', '222122', '222221', '121223', '121322', '131222', '122213', '122312', '132212', '221213',
  '221312', '231212', '112232', '122132', '122231', '113222', '123122', '123221', '223211', '221132',
  '221231', '213212', '223112', '312131', '311222', '321122', '321221', '312212', '322112', '322211',
  '212123', '212321', '232121', '111323', '131123', '131321', '112313', '132113', '132311', '211313',
  '231113', '231311', '112133', '112331', '132131', '113123', '113321', '133121', '313121', '211331',
  '231131', '213113', '213311', '213131', '311123', '311321', '331121', '312113', '312311', '332111',
  '314111', '221411', '431111', '111224', '111422', '121124', '121421', '141122', '141221', '112214',
  '112412', '122114', '122411', '142112', '142211', '241211', '221114', '413111', '241112', '134111',
  '111242', '121142', '121241', '114212', '124112', '124211', '411212', '421112', '421211', '212141',
  '214121', '412121', '111143', '111341', '131141', '114113', '114311', '411113', '411311', '113141',
  '114131', '311141', '411131', '211412', '211214', '211232', '2331112',
]

const START_B = 104
const STOP = 106

/**
 * Verilen metni Code128-B modül dizisine (bar/boşluk genişlikleri birleştirilmiş binary string)
 * çevirir: '1' = koyu modül, '0' = boşluk modülü. Code128-B ASCII 32..126'yı kapsar; kapsam
 * dışı karakterler '?' ile değiştirilir (barkod yine geçerli/taranabilir kalır).
 */
export function encodeCode128B(input: string): string {
  const text = (input || '').replace(/[^\x20-\x7e]/g, '?') || '0'

  const codes: number[] = [START_B]
  for (const ch of text) {
    codes.push(ch.charCodeAt(0) - 32) // Code set B: value = ascii - 32
  }

  // Checksum = (start + Σ value_i * position_i) mod 103 ; position 1-based (start hariç)
  let sum = START_B
  for (let i = 1; i < codes.length; i++) {
    sum += codes[i] * i
  }
  codes.push(sum % 103)
  codes.push(STOP)

  // Desenleri modül binary string'ine çevir (bar ile başlar, sırayla bar/boşluk)
  let modules = ''
  for (const code of codes) {
    const pattern = PATTERNS[code]
    for (let j = 0; j < pattern.length; j++) {
      const width = Number(pattern[j])
      const isBar = j % 2 === 0
      modules += (isBar ? '1' : '0').repeat(width)
    }
  }
  return modules
}

/**
 * Yazdırma/çıktı için ham SVG string üretir (React dışı; printSingleLabel gibi
 * document.write ile yazılan pencerelerde kullanılır). Değeri altına yazar.
 */
export function code128SvgMarkup(value: string, opts: { height?: number; showValue?: boolean } = {}): string {
  const height = opts.height ?? 80
  const showValue = opts.showValue !== false
  const { modules, bars } = code128Bars(value)
  const QUIET = 10
  const total = modules + QUIET * 2
  const rects = bars
    .map((b) => `<rect x="${b.x + QUIET}" y="0" width="${b.width}" height="${height}" fill="#000000"/>`)
    .join('')
  const svg = `<svg viewBox="0 0 ${total} ${height}" width="100%" height="${height}" preserveAspectRatio="none" shape-rendering="crispEdges" xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0" width="${total}" height="${height}" fill="#ffffff"/>${rects}</svg>`
  const caption = showValue
    ? `<div style="font-family:monospace;font-size:14px;letter-spacing:2px;text-align:center;margin-top:6px">${value}</div>`
    : ''
  return `<div style="width:100%;max-width:360px">${svg}${caption}</div>`
}

/** Modül string'ini ardışık koyu-bar dilimlerine ({x, width}) çevirir (SVG rect üretimi için). */
export function code128Bars(input: string): { modules: number; bars: Array<{ x: number; width: number }> } {
  const mods = encodeCode128B(input)
  const bars: Array<{ x: number; width: number }> = []
  let x = 0
  while (x < mods.length) {
    if (mods[x] === '1') {
      let w = 1
      while (x + w < mods.length && mods[x + w] === '1') w++
      bars.push({ x, width: w })
      x += w
    } else {
      x++
    }
  }
  return { modules: mods.length, bars }
}
