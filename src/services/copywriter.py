import random
from src.models import Deal
from src.services.category_classifier import classify

_TEMPLATES: dict[str, list[str]] = {
    "eletronico": [
        "tava na lista de desejos de muita gente 👀",
        "esse aqui some rápido quando aparece assim ⚡",
        "quem tá precisando de upgrade vai se arrepender de deixar passar 😬",
        "tem coisa que fica mais barata esperando e tem coisa que não. esse é o segundo tipo 🫡",
        "um dos melhores custo-benefício que apareceu por aqui 💻",
        "pra quem tá montando setup ou substituindo o velho 🖥️",
        "raro aparecer nessa faixa de preço com essa qualidade 🔥",
    ],
    "roupa": [
        "roupa boa barata é difícil. quando aparece, não fica 👕",
        "kit completo e ainda sobra dinheiro 😌",
        "dessas coisas que você lembra que precisa só quando tá sem 😅",
        "pra repor o estoque sem culpa nenhuma 🛍️",
        "atualiza o guarda-roupa sem fazer besteira no cartão ✅",
        "tem peça que você compra e usa anos. esse parece uma 👀",
        "pra quem deixou acumular essa necessidade faz tempo 😂",
    ],
    "casa": [
        "casa organizada começa por uma compra assim 🏠",
        "um daqueles itens que a diferença você sente no primeiro dia 😍",
        "pra quem tá montando ou reformando. hora certa 🔨",
        "lembra aquela coisa que precisava trocar faz tempo? então 👇",
        "esse tipo de compra você não arrepende 🤌",
        "utilidade do dia a dia por um preço que faz sentido 💡",
        "quem mora sozinho sabe a falta que faz 🙋",
    ],
    "alimento": [
        "pra estocar e não ficar na mão 🛒",
        "rende bastante. vale muito a compra 👌",
        "churras, hambúrguer, jantar. esse vai trabalhar muito 🍔",
        "dessas compras que deixa a despensa mais feliz 😋",
        "pra quem gosta de ter em casa e nunca deixar faltar 🏠",
        "compra agora e agradece daqui a três semanas 🙏",
        "quem faz mercado sabe reconhecer uma boa quando vê 🧐",
    ],
    "higiene": [
        "tem gente que usa desde sempre e nunca larga 💆",
        "daquelas marcas que você conhece e confia 👍",
        "oportunidade de estocar o que já usa 🧴",
        "básico que nunca pode faltar e tá barato agora ✅",
        "quem usa sabe que vale cada centavo. agora tá mais barato ainda 😏",
        "pele agradece, bolso também 🌸",
        "rotina de cuidado que cabe no orçamento certinho 💅",
    ],
    "ferramenta": [
        "quem tem em casa resolve qualquer coisa 🔧",
        "aquela tarefa parada vai sair hoje 💪",
        "ferramenta boa dura anos 🛠️",
        "pra quem fica chamando ajuda pra tudo: chegou a hora 😂",
        "kit completo que resolve a maioria dos problemas em casa 🏠",
        "compra uma vez, usa pra sempre 🤝",
        "daqueles que você não pensa duas vezes depois que tem ✅",
    ],
    "livro": [
        "esse tava na lista de muita gente faz tempo 📚",
        "pra quem procrastina a leitura por conta do preço. acabou a desculpa 😌",
        "leitura boa não precisa custar caro 📖",
        "daqueles que você lê e indica pra todo mundo 🔥",
        "coleção que vale muito a pena completar agora 👀",
        "presente certeiro pra quem gosta de ler 🎁",
    ],
    "brinquedo": [
        "presente resolvido sem dor de cabeça 🎁",
        "criança não esquece de presente assim 🥹",
        "o tipo de coisa que ocupa a criançada por horas 😂",
        "pra quem tá com aniversário chegando e ainda não comprou nada 👀",
        "clássico que nunca decepciona 🎉",
        "diversão garantida e ainda no orçamento 🎠",
    ],
    "esporte": [
        "desculpa de não treinar acabou 💪",
        "quem fica adiando a academia vai entender 😅",
        "pra quem prefere treinar em casa e nunca achou a hora. essa é a hora 🏋️",
        "um dos melhores investimentos que você pode fazer, sério 🙏",
        "equipamento bom faz diferença a longo prazo 📈",
        "meta de começar o treino finalmente vai sair do papel 🔥",
    ],
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
