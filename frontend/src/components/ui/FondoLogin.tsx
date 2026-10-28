/**
 * Fondo del inicio de sesión: la lámina de seguridad de la cédula.
 *
 * Dirección: para quien revisa documentos de identidad todos los días; debe sentirse oficial, preciso y seguro.
 * Concepto: el papel de seguridad de un documento colombiano. Elemento propio: una roseta de guilloche (las
 * líneas entrelazadas de billetes y cédulas) detrás de la tarjeta de acceso, con un anillo de microimpresión,
 * y un haz de escáner (el lector del OCR) que la recorre cada tanto y deja la trama iluminada a su paso.
 *
 * Las dos capas giran muy despacio en sentidos opuestos, así el entrelazado cambia sin llamar la atención.
 * Cada capa es un SVG propio que gira entero: el navegador la dibuja una vez y solo la rota. El haz es una
 * ventana que baja con otra copia de la trama, más intensa, que sube a la misma velocidad: la copia queda
 * siempre encima de la original. Estilos y movimiento en .fondo-login (globals.css).
 *
 * Cada anillo se calcula una vez (ondas en coordenadas polares) y se repite rotado con <use>: el tejido denso
 * del guilloche sale de pocos trazos.
 */

const punto = (r: number, t: number) => `${(r * Math.cos(t)).toFixed(1)},${(r * Math.sin(t)).toFixed(1)}`;

// Onda alrededor de un círculo: r = radio + amplitud · sen(ondas · t)
const anillo = (radio: number, amplitud: number, ondas: number, puntosPorOnda: number) => {
  const total = ondas * puntosPorOnda;
  const puntos = Array.from({ length: total }, (_, i) => {
    const t = (i / total) * 2 * Math.PI;
    return punto(radio + amplitud * Math.sin(ondas * t), t);
  });
  return `M${puntos.join("L")}Z`;
};

// Pétalos de la roseta central: r = radio + amplitud · cos(lóbulos · t)
const roseta = (radio: number, amplitud: number, lobulos: number, puntosPorLobulo: number) => {
  const total = lobulos * puntosPorLobulo;
  const puntos = Array.from({ length: total }, (_, i) => {
    const t = (i / total) * 2 * Math.PI;
    return punto(radio + amplitud * Math.cos(lobulos * t), t);
  });
  return `M${puntos.join("L")}Z`;
};

const BORDE = anillo(452, 6, 72, 6);
const EXTERIOR = anillo(330, 26, 20, 16);
const MEDIO = anillo(250, 18, 28, 14);
const CENTRO = roseta(118, 54, 9, 28);

// Copias rotadas una fracción de onda: las líneas se cruzan en malla
const copias = (cantidad: number, ondas: number) =>
  Array.from({ length: cantidad }, (_, k) => (k * 360) / ondas / cantidad);
const GIROS_BORDE = copias(3, 72);
const GIROS_EXTERIOR = copias(10, 20);
const GIROS_MEDIO = copias(8, 28);
const GIROS_CENTRO = copias(6, 9);

// Microimpresión sobre un círculo de radio 412: el texto se estira lo justo para cerrar la vuelta
const RADIO_TEXTO = 412;
const LARGO_TEXTO = Math.round(2 * Math.PI * RADIO_TEXTO) - 14;
const MICROTEXTO = "REPÚBLICA DE COLOMBIA · DOCUMENTO DE IDENTIDAD · KONDID · ".repeat(7);

const VISTA = "-500 -500 1000 1000";

function Copias({ id, giros }: { id: string; giros: number[] }) {
  return giros.map((g) => <use key={g} href={`#${id}`} transform={`rotate(${g.toFixed(2)})`} />);
}

// Gira a la derecha: borde festoneado, anillo exterior y microimpresión
function CapaExterior({ conTexto = false }: { conTexto?: boolean }) {
  return (
    <svg className="fondo-login-capa fondo-login-giro" viewBox={VISTA} focusable="false">
      {conTexto && (
        <defs>
          <path id="fl-anillo-texto" d={`M0,-${RADIO_TEXTO} A${RADIO_TEXTO},${RADIO_TEXTO} 0 1,1 -0.1,-${RADIO_TEXTO}`} />
        </defs>
      )}
      <Copias id="fl-borde" giros={GIROS_BORDE} />
      <Copias id="fl-exterior" giros={GIROS_EXTERIOR} />
      <circle r="392" className="fondo-login-punteado" />
      {conTexto && (
        <text className="fondo-login-microtexto">
          <textPath href="#fl-anillo-texto" textLength={LARGO_TEXTO} lengthAdjust="spacing">
            {MICROTEXTO}
          </textPath>
        </text>
      )}
    </svg>
  );
}

// Gira a la izquierda: anillo medio y roseta central
function CapaInterior() {
  return (
    <svg className="fondo-login-capa fondo-login-giro-inverso" viewBox={VISTA} focusable="false">
      <Copias id="fl-medio" giros={GIROS_MEDIO} />
      <Copias id="fl-centro" giros={GIROS_CENTRO} />
      <circle r="34" />
      <circle r="40" className="fondo-login-punteado" />
    </svg>
  );
}

export default function FondoLogin() {
  return (
    <div className="fondo-login" aria-hidden="true">
      <svg width="0" height="0" className="absolute" focusable="false">
        <defs>
          <path id="fl-borde" d={BORDE} />
          <path id="fl-exterior" d={EXTERIOR} />
          <path id="fl-medio" d={MEDIO} />
          <path id="fl-centro" d={CENTRO} />
        </defs>
      </svg>
      <div className="fondo-login-roseta">
        <CapaExterior conTexto />
        <CapaInterior />
        <div className="fondo-login-escaner">
          <div className="fondo-login-escaner-trama">
            <CapaExterior />
            <CapaInterior />
          </div>
          <div className="fondo-login-haz" />
        </div>
      </div>
    </div>
  );
}
