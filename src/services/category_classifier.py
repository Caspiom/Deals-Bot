import re
from src.models import Deal

# A ORDEM IMPORTA: mais específico antes do genérico da mesma família.
_PATTERNS: list[tuple[str, list[str]]] = [

    # ── Eletrônicos ────────────────────────────────────────────────────────────
    ("console", [
        r"console|playstation|xbox|nintendo\s*switch|ps[45]\b",
        r"controle\s*(sem\s*fio|dualsense|dualsense|xbox|ps[45])",
        r"jogo\s*(de\s*)?(ps[45]|xbox|switch|nintendo)",
        r"\bvr\b|oculus|meta\s*quest",
    ]),
    ("smartphone", [
        r"smartphone|iphone\s*\d|galaxy\s*[asmzf]\d|redmi\s*note|poco\s*[a-z]",
        r"celular\b|motorola\s*(edge|moto\s*g)|xiaomi\s*\d",
    ]),
    ("notebook", [
        r"notebook|laptop|macbook|ultrabook|chromebook",
    ]),
    ("tv_monitor", [
        r"\btv\b|televisão|televisor|smart\s*tv|oled|qled|neo\s*qled",
        r"monitor\s*(gamer|4k|144hz|ultrawide|curvo)?",
        r"projetor\b",
    ]),
    ("fone_headset", [
        r"headset|headphone|fone\s*de\s*ouvido|earbuds|airpods|earphone",
        r"caixa\s*de\s*som|caixa\s*bluetooth|speaker|soundbar|subwoofer",
        r"fone\s*(bluetooth|sem\s*fio|gamer|anc|cancelamento)",
    ]),
    ("eletronico_acessorio", [
        r"teclado\b|mouse\b|mousepad|webcam\b",
        r"carregador|power\s*bank|cabo\s*(usb|hdmi|displayport)",
        r"adaptador|hub\s*usb|switch\s*hdmi",
        r"smartwatch|relógio\s*inteligente|band\s*\d|mi\s*band",
        r"impressora|scanner|cartucho|toner",
        r"roteador|wi.?fi|modem|repetidor\s*sinal|mesh\b",
    ]),
    ("eletronico_geral", [
        r"tablet|ipad|kindle\b",
        r"\bpc\b|computador|desktop|processador|placa.*v[íi]deo|gpu|rtx|gtx|rx\s*\d",
        r"\bssd\b|\bhdd?\b|memória\s*ram|\bram\b|pendrive|hd\s+externo",
        r"câmera\b|camera\b|gopro|drone\b",
    ]),

    # ── Moda ──────────────────────────────────────────────────────────────────
    ("kit_intimo", [
        r"kit\s*\d+\s*(cueca|meia|calcinha|par)",
        r"\d+\s*(cuecas?|meias?|calcinhas?)\b",
        r"cueca\b|calcinha\b|meia\b|lingerie|sutiã",
    ]),
    ("calcado_esporte", [
        r"tênis\s*(nike|adidas|asics|new\s*balance|puma|mizuno|under\s*armour)",
        r"tênis\s*(corrida|treino|running|trail|esport)",
        r"chuteira|tênis\s*futsal",
    ]),
    ("calcado", [
        r"tênis\b|sandália|sapato\b|bota\b|chinelo|sapatilha|mocassim|scarpin|loafer",
    ]),
    ("roupa_esporte", [
        r"legging|calça\s*(de\s*)?(treino|yoga|academia|compressão)",
        r"regata\s*(treino|academia|fitness)|camiseta\s*dry.?fit",
        r"bermuda\s*(treino|academia|ciclismo)|shorts?\s*(treino|academia)",
        r"jaqueta\s*(corta.?vento|esport|running)|conjunto\s*(treino|academia)",
    ]),
    ("roupa_social", [
        r"camisa\s*social|camisa\s*(slim|fit|listrada|xadrez)",
        r"calça\s*(social|alfaiataria|de\s*terno)|blazer|terno\b|gravata",
        r"vestido\s*(festa|social|midi|longo)|saia\s*(midi|longa|social)",
    ]),
    ("roupa", [
        r"camiseta|camis[ae]\b|polo\b",
        r"calça\s*(jeans|moletom|cargo|jogger)|jeans\b|jogger\b",
        r"vestido\b|blusa\b|saia\b|body\b|macacão",
        r"jaqueta|casaco|moletom|hoodie|sobretudo|parka",
        r"pijama|conjunto\s*(de\s*)?(dormir|moletom)",
    ]),

    # ── Casa ──────────────────────────────────────────────────────────────────
    ("eletrodomestico_grande", [
        r"geladeira|refrigerador|freezer",
        r"fogão|cooktop\b|forno\s*(elétrico|de\s*embutir)",
        r"máquina\s*de?\s*(lavar|secar)|lava.?(louça|roupas?)",
        r"ar\s*condicionado|split\b",
    ]),
    ("eletrodomestico_pequeno", [
        r"fritadeira\s*air|air\s*fryer|airfryer",
        r"liquidificador|batedeira|processador\s*de\s*alimento|mixer\b",
        r"micro.?ondas",
        r"ventilador|climatizador|purificador\s*de\s*ar",
        r"aspirador|robô\s*(de\s*)?(limpeza|aspirador)",
        r"sanduicheira|wafleira|grill\b|churraqueira\s*elétrica",
    ]),
    ("cama_banho", [
        r"colchão|travesseiro|edredom|lençol|cobre.?leito|roupa\s*de\s*cama",
        r"toalha\b|jogo\s*de\s*toalha|roupão",
        r"cama\s*(box|casal|solteiro|queen|king)",
    ]),
    ("moveis", [
        r"sofá|sofa|poltrona|puff\b",
        r"armário|guarda.?roupa|estante|prateleira|rack\b|nicho\b",
        r"mesa\s*(de\s*)?(jantar|escritório|estudo)|escrivaninha|bancada",
        r"cadeira\s*(escritório|gamer|de\s*jantar)|cadeira\s*de\s*escritório",
        r"cama\b(?!\s*(de\s*)?(box|casal|queen|king|solteiro))",
    ]),
    ("utensilio_cozinha", [
        r"panela|frigideira|wok\b|caldeirão|caçarola",
        r"chaleira|cafeteira\b|french\s*press|aeropress",
        r"pote|tupperware|marmita\b|pote\s*hermet",
        r"copo\b|caneca\b|prato\b|tigela|jogo\s*(de\s*)?(cozinha|prato|copo|jantar)",
        r"faca\b|tábua\s*de\s*corte|espátula",
    ]),
    ("casa_geral", [
        r"luminária|abajur|pendente|lustre|fita\s*led",
        r"tapete|cortina|persiana|almofada|decoração",
        r"caixa\s*organizadora|organizador|cesto|cabide",
        r"quadro\b|espelho\b|vaso\b|planta\b",
    ]),

    # ── Alimento ──────────────────────────────────────────────────────────────
    ("churrasco", [
        r"kit\s*churrasco|churrasqueira|grelha\b|espeto\b|faca\s*(churrasco|de\s*churrasco)",
        r"tábua\s*de\s*churrasco|pegador\s*(churrasco|de\s*churrasco)|avental\s*churrasco",
        r"carvão\b|acendedor\b|gás\s*(butano|propano)|weber\b",
    ]),
    ("cafe", [
        r"\bcafé\b|nescafé|cappuccino|cápsula\s*(nespresso|dolce|café)",
        r"café\s*(em\s*pó|torrado|solúvel|especial|gourmet)",
    ]),
    ("condimento", [
        r"ketchup|maionese|mostarda|molho\s*(shoyu|inglês|tabasco|pimenta|barbecue)",
        r"azeite|vinagre|vinagrete|tempero|condimento|colorau|páprica",
        r"manteiga\s*de\s*amendoim|pasta\s*de\s*amendoim|geleia|mel\b",
    ]),
    ("chocolate_doce", [
        r"chocolate\b|bombom|barra\s*de\s*chocolate|trufa|kit\s*kat|ferrero",
        r"biscoito|bolacha|cookie|wafer|cracker|recheado",
        r"sorvete|brigadeiro|doce\b|açaí\b",
    ]),
    ("bebida_alcoolica", [
        r"cerveja|long\s*neck|pack\s*(cerveja|heineken|brahma|stella)",
        r"vinho\b|espumante|prosecco|champagne",
        r"whisky|whiskey|bourbon|scotch|single\s*malt",
        r"\bgin\b|vodka|cachaça|rum\b|licor\b|tequila",
    ]),
    ("suplemento", [
        r"whey\s*(protein|isolado|concentrado)|proteína\s*(em\s*pó|isolada)",
        r"creatina\b|pré.?treino|hipercalórico|albumina\b|bcaa\b|glutamina",
        r"colágeno\b|ômega\s*3|vitamina\s*[cdek]\b|multivitamínico",
    ]),
    ("alimento", [
        r"arroz\b|feijão\b|lentilha|grão.de.bico|quinoa",
        r"macarrão|espaguete|lasanha|massa\b|nhoque",
        r"leite\b|iogurte|queijo|requeijão|manteiga\b",
        r"suco\b|néctar|achocolatado|vitamina\b",
        r"energético|isotônico|água\s*de\s*coco|água\s*(mineral|com\s*gás)",
        r"atum\b|sardinha|frango\s*(enlatado|grelhado)|carne\s*seca",
        r"pipoca|amendoim|castanha|granola|barra\s*de\s*cereal|snack",
        r"farinha|fermento|açúcar|sal\b|óleo\s*(de\s*)?(soja|girassol|coco)",
        r"refrigerante|coca.?cola|pepsi|guaraná",
    ]),

    # ── Bebê ──────────────────────────────────────────────────────────────────
    ("bebe", [
        r"fralda\b|fralda\s*(descartável|pano|bebe|baby)",
        r"lenço\s*umedecido|toalha\s*umedecida",
        r"pomada\s*(assadur|frald|bebê|baby)|bepantol",
        r"shampoo\s*\w*\s*(baby|infantil)|condicionador\s*\w*\s*(baby|infantil)",
        r"johnson\s*baby|huggies\b|pampers\b|pequeno\s*príncipe",
        r"banheira\s*(infantil|bebê|baby)|banheirinha",
        r"mamadeira\b|chupeta\b|mordedor\s*(bebê|baby)|babador\b",
        r"berço\b|carrinho\s*de\s*bebê|cadeirinha\s*(bebê|carro|auto)",
        r"monitor\s*(de\s*bebê|baby)|babá\s*eletrônica",
        r"andador\b|bebê\s*conforto|moisés\b",
    ]),

    # ── Beleza e Higiene ──────────────────────────────────────────────────────
    ("perfume", [
        r"perfume\b|eau\s*de\s*(parfum|toilette|cologne)|deo\s*(colônia|parfum)",
        r"body\s*splash|body\s*mist|colônia\b(?!.*dental)",
    ]),
    ("skincare", [
        r"hidratante\s*(facial|pele|rosto)|creme\s*(facial|anti.?idade|cc\s*cream|bb\s*cream)",
        r"sérum\b|vitamina\s*c\s*facial|ácido\s*(hialurônico|glicólico|retinóico)",
        r"protetor\s*solar|filtro\s*solar|fps\s*\d+|bloqueador\s*solar",
        r"esfoliante\s*facial|tônico\s*facial|máscara\s*facial|demaquilante",
        r"loção\s*corporal|creme\s*corporal|nivea\b|vaselina\b|hidratante\b",
    ]),
    ("cabelo", [
        r"shampoo\b|condicionador\b|máscara\s*(capilar|de\s*hidratação)",
        r"creme\s*de?\s*cabelo|leave.?in|óleo\s*capilar|finalizador\s*capilar",
        r"tratamento\s*capilar|ampola\s*(capilar|de\s*tratamento)",
        r"progressiva|relaxamento|coloração|tintura\b|descoloração",
    ]),
    ("barba", [
        r"barbeador|barbeadora|gillette|aparelho\s*de\s*barbear",
        r"lâmina\s*(de\s*)?barb|espuma\s*de\s*barba|gel\s*de\s*barba|pós.?barba",
        r"aparador\s*(de\s*)?(barba|pelos)|barbeador\s*elétrico",
        r"óleo\s*de\s*barba|cera\s*de\s*barba|balm\s*de\s*barba",
    ]),
    ("higiene", [
        r"sabonete\b|sabão\s*(em\s*)?(barra|líquido)",
        r"desodorante\b|antitranspirante",
        r"pasta\s*de?\s*dente|escova\s*de?\s*dente|fio\s*dental|enxaguante\s*bucal",
        r"absorvente\b|fralda\b|lenço\s*umedecido|pomada\s*(assadur|frald)",
        r"barbeador\s*(descartável)?(?!.*elétrico)",
    ]),

    # ── Esporte e Saúde ───────────────────────────────────────────────────────
    ("musculacao", [
        r"haltere\b|kettlebell\b|anilha\b|barra\s*(olímpica|de\s*musculação|fixa)|supino\b",
        r"rack\s*(de\s*musculação|de\s*agachamento)|estação\s*de\s*musculação",
        r"cinto\s*(musculação|academia)|luva\s*(musculação|academia|treino)",
    ]),
    ("cardio_outdoor", [
        r"bicicleta\s*(ergométrica|spinning|speed|mtb)|bike\b",
        r"esteira\s*(ergométrica|elétrica)?",
        r"elíptico\b|transport\b|remo\s*ergométrico",
        r"patins\b|skate\b|trotinete|patinete|longboard",
    ]),
    ("esporte", [
        r"\bbola\b|chuteira|caneleira|goleiro",
        r"raquete\b|peteca\b|frescobol",
        r"corda\s*de?\s*pular|elástico\s*de?\s*treino|faixa\s*elástica|miniband",
        r"luva\s*(boxe|muay thai)|protetor\s*(bucal|canela)",
        r"mochila\s*esport|bolsa\s*academia|squeeze\b|garrafa\s*esport|coqueteleira",
        r"mat\s*(yoga|pilates)|colchonete|step\b",
    ]),

    # ── Ferramentas ───────────────────────────────────────────────────────────
    ("ferramenta_eletrica", [
        r"furadeira\b|parafusadeira\b|martelete\b|mandril\b",
        r"serra\s*(circular|tico.tico|mármore)|esmerilhadeira\b|lixadeira\b|plaina\b",
        r"parafusadeira\s*(a\s*bateria|sem\s*fio)",
    ]),
    ("ferramenta", [
        r"martelo\b|chave\s*de?\s*fenda|chave\s*combinada|alicate\b|torquesa\b|chave\s*inglesa",
        r"kit\s*(de\s*)?ferramenta|conjunto\s*(de\s*)?ferramenta|maleta\s*(de\s*)?ferramenta",
        r"extensão\s*elétrica|tomada\s*(múltipla|tripla)|régua\s*(elétrica|filtro)",
        r"cano\b|torneira\b|válvula\b|registro\b|sifão\b",
        r"trena\b|nível\b|esquadro\b|parafuso\b|bucha\b",
    ]),

    # ── Livros ────────────────────────────────────────────────────────────────
    ("livro_negocio", [
        r"(livro|box).*?(empreendedorismo|negócio|marketing|liderança|investimento|finanças\s*pessoais|hábitos|produtividade)",
        r"pai\s*rico|mindset|start.?up|lean\b|agile\b|scrum\b",
    ]),
    ("livro", [
        r"\blivro\b|e.?book",
        r"\bkindle\b",
        r"mangá|hq\b|quadrinho|graphic\s*novel",
        r"box\s*(de\s*)?livro|coleção\s*(de\s*)?livro|saga\b",
        r"romance\b|ficção\b|fantasia\b|thriller\b|autoajuda\b",
    ]),

    # ── Brinquedos ────────────────────────────────────────────────────────────
    ("brinquedo_educativo", [
        r"\blego\b|blocos\s*de?\s*montar|nanoblock|magnetico\s*block",
        r"quebra.?cabeça|puzzle\b",
        r"jogo\s*de\s*tabuleiro|card\s*game|rpg\b|uno\b|monopoly|detetive\b",
    ]),
    ("brinquedo", [
        r"brinquedo\b|boneca\b|boneco\b",
        r"carrinho\s*(de\s*)?brinquedo|pista\s*de\s*corrida|hot\s*wheels",
        r"pelúcia\b|ursinho\b",
        r"massinha\b|argila\s*colorida|slime\b",
        r"controle\s*remoto\s*(carro|avião|helicóptero)",
    ]),

    # ── Pets ──────────────────────────────────────────────────────────────────
    ("pet", [
        r"ração\b|petisco\b|snack\s*(pet|cachorro|gato)",
        r"coleira\b|guia\b|focinheira\b|peitoral\b",
        r"arranhador|cama\s*(pet|cachorro|gato)|casinha\b",
        r"brinquedo\s*(pet|cachorro|gato)|mordedor\b",
        r"areia\s*(sanitária|para\s*gato)|caixa\s*de\s*areia",
        r"shampoo\s*(pet|cachorro|gato)",
    ]),
]


def classify(deal: Deal) -> str:
    title = deal.title.lower()
    for category, patterns in _PATTERNS:
        for pattern in patterns:
            if re.search(pattern, title):
                return category
    return "geral"
