import re
import unicodedata
from src.models import Deal

# A ORDEM IMPORTA: mais específico antes do genérico da mesma família.
_PATTERNS: list[tuple[str, list[str]]] = [

    # ── Eletrônicos ────────────────────────────────────────────────────────────
    # Antes de smartphone: o acessório cita o aparelho ("suporte para celular",
    # "cabo para iphone") e seria classificado como o próprio celular.
    ("eletronico_acessorio", [
        r"(suporte|capa|película|pelicula|cabo|carregador|adaptador)\s*.{0,25}(celular|iphone|telefone|smartphone|tablet)",
        r"suporte\s*(magnético|magnetico|veicular|de\s*mesa|articulado)",
        r"(base|suporte)\s*.{0,20}(para\s*)?not(e)?book",
        r"pop\s*socket|anel\s*(de\s*)?suporte",
    ]),
    ("smartphone", [
        r"smartphone|iphone\s*\d|galaxy\s*[asmzf]\d|redmi\s*note|poco\s*[a-z]",
        r"\bcelular\b|motorola\s*(edge|moto\s*g)|xiaomi\s*\d",
    ]),
    ("hardware_pc", [
        r"mem[óo]ria\s*(para\s*)?notebook",
    ]),
    ("notebook", [
        r"notebook|laptop|macbook|ultrabook|chromebook",
    ]),
    ("tv_monitor", [
        r"smart\s*tv|televisão|televisor|\btv\s*\d{2}|oled|qled|neo\s*qled",
        r"monitor\s*(gamer|4k|144hz|ultrawide|curvo|led|ips|full\s*hd)|\bmonitor\s+\d{2}",
        r"\bprojetor\b",
    ]),
    # Acessório do fone, não o fone: precisa vir antes.
    ("eletronico_acessorio", [
        r"(adaptador|suporte|gancho)\s*.{0,15}(fone|headset|headphone)",
        r"organizador\s*(de\s*)?cabo|gerenciamento\s*de\s*cabo|protetor\s*de\s*cabo",
    ]),
    ("fone_headset", [
        r"headset|headphone|fone\s*de\s*ouvido|earbuds|airpods|earphone",
        r"caixa\s*de\s*som|caixa\s*bluetooth|speaker|soundbar|subwoofer|alto.?falante",
        r"fone\s*(bluetooth|sem\s*fio|gamer|anc|cancelamento)",
    ]),
    ("console", [
        r"console|playstation|xbox|nintendo\s*switch|ps[45]\b",
        r"controle\s*(sem\s*fio|dualsense|dualsense|xbox|ps[45])",
        r"jogo\s*(de\s*)?(ps[45]|xbox|switch|nintendo)",
        r"\bvr\b|oculus|meta\s*quest",
    ]),
    # Antes de eletronico_acessorio: o acessório de relógio cita "watch"/"smartwatch",
    # que lá casaria com o aparelho em si.
    ("acessorio_smartwatch", [
        r"(pulseira|correia|bracelete)\s*.{0,20}(watch|rel[oó]gio|smartwatch|\bband\b)",
        r"(apple|galaxy|amazfit|huawei|xiaomi|mi)\s*watch",
        r"caixa\s*(de\s*)?rel[oó]gio|porta.?rel[oó]gio",
        r"(protetor|película|capa)\s*.{0,20}(watch|smartwatch)",
    ]),
    # Depois de smartphone/notebook: celular e notebook citam RAM, SSD e Ryzen nas
    # especificações e seriam capturados por engano. Antes de eletronico_acessorio,
    # senão "Placa-Mãe ... WiFi" cai como acessório.
    ("hardware_pc", [
        r"\bprocessador\b(?!\s*de\s*aliment)|placa.?m[ãa]e|placa\s*de\s*v[íi]deo",
        r"mem[óo]ria\s*ram|\bssd\b|\bhdd\b|\bnvme\b|hd\s*externo",
        r"\bgabinete\b|water\s*cooler|air\s*cooler|cooler\s*(para\s*)?(cpu|processador)",
        # A marca fica entre "fonte" e a potência: "Fonte Cooler Master ... 850W".
        r"\bfonte\b.{0,40}(80\s*plus|\batx\b|modular|\d{3,4}\s*w)|pasta\s*térmica",
        r"\bventoinhas?\b|\bfan\s*\d+\s*mm|\bcooler\s*box",
        r"\brtx\s*\d|\bgtx\s*\d|\bradeon\b|\bgeforce\b|\bryzen\b|core\s*i[3579]\b",
    ]),
    ("eletronico_acessorio", [
        r"\bteclado\b|\bmouse\b|mousepad|\bwebcam\b",
        r"carregador|power\s*bank|cabo\s*(usb|hdmi|displayport|de\s*dados|tipo\s*c|lightning)",
        r"filtro\s*de\s*linha|estabilizador\b|\bnobreak\b|r[ée]gua\s*de\s*tomada",
        r"mesa\s*digitalizadora|rastreador\s*(gps|bluetooth)|air\s*?tags?\b",
        r"adaptador|hub\s*usb|switch\s*hdmi",
        r"smartwatch|relógio\s*inteligente|band\s*\d|mi\s*band",
        r"impressora|scanner|cartucho|toner",
        # 'wi-fi' solto é característica, não produto: capturava câmera de
        # segurança, impressora e TV. Os termos ao lado já cobrem o roteador.
        r"roteador|\bmodem\b|repetidor\s*(de\s*)?sinal|(wi.?fi|sistema|rede)\s*mesh",
    ]),
    # Componentes de PC saíram para hardware_pc, que roda antes. O 'processador'
    # solto aqui capturava "processador de alimentos" antes do eletrodoméstico.
    ("eletronico_geral", [
        r"tablet|ipad|\bkindle\b",
        r"\bpc\b\s*gamer|computador\s*(completo|gamer)?|desktop",
        r"pen\s*drive|pendrive|cart[ãa]o\s*(de\s*)?mem[óo]ria",
        r"echo\s*(show|dot|pop)|smart\s*(speaker|display)",
        r"fire\s*tv|chromecast|tv\s*box|streaming\s*stick|apple\s*tv",
        r"\bcâmera\b|\bcamera\b|gopro|\bdrone\b",
    ]),

    # ── Moda ──────────────────────────────────────────────────────────────────
    # "estojo" fica de fora de propósito: casaria "AirPods com Estojo de Recarga".
    # O lookbehind descarta descrição de forma ("almofada em formato de mochila").
    ("bolsa_mochila", [
        r"(?<!formato de )(\bmochila\b|bolsa\s*(feminina|masculina|de\s*ombro|transversal|térmica|tiracolo)?)",
        r"mala\s*(de\s*)?(viagem|bordo|rodinha)|\bpochete\b|\bnecessaire\b",
        r"carteira\s*(masculina|feminina|de\s*couro|porta.?cart)",
        r"bolsa\s*(de\s*)?(not(e)?book|laptop)|case\s*(para\s*)?not(e)?book",
    ]),
    ("kit_intimo", [
        r"kit\s*\d+\s*(cueca|meia|calcinha|par)",
        r"\d+\s*(cuecas?|meias?|calcinhas?)\b",
        r"\bcueca\b|\bcalcinha\b|\bmeia\b|lingerie|sutiã",
    ]),
    ("calcado_esporte", [
        r"tênis\s*(nike|adidas|asics|new\s*balance|puma|mizuno|under\s*armour)",
        r"tênis\s*(corrida|treino|running|trail|esport)",
        r"chuteira|tênis\s*futsal",
    ]),
    ("calcado", [
        r"\btênis\b|sandália|\bsapato\b|\bbota\b|chinelo|sapatilha|mocassim|scarpin|loafer",
    ]),
    ("roupa_esporte", [
        r"legging|calça\s*(de\s*)?(treino|yoga|academia|compressão)",
        r"regata\s*(treino|academia|fitness)|camiseta\s*dry.?fit",
        r"bermuda\s*(treino|academia|ciclismo)|shorts?\s*(treino|academia)",
        r"jaqueta\s*(corta.?vento|esport|running)|conjunto\s*(treino|academia)",
    ]),
    ("roupa_social", [
        r"camisa\s*social|camisa\s*(slim|fit|listrada|xadrez)",
        r"calça\s*(social|alfaiataria|de\s*terno)|blazer|\bterno\b|gravata",
        r"vestido\s*(festa|social|midi|longo)|saia\s*(midi|longa|social)",
    ]),
    ("roupa", [
        r"camiseta|camis[ae]\b|\bpolo\b",
        r"calça\s*(jeans|moletom|cargo|jogger)|\bjeans\b|\bjogger\b",
        r"\bvestido\b|\bblusa\b|\bsaia\b|\bbody\b|macacão",
        r"jaqueta|casaco|moletom|hoodie|sobretudo|parka",
        r"pijama|conjunto\s*(de\s*)?(dormir|moletom)",
    ]),

    # ── Casa ──────────────────────────────────────────────────────────────────
    ("bebe", [
        r"\bfralda\b|fralda\s*(descartável|pano|bebe|baby)",
        r"lenço\s*umedecido|toalha\s*umedecida",
        r"pomada\s*(assadur|frald|bebê|baby)|bepantol",
        r"shampoo\s*\w*\s*(baby|infantil)|condicionador\s*\w*\s*(baby|infantil)",
        r"johnson\s*baby|\bhuggies\b|\bpampers\b|pequeno\s*príncipe",
        r"banheira\s*(infantil|bebê|baby)|banheirinha",
        r"\bmamadeira\b|\bchupeta\b|mordedor\s*(bebê|baby)|\bbabador\b",
        r"\bberço\b|carrinho\s*de\s*bebê|cadeirinha\s*(bebê|carro|auto)",
        r"monitor\s*(de\s*bebê|baby)|babá\s*eletrônica",
        r"\bandador\b|bebê\s*conforto|\bmoisés\b",
    ]),
    ("utensilio_cozinha", [
        r"panela|frigideira|\bwok\b|caldeirão|caçarola",
        r"chaleira|\bcafeteira\b|french\s*press|aeropress",
        r"potes?\s*(herm[ée]tico|de\s*vidro|pl[áa]stico|t[ée]rmico)|tupperware|\bmarmita\b",
        r"\bcopo\b|\bcaneca\b|\bprato\b|tigela|jogo\s*(de\s*)?(cozinha|prato|copo|jantar)",
        r"\bfaca\b|tábua\s*de\s*corte|espátula",
        r"fatiador|amaciador\s*de\s*carne|\bmolde\b|forma\s*de\s*(bolo|gelo|biscoito)",
        r"m[áa]quina\s*de\s*selagem|seladora\b|selagem\s*(de\s*)?saco",
        r"triturador|picador\s*(de\s*)?alho|amassador|espremedor",
        r"abridor\s*(de\s*)?(garrafa|lata)|descascador|ralador|\bmoedor\b|spice\s*grinder",
    ]),
    ("eletrodomestico_grande", [
        r"geladeira|refrigerador|freezer",
        r"fogão|\bcooktop\b|forno\s*(elétrico|de\s*embutir)",
        r"máquina\s*de?\s*(lavar|secar)|lava.?(louça|roupas?)",
        r"ar\s*condicionado|\bsplit\b",
    ]),
    ("eletrodomestico_pequeno", [
        r"fritadeira\s*air|air\s*fryer|airfryer",
        r"liquidificador|batedeira|processador\s*de\s*alimento|\bmixer\b",
        r"micro.?ondas",
        r"ventilador|climatizador|purificador\s*de\s*ar",
        r"aspirador|robô\s*(de\s*)?(limpeza|aspirador)",
        r"sanduicheira|wafleira|\bgrill\b|churraqueira\s*elétrica",
        r"panificadora|máquina\s*de\s*p[ãa]o|cafeteira\s*el[ée]trica",
    ]),
    ("cama_banho", [
        r"colchão|travesseiro|edredom|lençol|cobre.?leito|roupa\s*de\s*cama",
        r"\btoalha\b|jogo\s*de\s*toalha|roupão",
        r"cama\s*(box|casal|solteiro|queen|king)",
    ]),
    ("moveis", [
        r"sofá|sofa|poltrona|\bpuff\b",
        r"armário|guarda.?roupa|estante|prateleira|\brack\b|\bnicho\b",
        r"mesa\s*(de\s*)?(jantar|escritório|estudo)|escrivaninha|bancada",
        r"cadeira\s*(de\s*)?(escritório|escritorio|office|gamer|jantar)",
        r"mesa\s*(office|gamer|de\s*trabalho)|apoio\s*(ergonômico|para\s*os?\s*p[ée]s)",
        r"\bcama\b(?!\s*(de\s*)?(box|casal|queen|king|solteiro))",
    ]),
    ("casa_geral", [
        r"luminária|abajur|pendente|lustre|fita\s*led|tira\s*(de\s*)?led",
        r"l[âa]mpada|luz\s*(noturna|led|de\s*tira|solar)|ilumina[çc][ãa]o|sensor\s*de\s*movimento",
        r"tapete|cortina|persiana|almofada|decoração",
        r"caixa\s*organizadora|organizador|cesto|cabide",
        r"\bquadro\b|\bespelho\b|\bvaso\b|\bplanta\b",
    ]),

    # ── Alimento ──────────────────────────────────────────────────────────────
    ("churrasco", [
        r"kit\s*churrasco|churrasqueira|\bgrelha\b|\bespeto\b|faca\s*(churrasco|de\s*churrasco)",
        r"tábua\s*de\s*churrasco|pegador\s*(churrasco|de\s*churrasco)|avental\s*churrasco",
        r"\bcarvão\b|\bacendedor\b|gás\s*(butano|propano)|\bweber\b",
    ]),
    ("cafe", [
        r"\bcafé\b|nescafé|cappuccino|cápsula\s*(nespresso|dolce|café)",
        r"café\s*(em\s*pó|torrado|solúvel|especial|gourmet)",
    ]),
    ("condimento", [
        r"ketchup|maionese|mostarda|molho\s*(shoyu|inglês|tabasco|pimenta|barbecue)",
        r"azeite|vinagre|vinagrete|tempero|condimento|colorau|páprica",
        r"manteiga\s*de\s*amendoim|pasta\s*de\s*amendoim|geleia|\bmel\b",
    ]),
    ("chocolate_doce", [
        r"\bchocolate\b|bombom|barra\s*de\s*chocolate|trufa|kit\s*kat|ferrero",
        r"biscoito|bolacha|cookie|wafer|cracker|recheado",
        r"sorvete|brigadeiro|\bdoce\b|\baçaí\b",
    ]),
    ("bebida_alcoolica", [
        r"cerveja|long\s*neck|pack\s*(cerveja|heineken|brahma|stella)",
        r"\bvinho\b|espumante|prosecco|champagne",
        r"whisky|whiskey|bourbon|scotch|single\s*malt",
        r"\bgin\b|vodka|cachaça|\brum\b|\blicor\b|tequila",
    ]),
    ("suplemento", [
        r"whey\s*(protein|isolado|concentrado)|proteína\s*(em\s*pó|isolada)",
        r"\bcreatina\b|pré.?treino|hipercalórico|\balbumina\b|\bbcaa\b|glutamina",
        r"\bcolágeno\b|ômega\s*3|vitamina\s*[cdek]\b|multivitamínico",
    ]),
    ("alimento", [
        r"\barroz\b|\bfeijão\b|lentilha|grão.de.bico|quinoa",
        r"macarrão|espaguete|lasanha|\bmassa\b|nhoque",
        r"\bleite\b|iogurte|queijo|requeijão|\bmanteiga\b",
        r"\bsuco\b|néctar|achocolatado|\bvitamina\b",
        r"energético|isotônico|água\s*de\s*coco|água\s*(mineral|com\s*gás)",
        r"\batum\b|sardinha|frango\s*(enlatado|grelhado)|carne\s*seca",
        r"pipoca|amendoim|castanha|granola|barra\s*de\s*cereal|snack",
        r"farinha|fermento|açúcar|\bsal\b|óleo\s*(de\s*)?(soja|girassol|coco)",
        r"refrigerante|coca.?cola|pepsi|guaraná",
    ]),

    # ── Bebê ──────────────────────────────────────────────────────────────────

    # ── Beleza e Higiene ──────────────────────────────────────────────────────
    ("perfume", [
        r"\bperfume\b|eau\s*de\s*(parfum|toilette|cologne)|deo\s*(colônia|parfum)",
        r"body\s*splash|body\s*mist|\bcolônia\b(?!.*dental)",
    ]),
    ("cabelo", [
        # 'capilar' qualifica o produto como de cabelo mesmo quando o formato
        # (sérum, creme, ampola) também existe em skincare.
        r"\bcapilar\b|\bshampoo\b|\bcondicionador\b|máscara\s*(capilar|de\s*hidratação)",
        r"creme\s*de?\s*cabelo|leave.?in|óleo\s*capilar|finalizador\s*capilar",
        r"tratamento\s*capilar|ampola\s*(capilar|de\s*tratamento)",
        r"progressiva|relaxamento|coloração|\btintura\b|descoloração",
    ]),
    ("skincare", [
        r"hidratante\s*(facial|pele|rosto)|creme\s*(facial|anti.?idade|cc\s*cream|bb\s*cream)",
        r"\bsérum\b|vitamina\s*c\s*facial|ácido\s*(hialurônico|glicólico|retinóico)",
        r"protetor\s*solar|filtro\s*solar|fps\s*\d+|bloqueador\s*solar",
        r"esfoliante\s*facial|tônico\s*facial|máscara\s*facial|demaquilante",
        r"loção\s*corporal|creme\s*corporal|\bnivea\b|\bvaselina\b|\bhidratante\b",
    ]),
    ("barba", [
        r"barbeador|barbeadora|gillette|aparelho\s*de\s*barbear",
        r"lâmina\s*(de\s*)?barb|espuma\s*de\s*barba|gel\s*de\s*barba|pós.?barba",
        r"aparador\s*(de\s*)?(barba|pelos)|barbeador\s*elétrico",
        r"óleo\s*de\s*barba|cera\s*de\s*barba|balm\s*de\s*barba",
    ]),
    ("higiene", [
        r"\bsabonete\b|sabão\s*(em\s*)?(barra|líquido)",
        r"\bdesodorante\b|antitranspirante",
        r"pasta\s*de?\s*dente|escova\s*de?\s*dente|fio\s*dental|enxaguante\s*bucal",
        r"\babsorvente\b|\bfralda\b|lenço\s*umedecido|pomada\s*(assadur|frald)",
        r"barbeador\s*(descartável)?(?!.*elétrico)",
    ]),

    # ── Esporte e Saúde ───────────────────────────────────────────────────────
    ("musculacao", [
        r"\bhaltere\b|\bkettlebell\b|\banilha\b|barra\s*(olímpica|de\s*musculação|fixa)|\bsupino\b",
        r"rack\s*(de\s*musculação|de\s*agachamento)|estação\s*de\s*musculação",
        r"cinto\s*(musculação|academia)|luva\s*(musculação|academia|treino)",
    ]),
    ("cardio_outdoor", [
        r"bicicleta\s*(ergométrica|spinning|speed|mtb)|\bbike\b",
        r"esteira\s*(ergométrica|elétrica)?",
        r"\belíptico\b|\btransport\b|remo\s*ergométrico",
        r"\bpatins\b|\bskate\b|trotinete|patinete|longboard",
    ]),
    ("esporte", [
        r"\bbola\b|chuteira|caneleira|goleiro",
        r"\braquete\b|\bpeteca\b|frescobol",
        r"corda\s*de?\s*pular|elástico\s*de?\s*treino|faixa\s*elástica|miniband",
        r"luva\s*(boxe|muay thai)|protetor\s*(bucal|canela)",
        r"mochila\s*esport|bolsa\s*academia|\bsqueeze\b|garrafa\s*esport|coqueteleira",
        r"mat\s*(yoga|pilates)|colchonete|\bstep\b",
    ]),

    # ── Ferramentas ───────────────────────────────────────────────────────────
    ("ferramenta_eletrica", [
        r"\bfuradeira\b|\bparafusadeira\b|\bmartelete\b|\bmandril\b",
        r"serra\s*(circular|tico.tico|mármore)|\besmerilhadeira\b|\blixadeira\b|\bplaina\b",
        r"parafusadeira\s*(a\s*bateria|sem\s*fio)",
    ]),
    ("ferramenta", [
        r"\blanterna\b|tocha\s*tática|luz\s*de\s*trabalho",
        r"escova\s*de\s*(arame|aço)|pulverizador|pistola\s*de\s*pintura",
        r"chave\s*(de\s*impacto|de\s*fenda|philips|allen|inglesa)|soquete\b",
        r"pin[çc]a\s*(de\s*precis[ãa]o)?|tweezer|extrator\b|picareta\b",
        r"\bmartelo\b|chave\s*de?\s*fenda|chave\s*combinada|\balicate\b|\btorquesa\b|chave\s*inglesa",
        r"kit\s*(de\s*)?ferramenta|conjunto\s*(de\s*)?ferramenta|maleta\s*(de\s*)?ferramenta",
        r"extensão\s*elétrica|tomada\s*(múltipla|tripla)|régua\s*(elétrica|filtro)",
        r"\bcano\b|\btorneira\b|\bválvula\b|\bregistro\b|\bsifão\b",
        r"\btrena\b|\bnível\b|\besquadro\b|\bparafuso\b|\bbucha\b",
    ]),

    # ── Livros ────────────────────────────────────────────────────────────────
    ("livro_negocio", [
        r"(livro|box).*?(empreendedorismo|negócio|marketing|liderança|investimento|finanças\s*pessoais|hábitos|produtividade)",
        r"pai\s*rico|mindset|start.?up|\blean\b|\bagile\b|\bscrum\b",
    ]),
    ("livro", [
        r"\blivro\b|e.?book",
        r"\bkindle\b",
        r"mangá|\bhq\b|quadrinho|graphic\s*novel",
        r"box\s*(de\s*)?livro|coleção\s*(de\s*)?livro|\bsaga\b",
        r"\bromance\b|\bficção\b|\bfantasia\b|\bthriller\b|\bautoajuda\b",
    ]),

    # ── Brinquedos ────────────────────────────────────────────────────────────
    ("brinquedo_educativo", [
        r"\blego\b|blocos\s*de?\s*montar|nanoblock|magnetico\s*block",
        r"quebra.?cabeça|\bpuzzle\b",
        r"jogo\s*de\s*tabuleiro|card\s*game|\brpg\b|\buno\b|monopoly|\bdetetive\b",
    ]),
    ("brinquedo", [
        r"figurinhas?\b|\bcromos?\b|álbum\s*(da\s*)?copa|blister\s*.{0,20}figurinha",
        r"\bbrinquedo\b|\bboneca\b|\bboneco\b",
        r"carrinho\s*(de\s*)?brinquedo|pista\s*de\s*corrida|hot\s*wheels",
        r"\bpelúcia\b|\bursinho\b",
        r"\bmassinha\b|argila\s*colorida|\bslime\b",
        r"controle\s*remoto\s*(carro|avião|helicóptero)",
    ]),

    # ── Pets ──────────────────────────────────────────────────────────────────
    ("pet", [
        r"\bração\b|\bpetisco\b|snack\s*(pet|cachorro|gato)",
        r"\bcoleira\b|\bguia\b|\bfocinheira\b|\bpeitoral\b",
        r"arranhador|cama\s*(pet|cachorro|gato)|\bcasinha\b",
        r"brinquedo\s*(pet|cachorro|gato)|\bmordedor\b",
        r"areia\s*(sanitária|para\s*gato)|caixa\s*de\s*areia",
        r"shampoo\s*(pet|cachorro|gato)",
    ]),
]


# ── Normalização ──────────────────────────────────────────────────────────────
# Títulos de loja são inconsistentes em acento e número ("Fone" vs "Fones",
# "vídeo" vs "video"). Normalizar os DOIS lados — texto e padrão — resolve a
# classe inteira de falhas, em vez de duplicar cada regex.


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", _strip_accents(text.lower())).strip()


# Singulares que já terminam em -s: singularizar produziria lixo ("tenis" → "teni").
_INVARIANT = frozenset({
    "tenis", "lapis", "onibus", "virus", "atlas", "bonus", "status", "gas",
    "mes", "pais", "arroz", "couros", "jeans", "fitness", "wireless", "plus",
    "bass", "class", "cross", "press", "gloss", "dress", "pcs", "pes",
})


def _singularize_word(word: str) -> str:
    if len(word) <= 3 or word in _INVARIANT:
        return word
    for suffix, replacement in (
        ("oes", "ao"), ("aes", "ao"), ("ais", "al"),
        ("eis", "el"), ("ois", "ol"), ("ns", "m"),
    ):
        if word.endswith(suffix):
            return word[: -len(suffix)] + replacement
    if word.endswith(("res", "zes", "ses")):
        return word[:-2]
    if word.endswith("s"):
        return word[:-1]
    return word


def _singularize(text: str) -> str:
    return " ".join(_singularize_word(w) for w in text.split(" "))


# Padrões compilados uma vez, já normalizados, preservando a ordem de precedência.
_COMPILED: list[tuple[str, list[re.Pattern[str]]]] = [
    (category, [re.compile(normalize(p)) for p in patterns])
    for category, patterns in _PATTERNS
]


def classify(deal: Deal) -> str:
    # Usa o título original quando existe: a limpeza para exibição corta as
    # cláusulas finais, que é justamente onde costuma estar o termo do produto.
    title = normalize(deal.text_for_matching())
    # Casa contra as duas formas: a singularização é heurística, então serve para
    # ganhar recall sem poder remover um acerto que a forma original já daria.
    singular = _singularize(title)

    for category, patterns in _COMPILED:
        for pattern in patterns:
            if pattern.search(title) or pattern.search(singular):
                return category
    return "geral"


# ── Agrupamento para o site ───────────────────────────────────────────────────
# A categoria fina serve para classificar; o grupo serve para o usuário filtrar.
# São coisas diferentes: 46 categorias finas viram um filtro inútil (metade com
# 1 item), mas apagá-las perderia sinal — a composição do catálogo muda conforme
# quais scrapers estão funcionando. Aqui o fino continua existindo e o site
# mostra o grosso.
#
# Recorte pensado para compra online no Brasil:
#  - "PC e Hardware" separado de "Eletrônicos": é público próprio (KaBuM), e
#    quem procura placa de vídeo não quer pulseira de relógio no mesmo filtro.
#  - "Esporte e Suplementos" junto: creatina/whey é um dos maiores drivers de
#    oferta no país e atende o mesmo público de artigo esportivo.
#  - "Celular e Smartwatch" junto: acessório de um puxa a atenção do outro.

_GROUP_MEMBERS: dict[str, list[str]] = {
    "informatica": ["hardware_pc", "notebook"],
    "celular": ["smartphone", "acessorio_smartwatch"],
    "audio": ["fone_headset"],
    "tv_video": ["tv_monitor"],
    "games": ["console"],
    "eletronicos": ["eletronico_acessorio", "eletronico_geral"],
    "casa_cozinha": [
        "utensilio_cozinha", "casa_geral", "moveis", "cama_banho",
        "eletrodomestico_pequeno", "eletrodomestico_grande",
    ],
    "moda": [
        "roupa", "roupa_social", "roupa_esporte", "calcado", "calcado_esporte",
        "bolsa_mochila", "kit_intimo",
    ],
    "beleza": ["perfume", "skincare", "cabelo", "barba", "higiene"],
    "esporte_suplementos": ["suplemento", "musculacao", "cardio_outdoor", "esporte"],
    "mercado": [
        "alimento", "chocolate_doce", "cafe", "condimento", "churrasco",
        "bebida_alcoolica",
    ],
    "ferramentas": ["ferramenta", "ferramenta_eletrica"],
    "infantil": ["bebe", "brinquedo", "brinquedo_educativo"],
    "pet": ["pet"],
    "livros": ["livro", "livro_negocio"],
}

_CATEGORY_TO_GROUP: dict[str, str] = {
    categoria: grupo
    for grupo, categorias in _GROUP_MEMBERS.items()
    for categoria in categorias
}

GROUP_FALLBACK = "outros"


def group_of(category: str) -> str:
    """Grupo exibido no site para uma categoria fina."""
    return _CATEGORY_TO_GROUP.get(category, GROUP_FALLBACK)
