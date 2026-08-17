"""
Servicio Geográfico Universal de Colombia (DANE / DIVIPOLA).
Cubre los 32 Departamentos y más de 1.100 Municipios de Colombia.
Proporciona extracción, desambiguación Municipio vs Departamento y corrección Fuzzy por OCR.
"""
import re
import unicodedata
from typing import Optional, Tuple, Set, Dict, List
from rapidfuzz import process, fuzz

from app.utils.logger import app_logger as logger


class ColombiaGeoService:
    """
    Servicio universal para identificación, validación y normalización
    de municipios y departamentos colombianos en documentos oficiales.
    """

    DEPARTAMENTOS: Set[str] = {
        "AMAZONAS", "ANTIOQUIA", "ARAUCA", "ATLANTICO", "ATLÁNTICO", "BOLIVAR", "BOLÍVAR",
        "BOYACA", "BOYACÁ", "CALDAS", "CAQUETA", "CAQUETÁ", "CASANARE", "CAUCA", "CESAR",
        "CHOCO", "CHOCÓ", "CORDOBA", "CÓRDOBA", "CUNDINAMARCA", "GUAINIA", "GUAINÍA",
        "GUAVIARE", "HUILA", "LA GUAJIRA", "GUAJIRA", "MAGDALENA", "META", "NARIÑO",
        "NORTE DE SANTANDER", "PUTUMAYO", "QUINDIO", "QUINDÍO", "RISARALDA",
        "SAN ANDRES Y PROVIDENCIA", "SAN ANDRES", "SAN ANDRÉS", "SANTANDER", "SUCRE",
        "TOLIMA", "VALLE DEL CAUCA", "VALLE", "VAUPES", "VAUPÉS", "VICHADA"
    }

    # Catálogo integral de municipios de Colombia (orden alfabético por departamentos)
    MUNICIPIOS: List[str] = [
        # Capital y Distritos Especiales
        "BOGOTA D.C.", "BOGOTA", "MEDELLIN", "CALI", "BARRANQUILLA", "CARTAGENA", "SANTA MARTA",
        "BUENAVENTURA", "TUMACO", "BARRANCABERMEJA", "RIOHACHA", "CUCUTA", "BUCARAMANGA",
        # Amazonas
        "LETICIA", "PUERTO NARIÑO", "EL ENCANTO", "LA CHORRERA", "LA PEDRERA", "LA VICTORIA",
        "MIRITI - PARANA", "PUERTO ALEGRIA", "PUERTO ARICA", "PUERTO SANTANDER", "TARAPACA",
        # Antioquia
        "ABEJORRAL", "ABRIAQUI", "ALEJANDRIA", "AMAGA", "AMALFI", "ANDES", "ANGELOPOLIS",
        "ANGOSTURA", "ANORI", "SANTAFE DE ANTIOQUIA", "ANZA", "APARTADO", "ARBOLETES",
        "ARGELIA", "ARMENIA MANTEQUILLA", "BARBOSA", "BELMIRA", "BELLO", "BETANIA", "BETULIA",
        "CIUDAD BOLIVAR", "BRICEÑO", "BURITICA", "CACERES", "CAICEDO", "CALDAS", "CAMPAMENTO",
        "CAÑASGORDAS", "CARACOLI", "CARAMANTA", "CAREPA", "EL CARMEN DE VIBORAL", "CAROLINA",
        "CAUCASIA", "CHIGORODO", "CISNEROS", "COCORNA", "CONCEPCION", "CONCORDIA", "COPACABANA",
        "DABEIBA", "DONMATIAS", "EBEJICO", "EL BAGRE", "ENTRERRIOS", "ENVIGADO", "FREDONIA",
        "FRONTINO", "GIRALDO", "GIRARDOTA", "GOMEZ PLATA", "GRANADA", "GUADALUPE", "GUARNE",
        "GUATAPE", "HELICONIA", "HISPANIA", "ITAGÜI", "ITUANGO", "JARDIN", "JERICO", "LA CEJA",
        "LA ESTRELLA", "LA PINTADA", "LA UNION", "LIBORINA", "MACEO", "MARINILLA", "MONTEBELLO",
        "MURINDO", "MUTATA", "NARIÑO", "NECOCLI", "NECHI", "OLAYA", "PEÑOL", "PEQUE", "PUEBLORRICO",
        "PUERTO BERRIO", "PUERTO NARE", "PUERTO TRIUNFO", "REMEDIOS", "RETIRO", "RIONEGRO",
        "SABANALARGA", "SABANETA", "SALGAR", "SAN ANDRES DE CUERQUIA", "SAN CARLOS", "SAN FRANCISCO",
        "SAN JERONIMO", "SAN JOSE DE LA MONTAÑA", "SAN JUAN DE URABA", "SAN LUIS", "SAN PEDRO DE LOS MILAGROS",
        "SAN PEDRO DE URABA", "SAN RAFAEL", "SAN ROQUE", "SAN VICENTE FERRER", "SANTA BARBARA",
        "SANTA ROSA DE OSOS", "SANTO DOMINGO", "SEGOVIA", "SONSON", "SOPETRAN", "TAMESIS",
        "TARAZA", "TARSO", "TITIRIBI", "TOLEDO", "TURBO", "URAMITA", "URRAO", "VALDIVIA",
        "VALPARAISO", "VEGACHI", "VENECIA", "VIGIA DEL FUERTE", "YALI", "YARUMAL", "YOLOMBO",
        "YONDO", "ZARAGOZA",
        # Arauca
        "ARAUCA", "ARAUQUITA", "CRAVO NORTE", "FORTUL", "PUERTO RONDON", "SARAVENA", "TAME",
        # Atlántico
        "BARANOA", "CAMPO DE LA CRUZ", "CANDELARIA", "GALAPA", "JUAN DE ACOSTA", "LURUACO",
        "MALAMBO", "MANATI", "PALMAR DE VARELA", "PIOJO", "POLONUEVO", "PONEDERA", "PUERTO COLOMBIA",
        "REPELON", "SABANAGRANDE", "SABANALARGA", "SANTA LUCIA", "SANTO TOMAS", "SOLEDAD",
        "SUAN", "TUBARA", "USIACURI",
        # Bolívar
        "ACHI", "ALTOS DEL ROSARIO", "ARENAL", "ARJONA", "ARROYOHONDO", "CALAMAR", "CANTAGALLO",
        "CICUCO", "CORDOBA", "CLEMENCIA", "EL CARMEN DE BOLIVAR", "EL GUAMO", "EL PEÑON",
        "HATILLO DE LOBA", "MAGANGUE", "MAHATES", "MARGARITA", "MARIA LA BAJA", "MONTECRISTO",
        "MOMPOS", "MORALES", "NOROSI", "PINILLOS", "REGIDOR", "RIO VIEJO", "SAN CRISTOBAL",
        "SAN ESTANISLAO", "SAN FERNANDO", "SAN JACINTO", "SAN JACINTO DEL CAUCA", "SAN JUAN NEPOMUCENO",
        "SAN MARTIN DE LOBA", "SAN PABLO", "SANTA CATALINA", "SANTA ROSA", "SANTA ROSA DEL SUR",
        "SIMITI", "SOPLAVIENTO", "TALAIGUA NUEVO", "TIQUISIO", "TURBACO", "TURBANA", "VILLANUEVA",
        "ZAMBRANO",
        # Boyacá
        "TUNJA", "ALMEIDA", "AQUITANIA", "ARCABUCO", "BELEN", "BERBEO", "BETEITIVA", "BOAVITA",
        "BOYACA", "BRICEÑO", "BUENAVISTA", "BUSBANZA", "CALDAS", "CAMPOHERMOSO", "CERINZA",
        "CHINAVITA", "CHIQUINQUIRA", "CHISCAS", "CHITA", "CHITARAQUE", "CHIVATA", "CIENEGA",
        "COMBITA", "COPER", "CORRALES", "COVARACHIA", "CUBARA", "CUCAITA", "CUITIVA", "CHIVOR",
        "DUITAMA", "EL COCUY", "EL ESPINO", "FIRAVITOBA", "FLORESTA", "GACHANTIVA", "GAMEZA",
        "GARAGOA", "GUACAMAYAS", "GUATEQUE", "GUAYATA", "GÜICAN", "IZA", "JENESANO", "JERICO",
        "LABRANZAGRANDE", "LA CAPILLA", "LA VICTORIA", "LA UVITA", "VILLA DE LEYVA", "MACANAL",
        "MARIPI", "MIRAFLORES", "MONGUA", "MONGUI", "MONIQUIRA", "MOTAVITA", "MUZO", "NOBSA",
        "NUEVO COLON", "OICATA", "OTANCHE", "PACHAVITA", "PAEZ", "PAIPA", "PAJARITO", "PANQUEBA",
        "PAUNA", "PAYA", "PAZ DE RIO", "PESCA", "PISBA", "PUERTO BOYACA", "QUIPAMA", "RAMIRIQUI",
        "RAQUIRA", "RONDON", "SABOYA", "SACHICA", "SAMACA", "SAN EDUARDO", "SAN JOSE DE PARE",
        "SAN LUIS DE GACENO", "SAN MATEO", "SAN MIGUEL DE SEMA", "SAN PABLO DE BORBUR", "SANTANA",
        "SANTA MARIA", "SANTA ROSA DE VITERBO", "SANTA SOFIA", "SATIVANORTE", "SATIVASUR",
        "SIACHOQUE", "SOATA", "SOCOTA", "SOCHA", "SOGAMOSO", "SOMONDOCO", "SORA", "SOTAQUIRA",
        "SORACA", "SUSACON", "SUTAMARCHAN", "SUTATENZA", "TASCO", "TENZA", "TIBANA", "TIBASOSA",
        "TINJACA", "TIPACOQUE", "TOCA", "TOGÜI", "TOPAGA", "TOTA", "TUNUNGUA", "TURMEQUE",
        "TUTA", "TUTAZA", "UMBITA", "VENTAQUEMADA", "VIRACACHA", "ZETAQUIRA",
        # Caldas
        "MANIZALES", "AGUADAS", "ANSERMA", "ARANZAZU", "BELALCAZAR", "CHINCHINA", "FILADELFIA",
        "LA DORADA", "LA MERCED", "MANZANARES", "MARMATO", "MARQUETALIA", "MARULANDA", "NEIRA",
        "NORCASIA", "PACORA", "PALESTINA", "PENSILVANIA", "RIOSUCIO", "RISARALDA", "SALAMINA",
        "SAMANA", "SAN JOSE", "SUPIA", "VICTORIA", "VILLAMARIA", "VITERBO",
        # Caquetá
        "FLORENCIA", "ALBANIA", "BELEN DE LOS ANDAQUIES", "CARTAGENA DEL CHAIRA", "CURILLO",
        "EL DONCELLO", "EL PAUJIL", "LA MONTAÑITA", "MILAN", "MORELIA", "PUERTO RICO",
        "SAN JOSE DEL FRAGUA", "SAN VICENTE DEL CAGUAN", "SOLANO", "SOLITA", "VALPARAISO",
        # Casanare
        "YOPAL", "AGUAZUL", "CHAMEZA", "HATO COROZAL", "LA SALINA", "MANI", "MONTERREY",
        "NUNCHIA", "OROCUE", "PAZ DE ARIPORO", "PORE", "RECETOR", "SABANALARGA", "SACAMA",
        "SAN LUIS DE PALENQUE", "TAMARA", "TAURAMENA", "TRINIDAD", "VILLANUEVA",
        # Cauca
        "POPAYAN", "ALMAGUER", "ARGELIA", "BALBOA", "BOLIVAR", "BUENOS AIRES", "CAJIBIO",
        "CALDONO", "CALOTO", "CORINTO", "EL TAMBO", "FLORENCIA", "GUACHENE", "GUAPI", "INZA",
        "JAMBALO", "LA SIERRA", "LA VEGA", "LOPEZ DE MICAY", "MERCADERES", "MIRANDA", "MORALES",
        "PADILLA", "PAEZ", "PATIA", "PIAMONTE", "PIENDAMO", "PUERTO TEJADA", "PURACE", "ROSAS",
        "SAN SEBASTIAN", "SANTANDER DE QUILICHAO", "SANTA ROSA", "SILVIA", "SOTARA", "SUAREZ",
        "SUCRE", "TIMBIO", "TIMBIQUI", "TORIBIO", "TOTORO", "VILLA RICA",
        # Cesar
        "VALLEDUPAR", "AGUACHICA", "AGUSTIN CODAZZI", "ASTREA", "BECERRIL", "BOSCONIA",
        "CHIMICHAGUA", "CHIRIGUANA", "CURUMANI", "EL COPEY", "EL PASO", "GAMARRA", "GONZALEZ",
        "LA GLORIA", "LA JAGUA DE IBIRICO", "MANAURE", "PAILITAS", "PELAYA", "PUEBLO BELLO",
        "RIO DE ORO", "LA PAZ", "SAN ALBERTO", "SAN DIEGO", "SAN MARTIN", "TAMALAMEQUE",
        # Chocó
        "QUIBDO", "ACANDI", "ALTO BAUDO", "ATRATO", "BAGADO", "BAHIA SOLANO", "BAJO BAUDO",
        "BOJAYA", "EL CANTON DEL SAN PABLO", "CARMEN DEL DARIEN", "CERTEGUI", "CONDOTO",
        "EL CARMEN DE ATRATO", "EL LITORAL DEL SAN JUAN", "ISTMINA", "JURADO", "LLORO",
        "MEDIO ATRATO", "MEDIO BAUDO", "MEDIO SAN JUAN", "NOVITA", "NUQUI", "RIO IRO",
        "RIO QUITO", "RIOSUCIO", "SAN JOSE DEL PALMAR", "SIPI", "TADO", "UNGUIA", "UNION PANAMERICANA",
        # Córdoba
        "MONTERIA", "AYAPEL", "BUENAVISTA", "CANALETE", "CERETE", "CHIMA", "CHINU", "CIENAGA DE ORO",
        "COTORRA", "LA APARTADA", "LORICA", "LOS CORDOBAS", "MOMIL", "MONTELIBANO", "MOÑITOS",
        "PLANETA RICA", "PUEBLO NUEVO", "PUERTO ESCONDIDO", "PUERTO LIBERTADOR", "PURISIMA",
        "SAHAGUN", "SAN ANDRES SOTAVENTO", "SAN ANTERO", "SAN BERNARDO DEL VIENTO", "SAN CARLOS",
        "SAN PELAYO", "TIERRALTA", "TUCHIN", "VALENCIA",
        # Cundinamarca
        "AGUA DE DIOS", "ALBAN", "ANAPOIMA", "ANOLAIMA", "ARBELAEZ", "BELTRAN", "BITUIMA",
        "BOJACA", "CABRERA", "CACHIPAY", "CAJICA", "CAPARRAPI", "CAQUEZA", "CARMEN DE CARUPA",
        "CHAGUANI", "CHIA", "CHIPAQUE", "CHOACHI", "CHOCONTA", "COGUA", "COTA", "CUCUNUBA",
        "EL COLEGIO", "EL PEÑON", "EL ROSAL", "FACATATIVA", "FOMEQUE", "FOSCA", "FUNZA",
        "FUQUENE", "FUSAGASUGA", "GACHALA", "GACHANCIPA", "GACHETA", "GAMA", "GIRARDOT",
        "GRANADA", "GUACHETA", "GUADUAS", "GUASCA", "GUATAQUI", "GUATAVITA", "GUAYABAL DE SIQUIMA",
        "GUAYABETAL", "GUTIERREZ", "JERUSALEN", "JUNIN", "LA CALERA", "LA MESA", "LA PALMA",
        "LA PEÑA", "LA VEGA", "LENGUAZAQUE", "MACHETA", "MADRID", "MANTA", "MEDINA", "MOSQUERA",
        "NARIÑO", "NEMOCON", "NILO", "NIMAIMA", "NOCAIMA", "VENECIA", "PACHO", "PAIME", "PANDI",
        "PARATEBUENO", "PASCA", "PUERTO SALGAR", "PULI", "QUEBRADANEGRA", "QUETAME", "QUIPILE",
        "APULO", "RICAURTE", "SAN ANTONIO DEL TEQUENDAMA", "SAN BERNARDO", "SAN CAYETANO",
        "SAN FRANCISCO", "SAN JUAN DE RIO SECO", "SASAIMA", "SESQUILE", "SIBATE", "SILVANIA",
        "SIMIJACA", "SOACHA", "SOPO", "SUBACHOQUE", "SUESCA", "SUPATA", "SUSA", "SUTATAUSA",
        "TABIO", "TAUSA", "TENA", "TENJO", "TIBACUY", "TIBIRITA", "TOCAIMA", "TOCANCIPA",
        "TOPAIPI", "UBALA", "UBAQUE", "VILLA DE SAN DIEGO DE UBATE", "UNE", "UTICA", "VERGARA",
        "VIANI", "VILLAGOMEZ", "VILLAPINZON", "VILLETA", "VIOTA", "YACOPI", "ZIPACON", "ZIPAQUIRA",
        # Guainía
        "INIRIDA", "BARRANCO MINAS", "MAPIRIPANA", "SAN FELIPE", "PUERTO COLOMBIA", "LA GUADALUPE",
        "CACAHUAL", "PANA PANA", "MORICHAL",
        # Guaviare
        "SAN JOSE DEL GUAVIARE", "CALAMAR", "EL RETORNO", "MIRAFLORES",
        # Huila
        "NEIVA", "ACEVEDO", "AGRADO", "AIPE", "ALGECIRAS", "ALTAMIRA", "BARAYA", "CAMPOALEGRE",
        "COLOMBIA", "ELIAS", "GARZON", "GIGANTE", "GUADALUPE", "HOBO", "IQUIRA", "ISNOS",
        "LA ARGENTINA", "LA PLATA", "NATAGA", "OPORAPA", "PAICOL", "PALERMO", "PALESTINA",
        "PITAL", "PITALITO", "RIVERA", "SALADOBLANCO", "SAN AGUSTIN", "SANTA MARIA", "SUAZA",
        "TARQUI", "TESALIA", "TELLO", "TERUEL", "TIMANA", "VILLAVIEJA", "YAGUARA",
        # La Guajira
        "RIOHACHA", "ALBANIA", "BARRANCAS", "DIBULLA", "DISTRACCION", "EL MOLINO", "FONSECA",
        "HATONUEVO", "LA JAGUA DEL PILAR", "MAICAO", "MANAURE", "SAN JUAN DEL CESAR", "URIBIA",
        "URUMITA", "VILLANUEVA",
        # Magdalena
        "SANTA MARTA", "ALGARROBO", "ARACATACA", "ARIGUANI", "CERRO SAN ANTONIO", "CHIBOLO",
        "CIENAGA", "CONCORDIA", "EL BANCO", "EL PIÑON", "EL RETEN", "FUNDACION", "GUAMAL",
        "NUEVA GRANADA", "PEDRAZA", "PIJIÑO DEL CARMEN", "PIVIJAY", "PLATO", "PUEBLOVIEJO",
        "REMOLINO", "SABANAS DE SAN ANGEL", "SALAMINA", "SAN SEBASTIAN DE BUENAVISTA", "SAN ZENON",
        "SANTA ANA", "SANTA BARBARA DE PINTO", "SITIONUEVO", "TENERIFE", "ZAPAYAN", "ZONA BANANERA",
        # Meta
        "VILLAVICENCIO", "ACACIAS", "BARRANCA DE UPIA", "CABUYARO", "CASTILLA LA NUEVA", "CUBARRAL",
        "CUMARAL", "EL CALVARIO", "EL CASTILLO", "EL DORADO", "FUENTE DE ORO", "GRANADA", "GUAMAL",
        "MAPIRIPAN", "MESETAS", "LA MACARENA", "URIBE", "LEJANIAS", "PUERTO CONCORDIA", "PUERTO GAITAN",
        "PUERTO LOPEZ", "PUERTO LLERAS", "PUERTO RICO", "RESTREPO", "SAN CARLOS DE GUAROA",
        "SAN JUAN DE ARAMA", "SAN JUANITO", "SAN MARTIN", "VISTA HERMOSA",
        # Nariño
        "PASTO", "ALBAN", "ALDANA", "ANCUYA", "ARBOLEDA", "BARBACOAS", "BELEN", "BUESACO",
        "COLON", "CONSACA", "CONTADERO", "CORDOBA", "CUASPUD", "CUMBAL", "CUMBITARA", "CHACHAGÜI",
        "EL CHARCO", "EL PEÑOL", "EL ROSARIO", "EL TABLON DE GOMEZ", "EL TAMBO", "FUNES",
        "GUACHUCAL", "GUAITARILLA", "GUALMATAN", "ILES", "IMUES", "IPIALES", "LA CRUZ",
        "LA FLORIDA", "LA LLANADA", "LA TOLA", "LA UNION", "LEIVA", "LINARES", "LOS ANDES",
        "MAGÜI", "MALLAMA", "MOSQUERA", "NARIÑO", "OLAYA HERRERA", "OSPINA", "FRANCISCO PIZARRO",
        "POLICARPA", "POTOSI", "PROVIDENCIA", "PUERRES", "PUPIALES", "RICAURTE", "ROBERTO PAYAN",
        "SAMANIEGO", "SANDONA", "SAN BERNARDO", "SAN LORENZO", "SAN PABLO", "SAN PEDRO DE CARTAGO",
        "SANTA BARBARA", "SANTACRUZ", "SAPUYES", "TAMINANGO", "TANGUA", "SAN ANDRES DE TUMACO",
        "TUQUERRES", "YACUANQUER",
        # Norte de Santander
        "CUCUTA", "ABREGO", "ARBOLEDAS", "BOCHALEMA", "BUCARASICA", "CACOTA", "CACHIRA",
        "CHINACOTA", "CHITAGA", "CONVENCION", "CUCUTILLA", "DURANIA", "EL CARMEN", "EL TARRA",
        "EL ZULIA", "GRAMALOTE", "HACARI", "HERRAN", "LABATECA", "LA ESPERANZA", "LA PLAYA",
        "LOS PATIOS", "LOURDES", "MUTISCUA", "OCAÑA", "PAMPLONA", "PAMPLONITA", "PUERTO SANTANDER",
        "RAGONVALIA", "SALAZAR", "SAN CALIXTO", "SAN CAYETANO", "SANTIAGO", "SARDINATA",
        "SILOS", "TEORAMA", "TIBU", "TOLEDO", "VILLA CARO", "VILLA DEL ROSARIO",
        # Putumayo
        "MOCOA", "COLON", "ORITO", "PUERTO ASIS", "PUERTO CAICEDO", "PUERTO GUZMAN", "PUERTO LEGUIZAMO",
        "SIBUNDOY", "SAN FRANCISCO", "SAN MIGUEL", "SANTIAGO", "VALLE DEL GUAMUEZ", "VILLAGARZON",
        # Quindío
        "ARMENIA", "BUENAVISTA", "CALARCA", "CIRCASIA", "CORDOBA", "FILANDIA", "GENOVA",
        "LA TEBAIDA", "MONTENEGRO", "PIJAO", "QUIMBAYA", "SALENTO",
        # Risaralda
        "PEREIRA", "APIA", "BALBOA", "BELEN DE UMBRIA", "DOSQUEBRADAS", "GUATICA", "LA CELIA",
        "LA VIRGINIA", "MARSELLA", "MISTRATO", "PUEBLO RICO", "QUINCHIA", "SANTA ROSA DE CABAL",
        "SANTUARIO",
        # San Andrés y Providencia
        "SAN ANDRES", "PROVIDENCIA",
        # Santander
        "BUCARAMANGA", "AGUADA", "ALBANIA", "ARATOCA", "BARBOSA", "BARICHARA", "BARRANCABERMEJA",
        "BETULIA", "BOLIVAR", "CABRERA", "CALIFORNIA", "CAPITANEJO", "CARCASI", "CEPITA",
        "CERRITO", "CHARALA", "CHARTA", "CHIMA", "CHIPATA", "CIMITARRA", "CONCEPCION", "CONFINES",
        "CONTRATACION", "COROMORO", "CURITI", "EL CARMEN DE CHUCURI", "EL GUACAMAYO", "EL PEÑON",
        "EL PLAYON", "ENCINO", "ENCISO", "FLORIAN", "FLORIDABLANCA", "GALAN", "GAMBITA", "GIRON",
        "GUACA", "GUADALUPE", "GUAPOTA", "GUAVATA", "GÜEPSA", "HATO", "JESUS MARIA", "JORDAN",
        "LA BELLEZA", "LANDAZURI", "LA PAZ", "LEBRIJA", "LOS SANTOS", "MACARAVITA", "MALAGA",
        "MATANZA", "MOGOTES", "MOLAGAVITA", "OCAMONTE", "OIBA", "ONZAGA", "PALMAR", "PALMAS DEL SOCORRO",
        "PARAMO", "PIEDECUESTA", "PINCHOTE", "PUENTE NACIONAL", "PUERTO PARRA", "PUERTO WILCHES",
        "RIONEGRO", "SABANA DE TORRES", "SAN ANDRES", "SAN BENITO", "SAN GIL", "SAN JOAQUIN",
        "SAN JOSE DE MIRANDA", "SAN MIGUEL", "SAN VICENTE DE CHUCURI", "SANTA BARBARA", "SANTA HELENA DEL OPON",
        "SIMACOTA", "SOCORRO", "SUAITA", "SUCRE", "SURATA", "TONA", "VALLE DE SAN JOSE", "VELEZ",
        "VETAS", "VILLANUEVA", "ZAPATOCA",
        # Sucre
        "SINCELEJO", "BUENAVISTA", "CAIMITO", "COLOSO", "COROZAL", "COVEÑAS", "CHALAN",
        "EL ROBLE", "GALERAS", "GUARANDA", "LA UNION", "LOS PALMITOS", "MAJAGUAL", "MORROA",
        "OVEJAS", "PALMITO", "SAMPUES", "SAN BENITO ABAD", "SAN JUAN DE BETULIA", "SAN MARCOS",
        "SAN ONOFRE", "SAN PEDRO", "SAN LUIS DE SINCE", "SINCE", "SUCRE", "TOLU", "TOLU VIEJO",
        # Tolima
        "IBAGUE", "ALPUJARRA", "ALVARADO", "AMBALEMA", "ANZOATEGUI", "ARMERO GUAYABAL", "ARMERO",
        "ATACACO", "CAJAMARCA", "CARMEN DE APICALA", "CASABIANCA", "CHAPARRAL", "COELLO",
        "COYAIMA", "CUNDAY", "DOLORES", "ESPINAL", "FALAN", "FLANDES", "FRESNO", "GUAMO",
        "HERVEO", "HONDA", "ICONONZO", "LERIDA", "LIBANO", "MARIQUITA", "MELGAR", "MURILLO",
        "NATAGAIMA", "ORTEGA", "PALOCABILDO", "PIEDRAS", "PLANADAS", "PRADO", "PURIFICACION",
        "RIOBLANCO", "RONCESVALLES", "ROVIRA", "SALDAÑA", "SAN ANTONIO", "SAN LUIS", "SANTA ISABEL",
        "SUAREZ", "VALLE DE SAN JUAN", "VENADILLO", "VILLAHERMOSA", "VILLARRICA",
        # Valle del Cauca
        "CALI", "ALCALA", "ANDALUCIA", "ANSERMANUEVO", "ARGELIA", "BOLIVAR", "BUENAVENTURA",
        "GUADALAJARA DE BUGA", "BUGA", "BUGALAGRANDE", "CAICEDONIA", "CALIMA DARIEN", "DARIEN",
        "CANDELARIA", "CARTAGO", "DAGUA", "EL AGUILA", "EL CAIRO", "EL CERRITO", "EL DOVIO",
        "FLORIDA", "GINEBRA", "GUACARI", "JAMUNDI", "LA CUMBRE", "LA UNION", "LA VICTORIA",
        "OBANDO", "PALMIRA", "PRADERA", "RESTREPO", "RIOFRIO", "ROLDANILLO", "SAN PEDRO",
        "SEVILLA", "TORO", "TRUJILLO", "TULUA", "ULLOA", "VERSALLES", "VIJES", "YOTOCO",
        "YUMBO", "ZARZAL",
        # Vaupés
        "MITU", "CARURU", "PACOA", "TARAIRA", "PAPUNAHUA", "YAVARATE",
        # Vichada
        "PUERTO CARREÑO", "LA PRIMAVERA", "SANTA ROSALIA", "CUMARIBO"
    ]

    _PATRON_MUNICIPIOS_REGEX = None

    def __init__(self):
        if ColombiaGeoService._PATRON_MUNICIPIOS_REGEX is None:
            # Ordenar por longitud descendente para emparejar nombres compuestos antes que simples
            muns_sorted = sorted(set(self.MUNICIPIOS), key=len, reverse=True)
            patron = "|".join(re.escape(m) for m in muns_sorted)
            ColombiaGeoService._PATRON_MUNICIPIOS_REGEX = re.compile(rf"\b({patron})\b", re.IGNORECASE)

    @classmethod
    def _quitar_tildes(cls, texto: str) -> str:
        if not texto:
            return ""
        return "".join(
            c for c in unicodedata.normalize("NFD", texto)
            if unicodedata.category(c) != "Mn"
        ).upper()

    @classmethod
    def limpiar_texto_crudo(cls, texto: str) -> str:
        """Limpia ruido de OCR, prefijos y formatos residuales."""
        if not texto:
            return ""
        txt = str(texto).upper()
        # Eliminar fechas
        txt = re.sub(r"\b\d{1,2}[\s/\-\.][A-Z0-9]{3,4}[\s/\-\.]\d{4}\b|\b\d{1,2}/\d{1,2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b|\b\d+\b", " ", txt)
        # Eliminar meses
        txt = re.sub(r"\b(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC|ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)\b", " ", txt)
        # Eliminar prefijos de etiquetas, verbos de expedición y cargos oficiales
        txt = re.sub(r"\b(FECHA|LUGAR|EXPEDICION|EXPEDICIÓN|EXPIRACION|EXPIRACIÓN|EXPEDIDA|EXPEDIDO|EXPEDIDAS|EXPEDIDOS|NACIMIENTO|NACIDO|MA|DE|DEL|EN|LA|EL|Y|POR|CON|FIRMA|FIRMAS|TITULAR|HUELLA|INDICE|ÍNDICE|DERECHO|IZQUIERDO|REGISTRADOR|REGISTRADORA|REGISTRADURIA|ESTADO|CIVIL|GIVIL|ALDEL|ESTADOL|DIRECTOR|SECRETARIO|REPUBLICA|REPÚBLICA|COLOMBIA|CEDULA|CÉDULA|CIUDADANIA|CIUDADANÍA|IDENTIFICACION|IDENTIFICACIÓN|NUIP|NUMERO|NÚMERO|TARJETA|PERSONAL|NACIONAL)\b", " ", txt)
        # Eliminar nombres de departamentos si vienen adjuntos al municipio (ej: "VILLAGARZON PUTUMAYO" -> "VILLAGARZON")
        for depto in cls.DEPARTAMENTOS:
            if len(depto) >= 4:
                txt = re.sub(rf"\b{re.escape(depto)}\b", " ", txt)
        # Solo letras y espacios
        txt = re.sub(r"[^A-ZÁÉÍÓÚÜÑ\s]", " ", txt)
        return " ".join(txt.split()).strip()

    def resolver_municipio_fuzzy(self, candidato: str, umbral: int = 80) -> Optional[str]:
        """
        Corrige errores tipográficos de OCR contra el catálogo oficial DANE usando RapidFuzz.
        Ej: 'FL0RENCIA' -> 'FLORENCIA', 'CARTAG0' -> 'CARTAGO', 'MEDELIN' -> 'MEDELLIN'
        """
        if not candidato or len(candidato.strip()) < 3:
            return None
        
        candidato_norm = self._quitar_tildes(candidato.strip())
        
        # Coincidencia exacta directa
        for mun in self.MUNICIPIOS:
            if self._quitar_tildes(mun) == candidato_norm:
                return mun

        # Fuzzy match contra todos los 1.100 municipios
        resultado = process.extractOne(
            candidato_norm,
            self.MUNICIPIOS,
            scorer=fuzz.ratio,
            score_cutoff=umbral
        )
        if resultado:
            mejor_match, score, _ = resultado
            # No permitir que un departamento genérico sea el resultado si es solo depto
            if mejor_match.upper() not in self.DEPARTAMENTOS:
                return mejor_match
        
        return None

    def extraer_lugar_universal(self, texto: str, lineas: List[str]) -> Optional[str]:
        """
        Algoritmo Universal de Extracción de Municipios Colombianos:
        1. Formato Nacional Registraduría: 'MUNICIPIO (DEPARTAMENTO)' o 'FECHA MUNICIPIO (DEPARTAMENTO)'
        2. Búsqueda Espacial y Sintáctica en líneas adyacentes a 'LUGAR', 'EXPEDICION', 'NACIMIENTO'
        3. Detección en todo el texto con corrección Fuzzy para cualquier municipio del país.
        """
        if not texto and not lineas:
            return None

        # ── 1. Formato oficial 'MUNICIPIO (DEPARTAMENTO)' en cualquier línea ────────
        for linea in (lineas or []):
            linea_up = linea.strip().upper()
            m_par = re.search(r"([A-ZÁÉÍÓÚÜÑ\s]{3,35})\s*\(\s*([A-ZÁÉÍÓÚÜÑ\s]{3,35})\s*\)", linea_up)
            if m_par:
                mun_raw = self.limpiar_texto_crudo(m_par.group(1))
                if mun_raw:
                    # Validar o corregir fuzzy con DANE
                    mun_res = self.resolver_municipio_fuzzy(mun_raw, umbral=78)
                    if mun_res:
                        return mun_res
                    if mun_raw not in self.DEPARTAMENTOS and len(mun_raw) >= 3:
                        return mun_raw

        # ── 2. Búsqueda en líneas adyacentes a etiquetas clave ─────────────────────
        for idx, linea in enumerate(lineas or []):
            if re.search(r"\b(LUGAR|EXPEDICI[OÓ]N|EXPEDIDA|NACIMIENTO)\b", linea, re.IGNORECASE):
                subtexto = " ".join(lineas[max(0, idx - 1): min(len(lineas), idx + 3)])
                
                # Revisar si hay formato con paréntesis en subtexto
                m_par = re.search(r"([A-ZÁÉÍÓÚÜÑ\s]{3,35})\s*\(\s*([A-ZÁÉÍÓÚÜÑ\s]{3,35})\s*\)", subtexto.upper())
                if m_par:
                    mun_raw = self.limpiar_texto_crudo(m_par.group(1))
                    mun_res = self.resolver_municipio_fuzzy(mun_raw, umbral=78)
                    if mun_res:
                        return mun_res

                # Buscar coincidencia directa con catálogo
                if self._PATRON_MUNICIPIOS_REGEX:
                    for match in self._PATRON_MUNICIPIOS_REGEX.finditer(subtexto):
                        cand = match.group(1).upper().strip()
                        if cand not in self.DEPARTAMENTOS and len(cand) >= 3:
                            return cand

                # Limpiar la línea adyacente y aplicar fuzzy
                limpia = self.limpiar_texto_crudo(subtexto)
                if limpia:
                    for token in limpia.split():
                        if len(token) >= 4 and token not in self.DEPARTAMENTOS:
                            f_res = self.resolver_municipio_fuzzy(token, umbral=84)
                            if f_res:
                                return f_res

        # ── 3. Búsqueda global en el texto completo ────────────────────────────────
        if self._PATRON_MUNICIPIOS_REGEX and texto:
            for match in self._PATRON_MUNICIPIOS_REGEX.finditer(texto):
                cand = match.group(1).upper().strip()
                if cand not in self.DEPARTAMENTOS and len(cand) >= 3:
                    return cand

        # ── 4. Fallback: Limpieza estricta y último intento fuzzy ──────────────────
        texto_limpio = self.limpiar_texto_crudo(texto)
        if texto_limpio:
            tokens = [t for t in texto_limpio.split() if len(t) >= 4 and t not in self.DEPARTAMENTOS]
            for tok in tokens:
                f_res = self.resolver_municipio_fuzzy(tok, umbral=85)
                if f_res:
                    return f_res

        return None


# Instancia singleton universal
colombia_geo = ColombiaGeoService()
