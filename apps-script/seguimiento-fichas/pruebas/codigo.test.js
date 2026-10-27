/**
 * Pruebas de Codigo.gs fuera de Google: se carga el script con imitaciones de SpreadsheetApp y compañía
 * sobre la estructura real del libro «FORMACIONES COMPLEMENTARIAS GRUPOS» (estructura_libro.json, con los
 * datos personales reemplazados). Correr con: node --test apps-script/seguimiento-fichas/pruebas/*.test.js
 *
 * LIBRO=/ruta/a/otro.json permite probar con otra exportación del libro.
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const CODIGO = fs.readFileSync(path.join(__dirname, '..', 'Codigo.gs'), 'utf8');
const LIBRO = process.env.LIBRO || path.join(__dirname, 'estructura_libro.json');
const CLAVE = 'clave-de-prueba';

function aValor(v) {
  if (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(v)) {
    const [a, m, d] = v.slice(0, 10).split('-').map(Number);
    return new Date(a, m - 1, d);
  }
  return v;
}

function aTexto(v) {
  if (v instanceof Date) return `${v.getDate()}/${v.getMonth() + 1}/${v.getFullYear()}`;
  return v == null ? '' : String(v);
}

class Hoja {
  constructor(def) {
    this.nombre = def.nombre;
    this.oculta = def.oculta;
    this.celdas = new Map(Object.entries(def.celdas).map(([k, [v, t]]) => [k, [aValor(v), t]]));
  }
  getName() { return this.nombre; }
  isSheetHidden() { return this.oculta; }
  hideSheet() { this.oculta = true; }
  getLastRow() { return Math.max(0, ...[...this.celdas.keys()].map((k) => Number(k.split(',')[0]))); }
  getLastColumn() { return Math.max(0, ...[...this.celdas.keys()].map((k) => Number(k.split(',')[1]))); }
  valor(f, c) { return this.celdas.get(`${f},${c}`) || ['', '']; }
  poner(f, c, v) { this.celdas.set(`${f},${c}`, [v, aTexto(v)]); }
  appendRow(fila) { const f = this.getLastRow() + 1; fila.forEach((v, i) => this.poner(f, i + 1, v)); }
  getRange(f, c, nf = 1, nc = 1) {
    const hoja = this;
    const matriz = (i) => Array.from({ length: nf }, (_, a) => Array.from({ length: nc }, (_, b) => hoja.valor(f + a, c + b)[i]));
    return {
      getValues: () => matriz(0),
      getDisplayValues: () => matriz(1),
      setValue: (v) => hoja.poner(f, c, v),
    };
  }
}

function entorno({ clave = CLAVE } = {}) {
  const libro = JSON.parse(fs.readFileSync(LIBRO, 'utf8'));
  const hojas = libro.hojas.map((h) => new Hoja(h));
  const propsScript = new Map(clave ? [['CLAVE', clave]] : []);
  const propsDoc = new Map();
  const propiedades = (m) => ({
    getProperty: (k) => (m.has(k) ? m.get(k) : null),
    setProperty: (k, v) => m.set(k, v),
    deleteProperty: (k) => m.delete(k),
  });
  const salida = (html) => ({ html, setXFrameOptionsMode() { return this; }, setTitle() { return this; }, addMetaTag() { return this; } });
  const ss = {
    getSheetByName: (n) => hojas.find((h) => h.nombre === n) || null,
    insertSheet: (n) => { const h = new Hoja({ nombre: n, oculta: false, celdas: {} }); hojas.push(h); return h; },
  };
  const ctx = {
    SpreadsheetApp: { getActiveSpreadsheet: () => ss, flush: () => {} },
    PropertiesService: { getScriptProperties: () => propiedades(propsScript), getDocumentProperties: () => propiedades(propsDoc) },
    LockService: { getDocumentLock: () => ({ waitLock() {}, releaseLock() {} }) },
    HtmlService: {
      XFrameOptionsMode: { ALLOWALL: 'ALLOWALL' },
      createHtmlOutput: salida,
      createTemplateFromFile: () => ({ evaluate() { return salida('PANEL:' + this.clave); } }),
    },
    Utilities: { getUuid: () => '1234-5678' },
    Logger: { log() {} },
    ScriptApp: { getProjectTriggers: () => [] },
  };
  vm.createContext(ctx);
  vm.runInContext(CODIGO, ctx);
  return { ctx, ss, hojas, propsDoc };
}

test('lee las 4 pestañas visibles y no la copia oculta', () => {
  const { ctx } = entorno();
  const datos = ctx.obtenerDatos(CLAVE);
  const totales = Object.fromEntries(datos.hojas.map((h) => [h.nombre, h.total]));
  assert.deepEqual(totales, { REGULADA: 35, PV: 71, CAMPESENA: 65, TECNOACADEMIA: 2 });
  assert.equal(datos.registros.length, 173);
  assert.ok(datos.hojas.every((h) => !h.aviso));
  assert.ok(datos.registros.every((r) => r.hoja !== 'TECNOACADEMIA '));
  // Solicitudes que aún no tienen programa (REGULADA fila 6) también son registros; las firmas al pie de PV no
  assert.ok(datos.registros.some((r) => r.id === 'REGULADA!6' && !r.campos.programa && r.campos.requerimiento));
  assert.ok(datos.registros.every((r) => !(r.hoja === 'PV' && r.fila > 77)));
});

test('encuentra cada columna por su título, aunque el encabezado ocupe varias filas', () => {
  const { ctx } = entorno();
  const datos = ctx.obtenerDatos(CLAVE);
  const editables = Object.fromEntries(datos.hojas.map((h) => [h.nombre, [...h.editables].sort()]));
  assert.deepEqual(editables.REGULADA, [
    'certificacion', 'estadoAprendices', 'estadoFicha', 'fechaPublicacion', 'inscritos', 'matriculados',
    'noAprobados', 'observaciones', 'programacion',
  ]);
  assert.deepEqual(editables.PV, ['observaciones']);
  assert.deepEqual(editables.CAMPESENA, ['observaciones']);
  assert.deepEqual(editables.TECNOACADEMIA, [
    'certificacion', 'fechaPublicacion', 'inscritos', 'matriculados', 'noAprobados', 'observaciones',
  ]);

  const primero = (hoja) => datos.registros.find((r) => r.hoja === hoja);
  // REGULADA: 3 filas combinadas por registro; el registro es la primera
  assert.equal(primero('REGULADA').fila, 3);
  assert.equal(datos.registros.filter((r) => r.hoja === 'REGULADA')[1].fila, 6);
  assert.equal(primero('PV').fila, 7);
  assert.equal(primero('CAMPESENA').fila, 2);
  assert.equal(primero('TECNOACADEMIA').fila, 5);
  // Fechas en ISO para el panel
  assert.match(primero('REGULADA').campos.inicio, /^\d{4}-\d{2}-\d{2}$/);
  assert.match(primero('PV').campos.fin, /^\d{4}-\d{2}-\d{2}$/);
  for (const hoja of ['REGULADA', 'PV', 'CAMPESENA', 'TECNOACADEMIA']) {
    const c = primero(hoja).campos;
    assert.ok(c.ficha, `${hoja} sin ficha`);
    assert.ok(c.instructor, `${hoja} sin instructor`);
  }
});

test('guardar escribe en la celda de la hoja, deja bitácora y sube la versión', () => {
  const { ctx, ss, propsDoc } = entorno();
  const r = ctx.obtenerDatos(CLAVE).registros.find((x) => x.hoja === 'REGULADA');
  const res = ctx.guardar(CLAVE, r.id, r.huella, {
    estadoFicha: { anterior: '', nuevo: 'PUBLICADA' },
    matriculados: { anterior: '', nuevo: '25' },
    fechaPublicacion: { anterior: '', nuevo: '2026-10-05' },
  });
  assert.equal(res.ok, true);
  assert.equal(res.registro.campos.estadoFicha, 'PUBLICADA');
  assert.equal(res.registro.campos.matriculados, '25');
  assert.equal(res.registro.campos.fechaPublicacion, '2026-10-05');
  const hoja = ss.getSheetByName('REGULADA');
  assert.equal(hoja.valor(3, 75)[0], 'PUBLICADA'); // BW = ESTADO DE LA FICHA
  assert.equal(hoja.valor(3, 79)[0], 25); // CA = N° DE MATRICULADOS, como número
  assert.equal(Object.prototype.toString.call(hoja.valor(3, 77)[0]), '[object Date]'); // BY = FECHA PUBLICACION, como fecha
  assert.equal(res.version, propsDoc.get('version'));
  const bitacora = ss.getSheetByName('BITACORA_PANEL');
  assert.equal(bitacora.isSheetHidden(), true);
  assert.equal(bitacora.getLastRow(), 4); // título + 3 cambios
});

test('no pisa lo que otra persona cambió mientras tanto', () => {
  const { ctx, ss } = entorno();
  const r = ctx.obtenerDatos(CLAVE).registros.find((x) => x.hoja === 'TECNOACADEMIA');
  ss.getSheetByName('TECNOACADEMIA').poner(r.fila, 120, 'APROBADA'); // DP = CERTIFICACION, la escribió otra persona
  const res = ctx.guardar(CLAVE, r.id, r.huella, { certificacion: { anterior: '', nuevo: 'SI' } });
  assert.equal(res.ok, false);
  assert.equal(res.conflictos[0].actual, 'APROBADA');
});

test('conflicto en observaciones de PV y sin cambios no escribe nada', () => {
  const { ctx, ss, propsDoc } = entorno();
  const r = ctx.obtenerDatos(CLAVE).registros.find((x) => x.hoja === 'PV');
  const columna = 16; // P = OBSERVACION
  ss.getSheetByName('PV').poner(r.fila, columna, 'Escrito a mano');
  const res = ctx.guardar(CLAVE, r.id, r.huella, { observaciones: { anterior: '', nuevo: 'Desde el panel' } });
  assert.equal(res.ok, false);
  assert.equal(res.conflictos[0].actual, 'Escrito a mano');

  const igual = ctx.guardar(CLAVE, r.id, r.huella, { observaciones: { anterior: 'Escrito a mano', nuevo: 'Escrito a mano ' } });
  assert.equal(igual.ok, true);
  assert.equal(propsDoc.get('version'), undefined);
});

test('si la fila ya no es el mismo registro, no escribe', () => {
  const { ctx } = entorno();
  const r = ctx.obtenerDatos(CLAVE).registros.find((x) => x.hoja === 'CAMPESENA');
  assert.throws(() => ctx.guardar(CLAVE, r.id, 'OTRO|123', { observaciones: { anterior: '', nuevo: 'x' } }), /cambió de lugar/);
  assert.throws(() => ctx.guardar(CLAVE, r.id, r.huella, { programa: { anterior: '', nuevo: 'x' } }), /no se puede editar/);
  assert.throws(() => ctx.guardar(CLAVE, 'TECNOACADEMIA !5', r.huella, {}), /no válido/);
});

test('sin la clave del enlace no se ve ni se edita nada', () => {
  const { ctx } = entorno();
  assert.throws(() => ctx.obtenerDatos('otra'), /Acceso denegado/);
  assert.throws(() => ctx.obtenerVersion(undefined), /Acceso denegado/);
  assert.throws(() => ctx.guardar('', 'PV!7', '', {}), /Acceso denegado/);
  assert.match(ctx.doGet({ parameter: {} }).html, /Enlace incompleto/);
  assert.equal(ctx.doGet({ parameter: { k: CLAVE } }).html, 'PANEL:' + CLAVE);

  const sinConfigurar = entorno({ clave: null }).ctx;
  assert.match(sinConfigurar.doGet({ parameter: { k: '' } }).html, /configurar/);
  assert.throws(() => sinConfigurar.obtenerDatos(null), /Acceso denegado/);
});

test('editar a mano la hoja cambia la versión que consulta el panel', () => {
  const { ctx } = entorno();
  const antes = ctx.obtenerVersion(CLAVE);
  ctx.onEdit({});
  assert.notEqual(ctx.obtenerVersion(CLAVE), antes);
});
