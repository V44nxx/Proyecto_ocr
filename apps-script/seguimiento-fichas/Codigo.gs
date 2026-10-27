/**
 * Panel de Seguimiento de fichas que KondID muestra incrustado (apartado «Seguimiento de fichas»).
 *
 * Va pegado a la hoja «FORMACIONES COMPLEMENTARIAS GRUPOS» (Extensiones → Apps Script) y lee sus pestañas
 * REGULADA, PV, CAMPESENA y TECNOACADEMIA. Las columnas se buscan por su título, no por su letra: si alguien
 * inserta o mueve una columna el panel sigue funcionando.
 *
 * - Un registro es una fila con programa, requerimiento, ficha o instructor (una solicitud nueva puede no tener
 *   programa todavía). En REGULADA cada registro ocupa 3 filas combinadas; el valor de una celda combinada vive
 *   en su primera fila, que es donde se lee y se escribe.
 * - Desde el panel solo se editan las columnas de seguimiento (estado, inscritos, matriculados, observaciones...).
 * - Cada registro trae su etapa según las fechas (por iniciar, en ejecución, por finalizar...) y sus alertas
 *   (sin ficha, sin instructor, cruce de instructor, datos distintos entre pestañas). Viene del antiguo Motor.gs.
 * - Cada cambio en la hoja (desde el panel o a mano) sube un número de versión; el panel lo consulta cada pocos
 *   segundos y se recarga solo cuando cambió, así lo que se escribe en la hoja aparece enseguida en KondID.
 * - La aplicación web se publica para «Cualquier persona»: por eso cada llamada exige la clave que va en el
 *   enlace (?k=...). Sin esa clave no se ve ni se edita nada.
 */

var HOJAS = ['REGULADA', 'PV', 'CAMPESENA', 'TECNOACADEMIA'];
var FILAS_ENCABEZADO = 10;
var HOJA_BITACORA = 'BITACORA_PANEL';
// Una fila es un registro si tiene alguno de estos. No se usan radicado ni empresa: al pie de PV hay firmas
// («Vo.Bo. Coordinación») que caen en esas columnas.
var CAMPOS_REGISTRO = ['programa', 'requerimiento', 'ficha', 'instructor'];

// alias: títulos posibles de la columna ya normalizados (ver normalizar). Gana el primer alias que aparezca.
var CAMPOS = {
  programa: { titulo: 'Programa', alias: ['NOMBRE DEL PROGRAMA', 'PROGRAMA DE FORMACION'] },
  requerimiento: { titulo: 'Requerimiento', alias: ['REQUERIMIENTO'] },
  codigo: { titulo: 'Código del programa', alias: ['CODIGO', 'CODIGO DEL PROGRAMA'] },
  ficha: { titulo: 'Ficha', alias: ['CODIGO DE FICHA', 'NO FICHA', 'FICHA'] },
  oferta: { titulo: 'Oferta / código de empresa', alias: ['CODIGO DE EMPRESA', 'NO OFERTA'] },
  instructor: {
    titulo: 'Instructor',
    alias: ['NOMBRE DEL INSTRUCTOR', 'INSTRUCTOR RESPONSABLE', 'INSTRUCTOR RESPONSABLE FACILITADOR'],
  },
  empresa: { titulo: 'Empresa', alias: ['EMPRESA'] },
  municipio: { titulo: 'Municipio', alias: ['MUNICIPIO', 'MUNICIPIO Y/O EMPRESA'] },
  radicado: { titulo: 'Radicado', alias: ['NUMERO DE RADICADO', 'RADICADO'] },
  area: { titulo: 'Área', alias: ['AREA'] },
  mes: { titulo: 'Mes', alias: ['MES'] },
  inicio: { titulo: 'Fecha de inicio', alias: ['FECHA DE INICIO', 'FECHA INICIO'], tipo: 'fecha' },
  fin: { titulo: 'Fecha de terminación', alias: ['FECHA DE TERMINACION', 'FECHA FIN'], tipo: 'fecha' },
  horas: { titulo: 'Horas', alias: ['TOTAL HORAS CURSO', 'HORAS'] },
  cupo: { titulo: 'Cupo', alias: ['CUPO', 'CUPOS'] },
  horario: { titulo: 'Horario', alias: ['HORARIO', 'HORARIO INICIO Y FIN'] },
  programacion: { titulo: 'Programación ficha', alias: ['PROGRAMACION FICHA'], editable: true },
  estadoFicha: { titulo: 'Estado de la ficha', alias: ['ESTADO DE LA FICHA'], editable: true },
  estadoAprendices: { titulo: 'Estado de los aprendices', alias: ['ESTADO DE LOS APRENDICES'], editable: true },
  fechaPublicacion: { titulo: 'Fecha de publicación', alias: ['FECHA PUBLICACION'], tipo: 'fecha', editable: true },
  inscritos: { titulo: 'N° de inscritos', alias: ['N DE INSCRITOS', 'NO DE INSCRITOS'], tipo: 'numero', editable: true },
  matriculados: {
    titulo: 'N° de matriculados', alias: ['N DE MATRICULADOS', 'NO DE MATRICULADOS'], tipo: 'numero', editable: true,
  },
  certificacion: { titulo: 'Certificación', alias: ['CERTIFICACION'], editable: true },
  noAprobados: { titulo: 'No aprobados u otra novedad', alias: ['NO APROBADOS U OTRA NOVEDAD'], editable: true },
  observaciones: { titulo: 'Observaciones', alias: ['OBSERVACIONES', 'OBSERVACION'], editable: true, largo: true },
};

// Sugerencias para los campos de texto; el panel también ofrece los valores que ya hay en la hoja
var OPCIONES = {
  programacion: ['CARGAR', 'CARGADA'],
  estadoFicha: ['CREADA', 'PUBLICADA', 'EN EJECUCIÓN', 'TERMINADA', 'CANCELADA'],
  estadoAprendices: ['EN FORMACIÓN', 'POR CERTIFICAR', 'CERTIFICADOS', 'RETIRADOS'],
  certificacion: ['SI', 'NO', 'EN PROCESO'],
};

// ─── Aplicación web ──────────────────────────────────────────────────────

function doGet(e) {
  var clave = claveGuardada_();
  if (!clave) {
    return pagina_('Falta configurar el panel: en el editor de Apps Script ejecuta la función «configurar».');
  }
  if (!e || !e.parameter || e.parameter.k !== clave) {
    return pagina_('Enlace incompleto: copia en KondID la URL del panel con su clave (termina en ?k=...).');
  }
  var plantilla = HtmlService.createTemplateFromFile('Index');
  plantilla.clave = clave;
  return plantilla.evaluate()
    .setTitle('Seguimiento de fichas')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1')
    // Sin esto el navegador no deja mostrar el panel dentro de KondID
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function pagina_(mensaje) {
  return HtmlService.createHtmlOutput(
    '<p style="font-family:system-ui,sans-serif;color:#475569;padding:24px">' + mensaje + '</p>'
  ).setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

/** Todos los registros de las 4 hojas, con lo necesario para pintar y editar el panel. */
function obtenerDatos(clave) {
  verificarClave_(clave);
  var libro = SpreadsheetApp.getActiveSpreadsheet();
  var hojas = [];
  var registros = [];
  HOJAS.forEach(function (nombre) {
    var hoja = hojaPorNombre_(libro, nombre);
    if (!hoja) {
      hojas.push({ nombre: nombre, total: 0, editables: [], aviso: 'No se encontró la pestaña' });
      return;
    }
    var leida = leerHoja_(hoja);
    hojas.push({ nombre: nombre, total: leida.registros.length, editables: leida.editables, aviso: leida.aviso });
    registros = registros.concat(leida.registros);
  });

  var campos = {};
  var opciones = {};
  Object.keys(CAMPOS).forEach(function (k) {
    var def = CAMPOS[k];
    campos[k] = { titulo: def.titulo, tipo: def.tipo || 'texto', editable: !!def.editable, largo: !!def.largo };
    if (def.editable && campos[k].tipo === 'texto') {
      var vistos = {};
      (OPCIONES[k] || []).concat(registros.map(function (r) { return r.campos[k]; })).forEach(function (v) {
        if (v && String(v).length <= 40) vistos[String(v).toUpperCase()] = String(v);
      });
      opciones[k] = Object.keys(vistos).map(function (x) { return vistos[x]; });
    }
  });

  calcularEtapas_(registros, fechaIso_(new Date()));
  return {
    hojas: hojas, registros: registros, campos: campos, opciones: opciones, etapas: ETAPAS, alertas: ALERTAS,
    version: versionActual_(),
  };
}

/** Número que cambia cada vez que alguien edita la hoja; el panel lo consulta para saber si debe recargar. */
function obtenerVersion(clave) {
  verificarClave_(clave);
  return versionActual_();
}

/**
 * Guarda los campos de seguimiento de un registro.
 * cambios = { campo: { anterior: 'lo que el panel mostraba', nuevo: 'valor nuevo' } }
 * Si otra persona cambió el mismo campo mientras tanto, no se pisa: se devuelve el conflicto y el registro actual.
 */
function guardar(clave, id, huella, cambios) {
  verificarClave_(clave);
  var partes = String(id).split('!');
  var nombre = partes[0];
  var fila = Number(partes[1]);
  if (HOJAS.indexOf(nombre) < 0 || !(fila >= 1)) throw new Error('Registro no válido');

  var candado = LockService.getDocumentLock() || LockService.getScriptLock();
  candado.waitLock(15000);
  try {
    var hoja = hojaPorNombre_(SpreadsheetApp.getActiveSpreadsheet(), nombre);
    if (!hoja) throw new Error('No se encontró la pestaña ' + nombre);
    var ultimaColumna = hoja.getLastColumn();
    var mapa = mapearColumnas_(
      hoja.getRange(1, 1, Math.min(FILAS_ENCABEZADO, hoja.getLastRow()), ultimaColumna).getDisplayValues()
    ).mapa;
    var actual = leerFila_(hoja, fila, mapa, ultimaColumna);
    if (!actual || actual.huella !== huella) {
      throw new Error('El registro cambió de lugar en la hoja (se insertaron o borraron filas). Recarga el panel.');
    }

    var conflictos = [];
    var escribir = [];
    Object.keys(cambios || {}).forEach(function (campo) {
      var def = CAMPOS[campo];
      if (!def || !def.editable || !mapa[campo]) throw new Error('El campo «' + campo + '» no se puede editar aquí');
      var cambio = cambios[campo] || {};
      if (comparable_(actual.campos[campo]) !== comparable_(cambio.anterior)) {
        conflictos.push({ campo: campo, titulo: def.titulo, actual: actual.campos[campo] });
      } else if (comparable_(cambio.nuevo) !== comparable_(cambio.anterior)) {
        escribir.push({ campo: campo, columna: mapa[campo].columna, valor: valorParaHoja_(cambio.nuevo, def.tipo) });
      }
    });
    if (conflictos.length) return { ok: false, conflictos: conflictos, registro: actual };

    escribir.forEach(function (c) {
      hoja.getRange(fila, c.columna + 1).setValue(c.valor);
    });
    if (escribir.length) {
      anotarBitacora_(nombre, fila, actual, escribir, cambios);
      SpreadsheetApp.flush();
      subirVersion_();
    }
    return { ok: true, registro: leerFila_(hoja, fila, mapa, ultimaColumna), version: versionActual_() };
  } finally {
    candado.releaseLock();
  }
}

// ─── Lectura de las hojas ────────────────────────────────────────────────

function hojaPorNombre_(libro, nombre) {
  // Exacto: hay una copia oculta que se llama «TECNOACADEMIA » (con espacio) y no debe leerse
  var hoja = libro.getSheetByName(nombre);
  return hoja && !hoja.isSheetHidden() ? hoja : null;
}

function normalizar(texto) {
  return String(texto == null ? '' : texto)
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toUpperCase()
    .replace(/[^A-Z0-9/]+/g, ' ')
    .trim();
}

/** Busca cada campo por su título en las primeras filas. Los datos empiezan debajo del título más bajo. */
function mapearColumnas_(encabezado) {
  var mapa = {};
  var usadas = {};
  var filaMaxima = -1;
  var normal = encabezado.map(function (fila) { return fila.map(normalizar); });
  Object.keys(CAMPOS).forEach(function (campo) {
    CAMPOS[campo].alias.some(function (alias) {
      for (var c = 0; c < (normal[0] || []).length; c++) {
        if (usadas[c]) continue;
        for (var f = 0; f < normal.length; f++) {
          if (normal[f][c] === alias) {
            mapa[campo] = { columna: c, fila: f };
            usadas[c] = true;
            filaMaxima = Math.max(filaMaxima, f);
            return true;
          }
        }
      }
      return false;
    });
  });
  return { mapa: mapa, primeraFilaDatos: filaMaxima + 1 };
}

function leerHoja_(hoja) {
  var ultimaFila = hoja.getLastRow();
  var ultimaColumna = hoja.getLastColumn();
  if (ultimaFila < 1 || ultimaColumna < 1) return { registros: [], editables: [], aviso: 'La pestaña está vacía' };
  var rango = hoja.getRange(1, 1, ultimaFila, ultimaColumna);
  var valores = rango.getValues();
  var textos = rango.getDisplayValues();
  var mapeo = mapearColumnas_(textos.slice(0, FILAS_ENCABEZADO));
  var mapa = mapeo.mapa;
  var editables = Object.keys(mapa).filter(function (k) { return CAMPOS[k].editable; });
  if (!mapa.programa) {
    return { registros: [], editables: editables, aviso: 'No se encontró la columna del nombre del programa' };
  }
  var registros = [];
  for (var f = mapeo.primeraFilaDatos; f < textos.length; f++) {
    var registro = registroDe_(hoja.getName(), f + 1, valores[f], textos[f], mapa);
    if (registro) registros.push(registro);
  }
  return { registros: registros, editables: editables, aviso: '' };
}

function leerFila_(hoja, fila, mapa, ultimaColumna) {
  if (fila > hoja.getLastRow()) return null;
  var rango = hoja.getRange(fila, 1, 1, ultimaColumna);
  return registroDe_(hoja.getName(), fila, rango.getValues()[0], rango.getDisplayValues()[0], mapa);
}

function registroDe_(nombreHoja, fila, valores, textos, mapa) {
  var campos = {};
  Object.keys(mapa).forEach(function (campo) {
    var c = mapa[campo].columna;
    campos[campo] = formatear_(valores[c], textos[c], CAMPOS[campo]);
  });
  var esRegistro = CAMPOS_REGISTRO.some(function (k) { return campos[k]; });
  if (!esRegistro) return null;
  return {
    id: nombreHoja + '!' + fila,
    hoja: nombreHoja,
    fila: fila,
    // Lo que identifica al registro: si no coincide al guardar, la fila ya no es la misma (se insertaron filas)
    huella: [campos.programa, campos.requerimiento, campos.instructor].map(normalizar).join('|'),
    campos: campos,
  };
}

function formatear_(valor, texto, def) {
  if (def.tipo === 'fecha') {
    if (Object.prototype.toString.call(valor) === '[object Date]' && !isNaN(valor)) return fechaIso_(valor);
    return limpiar_(texto);
  }
  if (def.tipo === 'numero' && typeof valor === 'number') return String(valor);
  // Las observaciones conservan sus saltos de línea; el resto se muestra en una sola línea
  return def.largo ? String(texto == null ? '' : texto).trim() : limpiar_(texto);
}

function limpiar_(texto) {
  return String(texto == null ? '' : texto).replace(/\s+/g, ' ').trim();
}

function comparable_(valor) {
  return limpiar_(valor).toUpperCase();
}

function fechaIso_(fecha) {
  var dos = function (n) { return (n < 10 ? '0' : '') + n; };
  return fecha.getFullYear() + '-' + dos(fecha.getMonth() + 1) + '-' + dos(fecha.getDate());
}

function valorParaHoja_(valor, tipo) {
  var texto = String(valor == null ? '' : valor).trim();
  if (!texto) return '';
  if (tipo === 'fecha') {
    var p = /^(\d{4})-(\d{2})-(\d{2})$/.exec(texto);
    if (!p) throw new Error('Fecha no válida: ' + texto);
    return new Date(Number(p[1]), Number(p[2]) - 1, Number(p[3]));
  }
  if (tipo === 'numero') {
    var n = Number(texto.replace(',', '.'));
    if (isNaN(n) || n < 0) throw new Error('Número no válido: ' + texto);
    return n;
  }
  return texto;
}

// ─── Etapas y alertas (antes en Motor.gs) ────────────────────────────────

var DIAS_POR_INICIAR = 7;
var DIAS_POR_FINALIZAR = 3;

// orden: cómo se ordena la lista (lo más urgente arriba)
var ETAPAS = {
  INICIA_HOY: { etiqueta: 'Inicia hoy', color: '#1D4ED8', fondo: '#DBEAFE', orden: 1 },
  POR_INICIAR: { etiqueta: 'Por iniciar', color: '#B45309', fondo: '#FEF3C7', orden: 2 },
  POR_FINALIZAR: { etiqueta: 'Por finalizar', color: '#C2410C', fondo: '#FFEDD5', orden: 3 },
  EN_EJECUCION: { etiqueta: 'En ejecución', color: '#15803D', fondo: '#DCFCE7', orden: 4 },
  PROGRAMADA: { etiqueta: 'Programada', color: '#475569', fondo: '#F1F5F9', orden: 5 },
  FINALIZADA: { etiqueta: 'Finalizada', color: '#374151', fondo: '#E5E7EB', orden: 6 },
  FECHAS_INVALIDAS: { etiqueta: 'Fechas inválidas', color: '#B91C1C', fondo: '#FEE2E2', orden: 7 },
  SIN_FECHAS: { etiqueta: 'Fecha faltante o ilegible', color: '#B91C1C', fondo: '#FEE2E2', orden: 8 },
};

var ALERTAS = {
  SIN_FICHA: { etiqueta: 'Ficha sin crear / sin código', color: '#9F1239', fondo: '#FFE4E6' },
  SIN_INSTRUCTOR: { etiqueta: 'Sin instructor', color: '#9F1239', fondo: '#FFE4E6' },
  CRUCE_INSTRUCTOR: { etiqueta: 'Cruce de instructor', color: '#A16207', fondo: '#FEF9C3' },
  INCONSISTENCIA: { etiqueta: 'Datos distintos entre pestañas', color: '#7E22CE', fondo: '#F3E8FF' },
};

/** Agrega a cada registro su etapa (según la fecha de hoy, 'AAAA-MM-DD') y sus alertas. */
function calcularEtapas_(registros, hoy) {
  registros.forEach(function (r) {
    var c = r.campos;
    var inicio = aIso_(c.inicio);
    var fin = aIso_(c.fin);
    var etapa;
    var dias = null;
    if (!inicio || !fin) etapa = 'SIN_FECHAS';
    else if (fin < inicio) etapa = 'FECHAS_INVALIDAS';
    else if (hoy < inicio) { dias = diasEntre_(hoy, inicio); etapa = dias <= DIAS_POR_INICIAR ? 'POR_INICIAR' : 'PROGRAMADA'; }
    else if (hoy === inicio) { dias = 0; etapa = 'INICIA_HOY'; }
    else if (hoy <= fin) { dias = diasEntre_(hoy, fin); etapa = dias <= DIAS_POR_FINALIZAR ? 'POR_FINALIZAR' : 'EN_EJECUCION'; }
    else { dias = diasEntre_(fin, hoy); etapa = 'FINALIZADA'; }
    r.etapa = etapa;
    r.detalleEtapa = detalleEtapa_(etapa, dias, c, inicio, fin);
    r.inicioIso = inicio;
    r.finIso = fin;
    r.alertas = [];
    if (!c.ficha) r.alertas.push('SIN_FICHA');
    if (!c.instructor) r.alertas.push('SIN_INSTRUCTOR');
  });
  marcarInconsistencias_(registros);
  marcarCruces_(registros);
  return registros;
}

/** Fecha ISO de lo que muestra el panel: ya viene ISO si la celda es fecha; si no, se intenta leer el texto. */
function aIso_(texto) {
  var s = String(texto || '').trim();
  var m = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(s);
  if (m) return +m[1] >= 2000 && +m[1] <= 2100 ? m[1] + '-' + dos_(+m[2]) + '-' + dos_(+m[3]) : '';
  m = /^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})$/.exec(s); // 01/10/2026 (día/mes/año)
  if (!m) return '';
  var anio = +m[3] < 100 ? +m[3] + 2000 : +m[3];
  if (anio < 2000 || anio > 2100) return ''; // p. ej. 8/10/0206
  var dia = +m[1];
  var mes = +m[2];
  if (mes > 12 && dia <= 12) { var t = dia; dia = mes; mes = t; } // 10/19/2026 (mes/día/año)
  return mes >= 1 && mes <= 12 && dia >= 1 && dia <= 31 ? anio + '-' + dos_(mes) + '-' + dos_(dia) : '';
}

function dos_(n) {
  return (n < 10 ? '0' : '') + n;
}

function diasEntre_(a, b) {
  var utc = function (x) { return Date.UTC(+x.slice(0, 4), +x.slice(5, 7) - 1, +x.slice(8, 10)); };
  return Math.round((utc(b) - utc(a)) / 86400000);
}

function detalleEtapa_(etapa, d, c, inicio, fin) {
  switch (etapa) {
    case 'SIN_FECHAS':
      var partes = [];
      if (!inicio) partes.push(c.inicio ? 'inicio ilegible («' + c.inicio + '»)' : 'falta inicio');
      if (!fin) partes.push(c.fin ? 'fin ilegible («' + c.fin + '»)' : 'falta fin');
      return partes.join(' · ');
    case 'FECHAS_INVALIDAS': return 'La fecha fin es anterior al inicio';
    case 'POR_INICIAR': return d === 1 ? 'Inicia mañana' : 'Inicia en ' + d + ' días';
    case 'PROGRAMADA': return 'Inicia en ' + d + ' días';
    case 'INICIA_HOY': return 'Inicia hoy';
    case 'POR_FINALIZAR': return d === 0 ? 'Finaliza hoy' : d === 1 ? 'Finaliza mañana' : 'Finaliza en ' + d + ' días';
    case 'EN_EJECUCION': return 'Faltan ' + d + ' días';
    case 'FINALIZADA': return d === 1 ? 'Finalizó ayer' : 'Finalizó hace ' + d + ' días';
  }
  return '';
}

/** La misma ficha en dos pestañas con fechas o instructor distintos. */
function marcarInconsistencias_(registros) {
  var porFicha = {};
  registros.forEach(function (r) {
    if (r.campos.ficha) (porFicha[r.campos.ficha] = porFicha[r.campos.ficha] || []).push(r);
  });
  Object.keys(porFicha).forEach(function (ficha) {
    var grupo = porFicha[ficha];
    grupo.forEach(function (r) {
      var notas = [];
      grupo.forEach(function (otro) {
        if (otro === r) return;
        var donde = ' en ' + otro.hoja + ' (fila ' + otro.fila + ')';
        if (r.inicioIso && otro.inicioIso && r.inicioIso !== otro.inicioIso) notas.push('Inicio ' + otro.inicioIso + donde);
        if (r.finIso && otro.finIso && r.finIso !== otro.finIso) notas.push('Fin ' + otro.finIso + donde);
        if (r.campos.instructor && otro.campos.instructor && !mismoInstructor_(r.campos.instructor, otro.campos.instructor)) {
          notas.push('Instructor «' + otro.campos.instructor + '»' + donde);
        }
      });
      if (notas.length) {
        r.alertas.push('INCONSISTENCIA');
        r.inconsistencias = notas;
      }
    });
  });
}

function mismoInstructor_(a, b) {
  var palabras = function (x) { return normalizar(x).split(' ').filter(function (t) { return t.length > 2; }); };
  var ta = palabras(a);
  var tb = palabras(b);
  if (!ta.length || !tb.length) return true;
  var comunes = ta.filter(function (t) { return tb.indexOf(t) >= 0; }).length;
  return comunes >= Math.min(2, ta.length, tb.length);
}

/** Un instructor con dos formaciones activas o próximas cuyas fechas se solapan. */
function marcarCruces_(registros) {
  var porInstructor = {};
  registros.forEach(function (r) {
    if (!r.campos.instructor || !r.inicioIso || !r.finIso) return;
    if (r.etapa === 'FINALIZADA' || r.etapa === 'FECHAS_INVALIDAS') return;
    var k = normalizar(r.campos.instructor);
    (porInstructor[k] = porInstructor[k] || []).push(r);
  });
  Object.keys(porInstructor).forEach(function (k) {
    var lista = porInstructor[k];
    for (var i = 0; i < lista.length; i++) {
      for (var j = i + 1; j < lista.length; j++) {
        var a = lista[i];
        var b = lista[j];
        // La misma ficha repetida en dos pestañas no es un cruce
        if (a.campos.ficha && a.campos.ficha === b.campos.ficha) continue;
        if (a.inicioIso <= b.finIso && b.inicioIso <= a.finIso) {
          anotarCruce_(a, b);
          anotarCruce_(b, a);
        }
      }
    }
  });
}

function anotarCruce_(r, otro) {
  if (r.alertas.indexOf('CRUCE_INSTRUCTOR') < 0) r.alertas.push('CRUCE_INSTRUCTOR');
  (r.cruces = r.cruces || []).push(
    (otro.campos.programa || otro.campos.requerimiento) + ' · ' + (otro.campos.ficha || 'sin ficha') +
    ' (' + otro.inicioIso + ' a ' + otro.finIso + ', ' + otro.hoja + ')'
  );
}

// ─── Versión, clave y bitácora ───────────────────────────────────────────

function versionActual_() {
  return PropertiesService.getDocumentProperties().getProperty('version') || '0';
}

function subirVersion_() {
  PropertiesService.getDocumentProperties().setProperty('version', String(Date.now()));
}

/** Se ejecuta solo cada vez que alguien edita una celda a mano. */
function onEdit() {
  subirVersion_();
}

/** Disparador instalable (ver instalarDisparadores): cubre filas insertadas o borradas, pegados grandes, etc. */
function alCambiar() {
  subirVersion_();
}

function claveGuardada_() {
  return PropertiesService.getScriptProperties().getProperty('CLAVE');
}

function verificarClave_(clave) {
  var guardada = claveGuardada_();
  if (!guardada || clave !== guardada) throw new Error('Acceso denegado');
}

function anotarBitacora_(nombreHoja, fila, registro, escritos, cambios) {
  var libro = SpreadsheetApp.getActiveSpreadsheet();
  var bitacora = libro.getSheetByName(HOJA_BITACORA);
  if (!bitacora) {
    bitacora = libro.insertSheet(HOJA_BITACORA);
    bitacora.appendRow(['Fecha', 'Pestaña', 'Fila', 'Ficha', 'Programa', 'Campo', 'Antes', 'Después']);
    bitacora.hideSheet();
  }
  escritos.forEach(function (e) {
    bitacora.appendRow([
      new Date(), nombreHoja, fila, registro.campos.ficha || '', registro.campos.programa || registro.campos.requerimiento,
      CAMPOS[e.campo].titulo, cambios[e.campo].anterior || '', cambios[e.campo].nuevo || '',
    ]);
  });
}

// ─── Menú en la hoja y puesta en marcha ──────────────────────────────────

/** Se ejecuta solo al abrir la hoja: agrega el menú «Seguimiento de fichas» junto a «Ayuda». */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Seguimiento de fichas')
    .addItem('Abrir panel', 'abrirPanel')
    .addItem('Ver enlace para KondID', 'mostrarEnlace')
    .addSeparator()
    .addItem('Configurar (primera vez)', 'configurar')
    .addItem('Cambiar la clave del enlace', 'cambiarClave')
    .addToUi();
}

/** Abre el mismo panel de KondID en una ventana encima de la hoja. */
function abrirPanel() {
  var ui = SpreadsheetApp.getUi();
  var clave = claveGuardada_();
  if (!clave) {
    ui.alert('Primero elige «Seguimiento de fichas → Configurar (primera vez)».');
    return;
  }
  var plantilla = HtmlService.createTemplateFromFile('Index');
  plantilla.clave = clave;
  ui.showModelessDialog(plantilla.evaluate().setWidth(1200).setHeight(760), 'Seguimiento de fichas');
}

/** Muestra el enlace con la clave para pegarlo en KondID. */
function mostrarEnlace() {
  var ui = SpreadsheetApp.getUi();
  var clave = claveGuardada_();
  if (!clave) {
    ui.alert('Primero elige «Seguimiento de fichas → Configurar (primera vez)».');
    return;
  }
  ui.alert('Enlace para KondID', textoEnlace_(clave), ui.ButtonSet.OK);
}

function textoEnlace_(clave) {
  var url = ScriptApp.getService().getUrl();
  if (!url || !/\/exec$/.test(url)) {
    return 'El panel todavía no está publicado. En Extensiones → Apps Script: Implementar → Nueva implementación → ' +
      'Aplicación web (ejecutar como «Yo», acceso «Cualquier persona»). Luego pega en KondID la URL que termina en ' +
      '/exec seguida de:\n\n?k=' + clave;
  }
  return 'Copia este enlace y pégalo en KondID → Seguimiento de fichas → Configurar:\n\n' + url + '?k=' + clave;
}

/** Crea la clave del enlace (si no existe) y los disparadores. Se hace una vez antes de publicar. */
function configurar() {
  var propiedades = PropertiesService.getScriptProperties();
  if (!propiedades.getProperty('CLAVE')) {
    propiedades.setProperty('CLAVE', Utilities.getUuid().replace(/-/g, ''));
  }
  instalarDisparadores();
  subirVersion_();
  var mensaje = textoEnlace_(claveGuardada_());
  Logger.log(mensaje);
  try {
    SpreadsheetApp.getUi().alert('Panel configurado', mensaje, SpreadsheetApp.getUi().ButtonSet.OK);
  } catch (e) {
    // Ejecutado desde el editor de Apps Script: el mensaje queda en el registro de ejecución
  }
}

/** Cambia la clave: los enlaces viejos dejan de funcionar y hay que actualizar el enlace en KondID. */
function cambiarClave() {
  try {
    var ui = SpreadsheetApp.getUi();
    var respuesta = ui.alert('¿Cambiar la clave?', 'El enlace actual deja de funcionar y habrá que pegar el nuevo en KondID.',
      ui.ButtonSet.YES_NO);
    if (respuesta !== ui.Button.YES) return;
  } catch (e) {
    // Ejecutado desde el editor: no hay a quién preguntar
  }
  PropertiesService.getScriptProperties().deleteProperty('CLAVE');
  configurar();
}

function instalarDisparadores() {
  var existe = ScriptApp.getProjectTriggers().some(function (t) { return t.getHandlerFunction() === 'alCambiar'; });
  if (!existe) {
    ScriptApp.newTrigger('alCambiar').forSpreadsheet(SpreadsheetApp.getActiveSpreadsheet()).onChange().create();
  }
}
