/**
 * Pruebas de Index.html (el panel): tema claro / oscuro.
 * Correr con: node --test apps-script/seguimiento-fichas/pruebas/*.test.js
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'Index.html'), 'utf8');
const CSS = HTML.slice(HTML.indexOf('<style>'), HTML.indexOf('</style>'));

test('la barra de desplazamiento y los controles siguen el tema (color-scheme)', () => {
  // Sin color-scheme el navegador pinta la barra de desplazamiento y las listas desplegables en claro
  assert.match(CSS, /:root\s*\{[^}]*color-scheme:\s*light/);
  assert.match(CSS, /:root\[data-tema="oscuro"\]\s*\{[^}]*color-scheme:\s*dark/);
  assert.match(CSS, /scrollbar-color:/);
});

test('el tema lo decide el atributo data-tema, no solo la configuración del sistema', () => {
  // Con KondID en claro y Windows en oscuro, el panel debe quedar claro: nada de variables oscuras por prefers-color-scheme
  assert.doesNotMatch(CSS, /@media\s*\(prefers-color-scheme:\s*dark\)/);
  const cabeza = HTML.slice(0, HTML.indexOf('</head>'));
  assert.match(cabeza, /<\?= tema \?>/);
  assert.match(cabeza, /setAttribute\('data-tema'/);
  assert.match(cabeza, /prefers-color-scheme: dark/); // sin elección, se usa la del sistema
});

test('hay un botón para cambiar de tema y la elección se recuerda', () => {
  assert.match(HTML, /<button[^>]*id="tema"/);
  assert.match(HTML, /localStorage\.setItem\('seguimiento_tema'/);
});

test('las etiquetas de etapa y alertas no llevan colores fijos de modo claro', () => {
  // Antes: chip.style.background = '#DBEAFE' (claro) también en modo oscuro
  assert.doesNotMatch(HTML, /style\.background\s*=/);
  assert.match(CSS, /:root\[data-tema="oscuro"\]\s*\.con-color/);
});

test('no hay dos funciones con el mismo nombre en el panel (la segunda reemplaza a la primera)', () => {
  const nombres = [...HTML.matchAll(/function\s+([A-Za-z_$][\w$]*)\s*\(/g)].map((m) => m[1]);
  const repetidos = nombres.filter((n, i) => nombres.indexOf(n) !== i);
  assert.deepEqual(repetidos, []);
});

test('las formaciones del día van en una columna del alto de la pantalla, con su propio scroll y una lista a la vez', () => {
  // Antes la columna crecía con las 3 listas (inician, terminan, en curso) y dejaba el calendario arriba con un hueco
  assert.match(CSS, /\.dia-panel\s*\{[^}]*position:\s*sticky[^}]*max-height:\s*calc\(100vh/);
  assert.match(CSS, /\.dia-lista\s*\{[^}]*overflow-y:\s*auto/);
  assert.match(HTML, /'dia-pestana'/);
  for (const grupo of ['inician', 'finalizan', 'enCurso']) assert.match(HTML, new RegExp(`'${grupo}'`));
});
