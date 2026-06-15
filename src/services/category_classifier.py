import re
from src.models import Deal

# (categoria, padrões regex no título — case-insensitive)
_PATTERNS: list[tuple[str, list[str]]] = [
    ("eletronico", [
        r"smartphone|celular|iphone|samsung|xiaomi|motorola|redmi|poco",
        r"notebook|laptop|macbook|ultrabook",
        r"\btv\b|televisão|televisor|smart\s*tv|oled|qled",
        r"monitor|teclado|mouse|mousepad|headset|fone|headphone|earbuds|airpods|caixa.*som|speaker",
        r"tablet|ipad",
        r"\bpc\b|computador|desktop|processador|placa.*v[íi]deo|gpu|rtx|gtx|rx\s*\d",
        r"\bssd\b|\bhdd?\b|memória\s*ram|\bram\b|pendrive|hd\s+externo",
        r"câmera|camera|webcam|gopro|drone",
        r"console|playstation|xbox|nintendo|switch|ps[45]\b|vr\b",
        r"roteador|wi.?fi|modem|repetidor\s*sinal",
        r"impressora|scanner|cartucho|toner",
        r"carregador|power\s*bank|cabo\s*usb|adaptador",
        r"smartwatch|relógio\s*inteligente|wearable",
    ]),
    ("roupa", [
        r"camis[ae]\b|camiseta|polo\b",
        r"calça|jeans|legging|bermuda|shorts?\b",
        r"vestido|blusa|saia|body\b|macacão",
        r"jaqueta|casaco|moletom|hoodie|sobretudo|parka",
        r"cueca|calcinha|meia\b|lingerie|sutiã|top\b",
        r"pijama|conjunto\s*(de\s*)?(dormir|moletom)",
        r"tênis|sandália|sapato|bota|chinelo|sapatilha|mocassim",
        r"kit\s*\d+\s*cueca|kit\s*\d+\s*meia|kit\s*\d+\s*calcinha",
    ]),
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
    ("alimento", [
        r"ketchup|maionese|mostarda|molho\b|vinagrete",
        r"macarrão|massa\b|espaguete|lasanha|nhoque",
        r"\barroz\b|\bfeijão\b|lentilha|grão.de.bico",
        r"azeite|óleo\s*(de\s*)?coco|manteiga\s*de\s*amendoim",
        r"\bcafé\b|nescafé|cappuccino|cápsula\s*(nespresso|dolce)",
        r"\bleite\b|iogurte|queijo|manteiga\b|requeijão",
        r"suco\b|néctar|vitamina\b|smoothie",
        r"biscoito|bolacha|cookie|wafer|cracker",
        r"chocolate\b|bombom|barra\s*de\s*chocolate|trufas?",
        r"refrigerante|energético|isotônico|água\s*(de\s*coco)?",
        r"cerveja|vinho|whisky|gin\b|vodka|espumante",
        r"whey|proteína\b|creatina|pré.?treino|suplemento",
        r"snack|pipoca|amendoim|castanha|granola|barra\s*de\s*cereal",
        r"farinha|fermento|açúcar|sal\b|tempero|condimento",
    ]),
    ("higiene", [
        r"shampoo|condicionador|creme\s*de?\s*cabelo|máscara\s*capilar|tratamento\s*capilar",
        r"sabonete|sabão\s*(em\s*)?(barra|líquido)",
        r"hidratante|loção\s*corporal|creme\s*corporal|nivea\b|vaselina",
        r"desodorante|antitranspirante",
        r"perfume|colônia|eau\s*de|body\s*splash",
        r"pasta\s*de?\s*dente|escova\s*de?\s*dente|fio\s*dental|enxaguante",
        r"absorvente|fralda|lenço\s*umedecido|pomada\s*assadur",
        r"protetor\s*solar|filtro\s*solar|fps\s*\d+",
        r"barbeador|lâmina\s*de?\s*barbear|espuma\s*de?\s*barba|gillette",
        r"esfoliante|tônico|sérum|vitamina\s*c\s*(facial|pele)",
    ]),
    ("ferramenta", [
        r"furadeira|parafusadeira|martelete|mandril",
        r"martelo|chave\s*de?\s*fenda|chave\s*combinada|alicate|torquesa|chave\s*inglesa",
        r"serra\b|esmerilhadeira|lixadeira|plaina",
        r"kit\s*de?\s*ferramenta|conjunto\s*de?\s*ferramenta|maleta\s*de?\s*ferramenta",
        r"extensão\s*elétrica|fita\s*led|cabo\s*energia",
        r"cano\b|torneira|válvula|registro\b|encanamento",
    ]),
    ("livro", [
        r"\blivro\b|e.?book",
        r"\bkindle\b",
        r"mangá|hq\b|quadrinho|graphic\s*novel",
        r"box\s*(de\s*)?livro|coleção\s*(de\s*)?livro",
    ]),
    ("brinquedo", [
        r"brinquedo|boneca|boneco\b",
        r"\blego\b|blocos\s*de?\s*montar|nanoblock",
        r"quebra.?cabeça|puzzle",
        r"jogo\s*de\s*tabuleiro|card\s*game|rpg\b",
        r"carrinho\s*(de\s*)?brinquedo|pista\s*de\s*corrida|hot\s*wheels",
        r"pelúcia|ursinho|boneco\s*de?\s*pelúcia",
        r"massinha|argila\s*colorida|slime\b",
    ]),
    ("esporte", [
        r"bicicleta|bike\b|patins|skate\b|trotinete|patinete",
        r"haltere|kettlebell|anilha|barra\s*de?\s*musculação|supino",
        r"corda\s*de?\s*pular|elástico\s*de?\s*treino|faixa\s*elástica",
        r"esteira|bicicleta\s*ergométrica|elíptico|spinning",
        r"\bbola\b|chuteira|luva\s*de?\s*boxe|raquete|protetor",
        r"mochila\s*esport|bolsa\s*academia|squeeze\b|garrafa\s*esport",
        r"suplemento\s*esport|coqueteleira",
    ]),
]


def classify(deal: Deal) -> str:
    title = deal.title.lower()
    for category, patterns in _PATTERNS:
        for pattern in patterns:
            if re.search(pattern, title):
                return category
    return "geral"
