// Makes and models sold or commonly driven across the African market
// (Kenya first, plus the regional used-import and Chinese/Indian brands now
// common in East, West, Southern and North Africa). Used by the motor quote
// form to turn "Make"/"Model" into dependent dropdowns.
//
// This is a convenience list, not a gate: the form always offers "Other"
// for both fields, so a make or model that isn't listed (or a very new one)
// can still be typed in. To add one, just add it to the right array below -
// keep models alphabetical-ish and use the name as printed on a logbook.

export const OTHER_OPTION = "__other__";

// Shown first in the Make dropdown - the brands most Kenyan customers drive.
export const POPULAR_MAKES = [
  "Toyota",
  "Nissan",
  "Mazda",
  "Honda",
  "Subaru",
  "Mitsubishi",
  "Suzuki",
  "Isuzu",
  "Volkswagen",
  "Mercedes-Benz",
  "BMW",
  "Ford",
  "Hyundai",
  "Kia",
  "Land Rover",
  "Audi",
];

export const VEHICLE_MODELS: Record<string, string[]> = {
  // ---------------- Japanese ----------------
  Toyota: [
    "Allex", "Allion", "Alphard", "Aqua", "Auris", "Avensis", "Axio", "Belta", "bB", "Blade", "Brevis", "C-HR",
    "Camry", "Carina", "Corolla", "Corolla Cross", "Corolla Fielder", "Corolla Rumion", "Corona", "Cresta", "Crown",
    "Duet", "Estima", "Fortuner", "FJ Cruiser", "Granvia", "Harrier", "Hiace", "Hilux", "Ipsum", "Isis", "Kluger",
    "Land Cruiser", "Land Cruiser Prado", "Land Cruiser V8", "Mark II", "Mark X", "Noah", "Passo", "Premio", "Prius",
    "Prius Alpha", "ProBox", "Ractis", "Raum", "RAV4", "Rush", "Sai", "Sienta", "Spacio", "Starlet", "Succeed",
    "Super Custom", "Surf", "Tacoma", "Townace", "Tundra", "Vanguard", "Vellfire", "Verso", "Vitz", "Voxy",
    "Wigo", "Wish", "Yaris", "Yaris Cross", "Dyna", "Coaster", "Quantum", "Etios", "Avanza", "Veloz", "Rumion",
  ],
  Nissan: [
    "AD Van", "Almera", "Altima", "Aura", "Bluebird", "Bluebird Sylphy", "Caravan", "Cefiro", "Cube", "Dayz",
    "Dualis", "Elgrand", "Expert", "Fairlady Z", "Fuga", "Hardbody", "Juke", "Kicks", "Latio", "Leaf", "March",
    "Maxima", "Micra", "Murano", "Navara", "Note", "NP200", "NP300", "NV200", "NV350", "Pathfinder", "Patrol",
    "Primera", "Pulsar", "Qashqai", "Rogue", "Safari", "Sentra", "Serena", "Skyline", "Stagea", "Sunny", "Teana",
    "Terrano", "Tiida", "Wingroad", "X-Trail", "Urvan", "Magnite", "Sylphy", "Titan", "Civilian", "Diesel UD",
  ],
  Mazda: [
    "2", "3", "6", "323", "626", "Atenza", "Axela", "Biante", "BT-50", "Bongo", "Carol", "CX-3", "CX-30", "CX-5",
    "CX-60", "CX-7", "CX-9", "Demio", "Familia", "MPV", "MX-5", "Premacy", "Tribute", "Verisa", "Titan", "Scrum",
  ],
  Honda: [
    "Accord", "Airwave", "Acty", "City", "Civic", "CR-V", "Crossroad", "Edix", "Elysion", "Fit", "Fit Shuttle",
    "Freed", "HR-V", "Insight", "Jazz", "Legend", "Mobilio", "N-Box", "N-One", "N-WGN", "Odyssey", "Partner",
    "Pilot", "Stepwgn", "Stream", "Vezel", "Zest", "BR-V", "Amaze", "WR-V", "Ridgeline",
  ],
  Subaru: [
    "Crosstrek", "Exiga", "Forester", "Impreza", "Impreza Sportswagon", "Legacy", "Legacy Outback", "Levorg",
    "Outback", "Sambar", "Stella", "Trezia", "Tribeca", "WRX", "XV", "BRZ", "Justy", "R2",
  ],
  Mitsubishi: [
    "ASX", "Attrage", "Canter", "Colt", "Delica", "Eclipse Cross", "Galant", "Grandis", "i-MiEV", "L200", "L300",
    "Lancer", "Minica", "Mirage", "Outlander", "Pajero", "Pajero IO", "Pajero Mini", "Pajero Sport", "RVR",
    "Shogun", "Space Star", "Triton", "Xpander", "Fuso Fighter", "Fuso Canter", "Fuso Rosa",
  ],
  Suzuki: [
    "Alto", "Baleno", "Carry", "Celerio", "Ciaz", "Dzire", "Ertiga", "Every", "Grand Vitara", "Hustler", "Ignis",
    "Jimny", "Kizashi", "Landy", "Mighty Boy", "Palette", "Pixis", "S-Presso", "Spacia", "Splash", "Swift",
    "SX4", "Vitara", "Wagon R", "XL6", "Fronx", "Brezza", "Eeco",
  ],
  Isuzu: [
    "D-Max", "Elf", "F-Series", "Forward", "FRR", "FSR", "FTR", "FVR", "FVZ", "Giga", "KB", "MU-X", "N-Series",
    "NKR", "NMR", "NPR", "NQR", "Rodeo", "Trooper", "Bighorn", "Mu-7", "Wizard", "Panther",
  ],
  Daihatsu: ["Atrai", "Boon", "Charade", "Copen", "Hijet", "Materia", "Mira", "Move", "Rocky", "Sirion", "Tanto", "Terios", "Thor", "Cast", "Terios Kid", "Gran Max", "Xenia"],
  Datsun: ["Go", "Go+", "Redi-Go", "Mi-Do", "On-Do", "1200", "Bluebird", "Sunny"],
  Lexus: ["CT 200h", "ES", "GS", "GX", "IS", "LC", "LS", "LX", "NX", "RC", "RX", "UX", "LM", "RZ"],
  Infiniti: ["FX", "G35", "G37", "M", "Q30", "Q50", "Q60", "Q70", "QX30", "QX50", "QX56", "QX60", "QX70", "QX80"],
  Hino: ["300", "500", "700", "Dutro", "Ranger", "Profia", "Rainbow", "Liesse", "Poncho", "Selega"],
  "UD Trucks": ["Condor", "Croner", "Kuzer", "Quester", "Quon", "Big Thumb", "PKB", "CWA", "CGB", "Condor MK"],
  Yamaha: ["Crux", "FZ", "FZS", "Mio", "NMAX", "R15", "Sniper", "Tricity", "YBR125", "XTZ", "XSR", "MT-07", "MT-09", "Tenere"],

  // ---------------- Korean ----------------
  Hyundai: [
    "Accent", "Atos", "Avante", "Creta", "Elantra", "Eon", "Getz", "Grand i10", "H-1", "H100", "i10", "i20", "i30",
    "i40", "iX35", "Kona", "Matrix", "Palisade", "Santa Fe", "Solaris", "Sonata", "Staria", "Terracan", "Tucson",
    "Veloster", "Venue", "Verna", "Mighty", "HD65", "HD72", "HD78", "County", "Ioniq", "Tucson NX4",
  ],
  Kia: [
    "Carens", "Carnival", "Ceed", "Cerato", "Forte", "K2700", "K3", "K5", "Morning", "Niro", "Optima", "Picanto",
    "Pregio", "Rio", "Rondo", "Seltos", "Sephia", "Sonet", "Sorento", "Soul", "Sportage", "Stinger", "Stonic",
    "Telluride", "Bongo", "Sedona", "Besta", "EV6", "Pride",
  ],
  SsangYong: ["Actyon", "Korando", "Kyron", "Musso", "Rexton", "Rodius", "Tivoli", "Torres"],
  Daewoo: ["Lanos", "Matiz", "Nubira", "Tico", "Espero", "Leganza"],

  // ---------------- German ----------------
  "Mercedes-Benz": [
    "A-Class", "B-Class", "C-Class", "CLA", "CLS", "E-Class", "G-Class", "GLA", "GLB", "GLC", "GLE", "GLK", "GLS",
    "M-Class", "ML", "R-Class", "S-Class", "SL", "SLK", "V-Class", "Vito", "Sprinter", "Viano", "X-Class", "Actros",
    "Atego", "Axor", "Unimog", "Citan", "EQC", "EQE", "EQS", "GL-Class", "Travego", "Tourismo",
  ],
  BMW: [
    "1 Series", "2 Series", "3 Series", "4 Series", "5 Series", "6 Series", "7 Series", "8 Series", "i3", "i4", "i8",
    "iX", "iX3", "M2", "M3", "M4", "M5", "X1", "X2", "X3", "X4", "X5", "X6", "X7", "Z4", "R1200GS", "F850GS",
  ],
  Audi: ["A1", "A3", "A4", "A5", "A6", "A7", "A8", "e-tron", "Q2", "Q3", "Q5", "Q7", "Q8", "R8", "RS3", "RS6", "S3", "S4", "TT", "Allroad"],
  Volkswagen: [
    "Amarok", "Arteon", "Beetle", "Caddy", "California", "Caravelle", "CC", "Crafter", "Eos", "Golf", "ID.4",
    "Jetta", "Kombi", "Multivan", "Passat", "Polo", "Polo Vivo", "Scirocco", "Sharan", "T-Cross", "T-Roc",
    "Tiguan", "Touareg", "Touran", "Transporter", "Up!", "Vento", "Taigun", "Virtus", "Atlas",
  ],
  Opel: ["Adam", "Agila", "Antara", "Astra", "Corsa", "Insignia", "Meriva", "Mokka", "Vectra", "Zafira", "Combo", "Vivaro", "Kadett", "Omega"],
  Porsche: ["911", "718 Boxster", "718 Cayman", "Cayenne", "Macan", "Panamera", "Taycan", "Boxster", "Cayman"],
  Mini: ["Cooper", "Cooper S", "Clubman", "Countryman", "Paceman", "One", "Convertible", "John Cooper Works"],
  Smart: ["Fortwo", "Forfour", "Roadster"],
  MAN: ["TGA", "TGL", "TGM", "TGS", "TGX", "F2000", "CLA", "Lion's Coach", "Lion's City", "L2000", "TGE"],

  // ---------------- American ----------------
  Ford: [
    "B-Max", "C-Max", "EcoSport", "Edge", "Escape", "Everest", "Explorer", "F-150", "F-250", "F-350", "Fiesta",
    "Figo", "Focus", "Fusion", "Galaxy", "Ka", "Kuga", "Mondeo", "Mustang", "Puma", "Ranger", "S-Max", "Territory",
    "Tourneo", "Transit", "Transit Custom", "Capri", "Cargo", "Courier", "Bronco", "Bantam", "Laser", "Telstar", "Escort",
  ],
  Chevrolet: ["Aveo", "Camaro", "Captiva", "Colorado", "Corvette", "Cruze", "Equinox", "Lacetti", "Malibu", "Optra", "Orlando", "Silverado", "Spark", "Suburban", "Tahoe", "Trailblazer", "Utility", "Sail", "Spin", "N300", "Blazer"],
  Jeep: ["Cherokee", "Commander", "Compass", "Gladiator", "Grand Cherokee", "Patriot", "Renegade", "Wrangler", "Wagoneer"],
  Dodge: ["Caliber", "Challenger", "Charger", "Dakota", "Durango", "Journey", "Nitro", "Ram", "Grand Caravan"],
  Chrysler: ["300C", "Grand Voyager", "PT Cruiser", "Sebring", "Voyager", "Pacifica"],
  GMC: ["Acadia", "Canyon", "Sierra", "Terrain", "Yukon", "Savana"],
  Cadillac: ["CTS", "Escalade", "SRX", "XT5", "ATS", "CT6"],
  Tesla: ["Model 3", "Model S", "Model X", "Model Y", "Cybertruck"],
  Hummer: ["H2", "H3", "H1"],
  Lincoln: ["Navigator", "MKZ", "Aviator", "Continental"],

  // ---------------- British ----------------
  "Land Rover": [
    "Defender", "Defender 90", "Defender 110", "Discovery", "Discovery 3", "Discovery 4", "Discovery 5",
    "Discovery Sport", "Freelander", "Range Rover", "Range Rover Evoque", "Range Rover Sport", "Range Rover Velar",
    "Series III", "Land Rover 109",
  ],
  Jaguar: ["E-Pace", "F-Pace", "F-Type", "I-Pace", "S-Type", "X-Type", "XE", "XF", "XJ", "XK"],
  Bentley: ["Bentayga", "Continental GT", "Flying Spur", "Mulsanne"],
  "Rolls-Royce": ["Cullinan", "Ghost", "Phantom", "Wraith", "Dawn"],
  MG: ["3", "5", "6", "GS", "HS", "ZS", "ZS EV", "RX5", "MG4", "Hector", "Gloster", "Marvel R", "T60"],
  "Aston Martin": ["DB11", "DBX", "Vantage", "DBS"],
  Bedford: ["TK", "CF", "Rascal", "Midi", "JJL"],
  Austin: ["Mini", "Maestro", "Metro"],
  Morris: ["Minor", "Marina"],

  // ---------------- French / Italian / other European ----------------
  Peugeot: ["106", "107", "205", "206", "207", "208", "301", "306", "307", "308", "407", "508", "2008", "3008", "5008", "Partner", "Expert", "Boxer", "Rifter", "Landtrek", "504", "404", "Traveller", "Pick Up"],
  Renault: ["Captur", "Clio", "Duster", "Fluence", "Kadjar", "Kangoo", "Koleos", "Kwid", "Laguna", "Logan", "Master", "Megane", "Sandero", "Scenic", "Symbol", "Trafic", "Triber", "Twingo", "Alaskan", "Stepway", "Oroch", "Arkana", "Kiger", "R4", "Express"],
  "Citroën": ["Berlingo", "C1", "C2", "C3", "C3 Aircross", "C4", "C4 Cactus", "C5", "C5 Aircross", "C-Elysée", "DS3", "Dispatch", "Jumper", "Jumpy", "Xsara", "Saxo", "Picasso", "Nemo", "Relay"],
  Fiat: ["500", "500X", "Albea", "Bravo", "Doblo", "Ducato", "Fiorino", "Grande Punto", "Linea", "Palio", "Panda", "Punto", "Siena", "Strada", "Tipo", "Uno", "Fullback", "Scudo", "126"],
  "Alfa Romeo": ["147", "156", "159", "Giulia", "Giulietta", "MiTo", "Stelvio", "Tonale", "Brera", "GT"],
  Volvo: ["C30", "C70", "S40", "S60", "S80", "S90", "V40", "V50", "V60", "V70", "V90", "XC40", "XC60", "XC70", "XC90", "FH", "FM", "FMX", "FL", "FE", "B-Series", "9700", "9900"],
  Skoda: ["Fabia", "Kamiq", "Karoq", "Kodiaq", "Octavia", "Rapid", "Roomster", "Scala", "Superb", "Yeti"],
  Seat: ["Altea", "Arona", "Ateca", "Cordoba", "Ibiza", "Leon", "Toledo", "Alhambra", "Tarraco"],
  Dacia: ["Dokker", "Duster", "Logan", "Sandero", "Lodgy", "Jogger", "Spring"],
  Saab: ["9-3", "9-5", "900", "9000"],
  Lancia: ["Delta", "Ypsilon", "Musa"],
  Maserati: ["Ghibli", "Levante", "Quattroporte", "GranTurismo", "Grecale"],
  Ferrari: ["488", "F8", "Roma", "California", "812", "Portofino"],
  Lamborghini: ["Huracan", "Urus", "Aventador"],
  Iveco: ["Daily", "Eurocargo", "Stralis", "Trakker", "S-Way", "Eurotech", "Massif", "Turbo Daily", "Eurostar", "Bus 70C"],
  DAF: ["CF", "LF", "XF", "XG", "XD", "95XF", "75CF", "85CF", "45", "55"],
  Scania: ["P-Series", "G-Series", "R-Series", "S-Series", "K-Series", "N-Series", "F-Series", "113", "124", "Touring"],
  Setra: ["S 415", "S 516", "TopClass", "ComfortClass"],
  Neoplan: ["Cityliner", "Starliner", "Tourliner"],

  // ---------------- Chinese ----------------
  Chery: ["Arrizo 5", "Arrizo 6", "QQ", "Tiggo 2", "Tiggo 4", "Tiggo 7", "Tiggo 8", "Omoda 5", "Jaecoo 7", "J11", "Eastar", "A1", "Fulwin"],
  Geely: ["Coolray", "Emgrand", "Emgrand 7", "Atlas", "Azkarra", "Monjaro", "Tugella", "GC6", "Okavango", "Panda", "CK", "LC", "Starray"],
  BYD: ["Atto 3", "Dolphin", "Han", "Seal", "Seagull", "Song Plus", "Tang", "F3", "S6", "Yuan Plus", "Qin", "Shark", "e6", "T3", "K9", "Sealion 6", "Sealion 7"],
  Haval: ["H1", "H2", "H5", "H6", "H9", "Jolion", "Dargo", "Big Dog", "F7", "H6 GT", "M6"],
  "Great Wall": ["Steed", "Wingle 5", "Wingle 7", "Wingle 6", "Poer", "Hover", "Hover H3", "Hover H5", "Voleex C30", "Deer", "Safe", "Florid"],
  GWM: ["Tank 300", "Tank 500", "Ora", "Poer", "Cannon", "Haval H6", "P-Series"],
  JAC: ["J2", "J3", "J4", "J5", "J6", "S2", "S3", "S4", "S5", "T6", "T8", "T9", "X200", "X250", "Refine", "Sunray", "Hunter", "iEV7", "N-Series", "HFC"],
  Foton: ["Tunland", "Tunland G7", "View", "Aumark", "Auman", "Ollin", "Gratour", "Toano", "Sauvana", "Forland", "Thunder", "Aumark S", "BJ"],
  FAW: ["Jiefang", "J6", "J7", "CA", "Xiali", "V2", "Besturn", "Hongqi", "Tiger V", "Sirius", "T77", "Bestune B70", "Bestune T77"],
  Dongfeng: ["Captain", "Rich", "Rich 6", "Glory 580", "Glory 330", "Joyear", "Kinland", "Kingrun", "Duolika", "Fengon", "Aeolus", "Mage", "KR", "Forthing", "Fengshen"],
  Changan: ["Alsvin", "CS15", "CS35", "CS55", "CS75", "CS95", "Eado", "Hunter", "Oshan X5", "Oshan X7", "Uni-K", "Uni-T", "Uni-V", "Star", "Benni", "Deepal", "Lumin"],
  Lifan: ["520", "620", "X50", "X60", "X70", "Foison", "Smily", "Cebrium", "Breez"],
  Zotye: ["T600", "Z300", "Z360", "Z500", "Nomad", "5008"],
  BAIC: ["BJ40", "X35", "X55", "X75", "D20", "D50", "Senova", "Plus", "BJ212", "Wevan", "Weiwang"],
  Maxus: ["D90", "G10", "T60", "T70", "T90", "V80", "Deliver 9", "eDeliver 3", "eDeliver 9", "V90", "Euniq", "Mifa"],
  Wuling: ["Hongguang", "Mini EV", "Almaz", "Cortez", "Confero", "Air EV", "Bingo", "Xingchen"],
  Hongqi: ["H5", "H9", "HS5", "HS7", "E-HS9"],
  Zeekr: ["001", "007", "009", "X"],
  Jetour: ["X70", "X90", "X95", "Dashing", "T2"],
  Jaecoo: ["J7", "J5", "J8"],
  Omoda: ["C5", "E5"],
  Leapmotor: ["T03", "C10", "C11"],
  Ora: ["Funky Cat", "Good Cat", "Ballet Cat"],
  Tank: ["300", "500"],
  Kaiyi: ["X3", "E5", "Kunlun"],
  Soueast: ["DX3", "DX5", "DX7", "V3", "V5", "Lioncel"],
  Hafei: ["Minyi", "Lobo", "Zhongyi", "Saibao"],
  DFSK: ["Glory 560", "Glory 580", "Glory i-Auto", "K01", "K05", "K07", "V21", "V22", "V25", "C31", "C32", "C35", "C37", "Mini Truck", "Super Cab"],
  Sinotruk: ["Howo", "Howo A7", "Howo T5G", "Howo T7H", "Sitrak", "Golden Prince", "Steyr", "Homan", "Hohan"],
  Shacman: ["F2000", "F3000", "F5000", "M3000", "X3000", "X5000", "H3000", "L3000", "Delong", "Aolong"],
  Higer: ["KLQ6129", "KLQ6109", "KLQ6119", "Paragon", "H-Series", "V-Series", "Kls", "Ace"],
  Yutong: ["ZK6122", "ZK6107", "ZK6119", "ZK6129", "ZK6930", "ZK6737", "ZK6831", "E-Series", "T-Series", "Grand", "Cruiser"],
  "King Long": ["XMQ6127", "XMQ6900", "XMQ6858", "Kingo", "Victory", "Cooper"],
  "Golden Dragon": ["XML6127", "XML6957", "XML6807", "XML6602", "Kaiwo", "Navigator"],
  Zhongtong: ["LCK6122", "LCK6128", "LCK6118", "Magnate", "Grand"],
  "Ankai": ["HFF6129", "HFF6120", "HFF6900"],
  Sunwin: ["WIN6120", "WIN6129"],
  CAMC: ["HN", "Hanma", "Star"],
  Beiben: ["2538", "ND", "V3", "V3ET"],
  Jmc: ["Vigus", "Vigus Pro", "Teshun", "Baodian", "Carrying", "Conquer", "Yuhu", "Landwind", "Kaiyun", "Shunda", "Dadao"],
  Changhe: ["Ideal", "Freedom", "Beidouxing", "Q25", "Q35"],

  // ---------------- Indian ----------------
  Tata: ["Ace", "Ace Gold", "Aria", "Bolt", "Harrier", "Hexa", "Indica", "Indigo", "Manza", "Nano", "Nexon", "Punch", "Safari", "Sumo", "Super Ace", "Tiago", "Tigor", "Xenon", "Yodha", "Intra", "LPT 709", "LPT 1109", "LPT 1613", "LPT 2518", "LPT 3118", "Prima", "Signa", "Ultra", "Starbus", "Marcopolo", "Winger", "Magic", "407", "709", "Telcoline"],
  Mahindra: ["Bolero", "Bolero Pik-Up", "Imperio", "KUV100", "Marazzo", "Pik-Up", "Quanto", "Scorpio", "Scorpio-N", "Thar", "TUV300", "XUV300", "XUV500", "XUV700", "Xylo", "Alturas", "Verito", "Genio", "Supro", "Jeeto", "Furio", "Blazo", "Loadking", "Cruzio", "Tourister", "Maxximo", "Armada", "Commander"],
  "Ashok Leyland": ["Boss", "Captain", "Comet", "Ecomet", "Stile", "Dost", "Partner", "Viking", "Lynx", "Cheetah", "U-Truck", "Falcon", "Tusker", "Oyster", "Sunshine", "Bada Dost"],
  Eicher: ["Pro 1049", "Pro 2049", "Pro 3015", "Pro 5016", "Pro 6016", "Pro 8031", "Skyline", "Starline", "Terra", "Skyline Pro", "Eicher 10.90", "Eicher 11.10", "Eicher 20.16"],
  Force: ["Traveller", "Trax", "Gurkha", "Tempo", "Urbania", "Cruiser", "Trump", "Kargo King", "Shaktiman"],
  Maruti: ["800", "Alto", "Baleno", "Celerio", "Ciaz", "Dzire", "Eeco", "Ertiga", "Grand Vitara", "Ignis", "Swift", "S-Presso", "Vitara Brezza", "Wagon R", "Omni", "Gypsy", "Zen", "Esteem", "XL6"],
  Piaggio: ["Ape", "Ape City", "Ape Xtra", "Ape Auto", "Porter", "Vespa", "Liberty", "Medley", "Beverly"],
  Bajaj: ["Boxer", "Boxer 150", "Boxer BM100", "Boxer X", "CT100", "Discover", "Platina", "Pulsar", "Dominar", "Avenger", "RE", "RE 4S", "Maxima", "Qute", "Maxima Cargo", "Maxima C", "Tuk-Tuk"],
  TVS: ["Apache", "HLX", "King", "King Deluxe", "Star City", "Sport", "Jupiter", "Raider", "Ntorq", "Victor", "Radeon", "Phoenix", "Metro", "TVS King Cargo"],
  Hero: ["Splendor", "HF Deluxe", "Passion", "Glamour", "Hunk", "Xtreme", "Super Splendor", "Pleasure", "Maestro", "Destini", "CD Deluxe", "Honda CG"],
  Haojue: ["DK150", "DR160", "HJ125", "HJ150", "Tuoyue", "Express", "Hayabusa", "Haojue Suzuki", "Haojue AX100", "Haojue Boda"],
  "Honda (motorcycle)": ["CG125", "CB125", "CB150", "CBR", "XR150L", "CRF", "Wave", "Dream", "Africa Twin", "Activa", "Navi", "Dio", "Shine", "Unicorn", "Hornet", "Livo", "Grazia"],
  Skygo: ["SG150", "SG125", "SG200", "Flame", "Phoenix", "Skygo 150"],
  Sanlg: ["SL150", "SL125", "SL200", "SL100"],
  Kenbo: ["KB150", "KB125", "Kenbo Boda"],
  Kymco: ["Agility", "Like", "Downtown", "People", "AK550", "Super 8", "Xciting", "K-Pipe", "Spacer"],
  KTM: ["Duke 200", "Duke 390", "Adventure", "RC", "EXC", "SX"],
  "Royal Enfield": ["Classic 350", "Bullet", "Himalayan", "Meteor", "Interceptor", "Continental GT", "Hunter"],
  Sinoray: ["SR125", "SR150", "Sinoray CG"],
  Zongshen: ["ZS125", "ZS150", "Zongshen Boda"],
  Lonchin: ["LX150", "Lonchin"],
  Vespa: ["Primavera", "Sprint", "GTS", "LX", "ET4", "PX"],
  "Harley-Davidson": ["Sportster", "Softail", "Street", "Fat Boy", "Road King", "Iron 883"],
  Ducati: ["Monster", "Panigale", "Multistrada", "Scrambler", "Diavel"],
  Triumph: ["Bonneville", "Tiger", "Street Triple", "Speed Triple", "Trident", "Scrambler"],
  Kawasaki: ["Ninja", "Z", "Versys", "KLX", "Vulcan", "ER-6n", "Z650", "Z900"],
  Aprilia: ["RS 125", "SR 150", "Tuono", "RSV4"],

  // ---------------- Malaysian / SE Asian ----------------
  Proton: ["Exora", "Gen-2", "Persona", "Preve", "Saga", "Satria", "Wira", "X50", "X70", "Savvy", "Iriz", "Waja"],
  Perodua: ["Alza", "Axia", "Bezza", "Kancil", "Kelisa", "Kenari", "Myvi", "Viva", "Ativa", "Aruz"],
  Vinfast: ["VF 5", "VF 6", "VF 7", "VF 8", "VF 9", "VF e34"],

  // ---------------- Trucks, buses, specialist ----------------
  "Mercedes-Benz Trucks": ["Actros", "Atego", "Axor", "Arocs", "Econic", "Unimog", "Zetros", "Vario", "LK", "SK"],
  "Renault Trucks": ["Premium", "Kerax", "Midlum", "T-Series", "C-Series", "K-Series", "Magnum", "Master"],
  "Mitsubishi Fuso": ["Canter", "Fighter", "Super Great", "Rosa", "Aero Star", "Aero Bus", "FE", "FK", "FP", "FV"],
  Freightliner: ["Cascadia", "Columbia", "Century", "M2", "FLD"],
  Kenworth: ["T680", "T800", "W900", "T370"],
  Peterbilt: ["579", "389", "567"],
  Mack: ["Granite", "Anthem", "Pinnacle", "Titan"],
  International: ["ProStar", "LT", "9400i", "Navistar", "Eagle"],
  Tatra: ["T815", "Phoenix", "T148"],
  Kamaz: ["5320", "53215", "6520", "43118", "Kamaz 65115"],
  Ural: ["4320", "375"],
  Gaz: ["Gazelle", "Sobol", "Valdai", "GAZ-66", "Next"],
  Uaz: ["Patriot", "Hunter", "452", "Pickup"],
  Lada: ["Niva", "Granta", "Vesta", "Samara", "2107", "Kalina", "Largus"],
  Marcopolo: ["Paradiso", "Viaggio", "Torino", "Andare", "Volare", "Audace", "G7"],
  Irizar: ["i6", "i8", "Century", "PB"],
  Caterpillar: ["CAT 320", "CAT 330", "CAT 336", "CAT 950", "CAT 966", "CAT 140", "CAT 12G", "CAT D6", "CAT D8", "CAT 416", "CAT 428", "CAT 740", "CAT 773"],
  JCB: ["3CX", "4CX", "JS 200", "JS 220", "Fastrac", "Loadall", "Teletruk", "540-170", "531-70", "1CX", "8018", "Hydradig"],
  Komatsu: ["PC200", "PC300", "PC130", "WA320", "WA470", "D65", "D85", "GD555", "HD465", "PC78", "PC400", "WB97"],
  Hitachi: ["ZX200", "ZX330", "ZX120", "ZX70", "EX200", "Zaxis"],
  "Volvo CE": ["EC210", "EC220", "EC300", "L90", "L120", "A25", "A30", "BL71", "G930", "SD110"],
  Liebherr: ["R 926", "R 936", "L 550", "LTM", "LR 1300"],
  Doosan: ["DX225", "DX300", "DX140", "DL200", "DL250", "DX55", "DX80"],
  Sany: ["SY215", "SY365", "SY135", "SY60", "STC", "SYM", "SY75"],
  XCMG: ["XE215", "XE370", "XE135", "LW300", "XC7", "ZL50G", "QY25K", "XCT", "GR215"],
  Liugong: ["CLG922", "CLG936", "CLG856", "CLG835", "CLG418"],
  Shantui: ["SD16", "SD22", "SD32", "SL50", "SR14"],
  Lonking: ["CDM833", "CDM855", "CDM6225"],
  Zoomlion: ["ZE210", "ZE360", "ZR250", "ZD320", "TC6013", "ZTC"],
  SDLG: ["LG936", "LG946", "LG956", "LG933", "E6210", "E6135"],
  Dynapac: ["CA25", "CA30", "CC122"],
  Bomag: ["BW 211", "BW 213", "BW 120", "BW 100", "BW 177"],
  Hamm: ["3410", "3412", "HD 12"],
  Hyster: ["H3.0", "H2.5", "H5.0", "J1.8", "J2.0", "S3.0"],
  Linde: ["H20", "H25", "H30", "E16", "E20", "R14"],
  Heli: ["CPCD30", "CPCD50", "CPCD25", "CPD15", "CPD20"],
  Tcm: ["FD30", "FD25", "FHD30"],

  // ---------------- Tractors & agricultural ----------------
  "Massey Ferguson": ["MF 135", "MF 165", "MF 240", "MF 260", "MF 275", "MF 290", "MF 375", "MF 385", "MF 399", "MF 435", "MF 440", "MF 445", "MF 455", "MF 4707", "MF 5455", "MF 5710", "MF 6110", "MF 7415", "MF 8737", "MF 1750"],
  "John Deere": ["5045D", "5050D", "5055E", "5075E", "5105", "5310", "5403", "5415", "6110", "6120", "6130", "6140", "6155", "6195", "6215", "7200", "7230", "7280", "8260", "8345", "9420", "Gator", "S660", "W550", "9500", "6B", "5E"],
  "New Holland": ["TT55", "TT75", "TD5.110", "TD5.90", "T4.75", "T5.100", "T6.140", "T7.210", "T8.380", "3630", "TL90", "TL100", "TN75", "Workmaster", "TS6", "CR 6.80", "CX 8.80", "Boomer"],
  "Case IH": ["Farmall 75C", "Farmall 100A", "Farmall 110A", "JX 75", "JX 90", "Maxxum 125", "Maxxum 140", "Puma 170", "Puma 210", "Magnum 260", "Magnum 340", "Axial-Flow", "Optum", "Steiger 500"],
  Kubota: ["B2420", "L3200", "L3408", "L4508", "L5018", "M7040", "M9540", "M104", "M135", "MU5501", "MU4501", "L2501", "ME", "SL", "DC-70"],
  Landini: ["Rex 90", "Rex 100", "Powerfarm 85", "Landpower 135", "Powermondial 120", "Mythos"],
  "Same": ["Explorer", "Iron", "Dorado", "Frutteto", "Solaris", "Argon", "Silver", "Virtus", "Titan"],
  "Deutz-Fahr": ["Agrotron", "Agrolux", "5G", "5090", "6140", "6190", "Agrofarm", "Agrofarm 100", "9340", "Agrostar", "Agrokid", "Series 5", "Series 6"],
  Fendt: ["211 Vario", "312 Vario", "516 Vario", "724 Vario", "828 Vario", "1050 Vario", "Farmer 309", "Favorit", "Xylon"],
  Claas: ["Axion", "Arion", "Atos", "Axos", "Ares", "Lexion", "Dominator", "Jaguar", "Xerion", "Nexos", "Celtis", "Tucano", "Avero"],
  "Valtra": ["A74", "A94", "A104", "A124", "A134", "N104", "N134", "N174", "T154", "T234", "S294", "G125", "BH154", "BM100", "BM110"],
  Zetor: ["Proxima", "Forterra", "Crystal", "Major", "Utilix", "5011", "7745", "Maxterra"],
  Belarus: ["MTZ 80", "MTZ 82", "MTZ 892", "MTZ 1025", "MTZ 1221", "820", "920", "1221.2", "570", "422"],
  Ursus: ["C-360", "C-330", "C-385", "1224", "Ursus 4512", "914"],
  "Ford Tractor": ["3600", "4000", "5000", "6600", "7600", "TW-20", "TW-30", "7710", "6610", "5610", "3910", "4610", "7000", "3000", "4100"],
  "Fiat Tractor": ["680", "780", "880", "980", "Fiat 480", "Fiat 640", "Fiat 90-90", "Fiat 100-90", "Fiat 70-90", "Fiat 60-90", "Fiat 82-93"],
  Sonalika: ["DI 35", "DI 42", "DI 50", "DI 60", "Rx 42", "Rx 50", "Tiger 55", "Tiger 60", "Tiger 26", "Worldtrac", "Sikander", "Sonalika Tiger"],
  Farmtrac: ["45", "50", "60", "Champion", "6055", "6065", "Atom", "Smart", "Farmtrac 60", "Farmtrac 45"],
  Swaraj: ["724", "735", "744", "855", "963", "843", "Swaraj 744 FE", "Swaraj 855 FE", "Swaraj 735 FE", "Swaraj Code"],
  "Mahindra Tractors": ["475 DI", "575 DI", "585 DI", "605 DI", "Yuvo", "Arjun", "Jivo", "Novo", "Mahindra 265 DI", "Mahindra 275 DI", "Mahindra 355", "Mahindra Bolero Pik-Up"],
  "Tafe": ["TAFE 9000", "TAFE 7250", "TAFE 5900", "TAFE 45 DI", "TAFE 35 DI", "MF 1035", "MF 241", "MF 7250", "MF 9500", "MF 5245"],
  "Eicher Tractors": ["380", "485", "557", "551", "333", "241", "5660", "Eicher Prima G3"],
  "Shifeng": ["SF 304", "SF 404", "SF 504", "Shifeng 25", "Shifeng 40"],
  "Foton Lovol": ["TB-Series", "TE-Series", "TL-Series", "TD-Series", "TK-Series", "TS", "M-Series", "Lovol M404", "Lovol M504", "Lovol M704", "Foton Tractor"],
  "YTO": ["X904", "X1004", "X1204", "ELX 1004", "LX 1204", "ME 800", "YTO X-454", "YTO X-554"],
  "Dongfeng Tractors": ["DF 300", "DF 404", "DF 504", "DF 604", "DF 800", "DF 900", "Dongfeng DF 1004"],
  "Jinma": ["JM 254", "JM 304", "JM 454", "JM 604", "Jinma 454"],

  // ---------------- Other ----------------
};

// Remove the empty placeholder entries used as scaffolding above so they
// never appear in the dropdown.
for (const key of Object.keys(VEHICLE_MODELS)) {
  if (VEHICLE_MODELS[key].length === 0) delete VEHICLE_MODELS[key];
}

export const ALL_MAKES: string[] = Object.keys(VEHICLE_MODELS).sort((a, b) => a.localeCompare(b));

export function makesGrouped(): { popular: string[]; others: string[] } {
  const popular = POPULAR_MAKES.filter((m) => VEHICLE_MODELS[m]);
  const popularSet = new Set(popular);
  return { popular, others: ALL_MAKES.filter((m) => !popularSet.has(m)) };
}

export function modelsFor(make: string): string[] {
  return VEHICLE_MODELS[make] ?? [];
}
