import random
from src.models import Deal
from src.services.category_classifier import classify

_TEMPLATES: dict[str, list[str]] = {

    # ── Eletrônicos ────────────────────────────────────────────────────────────
    "console": [
        "fim de semana que vem tem desculpa pra não sair de casa 🎮",
        "quem joga sabe que esse preço não fica por muito tempo 👀",
        "presente de aniversário que praticamente se escolhe sozinho 🎁",
        "esse tava na lista de desejos de muita gente faz tempo ⚡",
        "pra quem adiou essa compra esperando o preço certo. chegou 🫡",
        "horas e horas de diversão por esse valor. matemática que fecha 🕹️",
    ],
    "smartphone": [
        "câmera nova, memória boa e preço que cabe no bolso 📱",
        "upgrade que você vai sentir do primeiro ao último toque 🔥",
        "daqueles que some do estoque rápido quando aparece assim 👀",
        "celular novo por esse valor não aparece sempre. bora 😬",
        "pra quem tá carregando aquela bateria viciada faz meses 😅",
        "tela boa, câmera boa, bateria boa. por esse preço? vai 🫡",
    ],
    "notebook": [
        "trabalho, faculdade ou série. esse resolve os três sem reclamar 💻",
        "desempenho de respeito por um preço que faz sentido 🔥",
        "pra quem tá travando em tudo com o computador atual 😬",
        "aquele upgrade de produtividade que você fica adiando. chegou 👀",
        "por esse valor com essa configuração. raro aparecer assim 🫡",
        "leve, rápido e no orçamento. não tem muito mais o que pedir 😌",
    ],
    "tv_monitor": [
        "imagem grande, preço menor do que parece 📺",
        "sala de estar ou setup. esse transforma qualquer ambiente 🔥",
        "assistir série, jogar, trabalhar. tela boa muda tudo 👀",
        "por esse valor com esse tamanho dificilmente aparece melhor 🫡",
        "quem tem em casa sabe que não dá pra voltar pro tamanho antigo 😍",
        "home theater em casa por muito menos do que você imagina 🎬",
    ],
    "fone_headset": [
        "musica boa no ouvido muda o dia inteiro ✨",
        "som de qualidade por um preço que não dói 🎧",
        "pra quem trabalha em casa e cansa de ouvir o barulho externo 😌",
        "foco no home office ou imersão nos games. resolve os dois 🎮",
        "daqueles que você coloca e esquece que tá usando 👌",
        "grave, médio e agudo do jeito que tem que ser. por esse preço 🔥",
    ],
    "eletronico_acessorio": [
        "aquele acessório que faz falta só quando você não tem 🤌",
        "pequeno, necessário e barato agora 👌",
        "setup completo começa pelos detalhes certos ⚡",
        "pra quem vive no limite do cabo rasgado ou bateria fraca 😅",
        "daquelas compras que você faz e fica feliz que fez 😌",
        "complemento que você ia comprar de qualquer jeito 🛒",
    ],
    "eletronico_geral": [
        "um dos melhores preços que apareceu por aqui 👀",
        "desses que some antes de você terminar de pensar ⚡",
        "raro aparecer nessa faixa de preço com essa qualidade 🔥",
        "pra quem conhece o produto, sabe que esse preço não dura 😬",
        "pra quem tá esperando o momento certo. chegou 🫡",
        "tecnologia boa não precisa custar o que geralmente custa 😌",
    ],

    # ── Moda ─────────────────────────────────────────────────────────────────
    "kit_intimo": [
        "dessas coisas que a gente lembra que precisa só quando tá sem 😅",
        "kit completo e ainda sobra dinheiro no bolso 😌",
        "pra quem deixou acumular essa necessidade mais do que devia 😂",
        "compra e esquece por um bom tempo 🛒",
        "básico que nunca pode faltar. e por esse preço? manda ver 👌",
        "pra repor o estoque sem sentir no orçamento 😎",
    ],
    "calcado_esporte": [
        "tênis bom transforma treino em outro nível 👟",
        "pé confortável rende muito mais. esse prova 💪",
        "pra quem tá correndo com o tênis furado faz tempo 😬",
        "modelo que vende muito e tem motivo pra isso 🔥",
        "desempenho + durabilidade por um preço que não aparece sempre 👀",
        "aquele par que vai do treino pra rua sem esforço 😌",
    ],
    "calcado": [
        "par novo e o bolso agradece 👟",
        "daqueles que você usa e esquece que tá usando de tão confortável 😌",
        "versátil o suficiente pra vários momentos diferentes 🎯",
        "calçado bom por esse preço. não deixa pra depois 🔥",
        "pra quem tá de olho em renovar o calçado faz tempo 👀",
        "qualidade que você nota do primeiro uso 😍",
    ],
    "roupa_esporte": [
        "treinar com roupa certa faz diferença, não tem jeito 💪",
        "pra quem fica enrolando pra ir treinar. a roupa tá pronta 😂",
        "conforto e mobilidade sem gastar muito. bora 🏃",
        "daquelas peças que você usa toda semana e nunca enjoa 😌",
        "do treino pra qualquer outro lugar sem precisar trocar 🔥",
        "pra montar aquele uniforme de academia que você quer 💅",
    ],
    "roupa_social": [
        "primeira impressão começa antes de abrir a boca 👔",
        "visual arrumado sem precisar gastar o que parece 😌",
        "pra quem tem reunião, evento ou almoço importante chegando 🎯",
        "peça que valoriza qualquer guarda-roupa. e por esse preço 👀",
        "bem vestido de segunda a segunda por muito menos 🔥",
        "aquela camisa que combina com tudo e dura anos 🤝",
    ],
    "roupa": [
        "roupa boa barata é difícil. quando aparece, não fica 👕",
        "atualiza o guarda-roupa sem fazer besteira no cartão ✅",
        "peça que você vai usar mais vezes do que imagina 👀",
        "visual novo sem dor no bolso 😍",
        "versátil, combina com tudo que você já tem 🎯",
        "conforto e estilo sem pagar o dobro por marca 😌",
    ],

    # ── Casa ─────────────────────────────────────────────────────────────────
    "eletrodomestico_grande": [
        "compra que você usa todo dia pelo resto dos anos 🏠",
        "pra quem tá na lona com o eletrodoméstico atual. chegou a hora ⚡",
        "investimento que você sente no dia a dia por anos 😌",
        "por esse valor com essa marca? esse não fica 👀",
        "quando a necessidade aparece o preço costuma ser maior que esse 🫡",
        "reforma de casa começa pelos eletros. esse tá no ponto certo 🔥",
    ],
    "eletrodomestico_pequeno": [
        "aquela praticidade na cozinha que você fica adiando 😅",
        "airfryer, liquidificador ou cafeteira. muda o cotidiano 🍽️",
        "pra quem cozinha em casa e quer facilitar a vida 👌",
        "daqueles que você usa e fica sem entender como vivia sem 😍",
        "compra pequena, impacto enorme na rotina 🔥",
        "cozinha mais prática começa com uma compra assim 🏠",
    ],
    "cama_banho": [
        "dormir bem é a base de tudo. e começa por aqui 😴",
        "pra quem acorda cansado todo dia. tá na hora de trocar 🛏️",
        "qualidade de sono que você vai sentir na primeira noite 😍",
        "colchão, travesseiro ou edredom. o que for, vale muito 👌",
        "casa aconchegante começa pelo quarto. esse ajuda 🏠",
        "por esse preço com essa qualidade. compra sem arrependimento 😌",
    ],
    "moveis": [
        "móvel bom dura anos. esse preço faz a conta fechar 🏠",
        "casa organizada começa por uma decisão assim 😍",
        "pra quem tá montando, reformando ou simplesmente precisando renovar 🔨",
        "qualidade que você vai ver e sentir todo dia 👀",
        "aquele espaço que tava faltando resolver. chegou 🫡",
        "compra que transforma o ambiente do primeiro dia 💡",
    ],
    "utensilio_cozinha": [
        "cozinha equipada, vida mais fácil. simples assim 🍳",
        "pra quem gosta de cozinhar e não quer usar ferramenta ruim 👨‍🍳",
        "utensílio bom dura anos e faz diferença toda vez que usa 😌",
        "daqueles que parecem simples mas mudam sua rotina na cozinha 🔥",
        "presente certeiro pra quem ama cozinhar 🎁",
        "porque ninguém merece panela que gruda ou faca que não corta 😂",
    ],
    "casa_geral": [
        "detalhe que muda o visual do ambiente inteiro 💡",
        "casa mais bonita começa por uma compra assim 😍",
        "pra quem tá de olho em organizar ou decorar faz tempo 🏠",
        "pequena mudança, grande diferença no dia a dia 🤌",
        "ambiente certo começa por escolhas certas 👀",
        "daqueles que você olha e pensa: precisava disso faz tempo 😌",
    ],

    # ── Alimento ─────────────────────────────────────────────────────────────
    "cafe": [
        "dia bom começa com café bom. e por esse preço 😍",
        "pra quem não consegue funcionar sem a primeira xícara ☕",
        "estoca o mês inteiro sem sentir no orçamento 😌",
        "daquelas marcas que você prova uma vez e não larga 🔥",
        "presente pra quem ama café e vai agradecer de verdade 🎁",
        "porque café ruim de manhã estraga o dia inteiro. esse não é 👌",
    ],
    "churrasco": [
        "próximo churrasco tá praticamente organizado 🔥",
        "churrasqueiro bom começa com equipamento certo 🥩",
        "kit completo pra não faltar nada na hora do churrasco 👌",
        "pra quem leva o churrasco a sério. esse é o investimento certo 🫡",
        "presente pra quem faz o churrasco de todo final de semana 🎁",
        "porque ninguém merece churrasco com equipamento ruim 😤",
    ],
    "condimento": [
        "despensa incompleta sem esses básicos. tá barato agora 🛒",
        "ketchup, azeite, molho. o que for, rende bastante 🍔",
        "pra estocar e não ficar na mão no momento errado 👌",
        "churrasco, hambúrguer, salada. esse vai trabalhar muito 🔥",
        "daqueles que você coloca na mesa e some mais rápido do que imagina 😅",
        "compra agora e agradece na próxima vez que for cozinhar 🙏",
    ],
    "chocolate_doce": [
        "porque às vezes o dia pede um chocolate. e por esse preço 🍫",
        "presente fácil, certeiro e que todo mundo gosta 🎁",
        "pra estocar e ter em casa pra qualquer visita 😌",
        "aquele mimo que você merece de vez em quando 🥹",
        "daqueles que some do estoque mais rápido do que deveria 😂",
        "presente de criança, de adulto e de quem é do chocolate 😍",
    ],
    "bebida_alcoolica": [
        "próximo churrasco ou happy hour já tem o que servir 🍺",
        "pra estocar antes do próximo encontro 😏",
        "presente fácil e certeiro pra quem curte a boa 🎁",
        "rótulo bom por esse preço vale guardar 👀",
        "pra ter em casa e não depender de loja na hora h 🛒",
        "quem aprecia sabe que esse preço não aparece sempre 🍷",
    ],
    "suplemento": [
        "meta de proteína mais fácil de bater por menos 💪",
        "pra quem leva a dieta a sério e não quer pagar caro 🎯",
        "estoca o mês sem sentir no bolso 📦",
        "rendimento e recuperação por um preço que faz sentido 🏋️",
        "quem treina sabe quanto esse tipo de produto faz diferença 🔥",
        "compra agora, agradece na semana de treino 😌",
    ],
    "alimento": [
        "despensa cheia começa com uma compra assim 🛒",
        "básico de todo dia por um preço que vale estocar 👌",
        "pra quem faz mercado e sabe reconhecer uma boa quando vê 🧐",
        "compra agora e agradece daqui a três semanas 🙏",
        "rende bastante e cabe no orçamento. combinação perfeita 😋",
        "pra quem gosta de ter em casa e nunca deixar faltar 🏠",
    ],

    # ── Bebê ─────────────────────────────────────────────────────────────────
    "bebe": [
        "pacotão que os pais agradecem 🙏",
        "pra quem sabe que essas coisas acabam sempre no pior momento 😅",
        "produto de bebê bom por esse preço. não deixa passar 👶",
        "pra quem vive com olho no estoque e não quer ser surpreendido 😬",
        "bebê feliz, pai no bolso também 😌",
        "porque tem coisa que não dá pra economizar na errada. esse não é o caso 🤌",
    ],

    # ── Beleza e Higiene ─────────────────────────────────────────────────────
    "perfume": [
        "cheiro bom por esse preço não aparece sempre 😮",
        "aquele presente que todo mundo fica perguntando de onde veio 👀",
        "pra chegar num ambiente e deixar rastro 😏",
        "presente praticamente pronto. é só embrulhar 🎁",
        "bom demais pra usar só em ocasiões especiais 🌸",
        "quem gosta de perfume sabe que esse preço não volta fácil 🙏",
    ],
    "skincare": [
        "pele que você vai notar a diferença em poucas semanas 🌸",
        "rotina de skincare que cabe no orçamento. e funciona 💆",
        "porque cuidar da pele agora é o que você vai agradecer mais tarde 🙏",
        "daquelas marcas que dermatologista indica e funciona de verdade 👀",
        "pra quem quer começar a rotina de skincare sem gastar muito 😌",
        "protetor solar ou hidratante. sempre vale estocar 😍",
    ],
    "cabelo": [
        "cabelo bonito começa no banho. e por esse preço 🚿",
        "daqueles que você usa uma vez e já percebe a diferença 🔥",
        "pra estocar o que já funciona pra você sem pagar o preço cheio 😌",
        "hidratação, brilho e maciez por um preço que faz sentido 💆",
        "presente certeiro pra quem capricha no cabelo 🎁",
        "quem tem o cabelo difícil sabe o quanto produto bom importa 👌",
    ],
    "barba": [
        "barba bem feita começa com produto certo 🪒",
        "pra quem faz a barba todo dia. vale muito estocar 😌",
        "barbeador ou refil. sempre um deles tá acabando 😅",
        "aparência cuidada por muito menos do que parece 👀",
        "daqueles que você percebe a diferença já na primeira usada 👌",
        "pra quem não abre mão de um barbeamento limpo todo dia 🎯",
    ],
    "higiene": [
        "básico que nunca pode faltar 🛒",
        "daquelas marcas que você já conhece e confia 👍",
        "pra estocar o que já usa e não ser pego desprevenido 📦",
        "rotina do dia a dia por um preço que faz sentido 😌",
        "qualidade de sempre. preço melhor do que o de sempre ✅",
        "compra e fica tranquilo por um bom tempo 😎",
    ],

    # ── Esporte e Saúde ───────────────────────────────────────────────────────
    "musculacao": [
        "home gym real começa com equipamento assim 💪",
        "pra quem quer treinar em casa e parou de vez na desculpa 🏋️",
        "quanto você gasta de academia num ano? esse se paga rápido 🧮",
        "haltere bom dura décadas. por esse preço vale muito 💰",
        "força de verdade começa com investimento certo 🔥",
        "pra montar a home gym que você planeja faz tempo 🎯",
    ],
    "cardio_outdoor": [
        "cardio em casa sem depender de academia ou tempo bom 🚴",
        "pra quem faz promessa de academia todo mês e não vai 😂",
        "30 minutos por dia muda muita coisa. esse ajuda a começar 💪",
        "investimento que se paga em saúde e economia de mensalidade 🙏",
        "bicicleta boa ou patins. os dois deixam o sedentarismo sem desculpa 🔥",
        "pra quem prefere ar fresco e movimento de verdade 😍",
    ],
    "esporte": [
        "pra quem pratica de verdade e quer equipamento à altura 🏅",
        "esporte bom começa com material certo 🎯",
        "daqueles que você usa no treino e na partida sem distinção 💪",
        "pra completar o kit e não faltar nada na hora h 👌",
        "presente certeiro pra quem pratica esporte 🎁",
        "qualidade de jogo melhora com equipamento que não decepciona 🔥",
    ],

    # ── Ferramentas ───────────────────────────────────────────────────────────
    "ferramenta_eletrica": [
        "projeto parado vai sair hoje 🔧",
        "furadeira ou parafusadeira boa dura décadas. esse preço fecha 💪",
        "pra quem fica chamando ajuda pra qualquer coisa. chegou a hora 😂",
        "reforma ou manutenção. quem tem ferramenta elétrica resolve sozinho 🛠️",
        "uma das melhores aquisições pra quem mora em casa 🏠",
        "compra uma vez, usa pra sempre. e esse preço ajuda a decidir ✅",
    ],
    "ferramenta": [
        "quem tem ferramenta certa em casa resolve qualquer coisa 🔧",
        "kit completo que resolve a maioria dos problemas sem chamar ninguém 🛠️",
        "presente prático pra quem é do tipo que conserta em vez de jogar fora 🎁",
        "pra aquela tarefa específica que tá parada esperando a ferramenta certa 💡",
        "compra uma vez, usa pra sempre 🤝",
        "pequena, necessária e barata agora. vale ter 😌",
    ],

    # ── Livros ────────────────────────────────────────────────────────────────
    "livro_negocio": [
        "leitura que muda forma de pensar em negócio e em dinheiro 📈",
        "daqueles que você lê, sublinha e relê no ano seguinte 📚",
        "presente pra quem tá construindo algo. vai fazer diferença 🎁",
        "conhecimento que devolve muito mais do que custa 🔥",
        "pra quem quer crescer profissional e financeiramente 🎯",
        "o melhor investimento continua sendo em conhecimento. e esse tá barato 😌",
    ],
    "livro": [
        "esse tava na lista de muita gente faz tempo 📚",
        "pra quem procrastina a leitura por conta do preço. acabou a desculpa 😌",
        "daqueles que você lê e fica indicando pra todo mundo 🔥",
        "coleção que vale muito completar enquanto tá nesse preço 👀",
        "presente certeiro pra quem gosta de ler 🎁",
        "leitura boa é o entretenimento mais barato que existe 📖",
    ],

    # ── Brinquedos ───────────────────────────────────────────────────────────
    "brinquedo_educativo": [
        "brinquedo que diverte e desenvolve ao mesmo tempo. raro 🧩",
        "presente que os pais amam dar e as crianças amam ganhar 🎁",
        "horas de concentração e criatividade em uma caixa só 🔥",
        "pra estimular a criatividade sem precisar de bateria 😌",
        "daqueles que a criança vai querer todos os dias 🥹",
        "jogo que a família inteira acaba jogando junto 🎉",
    ],
    "brinquedo": [
        "presente resolvido sem dor de cabeça 🎁",
        "criança não esquece de presente assim 🥹",
        "o tipo de coisa que ocupa a criançada por horas 😂",
        "pra quem tá com aniversário chegando e ainda não comprou nada 👀",
        "clássico que nunca decepciona 🎉",
        "diversão garantida e ainda dentro do orçamento 🎠",
    ],

    # ── Pets ─────────────────────────────────────────────────────────────────
    "pet": [
        "porque pet feliz é dono feliz 🐾",
        "pra quem não abre mão da qualidade com o bichinho 😍",
        "ração boa, coleira nova ou brinquedo. o que for, pet agradece 🐶",
        "presente que o pet vai amar mesmo sem saber que é presente 🥹",
        "cuidado com o animal que não pesa no bolso 👌",
        "pra quem trata o pet como família. esse é o preço certo 🐾",
    ],

    # ── Fallback ─────────────────────────────────────────────────────────────
    "geral": [
        "um dos melhores preços que apareceu por aqui 👀",
        "desses que some antes de você terminar de pensar ⚡",
        "se tava esperando o momento certo, chegou 🫡",
        "raramente aparece assim. vale conferir 🔥",
        "pra quem conhece o produto, sabe que esse preço não dura 😬",
        "não é toda semana que aparece uma assim 🎯",
    ],
}


def generate(deal: Deal) -> str:
    category = classify(deal)
    options = _TEMPLATES.get(category, _TEMPLATES["geral"])
    return random.choice(options)
