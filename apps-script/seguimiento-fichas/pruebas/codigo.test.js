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
    this.formulas = [];
  }
  getName() { return this.nombre; }
  isSheetHidden() { return this.oculta; }
  hideSheet() { this.oculta = true; }
  getLastRow() { return Math.max(0, ...[...this.celdas.keys()].map((k) => Number(k.split(',')[0]))); }
  getLastColumn() { return Math.max(0, ...[...this.celdas.keys()].map((k) => Number(k.split(',')[1]))); }
  valor(f, c) { return this.celdas.get(`${f},${c}`) || ['', '']; }
  poner(f, c, v) {
    // Como Google Sheets: un texto que empieza con ' queda como texto (sin el apóstrofo); con = + - @ sería fórmula
    if (typeof v === 'string' && v.startsWith("'")) v = v.slice(1);
    else if (typeof v === 'string' && /^[=+\-@]/.test(v)) this.formulas.push(`${f},${c}: ${v}`);
    this.celdas.set(`${f},${c}`, [v, aTexto(v)]);
  }
  appendRow(fila) { const f = this.getLastRow() + 1; fila.forEach((v, i) => this.poner(f, i + 1, v)); }
  getRange(f, c, nf = 1, nc = 1) {
    const hoja = this;
    const matriz = (i) => Array.from({ length: nf }, (_, a) => Array.from({ length: nc }, (_, b) => hoja.valor(f + a, c + b)[i]));
    return {
      getSheet: () => hoja,
      getRow: () => f,
      getColumn: () => c,
      getNumRows: () => nf,
      getNumColumns: () => nc,
      getValues: () => matriz(0),
      getDisplayValues: () => matriz(1),
      setValue: (v) => hoja.poner(f, c, v),
      setValues: (m) => m.forEach((fila, a) => fila.forEach((v, b) => hoja.poner(f + a, c + b, v))),
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
  const salida = (html) => ({ html, setXFrameOptionsMode() { return this; }, setTitle() { return this; }, addMetaTag() { return this; }, setWidth() { return this; }, setHeight() { return this; } });
  let urlPublicada = null;
  const sesion = { correo: '' };
  const avisos = [];
  const menus = [];
  const ui = {
    ButtonSet: { OK: 'OK', YES_NO: 'YES_NO' },
    Button: { YES: 'YES', NO: 'NO' },
    respuesta: 'YES',
    alert(...a) { avisos.push(a); return ui.respuesta; },
    showModelessDialog(html, titulo) { avisos.push(['dialogo', titulo, html.html]); },
    createMenu(nombre) {
      const menu = { nombre, items: [], addItem(t, f) { menu.items.push([t, f]); return menu; }, addSeparator() { return menu; }, addToUi() { menus.push(menu); } };
      return menu;
    },
  };
  const ss = {
    getSheetByName: (n) => hojas.find((h) => h.nombre === n) || null,
    insertSheet: (n) => { const h = new Hoja({ nombre: n, oculta: false, celdas: {} }); hojas.push(h); return h; },
  };
  const ctx = {
    SpreadsheetApp: { getActiveSpreadsheet: () => ss, flush: () => {}, getUi: () => ui },
    PropertiesService: { getScriptProperties: () => propiedades(propsScript), getDocumentProperties: () => propiedades(propsDoc) },
    LockService: { getDocumentLock: () => ({ waitLock() {}, releaseLock() {} }) },
    HtmlService: {
      XFrameOptionsMode: { ALLOWALL: 'ALLOWALL' },
      createHtmlOutput: salida,
      createTemplateFromFile: () => ({ evaluate() { return salida('PANEL:' + this.clave); } }),
    },
    Utilities: { getUuid: () => '1234-5678' },
    Session: { getActiveUser: () => ({ getEmail: () => sesion.correo }) },
    console: { warn() {} },
    Logger: { log() {} },
    ScriptApp: {
      getProjectTriggers: () => [],
      newTrigger: () => ({ forSpreadsheet: () => ({ onChange: () => ({ create() {} }) }) }),
      getService: () => ({ getUrl: () => urlPublicada }),
    },
  };
  vm.createContext(ctx);
  vm.runInContext(CODIGO, ctx);
  return { ctx, ss, hojas, propsDoc, propsScript, ui, avisos, menus, sesion, publicar: (u) => { urlPublicada = u; } };
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

// ─── Etapas y alertas (lógica que antes estaba en Motor.gs) ───

function registro(campos, extra = {}) {
  return { hoja: 'REGULADA', fila: 3, campos: { ficha: '3641424', instructor: 'ANA PEREZ GOMEZ', ...campos }, ...extra };
}

test('etapa según la fecha de hoy', () => {
  const { ctx } = entorno();
  const hoy = '2026-10-15';
  const casos = [
    [{ inicio: '2026-10-15', fin: '2026-10-20' }, 'INICIA_HOY', 'Inicia hoy'],
    [{ inicio: '2026-10-16', fin: '2026-10-20' }, 'POR_INICIAR', 'Inicia mañana'],
    [{ inicio: '2026-10-22', fin: '2026-10-30' }, 'POR_INICIAR', 'Inicia en 7 días'],
    [{ inicio: '2026-10-23', fin: '2026-10-30' }, 'PROGRAMADA', 'Inicia en 8 días'],
    [{ inicio: '2026-10-01', fin: '2026-10-30' }, 'EN_EJECUCION', 'Faltan 15 días'],
    [{ inicio: '2026-10-01', fin: '2026-10-18' }, 'POR_FINALIZAR', 'Finaliza en 3 días'],
    [{ inicio: '2026-10-01', fin: '2026-10-15' }, 'POR_FINALIZAR', 'Finaliza hoy'],
    [{ inicio: '2026-10-01', fin: '2026-10-14' }, 'FINALIZADA', 'Finalizó ayer'],
    [{ inicio: '2026-10-20', fin: '2026-10-10' }, 'FECHAS_INVALIDAS', 'La fecha fin es anterior al inicio'],
    [{ inicio: '', fin: '2026-10-10' }, 'SIN_FECHAS', 'falta inicio'],
    [{ inicio: '0206-10-08', fin: 'OCTUBRE' }, 'SIN_FECHAS', 'inicio ilegible («0206-10-08») · fin ilegible («OCTUBRE»)'],
    // Fechas escritas como texto en la hoja
    [{ inicio: '1/10/2026', fin: '10/19/2026' }, 'EN_EJECUCION', 'Faltan 4 días'],
  ];
  for (const [fechas, etapa, detalle] of casos) {
    const [r] = ctx.calcularEtapas_([registro(fechas)], hoy);
    assert.equal(r.etapa, etapa, JSON.stringify(fechas));
    assert.equal(r.detalleEtapa, detalle, JSON.stringify(fechas));
  }
});

test('alertas: sin ficha, sin instructor, cruce de instructor e inconsistencia entre pestañas', () => {
  const { ctx } = entorno();
  const lista = ctx.calcularEtapas_([
    registro({ ficha: '', instructor: '', programa: 'A', inicio: '2026-10-01', fin: '2026-10-30' }),
    // Mismo instructor, fechas que se solapan: cruce en ambos
    registro({ ficha: '111111', programa: 'B', inicio: '2026-10-10', fin: '2026-10-20' }),
    registro({ ficha: '222222', programa: 'C', inicio: '2026-10-18', fin: '2026-10-25', instructor: 'Ana  Pérez Gómez' }),
    // Mismo instructor pero ya finalizada: no cuenta como cruce
    registro({ ficha: '333333', programa: 'D', inicio: '2026-09-01', fin: '2026-09-30' }),
    // La misma ficha en otra pestaña con otra fecha de fin y otro instructor
    registro({ ficha: '444444', programa: 'E', instructor: 'LUIS ROJAS', inicio: '2026-11-01', fin: '2026-11-10' }),
    registro({ ficha: '444444', programa: 'E', instructor: 'MARIA TORO', inicio: '2026-11-01', fin: '2026-11-12' }, { hoja: 'PV', fila: 9 }),
  ], '2026-10-15');
  assert.deepEqual([...lista[0].alertas], ['SIN_FICHA', 'SIN_INSTRUCTOR']);
  assert.deepEqual([...lista[1].alertas], ['CRUCE_INSTRUCTOR']);
  assert.deepEqual([...lista[2].alertas], ['CRUCE_INSTRUCTOR']);
  assert.match(lista[1].cruces[0], /^C · 222222 \(2026-10-18 a 2026-10-25, REGULADA\)$/);
  assert.deepEqual([...lista[3].alertas], []);
  assert.deepEqual([...lista[4].alertas], ['INCONSISTENCIA']);
  assert.deepEqual([...lista[4].inconsistencias], ['Fin 2026-11-12 en PV (fila 9)', 'Instructor «MARIA TORO» en PV (fila 9)']);
  // La misma ficha en dos pestañas no se cuenta como cruce consigo misma
  assert.ok(!lista[5].alertas.includes('CRUCE_INSTRUCTOR'));
});

test('obtenerDatos entrega etapa y alertas de cada registro del libro', () => {
  const { ctx } = entorno();
  const datos = ctx.obtenerDatos(CLAVE);
  assert.ok(datos.etapas.EN_EJECUCION && datos.alertas.CRUCE_INSTRUCTOR);
  for (const r of datos.registros) {
    assert.ok(datos.etapas[r.etapa], r.id);
    assert.ok(r.alertas.every((a) => datos.alertas[a]), r.id);
  }
  // Las solicitudes sin programa ni fechas quedan con fecha faltante y sin ficha
  const solicitud = datos.registros.find((r) => r.id === 'REGULADA!6');
  assert.equal(solicitud.etapa, 'SIN_FECHAS');
  assert.ok(solicitud.alertas.includes('SIN_FICHA'));
});

// ─── Menú dentro de la hoja ───

test('al abrir la hoja aparece el menú «Seguimiento de fichas» y cada opción existe', () => {
  const { ctx, menus } = entorno();
  ctx.onOpen();
  assert.equal(menus[0].nombre, 'Seguimiento de fichas');
  for (const [, funcion] of menus[0].items) assert.equal(typeof ctx[funcion], 'function', funcion);
});

test('abrir el panel y ver el enlace desde el menú', () => {
  const { ctx, avisos, publicar } = entorno();
  ctx.abrirPanel();
  assert.deepEqual(avisos.pop(), ['dialogo', 'Seguimiento de fichas', 'PANEL:' + CLAVE]);

  ctx.mostrarEnlace();
  const texto = avisos.pop()[1];
  assert.match(texto, /Gestionar implementaciones[\s\S]*\n\?k=clave-de-prueba\n/);
  // Nunca arma la URL por su cuenta: getUrl() puede ser de otra implementación
  publicar('https://script.google.com/macros/s/OTRA/exec');
  ctx.mostrarEnlace();
  assert.doesNotMatch(avisos.pop()[1], /OTRA/);

  const sinClave = entorno({ clave: null });
  sinClave.ctx.abrirPanel();
  assert.match(sinClave.avisos.pop()[0], /Configurar \(primera vez\)/);
});

test('configurar crea la clave una sola vez y cambiarClave pide confirmación', () => {
  const { ctx, propsScript, ui } = entorno({ clave: null });
  ctx.configurar();
  const clave = propsScript.get('CLAVE');
  assert.match(clave, /^[0-9a-z]+$/);
  ctx.configurar();
  assert.equal(propsScript.get('CLAVE'), clave);

  ui.respuesta = 'NO';
  ctx.cambiarClave();
  assert.equal(propsScript.get('CLAVE'), clave);
});

// ─── Historial de cambios: quién, qué y desde dónde ───

const bitacora = (ss) => {
  const h = ss.getSheetByName('BITACORA_PANEL');
  return h ? h.getRange(1, 1, h.getLastRow(), 10).getDisplayValues() : [];
};

test('lo guardado desde KondID queda con el nombre del usuario; desde la hoja, con su correo', () => {
  const { ctx, ss, sesion } = entorno();
  const r = ctx.obtenerDatos(CLAVE).registros.find((x) => x.hoja === 'PV');
  ctx.guardar(CLAVE, r.id, r.huella, { observaciones: { anterior: '', nuevo: 'Llamar a la empresa' } },
    { nombre: 'Emerson Murcia', origen: 'KondID' });
  let filas = bitacora(ss);
  assert.deepEqual(filas[0], ['Fecha', 'Pestaña', 'Fila', 'Ficha', 'Programa', 'Campo', 'Antes', 'Después', 'Quién', 'Origen']);
  assert.deepEqual(filas[1].slice(1), ['PV', String(r.fila), r.campos.ficha, r.campos.programa, 'Observaciones', '',
    'Llamar a la empresa', 'Emerson Murcia', 'KondID']);

  sesion.correo = 'coordinacion@example.com';
  ctx.guardar(CLAVE, r.id, r.huella, { observaciones: { anterior: 'Llamar a la empresa', nuevo: 'Listo' } },
    { nombre: '', origen: 'Panel en la hoja' });
  filas = bitacora(ss);
  assert.deepEqual(filas[2].slice(8), ['coordinacion@example.com', 'Panel en la hoja']);
});

test('lo que se escribe a mano en la hoja queda en la bitácora con el título de la columna', () => {
  const { ctx, ss } = entorno();
  const hoja = ss.getSheetByName('REGULADA');
  const programa = hoja.valor(3, 19)[1].replace(/\s+/g, ' ').trim();
  // Instructor (V) de la primera fila del registro
  hoja.poner(3, 22, 'NUEVO INSTRUCTOR');
  ctx.onEdit({ range: hoja.getRange(3, 22), oldValue: 'ANTERIOR', value: 'NUEVO INSTRUCTOR' });
  // Horas de un día en la segunda fila del registro combinado (fila 4): se anota en el registro de la fila 3
  hoja.poner(4, 50, 4);
  ctx.onEdit({ range: hoja.getRange(4, 50), oldValue: undefined, value: '4' });
  // Fecha de inicio (AA): el valor anterior llega como número de serie
  hoja.poner(3, 27, new Date(2026, 9, 20));
  ctx.onEdit({ range: hoja.getRange(3, 27), oldValue: '46305', value: '46315' });
  const filas = bitacora(ss);
  assert.equal(filas.length, 4);
  assert.deepEqual(filas[1].slice(1), ['REGULADA', '3', hoja.valor(3, 73)[1], programa, 'NOMBRE DEL INSTRUCTOR',
    'ANTERIOR', 'NUEVO INSTRUCTOR', 'Editor de la hoja', 'Hoja']);
  assert.deepEqual(filas[2].slice(2, 8), ['3', hoja.valor(3, 73)[1], programa, 'Día 11', '', '4']);
  assert.deepEqual(filas[3].slice(5, 8), ['FECHA DE INICIO', '10/10/2026', '20/10/2026']);
});

test('no se anotan ediciones de encabezados ni de otras pestañas, y un pegado grande tiene tope', () => {
  const { ctx, ss } = entorno();
  const hoja = ss.getSheetByName('REGULADA');
  ctx.onEdit({ range: hoja.getRange(2, 19), oldValue: 'NOMBRE DEL PROGRAMA', value: 'X' });
  ctx.onEdit({ range: ss.getSheetByName('TECNOACADEMIA ').getRange(5, 2), oldValue: 'a', value: 'b' });
  assert.equal(bitacora(ss).length, 0);
  ctx.onEdit({ range: hoja.getRange(3, 1, 10, 10) });
  assert.equal(bitacora(ss).length, 1 + 30);
});

test('el panel recibe los cambios del más nuevo al más viejo y marca «Modificada recientemente»', () => {
  const { ctx, ss } = entorno();
  const datos = ctx.obtenerDatos(CLAVE);
  const r = datos.registros.find((x) => x.hoja === 'CAMPESENA' && x.campos.ficha);
  ctx.guardar(CLAVE, r.id, r.huella, { observaciones: { anterior: r.campos.observaciones, nuevo: 'Uno' } }, { nombre: 'Ana', origen: 'KondID' });
  ctx.guardar(CLAVE, r.id, r.huella, { observaciones: { anterior: 'Uno', nuevo: 'Dos' } }, { nombre: 'Luis', origen: 'KondID' });
  // Un cambio de hace 10 días en otro registro no cuenta como reciente
  const otro = datos.registros.find((x) => x.hoja === 'PV');
  const h = ss.getSheetByName('BITACORA_PANEL');
  h.appendRow([new Date(Date.now() - 10 * 86400000), 'PV', otro.fila, otro.campos.ficha, 'X', 'Observaciones', '', 'viejo', 'Ana', 'Hoja']);

  const nuevos = ctx.obtenerDatos(CLAVE);
  assert.deepEqual(nuevos.cambios.slice(0, 3).map((c) => c.quien), ['Ana', 'Luis', 'Ana']);
  assert.equal(nuevos.cambios[1].despues, 'Dos');
  assert.match(nuevos.cambios[1].fecha, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
  const marcado = nuevos.registros.find((x) => x.id === r.id);
  assert.ok(marcado.alertas.includes('CAMBIO_RECIENTE'));
  assert.match(marcado.cambiosRecientes[0], /^Observaciones: «Uno» → «Dos» · Luis · /);
  assert.ok(!nuevos.registros.find((x) => x.id === otro.id).alertas.includes('CAMBIO_RECIENTE'));
});

// ─── Seguridad ───

const sinHojaAbierta = (ctx) => {
  // Así responde Google cuando la función se llama desde la aplicación web y no desde el menú de la hoja
  ctx.SpreadsheetApp.getUi = () => { throw new Error('Cannot call SpreadsheetApp.getUi() from this context.'); };
};

test('lo que se escribe desde el panel queda como texto en la hoja y en la bitácora, nunca como fórmula', () => {
  const { ctx, ss } = entorno();
  const r = ctx.obtenerDatos(CLAVE).registros.find((x) => x.hoja === 'REGULADA');
  const textos = ['=HYPERLINK("https://ejemplo.invalid";"x")', '+1+1', '-1+1', '@SUMA(1)'];
  const res = ctx.guardar(CLAVE, r.id, r.huella, {
    estadoFicha: { anterior: r.campos.estadoFicha, nuevo: textos[0] },
    estadoAprendices: { anterior: r.campos.estadoAprendices, nuevo: textos[1] },
    certificacion: { anterior: r.campos.certificacion, nuevo: textos[2] },
    observaciones: { anterior: r.campos.observaciones, nuevo: textos[3] },
  }, { nombre: '=IMPORTXML("https://ejemplo.invalid";"//a")', origen: 'KondID' });
  assert.equal(res.ok, true);
  const hoja = ss.getSheetByName('REGULADA');
  const fila = hoja.getRange(r.fila, 1, 1, 90).getValues()[0];
  for (const t of textos) assert.ok(fila.includes(t), `${t} no quedó en la hoja`);
  assert.deepEqual(hoja.formulas, []);
  assert.deepEqual(ss.getSheetByName('BITACORA_PANEL').formulas, []);
  const anotados = bitacora(ss).slice(1);
  assert.deepEqual(anotados.map((f) => f[7]).sort(), [...textos].sort());
  assert.equal(anotados[0][8], '=IMPORTXML("https://ejemplo.invalid";"//a")');
});

test('lo escrito a mano que se copia a la bitácora tampoco queda como fórmula', () => {
  const { ctx, ss } = entorno();
  const r = ctx.obtenerDatos(CLAVE).registros.find((x) => x.hoja === 'REGULADA');
  const hoja = ss.getSheetByName('REGULADA');
  hoja.poner(r.fila, 75, 'CREADA');
  ctx.onEdit({ range: hoja.getRange(r.fila, 75), oldValue: '=IMPORTXML("https://ejemplo.invalid";"//a")' });
  assert.deepEqual(ss.getSheetByName('BITACORA_PANEL').formulas, []);
  assert.equal(bitacora(ss)[1][6], '=IMPORTXML("https://ejemplo.invalid";"//a")');
});

test('cambiar la clave solo se puede desde el menú de la hoja', () => {
  const { ctx, propsScript } = entorno();
  sinHojaAbierta(ctx);
  assert.throws(() => ctx.cambiarClave(), /menú/);
  assert.equal(propsScript.get('CLAVE'), CLAVE);
});

test('sin la clave, ninguna función que la aplicación web deja llamar entrega ni cambia la clave', () => {
  const { ctx, propsScript } = entorno();
  sinHojaAbierta(ctx);
  // Google deja llamar desde el navegador (google.script.run) toda función cuyo nombre no termine en _
  const publicas = Object.keys(ctx).filter((k) => typeof ctx[k] === 'function' && !k.endsWith('_'));
  assert.ok(publicas.includes('cambiarClave') && publicas.includes('obtenerDatos'));
  for (const nombre of publicas) {
    let resultado;
    try {
      resultado = ctx[nombre]('clave-equivocada');
    } catch (error) {
      resultado = String(error && error.message);
    }
    assert.ok(!JSON.stringify(resultado ?? '').includes(CLAVE), `${nombre} entrega la clave`);
    assert.equal(propsScript.get('CLAVE'), CLAVE, `${nombre} cambió la clave`);
  }
});

// ─── Tema claro / oscuro ───

test('el panel recibe el tema de KondID por el enlace y solo acepta claro u oscuro', () => {
  const { ctx } = entorno();
  const plantillas = [];
  ctx.HtmlService.createTemplateFromFile = () => {
    const p = { evaluate() { return { setTitle() { return this; }, addMetaTag() { return this; }, setXFrameOptionsMode() { return this; }, setWidth() { return this; }, setHeight() { return this; } }; } };
    plantillas.push(p);
    return p;
  };
  ctx.doGet({ parameter: { k: CLAVE, tema: 'oscuro' } });
  ctx.doGet({ parameter: { k: CLAVE, tema: 'claro' } });
  ctx.doGet({ parameter: { k: CLAVE, tema: '"><script>' } });
  ctx.doGet({ parameter: { k: CLAVE } });
  ctx.abrirPanel();
  // Sin tema en el enlace (panel abierto directo o desde la hoja) el panel usa lo que eligió la persona o el sistema
  assert.deepEqual(plantillas.map((p) => p.tema), ['oscuro', 'claro', '', '', '']);
});
