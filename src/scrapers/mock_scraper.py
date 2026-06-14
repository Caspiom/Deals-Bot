import asyncio
import random
from src.config.settings import MIN_DISCOUNT_PERCENT, MAX_DEALS_PER_RUN
from src.models import Deal
from src.scrapers.base_scraper import BaseScraper

_PRODUCT_POOL = [
    {
        "title": "Smartphone Samsung Galaxy A55 5G 256GB",
        "url": "https://www.amazon.com.br/dp/B0CX1234AB",
        "price": 1799.90,
        "old_price": 2499.90,
        "image_url": "https://m.media-amazon.com/images/I/mock-galaxy-a55.jpg",
    },
    {
        "title": "Notebook Dell Inspiron 15 Intel Core i5 16GB RAM 512GB SSD",
        "url": "https://www.kabum.com.br/produto/123456/notebook-dell-inspiron",
        "price": 3199.00,
        "old_price": 4599.00,
        "image_url": "https://images.kabum.com.br/produtos/fotos/mock-dell-inspiron.jpg",
    },
    {
        "title": "Smart TV LG 55\" 4K OLED ThinQ AI",
        "url": "https://www.magazineluiza.com.br/smart-tv-lg-55-oled/p/mock001/et/oled/",
        "price": 3799.00,
        "old_price": 5999.00,
        "image_url": "https://a-static.mlcdn.com.br/800x560/mock-lg-oled.jpg",
    },
    {
        "title": "Fone de Ouvido Sony WH-1000XM5 Noise Cancelling Bluetooth",
        "url": "https://www.americanas.com.br/produto/mock-sony-wh1000xm5",
        "price": 1349.00,
        "old_price": 1999.00,
        "image_url": "https://images.americanas.com.br/produtos/mock-sony-xm5.jpg",
    },
    {
        "title": "SSD Kingston NV2 2TB M.2 NVMe PCIe 4.0",
        "url": "https://www.kabum.com.br/produto/234567/ssd-kingston-nv2-2tb",
        "price": 499.90,
        "old_price": 749.90,
        "image_url": "https://images.kabum.com.br/produtos/fotos/mock-ssd-kingston.jpg",
    },
    {
        "title": "Aspirador de Pó Robô Xiaomi Robot Vacuum E10 2500Pa",
        "url": "https://www.amazon.com.br/dp/B0MOCK1234",
        "price": 799.00,
        "old_price": 1299.00,
        "image_url": "https://m.media-amazon.com/images/I/mock-xiaomi-vacuum.jpg",
    },
    {
        "title": "Cafeteira Nespresso Vertuo Pop Capsulas Automática",
        "url": "https://www.submarino.com.br/produto/mock-nespresso-vertuo",
        "price": 399.90,
        "old_price": 599.90,
        "image_url": "https://images.submarino.com.br/mock-nespresso.jpg",
    },
    {
        "title": "Kindle 11ª Geração 16GB com Iluminação Embutida",
        "url": "https://www.amazon.com.br/dp/B09SWV3BYH",
        "price": 349.00,
        "old_price": 499.00,
        "image_url": "https://m.media-amazon.com/images/I/mock-kindle-11.jpg",
    },
    {
        "title": "Teclado Mecânico Redragon Kumara K552 RGB Switch Red",
        "url": "https://www.kabum.com.br/produto/345678/teclado-redragon-kumara",
        "price": 189.90,
        "old_price": 299.90,
        "image_url": "https://images.kabum.com.br/produtos/fotos/mock-redragon-kumara.jpg",
    },
    {
        "title": "Monitor Gamer LG 27\" 165Hz 1ms FHD IPS UltraGear",
        "url": "https://www.terabyteshop.com.br/produto/mock-monitor-lg-27",
        "price": 1099.00,
        "old_price": 1599.00,
        "image_url": "https://www.terabyteshop.com.br/imagens/produtos/mock-lg-27-ultragear.jpg",
    },
    {
        "title": "Headset HyperX Cloud II 7.1 Surround USB",
        "url": "https://www.pichau.com.br/headset-hyperx-cloud-ii-mock",
        "price": 399.00,
        "old_price": 599.00,
        "image_url": "https://www.pichau.com.br/media/catalog/product/mock-hyperx-cloud2.jpg",
    },
    {
        "title": "Placa de Vídeo NVIDIA RTX 4060 8GB GDDR6 ASUS Dual",
        "url": "https://www.kabum.com.br/produto/456789/rtx-4060-asus-dual",
        "price": 2199.00,
        "old_price": 2899.00,
        "image_url": "https://images.kabum.com.br/produtos/fotos/mock-rtx4060-asus.jpg",
    },
]


class MockScraper(BaseScraper):
    name = "mock"

    async def fetch(self) -> list[Deal]:
        await asyncio.sleep(0.1)  # simula latência de rede

        sample = random.sample(_PRODUCT_POOL, k=min(MAX_DEALS_PER_RUN + 3, len(_PRODUCT_POOL)))

        deals: list[Deal] = []
        for item in sample:
            deal = Deal(
                title=item["title"],
                url=item["url"],
                price=item["price"],
                old_price=item["old_price"],
                image_url=item["image_url"],
                source=self.name,
            )
            if deal.discount_pct is not None and deal.discount_pct >= MIN_DISCOUNT_PERCENT:
                deals.append(deal)

        return deals[:MAX_DEALS_PER_RUN]
