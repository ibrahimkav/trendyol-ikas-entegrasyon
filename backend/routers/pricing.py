"""
Fiyat Önerisi Router
AI destekli fiyat analizi ve önerileri
Groq API kullanıyor (ücretsiz ve hızlı)
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import os
import math

from sqlalchemy.orm import Session

from database.db import get_db
from database.models import Product, Store
from security import get_current_store
from utils.pricing_calc import calculate_suggested_price
from utils.store_trendyol import resolve_trendyol_creds, fetch_orders

router = APIRouter()

# Groq client (ücretsiz ve hızlı)
groq_client = None
groq_api_key = os.getenv("GROQ_API_KEY")

if groq_api_key:
    try:
        from groq import Groq
        groq_client = Groq(api_key=groq_api_key)
    except ImportError:
        print("⚠️ Groq paketi yüklü değil. 'pip install groq' komutu ile yükleyin.")
    except Exception as e:
        print(f"⚠️ Groq API bağlantı hatası: {e}")


class PricingRequest(BaseModel):
    """Fiyat önerisi isteği"""
    product_name: str
    product_category: Optional[str] = None
    current_price: Optional[float] = None
    cost_price: float
    target_profit_margin: Optional[float] = 0.30  # %30 varsayılan kâr marjı
    competitor_analysis: Optional[bool] = True


class PricingResponse(BaseModel):
    """Fiyat önerisi yanıtı"""
    recommended_price: float
    price_range: dict
    psychological_prices: List[float]
    competitor_analysis: Optional[dict] = None
    profit_margin: float
    reasoning: str
    golden_ratio_price: Optional[float] = None


def calculate_golden_ratio_price(min_price: float, max_price: float) -> float:
    """
    Altın oran (1.618) kullanarak psikolojik olarak çekici fiyat hesaplar.
    Altın oran noktası: min + (max - min) / 1.618
    """
    if max_price <= min_price:
        return min_price
    
    golden_point = min_price + (max_price - min_price) / 1.618
    return round(golden_point, 2)


def generate_psychological_prices(base_price: float) -> List[float]:
    """
    Psikolojik fiyatlandırma teknikleri:
    - 9 ile biten fiyatlar (99.99, 199.99)
    - Yuvarlak sayılar (100, 200)
    - Altın oran fiyatları
    """
    prices = []
    
    # 9 ile biten fiyatlar (charm pricing)
    prices.append(math.floor(base_price) - 0.01)
    prices.append(math.ceil(base_price) - 0.01)
    
    # Yuvarlak sayılar
    prices.append(round(base_price / 10) * 10)
    prices.append(round(base_price / 50) * 50)
    
    # 5 ile biten fiyatlar
    prices.append(round(base_price / 5) * 5)
    
    # Benzersiz ve sıralı
    prices = sorted(set([round(p, 2) for p in prices if p > 0]))
    
    return prices[:5]  # En iyi 5 seçeneği döndür


async def analyze_competitors(product_name: str, category: str = None) -> dict:
    """
    Trendyol ve rakip sitelerden fiyat analizi yapar.
    (Gerçek implementasyon için web scraping veya API gerekli)
    """
    # Bu kısım gerçek implementasyonda:
    # 1. Trendyol API ile ürün araması
    # 2. Web scraping (BeautifulSoup/Selenium)
    # 3. Fiyat karşılaştırma siteleri API'leri
    
    # Şimdilik mock data
    return {
        "average_price": 150.0,
        "min_price": 99.99,
        "max_price": 249.99,
        "median_price": 149.99,
        "competitor_count": 15,
        "price_distribution": {
            "low": 99.99,
            "medium": 149.99,
            "high": 199.99
        }
    }


async def get_ai_pricing_advice(
    product_name: str,
    cost_price: float,
    competitor_data: dict,
    target_margin: float
) -> str:
    """
    Groq API ile fiyat önerisi alır.
    """
    prompt = f"""
    Trendyol satıcısı için fiyat önerisi yap:
    
    Ürün: {product_name}
    Maliyet: {cost_price} TL
    Hedef Kâr Marjı: %{target_margin * 100}
    Piyasa Ortalama: {competitor_data.get('average_price', 'N/A')} TL
    Piyasa Aralığı: {competitor_data.get('min_price', 'N/A')} - {competitor_data.get('max_price', 'N/A')} TL
    
    Psikolojik fiyatlandırma ve altın oran prensiplerini dikkate alarak:
    1. Rekabetçi fiyat önerisi
    2. Kâr marjını koruyarak
    3. Müşteri psikolojisini düşünerek
    
    Kısa ve öz bir öneri yap (maksimum 150 kelime). Türkçe yanıt ver.
    """
    
    system_prompt = "Sen bir e-ticaret fiyatlandırma uzmanısın. Türkçe yanıt ver."
    
    # Groq API kullan
    if groq_client:
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",  # Hızlı ve ücretsiz
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"⚠️ Groq API hatası: {e}")
            # Hata durumunda fallback'e geç
            return generate_rule_based_advice(product_name, cost_price, competitor_data, target_margin)
    else:
        # Groq API key yoksa kural tabanlı öneri
        return generate_rule_based_advice(product_name, cost_price, competitor_data, target_margin)


def generate_rule_based_advice(
    product_name: str,
    cost_price: float,
    competitor_data: dict,
    target_margin: float
) -> str:
    """
    AI kullanılamazsa kural tabanlı öneri üretir.
    """
    base_price = cost_price * (1 + target_margin)
    avg_price = competitor_data.get('average_price', base_price)
    min_price = competitor_data.get('min_price', base_price * 0.9)
    max_price = competitor_data.get('max_price', base_price * 1.3)
    
    if avg_price < base_price:
        advice = f"Piyasa fiyatı ({avg_price:.2f} TL) maliyetinizin altında. "
        advice += f"Minimum {base_price:.2f} TL fiyat önerilir. "
        advice += "Kalite farkını vurgulayarak rekabet edin."
    elif avg_price <= base_price * 1.2:
        advice = f"Rekabetçi fiyat aralığında ({min_price:.2f}-{max_price:.2f} TL). "
        advice += f"Altın oran fiyatı {min_price + (max_price - min_price) / 1.618:.2f} TL önerilir. "
        advice += "Psikolojik fiyatlandırma (99.99, 199.99) kullanın."
    else:
        advice = f"Piyasa ortalaması ({avg_price:.2f} TL) yüksek. "
        advice += f"{base_price:.2f}-{avg_price:.2f} TL arası rekabetçi fiyat koyabilirsiniz. "
        advice += "Kâr marjınızı koruyarak satış hacmini artırın."
    
    return advice


@router.get("/active-products")
async def get_active_products(
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """
    Trendyol'da aktif satışta olan ürünleri listeler (Wave3: per-store).
    Önce siparişlerden ürünleri çıkarır (daha güvenilir).
    """
    creds = resolve_trendyol_creds(db, store)

    try:
        unique_products = {}

        # Wave3: bu mağazanın siparişlerini per-store creds ile çek (env DEĞİL),
        # sonra mevcut sayfalama/işleme yapısını koruyarak dilimle.
        _all_orders = fetch_orders(creds, max_pages=5)
        page = 0
        size = 200
        max_pages = 5  # Maksimum 5 sayfa (1000 sipariş)

        while page < max_pages:
            orders = _all_orders[page * size:(page + 1) * size]

            if not orders:
                break

            try:
                # Siparişlerden benzersiz ürünleri çıkar
                products_found_this_page = 0
                for order in orders:
                    lines = order.get("lines", [])
                    if not lines:
                        continue
                    
                    for line in lines:
                        # Farklı alan adlarını dene
                        product_id = (
                            str(line.get("productId") or "") or
                            str(line.get("product_id") or "") or
                            str(line.get("productCode") or "") or
                            str(line.get("barcode") or "") or
                            ""
                        )
                        
                        if not product_id or product_id == "None" or product_id == "":
                            continue
                        
                        # Eğer bu ürün daha önce eklenmemişse
                        if product_id not in unique_products:
                            product_name = (
                                line.get("productName") or
                                line.get("product_name") or
                                line.get("name") or
                                "Bilinmeyen Ürün"
                            )
                            
                            price = line.get("price") or line.get("salePrice") or 0
                            if isinstance(price, str):
                                try:
                                    price = float(price.replace(",", "."))
                                except:
                                    price = 0
                            
                            # Fiyat 0 ise atla
                            if price <= 0:
                                continue
                            
                            unique_products[product_id] = {
                                "product_id": product_id,
                                "product_name": product_name,
                                "current_price": float(price),
                                "category": (
                                    line.get("categoryName") or
                                    line.get("category_name") or
                                    line.get("category") or
                                    ""
                                ),
                                "barcode": line.get("barcode") or line.get("sku") or "",
                                "stock_quantity": 0  # Siparişlerden stok bilgisi yok
                            }
                            products_found_this_page += 1
                
                print(f"Sayfa {page}: {len(orders)} sipariş, {products_found_this_page} yeni ürün bulundu")
                
                if len(orders) < size:
                    break
                
                page += 1
            except Exception as e:
                print(f"Sipariş sayfası {page} işlenirken hata: {str(e)}")
                break
        
        # Ürünleri listeye çevir
        formatted_products = list(unique_products.values())
        
        # Fiyatı 0 olanları filtrele
        formatted_products = [p for p in formatted_products if p["current_price"] > 0]
        
        # Fiyata göre sırala (yüksekten düşüğe)
        formatted_products.sort(key=lambda x: x["current_price"], reverse=True)
        
        print(f"Toplam {len(formatted_products)} aktif ürün bulundu")
        
        return {
            "products": formatted_products,
            "total_count": len(formatted_products),
            "message": f"{len(formatted_products)} aktif ürün bulundu"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Aktif ürünler çekilirken hata: {error_detail}")
        raise HTTPException(
            status_code=500,
            detail=f"Aktif ürünler çekilemedi: {str(e)}"
        )


@router.get("/analyze-trendyol/{product_id}")
async def analyze_trendyol_product(
    product_id: str,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """
    Trendyol'daki aktif bir ürünü analiz eder (Wave3: per-store).
    Aktif satış yapan satıcıları kontrol ederek altın oran fiyat önerisi yapar.
    """
    creds = resolve_trendyol_creds(db, store)

    try:
        target_product = None
        competitor_prices = []

        # Wave3: per-store creds ile siparişleri çek (env DEĞİL), sayfalama yapısını koru
        _all_orders = fetch_orders(creds, max_pages=5)
        page = 0
        size = 200
        max_pages = 5

        while page < max_pages:
            orders = _all_orders[page * size:(page + 1) * size]

            if not orders:
                break

            try:
                for order in orders:
                    lines = order.get("lines", [])
                    if not lines:
                        continue
                    
                    for line in lines:
                        # Farklı alan adlarını kontrol et
                        line_product_id = (
                            str(line.get("productId") or "") or
                            str(line.get("product_id") or "") or
                            str(line.get("productCode") or "") or
                            ""
                        )
                        
                        # Ürün ID eşleşmesi
                        if line_product_id == str(product_id):
                            if not target_product:
                                product_name = (
                                    line.get("productName") or
                                    line.get("product_name") or
                                    line.get("name") or
                                    "Bilinmeyen Ürün"
                                )
                                price = line.get("price") or line.get("salePrice") or 0
                                if isinstance(price, str):
                                    try:
                                        price = float(price.replace(",", "."))
                                    except:
                                        price = 0
                                
                                target_product = {
                                    "id": product_id,
                                    "name": product_name,
                                    "price": float(price) if price else 0,
                                    "category": (
                                        line.get("categoryName") or
                                        line.get("category_name") or
                                        line.get("category") or
                                        ""
                                    )
                                }
                            
                            # Aynı ürün için fiyatları topla (rakip analizi için)
                            price = line.get("price") or 0
                            if isinstance(price, str):
                                try:
                                    price = float(price.replace(",", "."))
                                except:
                                    price = 0
                            if price and price > 0:
                                competitor_prices.append(float(price))
                        
                        # Benzer ürün isimleri için de fiyat topla (rakip analizi)
                        elif target_product:
                            line_product_name = (
                                line.get("productName") or
                                line.get("product_name") or
                                line.get("name") or
                                ""
                            )
                            if target_product["name"].lower() in line_product_name.lower() or line_product_name.lower() in target_product["name"].lower():
                                price = line.get("price") or 0
                                if isinstance(price, str):
                                    try:
                                        price = float(price.replace(",", "."))
                                    except:
                                        price = 0
                                if price and price > 0:
                                    competitor_prices.append(float(price))
                
                if len(orders) < size:
                    break
                
                page += 1
            except Exception as e:
                print(f"Sipariş sayfası {page} işlenirken hata: {str(e)}")
                break
        
        if not target_product:
            raise HTTPException(
                status_code=404,
                detail=f"Ürün bulunamadı (ID: {product_id}). Siparişlerde bu ürün bulunamadı."
            )
        
        product_name = target_product.get("name", "Bilinmeyen Ürün")
        current_price = target_product.get("price", 0)
        category = target_product.get("category", "")
        
        # Eğer rakip fiyat yoksa, mevcut fiyatı kullan
        if not competitor_prices:
            competitor_prices = [current_price] if current_price > 0 else [100.0]  # Varsayılan
        
        # Benzersiz fiyatları al
        competitor_prices = list(set(competitor_prices))
        
        min_price = min(competitor_prices)
        max_price = max(competitor_prices)
        avg_price = sum(competitor_prices) / len(competitor_prices)
        
        # Altın oran fiyatı hesapla
        golden_ratio_price = calculate_golden_ratio_price(min_price, max_price)
        
        # Psikolojik fiyatlar
        psychological_prices = generate_psychological_prices(golden_ratio_price)
        
        # Önerilen fiyat (altın oran fiyatı)
        recommended_price = golden_ratio_price
        
        # Kâr marjı hesapla (varsayılan maliyet %60'ı)
        estimated_cost = recommended_price * 0.6
        profit_margin = ((recommended_price - estimated_cost) / recommended_price) * 100 if recommended_price > 0 else 0
        
        reasoning = f"""
        Trendyol'da aktif satış yapan satıcılar analiz edildi.
        - En düşük fiyat: {min_price:.2f} TL
        - En yüksek fiyat: {max_price:.2f} TL
        - Ortalama fiyat: {avg_price:.2f} TL
        - Altın oran fiyatı: {golden_ratio_price:.2f} TL
        
        Altın oran fiyatı, psikolojik olarak en çekici fiyat noktasıdır ve 
        rekabetçi bir konumda olmanızı sağlar.
        """
        
        return {
            "product_id": product_id,
            "product_name": product_name,
            "current_price": current_price,
            "recommended_price": round(recommended_price, 2),
            "golden_ratio_price": round(golden_ratio_price, 2),
            "price_range": {
                "min": round(min_price, 2),
                "max": round(max_price, 2),
                "average": round(avg_price, 2)
            },
            "psychological_prices": [round(p, 2) for p in psychological_prices],
            "profit_margin": round(profit_margin, 2),
            "reasoning": reasoning.strip(),
            "competitor_count": len(competitor_prices),
            "category": category
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Ürün analizi hatası: {error_detail}")
        raise HTTPException(
            status_code=500,
            detail=f"Ürün analizi hatası: {str(e)}"
        )


@router.post("/recommend", response_model=PricingResponse)
async def recommend_price(request: PricingRequest):
    """
    AI destekli fiyat önerisi yapar.
    Altın oran ve psikolojik fiyatlandırma tekniklerini kullanır.
    """
    try:
        # Temel fiyat hesaplama (maliyet + kâr marjı)
        base_price = request.cost_price * (1 + request.target_profit_margin)
        
        # Rakip analizi
        competitor_data = None
        if request.competitor_analysis:
            competitor_data = await analyze_competitors(
                request.product_name,
                request.product_category
            )
            
            # Rekabetçi fiyat aralığı
            min_competitive = competitor_data.get("min_price", base_price * 0.8)
            max_competitive = competitor_data.get("max_price", base_price * 1.5)
            
            # Altın oran fiyatı hesapla
            golden_price = calculate_golden_ratio_price(min_competitive, max_competitive)
        else:
            # Rakip analizi yoksa, maliyet bazlı aralık
            min_competitive = base_price * 0.9
            max_competitive = base_price * 1.3
            golden_price = calculate_golden_ratio_price(min_competitive, max_competitive)
        
        # Önerilen fiyat: Altın oran fiyatı veya rekabetçi ortalama
        if competitor_data:
            recommended = min(
                golden_price,
                competitor_data.get("average_price", base_price)
            )
        else:
            recommended = golden_price
        
        # Psikolojik fiyatlar
        psychological_prices = generate_psychological_prices(recommended)
        
        # Kâr marjı hesapla
        actual_margin = (recommended - request.cost_price) / request.cost_price
        
        # AI önerisi
        reasoning = await get_ai_pricing_advice(
            request.product_name,
            request.cost_price,
            competitor_data or {},
            request.target_profit_margin
        )
        
        return PricingResponse(
            recommended_price=round(recommended, 2),
            price_range={
                "min": round(min_competitive, 2),
                "max": round(max_competitive, 2),
                "optimal": round(golden_price, 2)
            },
            psychological_prices=psychological_prices,
            competitor_analysis=competitor_data,
            profit_margin=round(actual_margin * 100, 2),
            reasoning=reasoning,
            golden_ratio_price=round(golden_price, 2)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fiyat önerisi hatası: {str(e)}")


@router.get("/test")
async def test_pricing():
    """Test endpoint"""
    test_request = PricingRequest(
        product_name="Bluetooth Kulaklık",
        product_category="Elektronik",
        cost_price=50.0,
        target_profit_margin=0.40,
        competitor_analysis=True
    )
    
    return await recommend_price(test_request)


# ---------------------------------------------------------------------------
# Wave2a — Ürün Fiyatlandırma sayfası: deterministik hesap makinesi (AI YOK,
# yukarıdaki /recommend'den farklı — bkz. utils/pricing_calc.py formül notu)
# ---------------------------------------------------------------------------
class PriceCalculatorRequest(BaseModel):
    product_id: Optional[str] = None  # verilirse cost/category DB'den otomatik doldurulur
    cost: Optional[float] = None
    cargo_cost: Optional[float] = None  # verilmezse financial.py'nin varsayılan değeri kullanılır
    category: Optional[str] = None
    commission_rate: Optional[float] = None  # ORAN (fraction, ör. %12 için 0.12) — verilirse "özel komisyon oranı" olarak category tabanlı hesaplamayı ezer
    vat_rate: Optional[float] = None  # ORAN (fraction) olarak, ör. %20 için 0.20 (financial.VAT_RATE ile aynı konvansiyon; verilmezse global VAT_RATE kullanılır)
    target_mode: str = "percent"  # "amount" (₺) | "percent" (%)
    target_value: float = 30.0  # target_mode=percent iken varsayılan %30 hedef marj


@router.post("/calculate")
async def calculate_price(
    request: PriceCalculatorRequest,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Maliyet + istenen kâr + kargo + KDV + komisyon → önerilen satış fiyatı."""
    from routers import financial as financial_module

    cost = request.cost
    category = request.category
    cargo_cost = request.cargo_cost if request.cargo_cost is not None else financial_module.CARGO_COST_PER_PRODUCT

    if request.product_id:
        product = db.query(Product).filter(Product.store_id == store.id, Product.product_id == request.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Ürün bulunamadı")
        if cost is None:
            cost = product.default_cost
        if category is None:
            category = product.category

    if cost is None:
        raise HTTPException(status_code=400, detail="cost veya product_id (maliyeti girilmiş bir ürün) gerekli")

    vat_rate = request.vat_rate  # zaten fraction (ör. 0.20) — financial.VAT_RATE konvansiyonuyla birebir

    result = calculate_suggested_price(
        cost=cost,
        cargo_cost=cargo_cost,
        category=category,
        target_mode=request.target_mode,
        target_value=request.target_value,
        vat_rate=vat_rate,
        commission_rate=request.commission_rate,
    )
    if result is None:
        raise HTTPException(
            status_code=400,
            detail="Hesaplanamadı — hedef kâr oranı + KDV + komisyon oranı toplamı %100'ü geçiyor olabilir, değerleri kontrol edin",
        )
    return result


# ---------------------------------------------------------------------------
# w3-price-writeback-preview — Dilim 1: PROVA (salt okuma). Spec: hive/docs/
# price-writeback-spec.md. Trendyol'a HİÇBİR çağrı yok, yerel DB'ye HİÇBİR
# yazma yok — calculate_suggested_price() zaten var olan saf hesaplama
# fonksiyonu, sadece store'un TÜM uygun ürünlerine uygulanıp SONUÇ DÖNÜYOR.
# Dilim 2 (gerçek Trendyol yazma) bu kartta YOK, sadece spec'te planlandı.
# ---------------------------------------------------------------------------
@router.get("/writeback-preview")
async def price_writeback_preview(
    target_mode: str,  # "amount" (₺) | "percent" (%)
    target_value: float,
    product_ids: Optional[str] = None,  # virgülle ayrılmış, verilmezse maliyeti olan TÜM ürünler
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Store'un ürünleri için önerilen fiyatı hesaplayıp mevcut fiyatla karşılaştırır.
    SALT OKUMA: ne Trendyol'a ne yerel DB'ye hiçbir yazma yapmaz."""
    from routers import financial as financial_module

    query = db.query(Product).filter(Product.store_id == store.id)
    if product_ids:
        ids = [p.strip() for p in product_ids.split(",") if p.strip()]
        query = query.filter(Product.product_id.in_(ids))
    products = query.all()

    if target_mode == "amount":
        reason = f"Hedef kâr tutarı: ₺{target_value:g}"
    elif target_mode == "percent":
        reason = f"Hedef kâr oranı: %{target_value:g}"
    else:
        raise HTTPException(status_code=400, detail="target_mode 'amount' veya 'percent' olmalı")

    preview = []
    skipped = []
    for product in products:
        if not product.default_cost or product.default_cost <= 0:
            skipped.append({"product_id": product.product_id, "reason": "maliyet girilmemiş (default_cost=0)"})
            continue

        result = calculate_suggested_price(
            cost=product.default_cost,
            cargo_cost=financial_module.CARGO_COST_PER_PRODUCT,
            category=product.category,
            target_mode=target_mode,
            target_value=target_value,
        )
        if result is None:
            skipped.append({
                "product_id": product.product_id,
                "reason": "hesaplanamadı (hedef oran + KDV + komisyon toplamı %100'ü geçiyor olabilir)",
            })
            continue

        current_price = product.current_price or 0.0
        suggested_price = result["suggested_price"]
        preview.append({
            "product_id": product.product_id,
            "product_name": product.product_name,
            "current_price": round(current_price, 2),
            "suggested_price": suggested_price,
            "diff": round(suggested_price - current_price, 2),
            "diff_percent": round((suggested_price - current_price) / current_price * 100, 2) if current_price > 0 else None,
            "reason": reason,
        })

    return {
        "preview": preview,
        "count": len(preview),
        "skipped": skipped,
        "skipped_count": len(skipped),
    }


