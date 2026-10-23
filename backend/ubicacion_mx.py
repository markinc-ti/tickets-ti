# -*- coding: utf-8 -*-
"""
Estado y municipio aproximados de un cliente en México, a partir de:
  1) su dirección (estado / ciudad capturados, o el código postal), y si no
  2) la lada de su teléfono.
La tabla de ladas da el estado (confiable) y la ciudad principal de esa lada
(una lada cubre varios municipios cercanos, así que el municipio por lada es
aproximado). Fuente: plan de numeración de México (listas de Wikipedia
"Area codes in Mexico by code").
"""
import re
import unicodedata

LADAS = {
    "33": ("Guadalajara", "Jalisco"),
    "55": ("Ciudad de México", "Ciudad de México"),
    "56": ("Ciudad de México", "Ciudad de México"),
    "81": ("Monterrey", "Nuevo León"),
    "220": ("Puebla", "Puebla"),
    "221": ("Puebla", "Puebla"),
    "222": ("Puebla", "Puebla"),
    "223": ("Tepeaca", "Puebla"),
    "224": ("Tecali de Herrera", "Puebla"),
    "225": ("Tlapacoyan", "Veracruz"),
    "226": ("Altotonga", "Veracruz"),
    "227": ("Huejotzingo", "Puebla"),
    "228": ("Xalapa", "Veracruz"),
    "229": ("Veracruz", "Veracruz"),
    "231": ("Teziutlán", "Puebla"),
    "232": ("Martínez de la Torre", "Veracruz"),
    "233": ("Zacapoaxtla", "Puebla"),
    "235": ("Misantla", "Veracruz"),
    "236": ("Ajalpan", "Puebla"),
    "237": ("Zapotitlán Salinas", "Puebla"),
    "238": ("Tehuacán", "Puebla"),
    "241": ("Apizaco", "Tlaxcala"),
    "243": ("Izúcar de Matamoros", "Puebla"),
    "244": ("Atlixco", "Puebla"),
    "245": ("Ciudad Serdán", "Puebla"),
    "246": ("Tlaxcala", "Tlaxcala"),
    "247": ("Huamantla", "Tlaxcala"),
    "248": ("San Martín Texmelucan", "Puebla"),
    "249": ("Tecamachalco", "Puebla"),
    "271": ("Córdoba", "Veracruz"),
    "272": ("Orizaba", "Veracruz"),
    "273": ("Huatusco", "Veracruz"),
    "274": ("Tierra Blanca", "Veracruz"),
    "275": ("Tulcingo de Valle", "Puebla"),
    "276": ("Libres", "Puebla"),
    "278": ("Cuitláhuac", "Veracruz"),
    "279": ("Actopan", "Veracruz"),
    "281": ("Loma Bonita", "Oaxaca"),
    "282": ("Perote", "Veracruz"),
    "283": ("Playa Vicente", "Veracruz"),
    "284": ("Ángel R. Cabada", "Veracruz"),
    "285": ("Medellín de Bravo", "Veracruz"),
    "287": ("Tuxtepec", "Oaxaca"),
    "288": ("Cosamaloapan", "Veracruz"),
    "294": ("San Andrés Tuxtla", "Veracruz"),
    "296": ("José Cardel", "Veracruz"),
    "297": ("Alvarado", "Veracruz"),
    "311": ("Tepic", "Nayarit"),
    "312": ("Colima", "Colima"),
    "313": ("Tecomán", "Colima"),
    "314": ("Manzanillo", "Colima"),
    "315": ("Cihuatlán", "Jalisco"),
    "316": ("Ayutla", "Jalisco"),
    "317": ("Autlán", "Jalisco"),
    "319": ("Rosamorada", "Nayarit"),
    "321": ("El Grullo", "Jalisco"),
    "322": ("Puerto Vallarta", "Jalisco"),
    "323": ("Santiago Ixcuintla", "Nayarit"),
    "324": ("Ixtlán del Río", "Nayarit"),
    "325": ("Acaponeta", "Nayarit"),
    "326": ("Zacoalco", "Jalisco"),
    "327": ("Compostela", "Nayarit"),
    "328": ("Ixtlán de los Hervores", "Michoacán"),
    "329": ("Bahía de Banderas", "Nayarit"),
    "341": ("Ciudad Guzmán", "Jalisco"),
    "342": ("Sayula", "Jalisco"),
    "343": ("Tapalpa", "Jalisco"),
    "344": ("Yahualica", "Jalisco"),
    "345": ("Ayotlán", "Jalisco"),
    "346": ("Teocaltiche", "Jalisco"),
    "347": ("San Miguel el Alto", "Jalisco"),
    "348": ("Arandas", "Jalisco"),
    "349": ("Tecolotlán", "Jalisco"),
    "351": ("Zamora", "Michoacán"),
    "352": ("La Piedad", "Michoacán"),
    "353": ("Sahuayo", "Michoacán"),
    "354": ("Los Reyes", "Michoacán"),
    "355": ("Chilchota", "Michoacán"),
    "356": ("Yurécuaro", "Michoacán"),
    "357": ("Casimiro Castillo", "Jalisco"),
    "358": ("Tamazula", "Jalisco"),
    "359": ("Penjamillo", "Michoacán"),
    "371": ("Tecalitlán", "Jalisco"),
    "372": ("Atoyac", "Jalisco"),
    "373": ("Zapotlanejo", "Jalisco"),
    "374": ("Tequila", "Jalisco"),
    "375": ("Ameca", "Jalisco"),
    "376": ("Chapala", "Jalisco"),
    "377": ("Cocula", "Jalisco"),
    "378": ("Tepatitlán de Morelos", "Jalisco"),
    "381": ("San José de Gracia", "Michoacán"),
    "382": ("Mazamitla", "Jalisco"),
    "383": ("Villamar", "Michoacán"),
    "384": ("Tala", "Jalisco"),
    "385": ("San Martín Hidalgo", "Jalisco"),
    "386": ("Etzatlán", "Jalisco"),
    "387": ("Jocotepec", "Jalisco"),
    "388": ("Mascota", "Jalisco"),
    "389": ("Tecuala", "Nayarit"),
    "391": ("Atotonilco el Alto", "Jalisco"),
    "392": ("Ocotlán", "Jalisco"),
    "393": ("La Barca", "Jalisco"),
    "394": ("Cotija", "Michoacán"),
    "395": ("San Juan de los Lagos", "Jalisco"),
    "411": ("Cortazar", "Guanajuato"),
    "412": ("Comonfort", "Guanajuato"),
    "413": ("Apaseo el Grande", "Guanajuato"),
    "414": ("Tequisquiapan", "Querétaro"),
    "415": ("San Miguel de Allende", "Guanajuato"),
    "417": ("Acámbaro", "Guanajuato"),
    "418": ("Dolores Hidalgo", "Guanajuato"),
    "419": ("San José Iturbide", "Guanajuato"),
    "421": ("Jerécuaro", "Guanajuato"),
    "422": ("Ario de Rosales", "Michoacán"),
    "423": ("Paracho", "Michoacán"),
    "424": ("Tepalcatepec", "Michoacán"),
    "425": ("Nueva Italia", "Michoacán"),
    "426": ("Buenavista", "Michoacán"),
    "427": ("San Juan del Río", "Querétaro"),
    "428": ("San Felipe", "Guanajuato"),
    "429": ("Abasolo", "Guanajuato"),
    "431": ("Jalostotitlán", "Jalisco"),
    "432": ("Manuel Doblado", "Guanajuato"),
    "433": ("Sombrerete", "Zacatecas"),
    "434": ("Pátzcuaro", "Michoacán"),
    "435": ("Huetamo", "Michoacán"),
    "436": ("Zacapu", "Michoacán"),
    "437": ("Tlaltenango", "Zacatecas"),
    "438": ("Puruándiro", "Michoacán"),
    "440": ("San Luis Potosí", "San Luis Potosí"),
    "441": ("Cadereyta de Montes", "Querétaro"),
    "442": ("Querétaro", "Querétaro"),
    "443": ("Morelia", "Michoacán"),
    "444": ("San Luis Potosí", "San Luis Potosí"),
    "445": ("Moroleón", "Guanajuato"),
    "446": ("Querétaro", "Querétaro"),
    "447": ("Maravatío", "Michoacán"),
    "448": ("Amealco de Bonfil", "Querétaro"),
    "449": ("Aguascalientes", "Aguascalientes"),
    "451": ("Zinapécuaro", "Michoacán"),
    "452": ("Uruapan", "Michoacán"),
    "453": ("Apatzingán", "Michoacán"),
    "454": ("Quiroga", "Michoacán"),
    "455": ("Huandacareo", "Michoacán"),
    "456": ("Valle de Santiago", "Guanajuato"),
    "457": ("Valparaíso", "Zacatecas"),
    "458": ("Villa de Ramos", "San Luis Potosí"),
    "459": ("Tacámbaro", "Michoacán"),
    "461": ("Celaya", "Guanajuato"),
    "462": ("Irapuato", "Guanajuato"),
    "463": ("Jalpa", "Zacatecas"),
    "464": ("Salamanca", "Guanajuato"),
    "465": ("Rincón de Romos", "Aguascalientes"),
    "466": ("Salvatierra", "Guanajuato"),
    "467": ("Juchipila", "Zacatecas"),
    "468": ("San Luis de la Paz", "Guanajuato"),
    "469": ("Pénjamo", "Guanajuato"),
    "471": ("Purépero", "Michoacán"),
    "472": ("Silao", "Guanajuato"),
    "473": ("Guanajuato", "Guanajuato"),
    "474": ("Lagos de Moreno", "Jalisco"),
    "475": ("Encarnación de Díaz", "Jalisco"),
    "476": ("San Francisco del Rincón", "Guanajuato"),
    "477": ("León", "Guanajuato"),
    "478": ("Calera", "Zacatecas"),
    "479": ("León", "Guanajuato"),
    "481": ("Ciudad Valles", "San Luis Potosí"),
    "482": ("Ciudad del Maíz", "San Luis Potosí"),
    "483": ("Tamazunchale", "San Luis Potosí"),
    "485": ("Villa de Reyes", "San Luis Potosí"),
    "486": ("Charcas", "San Luis Potosí"),
    "487": ("Rioverde", "San Luis Potosí"),
    "488": ("Matehuala", "San Luis Potosí"),
    "489": ("Tamuín", "San Luis Potosí"),
    "492": ("Zacatecas", "Zacatecas"),
    "493": ("Fresnillo", "Zacatecas"),
    "494": ("Jerez", "Zacatecas"),
    "495": ("Calvillo", "Aguascalientes"),
    "496": ("Pinos", "Zacatecas"),
    "498": ("Río Grande", "Zacatecas"),
    "499": ("Colotlán", "Jalisco"),
    "612": ("La Paz", "Baja California Sur"),
    "613": ("Ciudad Constitución", "Baja California Sur"),
    "614": ("Chihuahua", "Chihuahua"),
    "615": ("Guerrero Negro", "Baja California Sur"),
    "616": ("San Quintín", "Baja California"),
    "618": ("Durango", "Durango"),
    "621": ("Saucillo", "Chihuahua"),
    "622": ("Guaymas", "Sonora"),
    "623": ("Ures", "Sonora"),
    "624": ("Los Cabos", "Baja California Sur"),
    "625": ("Cuauhtémoc", "Chihuahua"),
    "626": ("Ojinaga", "Chihuahua"),
    "627": ("Hidalgo del Parral", "Chihuahua"),
    "628": ("Santa Bárbara", "Chihuahua"),
    "629": ("Jiménez", "Chihuahua"),
    "631": ("Nogales", "Sonora"),
    "632": ("Magdalena de Kino", "Sonora"),
    "633": ("Agua Prieta", "Sonora"),
    "634": ("Nacozari", "Sonora"),
    "635": ("Creel", "Chihuahua"),
    "636": ("Nuevo Casas Grandes", "Chihuahua"),
    "637": ("Caborca", "Sonora"),
    "638": ("Puerto Peñasco", "Sonora"),
    "639": ("Delicias", "Chihuahua"),
    "641": ("Santa Ana", "Sonora"),
    "642": ("Navojoa", "Sonora"),
    "643": ("Villa Juárez", "Sonora"),
    "644": ("Ciudad Obregón", "Sonora"),
    "645": ("Cananea", "Sonora"),
    "646": ("Ensenada", "Baja California"),
    "647": ("Huatabampo", "Sonora"),
    "648": ("Camargo", "Chihuahua"),
    "649": ("Guachochi", "Chihuahua"),
    "651": ("Sonoyta", "Sonora"),
    "652": ("Madera", "Chihuahua"),
    "653": ("San Luis Río Colorado", "Sonora"),
    "656": ("Ciudad Juárez", "Chihuahua"),
    "658": ("Mexicali", "Baja California"),
    "659": ("Namiquipa", "Chihuahua"),
    "661": ("Playas de Rosarito", "Baja California"),
    "662": ("Hermosillo", "Sonora"),
    "663": ("Tijuana", "Baja California"),
    "664": ("Tijuana", "Baja California"),
    "665": ("Tecate", "Baja California"),
    "667": ("Culiacán", "Sinaloa"),
    "668": ("Los Mochis", "Sinaloa"),
    "669": ("Mazatlán", "Sinaloa"),
    "671": ("Cuencamé", "Durango"),
    "672": ("Navolato", "Sinaloa"),
    "673": ("Guamúchil", "Sinaloa"),
    "674": ("Santiago Papasquiaro", "Durango"),
    "675": ("Villa Unión", "Durango"),
    "676": ("Pánuco de Coronado", "Durango"),
    "677": ("Canatlán", "Durango"),
    "686": ("Mexicali", "Baja California"),
    "687": ("Guasave", "Sinaloa"),
    "694": ("Concordia", "Sinaloa"),
    "695": ("Escuinapa", "Sinaloa"),
    "696": ("Cosalá", "Sinaloa"),
    "697": ("Badiraguato", "Sinaloa"),
    "698": ("El Fuerte", "Sinaloa"),
    "711": ("El Oro", "Estado de México"),
    "712": ("Atlacomulco", "Estado de México"),
    "713": ("Santiago Tianguistenco", "Estado de México"),
    "714": ("Tenancingo", "Estado de México"),
    "715": ("Zitácuaro", "Michoacán"),
    "716": ("Temascaltepec", "Estado de México"),
    "717": ("Tenango del Valle", "Estado de México"),
    "718": ("Temascalcingo", "Estado de México"),
    "719": ("Temoaya", "Estado de México"),
    "720": ("Toluca", "Estado de México"),
    "721": ("Ixtapan de la Sal", "Estado de México"),
    "722": ("Toluca", "Estado de México"),
    "723": ("Ixtlahuaca", "Estado de México"),
    "724": ("Tejupilco", "Estado de México"),
    "725": ("Almoloya de Juárez", "Estado de México"),
    "726": ("Villa Victoria", "Estado de México"),
    "727": ("Huitzuco", "Guerrero"),
    "728": ("Lerma", "Estado de México"),
    "729": ("Toluca", "Estado de México"),
    "731": ("Yecapixtla", "Morelos"),
    "732": ("Arcelia", "Guerrero"),
    "733": ("Iguala", "Guerrero"),
    "734": ("Jojutla", "Morelos"),
    "735": ("Cuautla", "Morelos"),
    "736": ("Teloloapan", "Guerrero"),
    "737": ("Miacatlán", "Morelos"),
    "738": ("Mixquiahuala", "Hidalgo"),
    "739": ("Tepoztlán", "Morelos"),
    "741": ("Ometepec", "Guerrero"),
    "742": ("Tecpan de Galeana", "Guerrero"),
    "743": ("Tolcayuca", "Hidalgo"),
    "744": ("Acapulco", "Guerrero"),
    "745": ("Ayutla de los Libres", "Guerrero"),
    "746": ("Chicontepec", "Veracruz"),
    "747": ("Chilpancingo", "Guerrero"),
    "748": ("Apan", "Hidalgo"),
    "749": ("Calpulalpan", "Tlaxcala"),
    "751": ("Puente de Ixtla", "Morelos"),
    "753": ("Lázaro Cárdenas", "Michoacán"),
    "754": ("Tixtla", "Guerrero"),
    "755": ("Zihuatanejo", "Guerrero"),
    "756": ("Chilapa", "Guerrero"),
    "757": ("Tlapa de Comonfort", "Guerrero"),
    "758": ("Petatlán", "Guerrero"),
    "759": ("Ixmiquilpan", "Hidalgo"),
    "761": ("Jilotepec", "Estado de México"),
    "762": ("Taxco", "Guerrero"),
    "763": ("Tezontepec de Aldama", "Hidalgo"),
    "764": ("Xicotepec", "Puebla"),
    "765": ("Álamo Temapache", "Veracruz"),
    "766": ("Gutiérrez Zamora", "Veracruz"),
    "767": ("Ciudad Altamirano", "Guerrero"),
    "768": ("Tamiahua", "Veracruz"),
    "769": ("Axochiapan", "Morelos"),
    "771": ("Pachuca", "Hidalgo"),
    "772": ("Actopan", "Hidalgo"),
    "773": ("Tula de Allende", "Hidalgo"),
    "774": ("Zacualtipán", "Hidalgo"),
    "775": ("Tulancingo", "Hidalgo"),
    "776": ("Huauchinango", "Puebla"),
    "777": ("Cuernavaca", "Morelos"),
    "778": ("Atotonilco de Tula", "Hidalgo"),
    "779": ("Tizayuca", "Hidalgo"),
    "781": ("Coyuca de Benítez", "Guerrero"),
    "782": ("Poza Rica", "Veracruz"),
    "783": ("Tuxpan", "Veracruz"),
    "784": ("Papantla", "Veracruz"),
    "785": ("Cerro Azul", "Veracruz"),
    "786": ("Ciudad Hidalgo", "Michoacán"),
    "789": ("Huejutla", "Hidalgo"),
    "791": ("Ciudad Sahagún", "Hidalgo"),
    "797": ("Zacatlán", "Puebla"),
    "821": ("Linares", "Nuevo León"),
    "823": ("General Bravo", "Nuevo León"),
    "824": ("Sabinas Hidalgo", "Nuevo León"),
    "825": ("General Zuazua", "Nuevo León"),
    "826": ("Montemorelos", "Nuevo León"),
    "828": ("Cadereyta Jiménez", "Nuevo León"),
    "829": ("Villa Aldama", "Nuevo León"),
    "831": ("Ciudad Mante", "Tamaulipas"),
    "832": ("Llera", "Tamaulipas"),
    "833": ("Tampico", "Tamaulipas"),
    "834": ("Ciudad Victoria", "Tamaulipas"),
    "835": ("Soto la Marina", "Tamaulipas"),
    "836": ("González", "Tamaulipas"),
    "841": ("San Fernando", "Tamaulipas"),
    "842": ("General Cepeda", "Coahuila"),
    "844": ("Saltillo", "Coahuila"),
    "845": ("Ébano", "San Luis Potosí"),
    "846": ("Pánuco", "Veracruz"),
    "861": ("Nueva Rosita", "Coahuila"),
    "862": ("Allende", "Coahuila"),
    "864": ("Múzquiz", "Coahuila"),
    "866": ("Monclova", "Coahuila"),
    "867": ("Nuevo Laredo", "Tamaulipas"),
    "868": ("Matamoros", "Tamaulipas"),
    "869": ("Cuatro Ciénegas", "Coahuila"),
    "871": ("Torreón", "Coahuila"),
    "872": ("Francisco I. Madero", "Coahuila"),
    "873": ("Anáhuac", "Nuevo León"),
    "877": ("Ciudad Acuña", "Coahuila"),
    "878": ("Piedras Negras", "Coahuila"),
    "891": ("Camargo", "Tamaulipas"),
    "892": ("Cerralvo", "Nuevo León"),
    "894": ("Valle Hermoso", "Tamaulipas"),
    "897": ("Miguel Alemán", "Tamaulipas"),
    "899": ("Reynosa", "Tamaulipas"),
    "913": ("Frontera", "Tabasco"),
    "914": ("Cunduacán", "Tabasco"),
    "916": ("Palenque", "Chiapas"),
    "917": ("Huimanguillo", "Tabasco"),
    "918": ("Pijijiapan", "Chiapas"),
    "919": ("Ocosingo", "Chiapas"),
    "921": ("Coatzacoalcos", "Veracruz"),
    "922": ("Minatitlán", "Veracruz"),
    "923": ("Las Choapas", "Veracruz"),
    "924": ("Acayucan", "Veracruz"),
    "932": ("Pichucalco", "Chiapas"),
    "933": ("Comalcalco", "Tabasco"),
    "934": ("Tenosique", "Tabasco"),
    "936": ("Macuspana", "Tabasco"),
    "937": ("Cárdenas", "Tabasco"),
    "938": ("Ciudad del Carmen", "Campeche"),
    "951": ("Oaxaca de Juárez", "Oaxaca"),
    "953": ("Huajuapan de León", "Oaxaca"),
    "954": ("Pinotepa Nacional", "Oaxaca"),
    "958": ("Santa María Huatulco", "Oaxaca"),
    "961": ("Tuxtla Gutiérrez", "Chiapas"),
    "962": ("Tapachula", "Chiapas"),
    "963": ("Comitán", "Chiapas"),
    "964": ("Huixtla", "Chiapas"),
    "965": ("Villaflores", "Chiapas"),
    "966": ("Arriaga", "Chiapas"),
    "967": ("San Cristóbal de las Casas", "Chiapas"),
    "968": ("Cintalapa", "Chiapas"),
    "969": ("Progreso", "Yucatán"),
    "971": ("Juchitán", "Oaxaca"),
    "972": ("Matías Romero", "Oaxaca"),
    "981": ("Campeche", "Campeche"),
    "982": ("Champotón", "Campeche"),
    "983": ("Chetumal", "Quintana Roo"),
    "984": ("Playa del Carmen", "Quintana Roo"),
    "985": ("Valladolid", "Yucatán"),
    "986": ("Tizimín", "Yucatán"),
    "987": ("Cozumel", "Quintana Roo"),
    "988": ("Umán", "Yucatán"),
    "990": ("Mérida", "Yucatán"),
    "991": ("Motul", "Yucatán"),
    "992": ("Venustiano Carranza", "Chiapas"),
    "993": ("Villahermosa", "Tabasco"),
    "994": ("Chahuites", "Oaxaca"),
    "995": ("Jalapa del Marqués", "Oaxaca"),
    "996": ("Calkiní", "Campeche"),
    "997": ("Ticul", "Yucatán"),
    "998": ("Cancún", "Quintana Roo"),
    "999": ("Mérida", "Yucatán"),
}

ESTADOS = [
    "Aguascalientes", "Baja California", "Baja California Sur", "Campeche", "Chiapas", "Chihuahua",
    "Ciudad de México", "Coahuila", "Colima", "Durango", "Estado de México", "Guanajuato", "Guerrero",
    "Hidalgo", "Jalisco", "Michoacán", "Morelos", "Nayarit", "Nuevo León", "Oaxaca", "Puebla", "Querétaro",
    "Quintana Roo", "San Luis Potosí", "Sinaloa", "Sonora", "Tabasco", "Tamaulipas", "Tlaxcala",
    "Veracruz", "Yucatán", "Zacatecas",
]

# Primeros 2 dígitos del código postal -> estado (SEPOMEX).
_CP = [
    (1, 16, "Ciudad de México"), (20, 20, "Aguascalientes"), (21, 22, "Baja California"),
    (23, 23, "Baja California Sur"), (24, 24, "Campeche"), (25, 27, "Coahuila"), (28, 28, "Colima"),
    (29, 30, "Chiapas"), (31, 33, "Chihuahua"), (34, 35, "Durango"), (36, 38, "Guanajuato"),
    (39, 41, "Guerrero"), (42, 43, "Hidalgo"), (44, 49, "Jalisco"), (50, 57, "Estado de México"),
    (58, 61, "Michoacán"), (62, 62, "Morelos"), (63, 63, "Nayarit"), (64, 67, "Nuevo León"),
    (68, 71, "Oaxaca"), (72, 75, "Puebla"), (76, 76, "Querétaro"), (77, 77, "Quintana Roo"),
    (78, 79, "San Luis Potosí"), (80, 82, "Sinaloa"), (83, 85, "Sonora"), (86, 86, "Tabasco"),
    (87, 89, "Tamaulipas"), (90, 90, "Tlaxcala"), (91, 96, "Veracruz"), (97, 97, "Yucatán"),
    (98, 99, "Zacatecas"),
]

_SINONIMOS = {
    "df": "Ciudad de México", "distrito federal": "Ciudad de México", "cdmx": "Ciudad de México",
    "cd de mexico": "Ciudad de México", "mexico df": "Ciudad de México",
    "edomex": "Estado de México", "edo de mexico": "Estado de México", "edo mex": "Estado de México",
    "estado de mexico": "Estado de México", "mexico": "Estado de México",
    "coahuila de zaragoza": "Coahuila", "michoacan de ocampo": "Michoacán",
    "veracruz de ignacio de la llave": "Veracruz", "ver": "Veracruz", "pue": "Puebla", "tlax": "Tlaxcala",
    "qro": "Querétaro", "slp": "San Luis Potosí", "nl": "Nuevo León", "bc": "Baja California",
    "bcs": "Baja California Sur", "gto": "Guanajuato", "jal": "Jalisco", "oax": "Oaxaca", "gro": "Guerrero",
    "hgo": "Hidalgo", "mor": "Morelos", "chis": "Chiapas", "tab": "Tabasco", "yuc": "Yucatán",
    "q roo": "Quintana Roo", "zac": "Zacatecas", "ags": "Aguascalientes", "son": "Sonora", "sin": "Sinaloa",
    "tamps": "Tamaulipas", "chih": "Chihuahua", "dgo": "Durango", "nay": "Nayarit", "col": "Colima",
    "camp": "Campeche", "mich": "Michoacán",
}


def _norm(t):
    t = unicodedata.normalize("NFD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", t).strip()


_POR_NOMBRE = {_norm(e): e for e in ESTADOS}
_POR_NOMBRE.update({_norm(k): v for k, v in _SINONIMOS.items()})


def estado_normalizado(texto):
    """'PUEBLA' / 'Pue.' / 'Edo. de México' -> nombre oficial, o None."""
    n = re.sub(r"\s+", " ", _norm(texto))
    if not n:
        return None
    return _POR_NOMBRE.get(n) or _POR_NOMBRE.get(n.replace("edo ", "estado "))


def estado_en_texto(texto):
    """Busca el nombre de un estado dentro de un texto libre (colonia,
    población...). Solo nombres completos, para no adivinar de más."""
    n = " " + re.sub(r"\s+", " ", _norm(texto)) + " "
    for e in sorted(ESTADOS, key=len, reverse=True):
        if e in ("Estado de México",):
            continue
        if " " + _norm(e) + " " in n:
            return e
    return None


def estado_por_cp(cp):
    d = re.sub(r"\D", "", str(cp or ""))
    if len(d) != 5:
        return None
    p = int(d[:2])
    for a, b, e in _CP:
        if a <= p <= b:
            return e
    return None


def telefono_10(texto):
    """Primer teléfono de 10 dígitos que encuentre (quita +52, 01, 044...)."""
    for pedazo in re.split(r"[/,;]| y |\|", str(texto or "")):
        d = re.sub(r"\D", "", pedazo)
        if len(d) == 13 and d.startswith("521"):
            d = d[3:]
        elif len(d) == 12 and d.startswith("52"):
            d = d[2:]
        elif len(d) in (12, 13) and d[:3] in ("044", "045"):
            d = d[3:]
        elif len(d) == 12 and d.startswith("01"):
            d = d[2:]
        if len(d) == 10:
            return d
    return None


def lada_de(telefono):
    d = telefono_10(telefono)
    if not d:
        return None
    if d[:2] in LADAS:
        return d[:2]
    if d[:3] in LADAS:
        return d[:3]
    return None


def _sin_estado(poblacion):
    """'HUAMANTLA, TLAXCALA' -> 'HUAMANTLA' (quita el estado si viene pegado)."""
    partes = [p.strip() for p in re.split(r"[,.;-]", str(poblacion or "")) if p.strip()]
    if len(partes) > 1 and (estado_normalizado(partes[-1]) or estado_en_texto(partes[-1])):
        partes = partes[:-1]
    return ", ".join(partes) if partes else str(poblacion or "").strip()


def _estado_de_poblacion(poblacion):
    partes = [p.strip() for p in re.split(r"[,;-]", str(poblacion or "")) if p.strip()]
    if len(partes) > 1:
        e = estado_normalizado(partes[-1])
        if e:
            return e
    return estado_en_texto(poblacion)


def ubicar(estado_dir=None, municipio_dir=None, cp=None, poblacion=None, telefonos=()):
    """Regresa (estado, municipio, fuente). Primero la dirección (estado y
    ciudad capturados, código postal o el nombre de un estado en la
    población); si no hay, la lada del teléfono. Si la dirección da el
    estado pero no el municipio, y la lada es de ese mismo estado, el
    municipio se toma de la lada."""
    municipio = (municipio_dir or "").strip()
    estado = None
    if estado_dir:
        estado = estado_normalizado(estado_dir)
    estado = estado or estado_por_cp(cp) or (_estado_de_poblacion(poblacion) if poblacion else None)
    if not municipio and poblacion and estado:
        municipio = _sin_estado(poblacion)
    lada = None
    for t in telefonos:
        lada = lada_de(t)
        if lada:
            break
    if estado:
        if not municipio and lada and LADAS[lada][1] == estado:
            return estado, LADAS[lada][0], "Dirección + lada"
        return estado, municipio, "Dirección"
    if lada:
        ciudad, est = LADAS[lada]
        if poblacion and str(poblacion).strip():
            return est, _sin_estado(poblacion), "Lada " + lada + " (municipio de la dirección)"
        return est, ciudad, "Lada " + lada
    return "", municipio, "Sin datos"
