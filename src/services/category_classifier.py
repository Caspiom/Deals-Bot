import re
from src.models import Deal

# (categoria, padrões regex no título — case-insensitive)
# A ORDEM IMPORTA: padrões mais específicos antes dos genéricos da mesma família.
_PATTERNS: list[tuple[str, list[str]]] = [
    # ── Eletrônicos ────────────────────────────────────────────────────────────
    ("console", [
        r"console|playstation|xbox|nintendo|switch|ps[45]\b|vr\b",
        r"controle\s*(sem\s*fio|wireless|dualsense|dualsense|xbox)",
        r"jogo\s*(de\s*)?(ps[45]|xbox|switch|nintendo)",
    ]),
    ("smartphone", [
        r"smartphone|celular|iphone|galaxy\s*[as]\d|redmi|poco|motorola\s*(edge|moto)",
        r"xiaomi|motorola|asus\s*rog\s*phone",
    ]),
    ("notebook", [
        r"notebook|laptop|macbook|ultrabook",
    ]),
    ("eletronico", [
        r"\btv\b|televisão|televisor|smart\s*tv|oled|qled",
        r"monitor|teclado|mouse\b|mousepad|headset|fone|headphone|earbuds|airpods|caixa.*som|speaker",
        r"tablet|ipad",
        r"\bpc\b|computador|desktop|processador|placa.*v[íi]deo|gpu|rtx|gtx|rx\s*\d",
        r"\bssd\b|\bhdd?\b|memória\s*ram|\bram\b|pendrive|hd\s+externo",
        r"câmera|camera|webcam|gopro|drone",
        r"roteador|wi.?fi|modem|repetidor\s*sinal",
        r"impressora|scanner|cartucho|toner",
        r"carregador|power\s*bank|cabo\s*usb|adaptador",
        r"smartwatch|relógio\s*inteligente|wearable",
    ]),

    # ── Roupa ──────────────────────────────────────────────────────────────────
    ("kit_intimo", [
        r"kit\s*\d+\s*(cueca|meia|calcinha|par\s*de)",
        r"\d+\s*(cuecas?|meias?|calcinhas?)\b",
        r"cueca\b|calcinha\b|meia\b|lingerie|sutiã",
    ]),
    ("calcado", [
        r"tênis\b|sandália|sapato\b|bota\b|chinelo|sapatilha|mocassim",
    ]),
    ("roupa", [
        r"camis[ae]\b|camiseta|polo\b",
        r"calça|jeans|legging|bermuda|shorts?\b",
        r"vestido|blusa|saia|body\b|macacão",
        r"jaqueta|casaco|moletom|hoodie|sobretudo|parka",
        r"pijama|conjunto\s*(de\s*)?(dormir|moletom)",
    ]),

    # ── Casa ───────────────────────────────────────────────────────────────────
    ("casa", [
        r"sofá|sofa|poltrona|puff",
        r"cama\b|colchão|travesseiro|edredom|lençol|roupa\s*de\s*cama",
        r"armário|guarda.?roupa|estante|prateleira|rack\b",
        r"mesa\b|cadeira|escrivaninha|bancada",
        r"geladeira|refrigerador|freezer",
        r"fogão|cooktop|forno\s*(elétrico)?",
        r"micro.?ondas",
        r"máquina\s*de?\s*(lavar|secar)|lava.?(louça|roupas?)",
        r"aspirador|robô\s*(de\s*)?(limpeza|aspirador)",
        r"ventilador|ar\s*condicionado|climatizador|purificador",
        r"liquidificador|batedeira|processador\s*de\s*alimento",
        r"fritadeira\s*air|air\s*fryer|airfryer",
        r"panela|frigideira|wok\b|chaleira|cafeteira",
        r"pote|copo\b|prato\b|tigela|jogo\s*(de\s*)?(cozinha|prato|copo)",
        r"luminária|abajur|pendente|lustre",
        r"tapete|cortina|persiana|toalha",
    ]),

    # ── Alimento ───────────────────────────────────────────────────────────────
    ("bebida_alcoolica", [
        r"cerveja|vinho|whisky|whiskey|gin\b|vodka|espumante|prosecco|cachaça|rum\b|licor",
    ]),
    ("suplemento", [
        r"whey|proteína\b|creatina|pré.?treino|hipercalórico|albumina|bcaa|glutamina",
    ]),
    ("alimento", [
        r"ketchup|maionese|mostarda|molho\b|vinagrete|shoyu",
        r"macarrão|massa\b|espaguete|lasanha|nhoque",
        r"\barroz\b|\bfeijão\b|lentilha|grão.de.bico",
        r"azeite|óleo\s*(de\s*)?coco|manteiga\s*de\s*amendoim",
        r"\bcafé\b|nescafé|cappuccino|cápsula\s*(nespresso|dolce)",
        r"\bleite\b|iogurte|queijo|manteiga\b|requeijão",
        r"suco\b|néctar|vitamina\b|smoothie|achocolatado",
        r"biscoito|bolacha|cookie|wafer|cracker",
        r"chocolate\b|bombom|barra\s*de\s*chocolate|trufa",
        r"refrigerante|energético|isotônico|água\s*(de\s*coco)?",
        r"snack|pipoca|amendoim|castanha|granola|barra\s*de\s*cereal",
        r"farinha|fermento|açúcar|sal\b|tempero|condimento",
    ]),

    # ── Higiene e Beleza ───────────────────────────────────────────────────────
    ("perfume", [
        r"perfume|eau\s*de\s*(parfum|toilette|cologne)|colônia\b|body\s*splash|deo\s*colônia",
    ]),
    ("higiene", [
        r"shampoo|condicionador|creme\s*de?\s*cabelo|máscara\s*capilar|tratamento\s*capilar",
        r"sabonete|sabão\s*(em\s*)?(barra|líquido)",
        r"hidratante|loção\s*corporal|creme\s*corporal|nivea\b|vaselina",
        r"desodorante|antitranspirante",
        r"pasta\s*de?\s*dente|escova\s*de?\s*dente|fio\s*dental|enxaguante",
        r"absorvente|fralda|lenço\s*umedecido|pomada\s*assadur",
        r"protetor\s*solar|filtro\s*solar|fps\s*\d+",
        r"barbeador|lâmina\s*de?\s*barbear|espuma\s*de?\s*barba|gillette",
        r"esfoliante|tônico|sérum|vitamina\s*c\s*(facial|pele)",
    ]),

    # ── Ferramentas ────────────────────────────────────────────────────────────
    ("ferramenta", [
        r"furadeira|parafusadeira|martelete|mandril",
        r"martelo|chave\s*de?\s*fenda|chave\s*combinada|alicate|torquesa|chave\s*inglesa",
        r"serra\b|esmerilhadeira|lixadeira|plaina",
        r"kit\s*de?\s*ferramenta|conjunto\s*de?\s*ferramenta|maleta\s*de?\s*ferramenta",
        r"extensão\s*elétrica|fita\s*led|cabo\s*energia",
        r"cano\b|torneira|válvula|registro\b|encanamento",
    ]),

    # ── Livros ─────────────────────────────────────────────────────────────────
    ("livro", [
        r"\blivro\b|e.?book",
        r"\bkindle\b",
        r"mangá|hq\b|quadrinho|graphic\s*novel",
        r"box\s*(de\s*)?livro|coleção\s*(de\s*)?livro",
    ]),

    # ── Brinquedos ─────────────────────────────────────────────────────────────
    ("brinquedo", [
        r"brinquedo|boneca|boneco\b",
        r"\blego\b|blocos\s*de?\s*montar|nanoblock",
        r"quebra.?cabeça|puzzle",
        r"jogo\s*de\s*tabuleiro|card\s*game|rpg\b",
        r"carrinho\s*(de\s*)?brinquedo|pista\s*de\s*corrida|hot\s*wheels",
        r"pelúcia|ursinho",
        r"massinha|argila\s*colorida|slime\b",
    ]),

    # ── Esporte ────────────────────────────────────────────────────────────────
    ("esporte", [
        r"bicicleta|bike\b|patins|skate\b|trotinete|patinete",
        r"haltere|kettlebell|anilha|barra\s*de?\s*musculação|supino",
        r"corda\s*de?\s*pular|elástico\s*de?\s*treino|faixa\s*elástica",
        r"esteira|bicicleta\s*ergométrica|elíptico|spinning",
        r"\bbola\b|chuteira|luva\s*de?\s*boxe|raquete",
        r"mochila\s*esport|bolsa\s*academia|squeeze\b|garrafa\s*esport",
    ]),
]


def classify(deal: Deal) -> str:
    title = deal.title.lower()
    for category, patterns in _PATTERNS:
        for pattern in patterns:
            if re.search(pattern, title):
                return category
    return "geral"
