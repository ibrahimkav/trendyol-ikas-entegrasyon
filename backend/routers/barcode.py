"""
Barkod Sistemi Router
Akıllı barkod oluşturma ve okuma işlemleri
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
import qrcode
import barcode
from barcode.writer import ImageWriter
from io import BytesIO, StringIO
import base64
import json
from PIL import Image, ImageDraw, ImageFont
import os
import uuid
import csv
import io
from fastapi.responses import StreamingResponse

router = APIRouter()

# Database modülünü optional olarak yükle
_db_available = False
try:
    from database.db import get_db, init_db
    from database.models import BarcodeHistory, BarcodeTemplate, Store
    from security import get_current_store
    # Database'i başlat
    try:
        init_db()
        _db_available = True
        print("[Barcode] Database initialized successfully")
    except Exception as db_init_error:
        print(f"[Barcode] Database initialization warning: {db_init_error}")
        # Database modülü mevcut ama başlatılamadı, yine de kullanmayı dene
        _db_available = True
except Exception as import_error:
    print(f"[Barcode] Database module not available (ghost mode): {import_error}")
    pass


def _check_db():
    """Database kontrolü"""
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")


def _format_trendyol_date(raw) -> str:
    """Ham Trendyol tarih değerini (epoch-ms int veya ISO string) okunabilir formata çevirir.
    w3-backend-cleanup Madde 3: önceden ham epoch-ms int JSON'a olduğu gibi yazılıyordu."""
    if not raw:
        return ""
    try:
        if isinstance(raw, (int, float)):
            ts = float(raw)
            if ts > 1e12:
                ts = ts / 1000
            dt = datetime.fromtimestamp(ts)
        elif isinstance(raw, str):
            if 'T' in raw:
                dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
                if dt.tzinfo:
                    dt = dt.replace(tzinfo=None)
            else:
                dt = datetime.strptime(raw, "%Y-%m-%d")
        else:
            return str(raw)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(raw)


def _extract_dsmcdn_urls_from_json(obj: Any, depth: int = 0, out: Optional[set] = None) -> List[str]:
    """Trendyol discovery/public API yanıtındaki tüm cdn.dsmcdn.com adreslerini toplar."""
    if out is None:
        out = set()
    if depth > 10:
        return list(out)
    if isinstance(obj, str):
        s = obj.strip()
        if s.startswith("http") and "cdn.dsmcdn.com" in s:
            out.add(s.split("?")[0])
    elif isinstance(obj, dict):
        for v in obj.values():
            _extract_dsmcdn_urls_from_json(v, depth + 1, out)
    elif isinstance(obj, list):
        for v in obj:
            _extract_dsmcdn_urls_from_json(v, depth + 1, out)
    return list(out)


def _cdn_urls_for_trendyol_content_id(content_id: Any) -> List[str]:
    """contentId sayısal ise yaygın mnresize şablonları (sipariş API görsel döndürmezse)."""
    if content_id is None:
        return []
    cid = str(content_id).strip()
    if not cid.isdigit():
        return []
    return [
        f"https://cdn.dsmcdn.com/mnresize/800/800/ty{cid}.jpg",
        f"https://cdn.dsmcdn.com/mnresize/500/500/ty{cid}.jpg",
        f"https://cdn.dsmcdn.com/mnresize/1200/1200/ty{cid}.jpg",
        f"https://cdn.dsmcdn.com/mnresize/800/800/ty{cid}.webp",
    ]


class OrderItem(BaseModel):
    """Sipariş ürünü modeli"""
    product_id: str
    product_name: str
    quantity: int
    price: float
    sku: Optional[str] = None


class BarcodeRequest(BaseModel):
    """Barkod oluşturma isteği"""
    order_id: str
    items: List[OrderItem]
    shipping_info: Optional[dict] = None
    discount_code: Optional[str] = "TRENDYOL15"  # Varsayılan indirim kodu


class ScanOrderRequest(BaseModel):
    """Barkod okuma isteği"""
    barcode_data: Optional[str] = None
    barcode: Optional[str] = None  # Alternatif alan adı


class BarcodeResponse(BaseModel):
    """Barkod oluşturma yanıtı"""
    barcode_image: str  # Base64 encoded image
    barcode_data: str  # Barkod içindeki veri
    qr_code_image: str  # QR kod görseli
    shipping_label: Optional[str] = None  # Kargo etiketi üzerine yapıştırılacak etiket (base64)
    order_summary: dict


def create_smart_barcode_data(order_id: str, items: List[OrderItem], discount_code: str = None) -> str:
    """
    Akıllı barkod verisi oluşturur.
    Sipariş ID, ürün sayısı, ürün bilgileri ve indirim kodu içerir.
    """
    total_items = sum(item.quantity for item in items)
    
    barcode_data = {
        "order_id": order_id,
        "total_items": total_items,
        "item_count": len(items),
        "items": [
            {
                "product_id": item.product_id,
                "sku": item.sku,
                "quantity": item.quantity,
                "name": item.product_name[:50]  # Kısa isim
            }
            for item in items
        ],
        "discount": {
            "website": "penaltidenim.com",
            "code": discount_code or "TRENDYOL15",
            "percentage": 15
        },
        "format": "v2"
    }
    
    # JSON string'e çevir ve optimize et
    json_str = json.dumps(barcode_data, separators=(',', ':'))
    return json_str


def generate_qr_code(data: str) -> str:
    """QR kod oluşturur ve base64 string döner"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"


def generate_barcode(data: str) -> str:
    """Code128 barkod oluşturur ve base64 string döner"""
    try:
        # Code128 formatında barkod oluştur
        code128 = barcode.get_barcode_class('code128')
        barcode_instance = code128(data, writer=ImageWriter())
        
        buffer = BytesIO()
        barcode_instance.write(buffer)
        buffer.seek(0)
        
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        # Eğer barkod çok uzunsa, sadece QR kod kullan
        return None


def combine_trendyol_label_with_custom(
    trendyol_label_bytes: Optional[bytes],
    custom_sticker_img: Image.Image
) -> Image.Image:
    """
    Trendyol kargo etiketi ile özel etiketi birleştirir
    
    Args:
        trendyol_label_bytes: Trendyol'dan gelen kargo etiketi (bytes)
        custom_sticker_img: Özel etiket görseli (PIL Image)
    
    Returns:
        Birleştirilmiş görsel (PIL Image)
    """
    try:
        if trendyol_label_bytes:
            # Trendyol etiketini yükle
            from io import BytesIO
            trendyol_buffer = BytesIO(trendyol_label_bytes)
            trendyol_img = Image.open(trendyol_buffer)
            
            # RGBA ise RGB'ye çevir
            if trendyol_img.mode == 'RGBA':
                trendyol_rgb = Image.new('RGB', trendyol_img.size, 'white')
                trendyol_rgb.paste(trendyol_img, mask=trendyol_img.split()[3] if len(trendyol_img.split()) == 4 else None)
                trendyol_img = trendyol_rgb
            elif trendyol_img.mode != 'RGB':
                trendyol_img = trendyol_img.convert('RGB')
            
            # Trendyol etiketinin genişliğine göre özel etiketi ölçekle
            trendyol_width = trendyol_img.width
            custom_width = custom_sticker_img.width
            
            if custom_width > trendyol_width:
                # Özel etiketi Trendyol etiketinin genişliğine sığdır
                scale_factor = trendyol_width / custom_width
                new_custom_height = int(custom_sticker_img.height * scale_factor)
                custom_sticker_img = custom_sticker_img.resize((trendyol_width, new_custom_height), Image.Resampling.LANCZOS)
            
            # Birleştirilmiş görsel oluştur (Trendyol üstte, özel etiket altta)
            combined_height = trendyol_img.height + custom_sticker_img.height
            combined_img = Image.new('RGB', (trendyol_width, combined_height), 'white')
            
            # Trendyol etiketini üste ekle
            combined_img.paste(trendyol_img, (0, 0))
            
            # Özel etiketi alta ekle
            combined_img.paste(custom_sticker_img, (0, trendyol_img.height))
            
            return combined_img
        else:
            # Trendyol etiketi yoksa sadece özel etiketi döndür
            return custom_sticker_img
            
    except Exception as e:
        print(f"Etiket birleştirme hatası: {str(e)}")
        # Hata durumunda sadece özel etiketi döndür
        return custom_sticker_img


def _load_bold_font(size: int):
    """Kalın font yükle (Windows Arial Bold → Linux DejaVu/Liberation → default)."""
    for name in (
        "arialbd.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _brand_ribbon_strip(length: int, band: int, text: str = "PENALTI DENİM") -> Image.Image:
    """Yatay bir marka şeridi: 'PENALTI DENİM • PENALTI DENİM • ...'
    Tekrar sayısı şeride sığacak kadar seçilir ve aralar eşit dağıtılır (iki uç simetrik)."""
    strip = Image.new('RGB', (max(length, 1), band), 'white')
    d = ImageDraw.Draw(strip)
    font_size = max(int(band * 0.62), 8)
    font = _load_bold_font(font_size)
    unit_w = d.textlength(text, font=font)
    min_gap = font_size * 1.4  # ayraç (•) + nefes payı
    count = max(1, int((length + min_gap) // (unit_w + min_gap)))
    # Tek kelime bile sığmıyorsa fontu küçült
    while count == 1 and unit_w > length - 4 and font_size > 8:
        font_size -= 1
        font = _load_bold_font(font_size)
        unit_w = d.textlength(text, font=font)
    slot = length / count
    bbox = d.textbbox((0, 0), text, font=font)
    text_y = (band - (bbox[3] - bbox[1])) / 2 - bbox[1]
    dot_r = max(band // 9, 2)
    for i in range(count):
        x = i * slot + (slot - unit_w) / 2
        d.text((x, text_y), text, fill='black', font=font)
        if i > 0:  # birimler arasına ayraç nokta
            cx, cy = i * slot, band / 2
            d.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill='black')
    return strip


def _frame_with_brand_ribbon(content: Image.Image, band: int = 26, inner_pad: int = 12) -> Image.Image:
    """İçeriği (dikey kargo barkodu) saat yönünde dönen bir 'PENALTI DENİM •' yazı
    şeridiyle çerçeveler: üst soldan sağa, sağ yukarıdan aşağı, alt sağdan sola,
    sol aşağıdan yukarı okunur. Köşelerde dolu kare süs, dış ve iç ince çizgi."""
    cw, ch = content.size
    inner_w = cw + inner_pad * 2
    inner_h = ch + inner_pad * 2
    W, H = inner_w + band * 2, inner_h + band * 2
    framed = Image.new('RGB', (W, H), 'white')
    framed.paste(content, (band + inner_pad, band + inner_pad))

    top = _brand_ribbon_strip(inner_w, band)
    side = _brand_ribbon_strip(inner_h, band)
    framed.paste(top, (band, 0))                                   # üst: soldan sağa
    framed.paste(side.rotate(-90, expand=True), (band + inner_w, band))  # sağ: yukarıdan aşağı
    framed.paste(top.rotate(180), (band, band + inner_h))          # alt: sağdan sola
    framed.paste(side.rotate(90, expand=True), (0, band))          # sol: aşağıdan yukarı

    fd = ImageDraw.Draw(framed)
    fd.rectangle([(0, 0), (W - 1, H - 1)], outline='black', width=3)  # dış çerçeve
    fd.rectangle([(band, band), (band + inner_w - 1, band + inner_h - 1)], outline='black', width=2)  # iç çerçeve
    # Köşe süsleri: dolu kare + ortasında beyaz elmas
    for cx, cy in ((0, 0), (W - band, 0), (0, H - band), (W - band, H - band)):
        fd.rectangle([(cx, cy), (cx + band - 1, cy + band - 1)], fill='black')
        m, r = band / 2, band / 4
        fd.polygon([(cx + m, cy + m - r), (cx + m + r, cy + m), (cx + m, cy + m + r), (cx + m - r, cy + m)], fill='white')
    return framed


def generate_shipping_label_sticker(
    order_id: str,
    items: List[OrderItem],
    discount_code: str = "TRENDYOL15",
    cargo_barcode: Optional[str] = None,
    combine_with_trendyol: bool = False,
    trendyol_label_bytes: Optional[bytes] = None,
    order_info: Optional[dict] = None  # Trendyol sipariş bilgileri
) -> str:
    """
    Kargo etiketinin ALTINA yapıştırılacak küçük etiket oluşturur.
    Ürün listesi ve indirim bilgisi içerir. Web sitesine yönlendiren QR kod ekler.
    """
    try:
        # Etiket boyutları - Argox X-1000VL için 100x100mm (kare) standart
        # 203 DPI (Argox standart)
        dpi = 203  # Argox yazıcı standart DPI
        # 100mm = 3.937 inç, 203 DPI'da = 800 px
        width = int(3.937 * dpi)  # 100mm = 800 px @ 203 DPI
        height = int(3.937 * dpi)  # 100mm = 800 px @ 203 DPI (kare etiket)
        
        # Beyaz arka plan
        img = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(img)
        
        # Font'lar - Argox X-1000VL 100x100mm için optimize edilmiş boyutlar (daha büyük)
        try:
            # Windows'ta farklı font'lar deneyelim - 100x100mm için daha büyük fontlar
            try:
                title_font = ImageFont.truetype("arial.ttf", 36)
                header_font = ImageFont.truetype("arial.ttf", 28)
                text_font = ImageFont.truetype("arial.ttf", 24)  # Ürün bilgileri için daha büyük
                small_font = ImageFont.truetype("arial.ttf", 18)
                tiny_font = ImageFont.truetype("arial.ttf", 16)
            except:
                try:
                    title_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 36)
                    header_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 28)
                    text_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 24)  # Ürün bilgileri için daha büyük
                    small_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 18)
                    tiny_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 16)
                except:
                    # Font bulunamazsa default kullan
                    title_font = ImageFont.load_default()
                    header_font = ImageFont.load_default()
                    text_font = ImageFont.load_default()
                    small_font = ImageFont.load_default()
                    tiny_font = ImageFont.load_default()
        except:
            # Fallback: default font'lar
            title_font = ImageFont.load_default()
            header_font = ImageFont.load_default()
            text_font = ImageFont.load_default()
            small_font = ImageFont.load_default()
            tiny_font = ImageFont.load_default()
        
        y_position = 20
        padding = 25
        # Sağ tarafta dikey barkod için alan ayır (100x100mm için optimize)
        right_barcode_area = 200  # Sağ tarafta dikey barkod için ayrılan alan (kare + padding dahil)
        left_content_width = width - right_barcode_area - padding  # Sol içerik için maksimum genişlik

        def _clamp_to_width(text: str, font, max_width: int) -> str:
            """Tek satırı ÖLÇÜLEN genişliğe göre kısalt (sabit karakter sayısı DEĞİL).
            Sığmıyorsa '…' ile biter; kutu/satır sınırını asla aşmaz."""
            if draw.textlength(text, font=font) <= max_width:
                return text
            clamped = text
            while len(clamped) > 1 and draw.textlength(clamped + '…', font=font) > max_width:
                clamped = clamped[:-1]
            return clamped.rstrip() + '…'
        
        # Sağ köşede dikey kargo barkodu (barkod cihazı için - uzunlamasına dikey, ortalı)
        if cargo_barcode:
            cargo_barcode_str = str(cargo_barcode).strip()
            try:
                # Yatay barkod oluştur (sonra dikey yapacağız)
                code128 = barcode.get_barcode_class('code128')
                writer = ImageWriter()
                barcode_instance = code128(cargo_barcode_str, writer=writer)
                
                barcode_buffer = BytesIO()
                try:
                    barcode_instance.write(barcode_buffer, options={'write_text': False})
                except:
                    barcode_instance.write(barcode_buffer)
                barcode_buffer.seek(0)
                horizontal_barcode_img = Image.open(barcode_buffer)
                
                # Barkod görselinden metin kısmını kaldır
                if horizontal_barcode_img.height > 0:
                    estimated_text_height = int(horizontal_barcode_img.height * 0.30)
                    barcode_only_height = horizontal_barcode_img.height - estimated_text_height
                    if barcode_only_height < 50:
                        barcode_only_height = int(horizontal_barcode_img.height * 0.70)
                    horizontal_barcode_img = horizontal_barcode_img.crop((0, 0, horizontal_barcode_img.width, barcode_only_height))
                
                # Uzunlamasına dikey barkod boyutları (100x100mm için optimize)
                # Genişlik: barkod çizgilerinin genişliği
                # Yükseklik: barkod çizgilerinin uzunluğu (etiket yüksekliğine uygun)
                vertical_barcode_width = 120  # Dikey genişlik (100x100mm için optimize)
                # Yüksekliği etiket yüksekliğine göre ayarla (üst ve alt padding için alan bırak)
                max_vertical_height = height - 80  # Üst ve alt için 80px boşluk
                vertical_barcode_height = min(450, max_vertical_height)  # Maksimum 450px veya etiket yüksekliğine göre
                
                # Önce boyutlandır, sonra döndür (uzunlamasına dikey için)
                horizontal_barcode_img = horizontal_barcode_img.resize((vertical_barcode_height, vertical_barcode_width), Image.Resampling.LANCZOS)
                
                # Barkodu 90 derece saat yönü tersi döndür (uzunlamasına dikey - çizgiler dikey olacak)
                vertical_barcode_img = horizontal_barcode_img.rotate(-90, expand=True)
                
                # RGB'ye çevir
                if vertical_barcode_img.mode == 'RGBA':
                    barcode_rgb = Image.new('RGB', vertical_barcode_img.size, 'white')
                    barcode_rgb.paste(vertical_barcode_img, mask=vertical_barcode_img.split()[3] if len(vertical_barcode_img.split()) == 4 else None)
                    vertical_barcode_img = barcode_rgb
                elif vertical_barcode_img.mode != 'RGB':
                    vertical_barcode_img = vertical_barcode_img.convert('RGB')
                
                # Barkodun etrafına "PENALTI DENİM •" yazılı marka şeridi çerçeve
                square_img = _frame_with_brand_ribbon(vertical_barcode_img)
                square_width, square_height = square_img.size

                # Sağ köşeye ortalı bir şekilde yerleştir (100x100mm için optimize)
                square_x = width - square_width - 16  # Sağdan 16px içeride
                square_y = (height - square_height) // 2  # Dikey olarak tam ortada
                # Eğer üst veya alt taşıyorsa, içeride tut
                if square_y < 20:
                    square_y = 20
                if square_y + square_height > height - 20:
                    square_y = height - square_height - 20
                img.paste(square_img, (square_x, square_y))
                
                # Sol içerik genişliğini dikey barkodun konumuna göre güncelle (çakışmayı önlemek için)
                left_content_width = min(left_content_width, square_x - padding - 30)  # Dikey barkodun solundan 30px önce bit
                
                # Numara yazılmayacak - sadece barkod (kare içinde)
                
            except Exception as e:
                import sys
                print(f"Dikey kargo barkodu oluşturma hatası: {str(e)}", file=sys.stderr)
        
        # Üst kısım: Sipariş bilgisi (büyük ve belirgin)
        draw.text((padding, y_position), f"Sipariş No: {order_id}", fill='black', font=header_font)
        y_position += 36  # header_font(28) altına nefes payı — alttaki alıcı kutusuyla çakışmayı önler
        
        # Alıcı bilgileri (varsa) - Kutu içinde
        if order_info:
            # Alıcı adı
            customer_name = (
                order_info.get("shipmentAddress", {}).get("fullName") or
                order_info.get("customerFirstName") or
                order_info.get("customerName") or
                None
            )
            if customer_name:
                # Alıcı adı kutusu (100x100mm için optimize) — kutu yüksekliği header_font(28)
                # yazıyı içine tam alacak şekilde; uzun isim kutu genişliğine göre kısaltılır.
                customer_box_y = y_position
                customer_box_height = 42
                draw.rectangle(
                    [(padding, customer_box_y), (left_content_width, customer_box_y + customer_box_height)],
                    outline='black',
                    width=2
                )
                customer_text = customer_name.upper()
                max_name_width = left_content_width - padding - 16
                while len(customer_text) > 4 and draw.textlength(customer_text, font=header_font) > max_name_width:
                    customer_text = customer_text[:-1]
                if customer_text != customer_name.upper():
                    customer_text = customer_text.rstrip() + '…'
                draw.text((padding + 10, customer_box_y + 8), customer_text, fill='black', font=header_font)
                y_position += customer_box_height + 12
            
            # Adres bilgileri - Kutu içinde (Trendyol gibi)
            address = order_info.get("shipmentAddress", {})
            if address:
                addr_line1 = address.get("address1") or address.get("address")
                addr_line2 = address.get("address2")
                district = address.get("district") or address.get("neighborhood")
                city = address.get("city")
                province = address.get("province") or address.get("cityName")
                if city and province:
                    city_line = f"{city.upper()} / {province.upper()}"
                elif city:
                    city_line = city.upper()
                elif province:
                    city_line = province.upper()
                else:
                    city_line = None

                # adres2 en düşük öncelikli — yer darsa önce O düşer, ilçe/şehir her zaman kalır
                required_segments = [s.upper() for s in (addr_line1, district, city_line) if s]
                optional_segment = addr_line2.upper() if addr_line2 else None

                if required_segments or optional_segment:
                    # ÖLÇÜLEN GENİŞLİĞE göre kelime sarma (sabit karakter kesmesi DEĞİL).
                    # Kelime sınırından sarar; tek kelime bile sığmıyorsa karakter karakter böler.
                    max_addr_width = left_content_width - padding - 16

                    def _wrap_line(text, font):
                        words = text.split(' ')
                        lines, current = [], ''
                        for word in words:
                            candidate = f"{current} {word}".strip()
                            if current and draw.textlength(candidate, font=font) > max_addr_width:
                                lines.append(current)
                                current = word
                                while draw.textlength(current, font=font) > max_addr_width and len(current) > 1:
                                    cut = len(current)
                                    while cut > 1 and draw.textlength(current[:cut], font=font) > max_addr_width:
                                        cut -= 1
                                    lines.append(current[:cut])
                                    current = current[cut:]
                            else:
                                current = candidate
                        if current:
                            lines.append(current)
                        return lines or ['']

                    def _wrap_segments(segments, font):
                        wrapped = []
                        for seg in segments:
                            wrapped.extend(_wrap_line(seg, font))
                        return wrapped

                    # Alttaki kargo barkod alanına asla taşmaması için sabit üst sınır (satır sayısı).
                    MAX_ADDRESS_LINES = 4

                    # Sırayla dene: (a) tam içerik normal font, (b) adres2 düşür (ilçe/şehir korunur),
                    # (c) tam içerik küçük font, (d) adres2 düşür + küçük font.
                    candidates = []
                    if optional_segment:
                        candidates.append((required_segments + [optional_segment], small_font, 20))
                    candidates.append((required_segments, small_font, 20))
                    if optional_segment:
                        candidates.append((required_segments + [optional_segment], tiny_font, 18))
                    candidates.append((required_segments, tiny_font, 18))

                    address_display_lines = None
                    address_font, line_height = small_font, 20
                    for segs, font, lh in candidates:
                        wrapped = _wrap_segments(segs, font)
                        if len(wrapped) <= MAX_ADDRESS_LINES:
                            address_display_lines, address_font, line_height = wrapped, font, lh
                            break

                    if address_display_lines is None:
                        # Hiçbiri sığmadı — SERT GARANTİ: sabit satır sınırına kırp, son satır '…' ile
                        # biter. Barkod alanına asla taşmaz.
                        address_font, line_height = tiny_font, 18
                        wrapped = _wrap_segments(required_segments, address_font) or ['']
                        address_display_lines = wrapped[:MAX_ADDRESS_LINES]
                        last = address_display_lines[-1]
                        while len(last) > 1 and draw.textlength(last + '…', font=address_font) > max_addr_width:
                            last = last[:-1]
                        address_display_lines[-1] = last.rstrip() + '…'

                    # Adres kutusu — yükseklik GERÇEKTEN ÇİZİLEN satır sayısından hesaplanır
                    # (önceki bug: tüm ham segment sayısından hesaplanıyordu, ama sadece ilk 3'ü
                    # çiziliyordu — kutu gereğinden uzun olup y_position'ı fazladan aşağı itiyordu).
                    address_box_y = y_position
                    address_box_height = len(address_display_lines) * line_height + 12
                    draw.rectangle(
                        [(padding, address_box_y), (left_content_width, address_box_y + address_box_height)],
                        outline='black',
                        width=2
                    )

                    addr_y = address_box_y + 8
                    for addr_line in address_display_lines:
                        draw.text((padding + 8, addr_y), addr_line, fill='black', font=address_font)
                        addr_y += line_height

                    y_position += address_box_height + 10
        
        # Kargo firması bilgisi artık barkodun üstünde gösterilecek (kaldırıldı)
        
        # Çizgi (sol içerik alanında)
        draw.line([(padding, y_position), (left_content_width, y_position)], fill='black', width=2)
        y_position += 12
        
        # Kargo firması bilgisi (varsa) - Barkodun üstüne, belirgin
        # Trendyol API'den gelen farklı alanları kontrol et
        cargo_company = None
        if order_info:
            # Tüm olası alanları kontrol et (cargoProviderName öncelikli - Trendyol API'de bu alan var)
            cargo_company = (
                order_info.get("cargoProviderName") or  # Trendyol API'de bu alan mevcut!
                order_info.get("cargoCompany") or
                order_info.get("shipmentCompany") or
                order_info.get("cargoProvider") or
                order_info.get("cargoFirm") or
                order_info.get("cargoCompanyName") or
                order_info.get("shipmentCompanyName") or
                order_info.get("cargo") or
                (order_info.get("shipment", {}).get("cargoProviderName") if isinstance(order_info.get("shipment"), dict) else None) or
                (order_info.get("shipment", {}).get("cargoCompany") if isinstance(order_info.get("shipment"), dict) else None) or
                (order_info.get("shipment", {}).get("shipmentCompany") if isinstance(order_info.get("shipment"), dict) else None) or
                (order_info.get("shipment", {}).get("cargoProvider") if isinstance(order_info.get("shipment"), dict) else None) or
                (order_info.get("shipment", {}).get("cargoCompanyName") if isinstance(order_info.get("shipment"), dict) else None) or
                None
            )
            
        
        if cargo_company:
            # Kargo firması adını barkodun üstüne yaz — SAĞDAKİ dikey barkod alanına taşmayacak
            # şekilde: sığmazsa fontu kademeli küçült, o da yetmezse metni kısalt (…).
            cargo_text = f"KARGO: {str(cargo_company).upper()}"
            max_cargo_width = left_content_width - padding
            cargo_font = None
            for candidate in (header_font, text_font, small_font):
                if draw.textlength(cargo_text, font=candidate) <= max_cargo_width:
                    cargo_font = candidate
                    break
            if cargo_font is None:
                cargo_font = small_font
                while len(cargo_text) > 8 and draw.textlength(cargo_text + '…', font=cargo_font) > max_cargo_width:
                    cargo_text = cargo_text[:-1]
                cargo_text = cargo_text.rstrip() + '…'
            draw.text((padding, y_position), cargo_text, fill='black', font=cargo_font)
            y_position += 25
        else:
            # Eğer kargo firması bilgisi yoksa, varsayılan olarak "KARGO" yaz
            # Veya hiçbir şey yazma (kullanıcı tercihine göre)
            pass
        
        # Kargo barkodu (varsa) - Büyük ve merkezi (Trendyol gibi)
        if cargo_barcode:
            cargo_barcode_str = str(cargo_barcode).strip()
            
            # Barkod görseli oluştur (Code128) - tam numara ile
            try:
                code128 = barcode.get_barcode_class('code128')
                # ImageWriter - metin olmadan sadece barkod çizgileri
                writer = ImageWriter()
                # Barkod altındaki metni kaldırmak için options kullan
                barcode_instance = code128(cargo_barcode_str, writer=writer)
                
                # Barkod görselini geçici olarak kaydet
                barcode_buffer = BytesIO()
                # Options ile metni kaldırmayı dene
                try:
                    barcode_instance.write(barcode_buffer, options={'write_text': False})
                except:
                    # Options desteklenmiyorsa normal yaz
                    barcode_instance.write(barcode_buffer)
                barcode_buffer.seek(0)
                barcode_img = Image.open(barcode_buffer)
                
                # Barkod görselinden metin kısmını kaldır (crop)
                # Barkod çizgileri genellikle üst kısımda, metin alt kısımda
                if barcode_img.height > 0:
                    # Metin genellikle alt %25-30'da, sadece üst kısmı al
                    estimated_text_height = int(barcode_img.height * 0.30)  # Alt %30 metin alanı
                    barcode_only_height = barcode_img.height - estimated_text_height
                    # Minimum yükseklik garantile
                    if barcode_only_height < 50:
                        barcode_only_height = int(barcode_img.height * 0.70)  # En az %70'i barkod
                    # Sadece barkod çizgilerini al (üst kısım) - metin kısmını kes
                    barcode_img = barcode_img.crop((0, 0, barcode_img.width, barcode_only_height))
                
                # Barkod boyutunu ayarla (100x100mm için optimize)
                # Sol köşeye dayalı olarak yerleştirilecek, genişlik sınırlı
                barcode_width = min(left_content_width - padding, 500)  # 100x100mm için maksimum 500px genişlik
                original_width = barcode_img.width
                original_height = barcode_img.height
                if original_width > 0:
                    scale_factor = min(barcode_width / original_width, 1.0)
                    barcode_height = int(original_height * scale_factor)
                    # Minimum yükseklik
                    barcode_height = max(barcode_height, 120)  # 100x100mm için optimize
                else:
                    barcode_height = 120  # 100x100mm için optimize
                
                barcode_img = barcode_img.resize((barcode_width, barcode_height), Image.Resampling.LANCZOS)
                
                # Barkod görselini ekle (RGBA ise RGB'ye çevir)
                if barcode_img.mode == 'RGBA':
                    barcode_rgb = Image.new('RGB', barcode_img.size, 'white')
                    barcode_rgb.paste(barcode_img, mask=barcode_img.split()[3] if len(barcode_img.split()) == 4 else None)
                    barcode_img = barcode_rgb
                elif barcode_img.mode != 'RGB':
                    barcode_img = barcode_img.convert('RGB')
                
                # Barkod görselini ekle (merkeze)
                img.paste(barcode_img, (padding, y_position))
                
                # Barkod görselinin altına tam numarayı yazdır (büyük font, merkez)
                y_position += barcode_height + 6
                try:
                    num_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 18)
                except:
                    try:
                        num_font = ImageFont.truetype("arial.ttf", 18)
                    except:
                        num_font = small_font
                
                # Numara metnini ortalı hizala (barkodun altına, ortalı)
                num_text = cargo_barcode_str
                bbox = draw.textbbox((0, 0), num_text, font=num_font)
                text_width = bbox[2] - bbox[0]
                num_x = padding + (barcode_width - text_width) // 2
                draw.text((num_x, y_position), num_text, fill='black', font=num_font)
                y_position += 25
                
            except Exception as e:
                import sys
                print(f"Kargo barkodu oluşturma hatası: {str(e)}", file=sys.stderr)
                # Hata durumunda sadece numara göster
                draw.text((padding, y_position), f"Kargo: {cargo_barcode_str}", fill='black', font=text_font)
                y_position += 25
        
        # Ürün listesi (detaylı - 100x100mm için optimize, daha büyük ve okunur)
        draw.text((padding, y_position), "ÜRÜNLER:", fill='black', font=header_font)
        y_position += 24
        
        # Her ürünü detaylı göster (ad, barkod, adet) - daha büyük fontlarla
        # NOT: satır genişliği ÖLÇÜLEN piksel genişliğiyle kısaltılır (sabit karakter sayısı DEĞİL) —
        # aksi halde geniş karakterli uzun ürün adları sağdaki dikey barkod alanına taşabilir.
        max_product_width = left_content_width - (padding + 8) - 8
        max_detail_width = left_content_width - (padding + 12) - 8
        for idx, item in enumerate(items[:4], 1):  # 100x100mm için maksimum 4 ürün (daha büyük fontlar için)
            # Barkod/SKU bilgisi
            barcode_sku = item.sku or item.product_id or "Barkod yok"

            # Ürün satırı: "1. Ürün Adı" - daha büyük font
            product_line = _clamp_to_width(f"{idx}. {item.product_name}", text_font, max_product_width)
            draw.text((padding + 8, y_position), product_line, fill='black', font=text_font)
            y_position += 24

            # Barkod ve adet bilgisi (alt satır, biraz içeride) - daha büyük font
            detail_line = _clamp_to_width(
                f"   Barkod: {barcode_sku} | Adet: {item.quantity}", small_font, max_detail_width
            )
            draw.text((padding + 12, y_position), detail_line, fill='black', font=small_font)  # Siyah yapıldı, daha okunur
            y_position += 24
        
        if len(items) > 4:
            draw.text((padding + 8, y_position), f"... ve {len(items) - 4} ürün daha", fill='gray', font=small_font)
            y_position += 20
        
        y_position += 8
        
        # Alt kısım: Website bilgisi ve QR kod (100x100mm için optimize)
        website_url = f"https://penaltidenim.com?discount={discount_code}&ref=trendyol&order={order_id}"
        
        # QR kod ekle (daha büyük - 100x100mm için optimize)
        qr = qrcode.QRCode(version=1, box_size=5, border=2)  # box_size artırıldı, border artırıldı
        qr.add_data(website_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_size = 120  # QR kod büyütüldü (100x100mm için)
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
        
        # QR kod'u sol alt köşeye yerleştir
        qr_x = padding
        qr_y = height - qr_size - 30  # Alttan 30px yukarıda
        img.paste(qr_img, (qr_x, qr_y))
        
        # Website adını QR kodun yanına veya altına yaz (siyah, büyük)
        website_text = "penaltıdenim.com"
        try:
            website_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
        except:
            try:
                website_font = ImageFont.truetype("arial.ttf", 20)
            except:
                website_font = small_font
        
        # Website adını QR kodun altına veya yanına yaz
        website_y = qr_y + qr_size + 5
        bbox = draw.textbbox((0, 0), website_text, font=website_font)
        text_width = bbox[2] - bbox[0]
        website_x = qr_x + (qr_size - text_width) // 2  # QR kodun altında ortalanmış
        draw.text((website_x, website_y), website_text, fill='black', font=website_font)
        
        # Trendyol etiketi ile birleştir (eğer isteniyorsa)
        if combine_with_trendyol and trendyol_label_bytes:
            img = combine_trendyol_label_with_custom(trendyol_label_bytes, img)
        
        # Base64'e çevir - Argox X-1000VL yazıcı için optimize
        buffer = BytesIO()
        # Argox yazıcılar için 203 DPI kullan (standart)
        img.save(buffer, format="PNG", dpi=(dpi, dpi))
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    
    except Exception as e:
        # Hata durumunda basit bir görsel oluştur
        img = Image.new('RGB', (400, 200), 'white')
        draw = ImageDraw.Draw(img)
        draw.text((50, 50), f"Error: {str(e)}", fill='red')
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"


@router.post("/generate", response_model=BarcodeResponse)
async def generate_barcode_endpoint(
    request: BarcodeRequest,
    store: Store = Depends(get_current_store) if _db_available else None
):
    """
    Akıllı barkod oluşturur.
    Sipariş içindeki ürün sayısı ve bilgileri barkoda eklenir.
    """
    try:
        # İndirim kodunu al (varsayılan: TRENDYOL15)
        discount_code = request.discount_code or "TRENDYOL15"
        
        # Barkod verisini oluştur (indirim kodu ile)
        barcode_data = create_smart_barcode_data(request.order_id, request.items, discount_code)
        
        # QR kod oluştur (her zaman çalışır)
        qr_image = generate_qr_code(barcode_data)
        
        # Code128 barkod oluştur (daha kısa veriler için)
        # Eğer veri çok uzunsa sadece QR kod kullanılır
        barcode_image = generate_barcode(barcode_data[:50]) if len(barcode_data) <= 50 else None
        
        # Kargo barkodu (request'ten al, yoksa None)
        cargo_barcode = request.shipping_info.get("cargo_barcode") if request.shipping_info else None
        
        # Kargo etiketi üzerine yapıştırılacak özel etiket oluştur
        shipping_label = generate_shipping_label_sticker(
            request.order_id,
            request.items,
            discount_code,
            cargo_barcode
        )
        
        # Sipariş özeti
        total_items = sum(item.quantity for item in request.items)
        total_value = sum(item.price * item.quantity for item in request.items)
        
        order_summary = {
            "order_id": request.order_id,
            "total_items": total_items,
            "unique_products": len(request.items),
            "total_value": total_value,
            "discount_code": discount_code,
            "discount_website": "penaltidenim.com",
            "discount_percentage": 15,
            "items": [
                {
                    "product_id": item.product_id,
                    "name": item.product_name,
                    "quantity": item.quantity,
                    "price": item.price
                }
                for item in request.items
            ]
        }
        
        # Barkod geçmişine kaydet (database varsa)
        if _db_available:
            try:
                from database.db import get_db
                db = next(get_db())
                cargo_barcode = request.shipping_info.get("cargo_barcode") if request.shipping_info else None
                
                barcode_history = BarcodeHistory(
                    store_id=store.id,
                    order_id=request.order_id,
                    order_number=request.order_id,
                    barcode_data=barcode_data,
                    barcode_type="both" if barcode_image else "qr",
                    status="created",
                    total_items=total_items,
                    total_value=total_value,
                    discount_code=discount_code,
                    cargo_tracking_number=cargo_barcode
                )
                db.add(barcode_history)
                db.commit()
            except Exception as e:
                print(f"[Barcode] Geçmiş kaydetme hatası: {e}")
        
        return BarcodeResponse(
            barcode_image=barcode_image or qr_image,
            barcode_data=barcode_data,
            qr_code_image=qr_image,
            shipping_label=shipping_label,
            order_summary=order_summary
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Barkod oluşturma hatası: {str(e)}")


@router.post("/scan")
async def scan_barcode(barcode_data: str):
    """
    Barkod/QR kod okur ve sipariş bilgilerini döner.
    """
    try:
        # JSON verisini parse et
        data = json.loads(barcode_data)
        
        return {
            "order_id": data.get("order_id"),
            "total_items": data.get("total_items"),
            "item_count": data.get("item_count"),
            "items": data.get("items", []),
            "message": f"Sipariş {data.get('order_id')} - {data.get('total_items')} ürün"
        }
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Geçersiz barkod formatı")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Barkod okuma hatası: {str(e)}")


@router.get("/auto-generate")
async def auto_generate_barcodes(
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Kargoya gönderilmesi gereken tüm siparişler için otomatik barkod oluşturur.
    Trendyol API'den bekleyen siparişleri çeker ve her biri için barkod hazırlar.
    w3-bulk-label-perstore: per-store credential (env DEĞİL) — bağlı değilse resolve_trendyol_creds 409 fırlatır.
    """
    import requests
    from utils.store_trendyol import resolve_trendyol_creds, fetch_orders as _fetch_store_orders, _auth_headers

    creds = resolve_trendyol_creds(db, store)
    headers = _auth_headers(creds)
    supplier_id = creds.supplier_id

    try:
        # Kargoya hazır sipariş durumları
        ready_for_shipping_statuses = ["Created", "Picking", "Invoiced"]

        # Bu mağazanın tüm siparişlerini per-store creds ile çek
        all_orders_raw = _fetch_store_orders(creds, max_pages=100, size=200)

        # Sadece kargoya hazır olanları filtrele
        ready_orders = [
            o for o in all_orders_raw
            if o.get("status") in ready_for_shipping_statuses
            or o.get("orderStatus") in ready_for_shipping_statuses
        ]

        all_orders = ready_orders

        if not all_orders:
            return {
                "message": "Kargoya gönderilmesi gereken sipariş bulunamadı",
                "barcodes": [],
                "total": 0
            }

        # Her sipariş için barkod oluştur
        barcodes = []

        for order in all_orders:
            try:
                order_id = order.get("orderNumber") or order.get("id", "")
                order_lines = order.get("lines", [])
                
                # Sipariş ürünlerini formatla
                items = []
                for line in order_lines:
                    product_name = line.get("productName", "Ürün")
                    quantity = line.get("quantity", 1)
                    price = float(line.get("price", 0) or 0)
                    product_id = line.get("productId", "")
                    barcode = line.get("barcode", "")
                    
                    items.append(OrderItem(
                        product_id=str(product_id),
                        product_name=product_name,
                        quantity=quantity,
                        price=price,
                        sku=barcode
                    ))
                
                if not items:
                    continue
                
                # Barkod oluştur (indirim kodu ile)
                discount_code = "TRENDYOL15"
                barcode_data = create_smart_barcode_data(order_id, items, discount_code)
                qr_image = generate_qr_code(barcode_data)
                barcode_image = generate_barcode(barcode_data[:50]) if len(barcode_data) <= 50 else None
                
                # Kargo barkodu (Trendyol API'den al)
                cargo_barcode = (
                    order.get("cargoTrackingNumber") or 
                    order.get("trackingNumber") or 
                    order.get("shipmentPackageBarcode") or
                    order.get("packageBarcode") or
                    order.get("cargoBarcode") or
                    None
                )
                
                # Eğer sipariş detayında yoksa, shipment bilgilerinden al
                if not cargo_barcode:
                    shipment = order.get("shipment", {})
                    cargo_barcode = (
                        shipment.get("cargoTrackingNumber") or
                        shipment.get("trackingNumber") or
                        shipment.get("barcode") or
                        None
                    )
                
                # Trendyol kargo etiketini çek (opsiyonel - hata olsa bile devam et)
                trendyol_label_bytes = None
                try:
                    from utils.trendyol_api import get_trendyol_shipment_label
                    package_id = order.get("packageId") or order.get("shipmentPackageId") or order_id
                    trendyol_label_bytes = get_trendyol_shipment_label(package_id)
                except Exception as label_error:
                    # Kargo etiketi çekilemezse sadece özel etiket oluştur
                    print(f"Kargo etiketi çekilemedi (sipariş {order_id}): {str(label_error)}")
                    trendyol_label_bytes = None
                
                # Kargo etiketi üzerine yapıştırılacak etiket (Trendyol etiketi ile birleştir)
                # Sipariş bilgilerini de geç
                # Kargo firması bilgisini al (cargoProviderName öncelikli)
                cargo_company_debug = (
                    order.get("cargoProviderName") or
                    order.get("cargoCompany") or
                    order.get("shipmentCompany") or
                    order.get("cargoProvider") or
                    order.get("cargoFirm") or
                    order.get("cargoCompanyName") or
                    order.get("shipmentCompanyName") or
                    order.get("cargo") or
                    None
                )
                
                # Eğer bulunamadıysa, shipment içinden dene
                if not cargo_company_debug and isinstance(order.get("shipment"), dict):
                    shipment = order.get("shipment", {})
                    cargo_company_debug = (
                        shipment.get("cargoProviderName") or
                        shipment.get("cargoCompany") or
                        shipment.get("shipmentCompany") or
                        shipment.get("cargoProvider") or
                        shipment.get("cargoFirm") or
                        shipment.get("cargoCompanyName") or
                        shipment.get("companyName") or
                        None
                    )
                
                # Bulunan kargo firması bilgisini order objesine ekle
                if cargo_company_debug and not order.get("cargoCompany"):
                    order["cargoCompany"] = cargo_company_debug
                
                shipping_label = generate_shipping_label_sticker(
                    order_id, 
                    items, 
                    discount_code, 
                    cargo_barcode,
                    combine_with_trendyol=True,
                    trendyol_label_bytes=trendyol_label_bytes,
                    order_info=order  # Tüm sipariş bilgilerini geç
                )
                
                total_items = sum(item.quantity for item in items)
                total_value = sum(item.price * item.quantity for item in items)
                
                # Database'e kaydet (created olarak)
                if _db_available:
                    try:
                        from database.db import get_db
                        db = next(get_db())
                        
                        # Mevcut kaydı kontrol et
                        existing = db.query(BarcodeHistory).filter(
                            BarcodeHistory.store_id == store.id,
                            BarcodeHistory.order_id == order_id
                        ).first()
                        
                        if existing:
                            # Mevcut kaydı güncelle - status'ü "created" yap
                            existing.barcode_data = barcode_data
                            existing.barcode_type = "both" if barcode_image else "qr"
                            existing.status = "created"  # Her zaman "created" olarak güncelle
                            existing.total_items = total_items
                            existing.total_value = total_value
                            existing.discount_code = discount_code
                            existing.cargo_tracking_number = cargo_barcode
                            existing.updated_at = datetime.now()
                            # Arşivlenmişse geri getir
                            if existing.status == "archived":
                                existing.archived_at = None
                        else:
                            # Yeni kayıt oluştur - status "created"
                            barcode_history = BarcodeHistory(
                                store_id=store.id,
                                order_id=order_id,
                                order_number=order_id,
                                barcode_data=barcode_data,
                                barcode_type="both" if barcode_image else "qr",
                                status="created",  # Yeni oluşturulanlar "created" olarak kaydedilir
                                total_items=total_items,
                                total_value=total_value,
                                discount_code=discount_code,
                                cargo_tracking_number=cargo_barcode
                            )
                            db.add(barcode_history)
                        
                        db.commit()
                    except Exception as db_error:
                        print(f"[Barcode] Database kayıt hatası (sipariş {order_id}): {db_error}")
                        # Hata olsa bile devam et
                
                barcodes.append({
                    "order_id": order_id,
                    "order_date": _format_trendyol_date(order.get("orderDate", "")),
                    "status": order.get("status") or order.get("orderStatus", ""),
                    "barcode_image": barcode_image or qr_image,
                    "qr_code_image": qr_image,
                    "shipping_label": shipping_label,
                    "barcode_data": barcode_data,
                    "order_summary": {
                        "total_items": total_items,
                        "unique_products": len(items),
                        "total_value": total_value,
                        "discount_code": discount_code,
                        "discount_website": "penaltidenim.com",
                        "discount_percentage": 15,
                        "items": [
                            {
                                "product_id": item.product_id,
                                "name": item.product_name,
                                "quantity": item.quantity,
                                "price": item.price
                            }
                            for item in items
                        ]
                    }
                })
                
            except Exception as e:
                # Bir sipariş için hata olsa bile diğerlerine devam et
                import sys
                import traceback
                print(f"Sipariş {order_id} için barkod oluşturma hatası: {str(e)}", file=sys.stderr)
                traceback.print_exc()
                continue
        
        return {
            "message": f"{len(barcodes)} sipariş için barkod oluşturuldu",
            "barcodes": barcodes,
            "total": len(barcodes),
            "ready_for_shipping": len(all_orders)
        }
    
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Trendyol API'ye bağlanılamadı: {str(e)}"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Barkod oluşturma hatası: {str(e)}"
        )


@router.get("/pending-orders")
async def get_pending_orders_for_barcode():
    """
    Kargoya gönderilmesi gereken siparişleri listeler (barkod oluşturulmadan önce önizleme).
    """
    import os
    import requests
    import base64
    import traceback
    
    # API bilgilerini al
    api_key = os.getenv("TRENDYOL_API_KEY")
    api_secret = os.getenv("TRENDYOL_API_SECRET")
    supplier_id = os.getenv("TRENDYOL_SUPPLIER_ID")
    
    if not all([api_key, api_secret, supplier_id]):
        return {
            "orders": [],
            "total": 0,
            "error": "Trendyol API bilgileri eksik"
        }
    
    try:
        # Trendyol API'den siparişleri çek
        url = f"https://api.trendyol.com/sapigw/suppliers/{supplier_id}/orders"
        
        # Basic Authentication
        auth_string = f"{api_key}:{api_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json",
            "User-Agent": "Trendyol-AI-Assistant/1.0"
        }
        
        # Kargoya hazır sipariş durumları
        ready_for_shipping_statuses = ["Created", "Picking", "Invoiced"]
        
        # Bekleyen siparişleri çek
        response = requests.get(
            url,
            headers=headers,
            params={"page": 0, "size": 50},
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"[pending-orders] API yanıt kodu: {response.status_code}")
            print(f"[pending-orders] API yanıt: {response.text[:500]}")
            return {
                "orders": [],
                "total": 0,
                "error": f"API yanıt kodu: {response.status_code}"
            }
        
        try:
            data = response.json()
        except Exception as json_error:
            print(f"[pending-orders] JSON parse hatası: {str(json_error)}")
            print(f"[pending-orders] Response text: {response.text[:500]}")
            return {
                "orders": [],
                "total": 0,
                "error": f"API yanıtı parse edilemedi: {str(json_error)}"
            }
        
        orders = data.get("content", [])
        
        # Sadece kargoya hazır olanları filtrele
        ready_orders = []
        for o in orders:
            try:
                status = o.get("status") or o.get("orderStatus", "")
                if status in ready_for_shipping_statuses:
                    order_id = o.get("orderNumber") or o.get("id", "") or str(o.get("orderNumber", ""))
                    lines = o.get("lines", [])
                    
                    ready_orders.append({
                        "order_id": order_id,
                        "order_date": _format_trendyol_date(o.get("orderDate", "")),
                        "status": status,
                        "total_price": float(o.get("totalPrice", o.get("totalPriceValue", 0)) or 0),
                        "item_count": len(lines),
                        "items": [
                            {
                                "product_name": line.get("productName", "Ürün"),
                                "quantity": int(line.get("quantity", 0) or 0),
                                "price": float(line.get("price", 0) or 0)
                            }
                            for line in lines
                        ]
                    })
            except Exception as order_error:
                print(f"[pending-orders] Sipariş işleme hatası: {str(order_error)}")
                continue
        
        return {
            "orders": ready_orders,
            "total": len(ready_orders),
            "message": f"{len(ready_orders)} sipariş kargoya hazır"
        }
    
    except requests.exceptions.RequestException as e:
        print(f"[pending-orders] Request hatası: {str(e)}")
        traceback.print_exc()
        return {
            "orders": [],
            "total": 0,
            "error": f"API bağlantı hatası: {str(e)}"
        }
    except Exception as e:
        print(f"[pending-orders] Genel hata: {str(e)}")
        traceback.print_exc()
        return {
            "orders": [],
            "total": 0,
            "error": f"Hata: {str(e)}"
        }


@router.get("/stats")
async def get_barcode_stats(
    store: Store = Depends(get_current_store) if _db_available else None
):
    """
    Barkod sayfası için istatistikler döner.
    """
    import os
    import requests
    import base64
    from datetime import datetime, timedelta
    
    # API bilgilerini al
    api_key = os.getenv("TRENDYOL_API_KEY")
    api_secret = os.getenv("TRENDYOL_API_SECRET")
    supplier_id = os.getenv("TRENDYOL_SUPPLIER_ID")
    
    if not all([api_key, api_secret, supplier_id]):
        return {
            "total_pending_orders": 0,
            "total_value": 0.0,
            "average_order_value": 0.0,
            "today_barcodes": 0,
            "total_items": 0,
            "error": "Trendyol API bilgileri eksik"
        }
    
    try:
        url = f"https://api.trendyol.com/sapigw/suppliers/{supplier_id}/orders"
        
        auth_string = f"{api_key}:{api_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json",
            "User-Agent": "Trendyol-AI-Assistant/1.0"
        }
        
        ready_for_shipping_statuses = ["Created", "Picking", "Invoiced"]
        
        # Bekleyen siparişleri çek
        all_orders = []
        page = 0
        size = 200
        
        while True:
            response = requests.get(
                url,
                headers=headers,
                params={"page": page, "size": size},
                timeout=30
            )
            
            if response.status_code != 200:
                break
            
            try:
                data = response.json()
                orders = data.get("content", [])
                
                if not orders:
                    break
                
                ready_orders = [
                    o for o in orders
                    if o.get("status") in ready_for_shipping_statuses
                    or o.get("orderStatus") in ready_for_shipping_statuses
                ]
                
                all_orders.extend(ready_orders)
                
                if len(orders) < size:
                    break
                
                page += 1
                
            except Exception:
                break
        
        # İstatistikleri hesapla
        total_pending = len(all_orders)
        total_value = sum(float(o.get("totalPrice", 0) or 0) for o in all_orders)
        average_value = total_value / total_pending if total_pending > 0 else 0.0
        total_items = sum(
            sum(line.get("quantity", 1) for line in o.get("lines", []))
            for o in all_orders
        )
        
        # Bugün oluşturulan barkod sayısı (database'den)
        today_barcodes = 0
        if _db_available:
            try:
                from database.db import get_db
                db = next(get_db())
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                today_barcodes = db.query(BarcodeHistory).filter(
                    BarcodeHistory.store_id == store.id,
                    BarcodeHistory.created_at >= today_start
                ).count()
            except Exception:
                pass
        
        return {
            "total_pending_orders": total_pending,
            "total_value": round(total_value, 2),
            "average_order_value": round(average_value, 2),
            "today_barcodes": today_barcodes,
            "total_items": total_items
        }
    
    except Exception as e:
        return {
            "total_pending_orders": 0,
            "total_value": 0.0,
            "average_order_value": 0.0,
            "today_barcodes": 0,
            "total_items": 0,
            "error": str(e)
        }


@router.get("/bulk-print")
async def bulk_print_labels(
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Kargoya gönderilmesi gereken tüm siparişlerin etiketlerini ayrı ayrı oluşturur.
    Her etiket ayrı bir görsel olarak döndürülür, böylece yazıcıya tek tek gönderilebilir.
    w3-bulk-label-perstore: per-store credential (env DEĞİL) — bağlı değilse resolve_trendyol_creds 409 fırlatır.
    """
    import requests
    from utils.store_trendyol import resolve_trendyol_creds, fetch_orders as _fetch_store_orders

    creds = resolve_trendyol_creds(db, store)

    try:
        # Kargoya hazır sipariş durumları
        ready_for_shipping_statuses = ["Created", "Picking", "Invoiced"]

        # Bu mağazanın tüm siparişlerini per-store creds ile çek
        all_orders_raw = _fetch_store_orders(creds, max_pages=100, size=200)
        all_orders = [
            o for o in all_orders_raw
            if o.get("status") in ready_for_shipping_statuses
            or o.get("orderStatus") in ready_for_shipping_statuses
        ]

        if not all_orders:
            raise HTTPException(
                status_code=404,
                detail="Kargoya gönderilmesi gereken sipariş bulunamadı"
            )
        
        # Her sipariş için etiket oluştur (ayrı ayrı)
        labels = []
        
        for order in all_orders:
            try:
                order_id = order.get("orderNumber") or order.get("id", "")
                order_lines = order.get("lines", [])
                
                # Sipariş ürünlerini formatla
                items = []
                for line in order_lines:
                    product_name = line.get("productName", "Ürün")
                    quantity = line.get("quantity", 1)
                    price = float(line.get("price", 0) or 0)
                    product_id = line.get("productId", "")
                    barcode = line.get("barcode", "")
                    
                    items.append(OrderItem(
                        product_id=str(product_id),
                        product_name=product_name,
                        quantity=quantity,
                        price=price,
                        sku=barcode
                    ))
                
                if not items:
                    continue
                
                # Kargo barkodu
                cargo_barcode = (
                    order.get("cargoTrackingNumber") or 
                    order.get("trackingNumber") or 
                    order.get("shipmentPackageBarcode") or
                    order.get("packageBarcode") or
                    order.get("cargoBarcode") or
                    None
                )
                
                if not cargo_barcode:
                    shipment = order.get("shipment", {})
                    cargo_barcode = (
                        shipment.get("cargoTrackingNumber") or
                        shipment.get("trackingNumber") or
                        shipment.get("barcode") or
                        None
                    )
                
                # Trendyol kargo etiketini çek
                trendyol_label_bytes = None
                try:
                    from utils.trendyol_api import get_trendyol_shipment_label
                    package_id = order.get("packageId") or order.get("shipmentPackageId") or order_id
                    trendyol_label_bytes = get_trendyol_shipment_label(package_id)
                except Exception:
                    trendyol_label_bytes = None
                
                # Kargo firması bilgisini al
                cargo_company = (
                    order.get("cargoProviderName") or
                    order.get("cargoCompany") or
                    order.get("shipmentCompany") or
                    None
                )
                
                if not cargo_company and isinstance(order.get("shipment"), dict):
                    shipment = order.get("shipment", {})
                    cargo_company = (
                        shipment.get("cargoProviderName") or
                        shipment.get("cargoCompany") or
                        shipment.get("shipmentCompany") or
                        None
                    )
                
                if cargo_company and not order.get("cargoCompany"):
                    order["cargoCompany"] = cargo_company
                
                # Etiket oluştur
                discount_code = "TRENDYOL15"
                shipping_label_base64 = generate_shipping_label_sticker(
                    order_id, 
                    items, 
                    discount_code, 
                    cargo_barcode,
                    combine_with_trendyol=True,
                    trendyol_label_bytes=trendyol_label_bytes,
                    order_info=order
                )
                
                labels.append({
                    "order_id": order_id,
                    "order_date": _format_trendyol_date(order.get("orderDate", "")),
                    "label": shipping_label_base64
                })
                
            except Exception as e:
                # Bir sipariş için hata olsa bile diğerlerine devam et
                import sys
                print(f"Sipariş {order.get('orderNumber', 'bilinmeyen')} için etiket oluşturma hatası: {str(e)}", file=sys.stderr)
                continue
        
        if not labels:
            raise HTTPException(
                status_code=500,
                detail="Hiçbir sipariş için etiket oluşturulamadı"
            )
        
        return {
            "message": f"{len(labels)} sipariş için etiketler hazırlandı",
            "labels": labels,
            "total_labels": len(labels),
            "total_orders": len(all_orders)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Toplu etiket oluşturma hatası: {str(e)}"
        )


@router.get("/test")
async def test_barcode():
    """Test endpoint - örnek barkod oluşturur (kargo barkodu ile)"""
    # Test için örnek order_info (kargo firması bilgisi ile)
    test_order_info = {
        "cargoCompany": "YURTICI KARGO",  # Test için örnek kargo firması
        "shipmentCompany": "YURTICI KARGO",
        "cargoProvider": "YURTICI KARGO",
        "shipmentAddress": {
            "fullName": "TEST KULLANICI",
            "address1": "TEST ADRES",
            "city": "ISTANBUL",
            "province": "ISTANBUL"
        }
    }
    
    test_request = BarcodeRequest(
        order_id="10825360366",
        items=[
            OrderItem(
                product_id="PRD-001",
                product_name="Erkek Baggy Kargo Ce",
                quantity=1,
                price=99.99,
                sku="SKU-001"
            )
        ],
        shipping_info={
            "cargo_barcode": "7260029173096350"  # Örnek kargo barkodu
        }
    )
    
    # Test için shipping_label oluştur (order_info ile)
    shipping_label = generate_shipping_label_sticker(
        test_request.order_id,
        test_request.items,
        "TRENDYOL15",
        test_request.shipping_info.get("cargo_barcode") if test_request.shipping_info else None,
        combine_with_trendyol=False,
        trendyol_label_bytes=None,
        order_info=test_order_info  # Test order_info ekle
    )
    
    # Normal response oluştur
    barcode_data = create_smart_barcode_data(test_request.order_id, test_request.items, "TRENDYOL15")
    qr_image = generate_qr_code(barcode_data)
    barcode_image = generate_barcode(barcode_data[:50]) if len(barcode_data) <= 50 else None
    
    return BarcodeResponse(
        barcode_image=barcode_image or qr_image,
        barcode_data=barcode_data,
        qr_code_image=qr_image,
        shipping_label=shipping_label,
        order_summary={
            "order_id": test_request.order_id,
            "total_items": 1,
            "unique_products": 1,
            "total_value": 99.99,
            "discount_code": "TRENDYOL15",
            "discount_website": "penaltidenim.com",
            "discount_percentage": 15,
            "items": [
                {
                "product_id": item.product_id,
                    "name": item.product_name,
                "quantity": item.quantity,
                    "price": item.price
                }
                for item in test_request.items
            ]
        }
    )


# ==================== BARKOD GEÇMİŞİ VE TAKİP ====================

@router.get("/history")
async def get_barcode_history(
    order_id: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Barkod geçmişini getirir.
    Filtreleme: order_id, status, tarih aralığı
    """
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    try:
        query = db.query(BarcodeHistory).filter(BarcodeHistory.store_id == store.id)

        # Filtreleme
        if order_id:
            query = query.filter(BarcodeHistory.order_id == order_id)
        if status:
            query = query.filter(BarcodeHistory.status == status)
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(BarcodeHistory.created_at >= start_dt)
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(BarcodeHistory.created_at <= end_dt)
        
        # Sıralama ve limit
        total = query.count()
        barcodes = query.order_by(BarcodeHistory.created_at.desc()).offset(offset).limit(limit).all()
        
        # Barkod görsellerini yeniden oluştur
        formatted_barcodes = []
        for b in barcodes:
            barcode_dict = {
                "id": b.id,
                "order_id": b.order_id,
                "order_number": b.order_number,
                "barcode_type": b.barcode_type,
                "template_id": b.template_id,
                "status": b.status,
                "printed_at": b.printed_at.isoformat() if b.printed_at else None,
                "shipped_at": b.shipped_at.isoformat() if b.shipped_at else None,
                "archived_at": b.archived_at.isoformat() if b.archived_at else None,
                "total_items": b.total_items,
                "total_value": b.total_value,
                "discount_code": b.discount_code,
                "cargo_tracking_number": b.cargo_tracking_number,
                "notes": b.notes,
                "created_at": b.created_at.isoformat(),
                "updated_at": b.updated_at.isoformat(),
                "barcode_data": b.barcode_data
            }
            
            # Eğer barcode_data varsa, görselleri yeniden oluştur
            if b.barcode_data:
                try:
                    # barcode_data JSON string ise parse et, değilse direkt kullan
                    barcode_data_str = b.barcode_data
                    if isinstance(b.barcode_data, str):
                        try:
                            # JSON string ise parse et ve tekrar string'e çevir
                            parsed = json.loads(b.barcode_data)
                            if isinstance(parsed, dict):
                                # Eğer order_id, items gibi alanlar varsa, JSON string olarak kullan
                                barcode_data_str = json.dumps(parsed, ensure_ascii=False)
                            else:
                                barcode_data_str = b.barcode_data
                        except:
                            # JSON değilse direkt kullan
                            barcode_data_str = b.barcode_data
                    
                    # QR kod görselini oluştur
                    qr_image = generate_qr_code(barcode_data_str)
                    barcode_dict["qr_code_image"] = qr_image
                    
                    # Code128 barkod görselini oluştur (eğer barcode_type "both" veya "code128" ise)
                    if b.barcode_type in ["both", "code128"]:
                        try:
                            # Code128 için kısa bir string kullan (order_id veya ilk 50 karakter)
                            code128_data = b.order_id if b.order_id else (barcode_data_str[:50] if len(barcode_data_str) <= 50 else None)
                            if code128_data:
                                barcode_image = generate_barcode(code128_data)
                                if barcode_image:
                                    barcode_dict["barcode_image"] = barcode_image
                        except Exception as code128_error:
                            print(f"[History] Code128 oluşturma hatası (order {b.order_id}): {code128_error}")
                except Exception as img_error:
                    print(f"[History] Görsel oluşturma hatası (order {b.order_id}): {img_error}")
                    import traceback
                    traceback.print_exc()
            
            formatted_barcodes.append(barcode_dict)
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "barcodes": formatted_barcodes
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Geçmiş getirme hatası: {str(e)}")


@router.put("/history/{barcode_id}/status")
async def update_barcode_status(
    barcode_id: int,
    status: str,
    notes: Optional[str] = None,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Barkod durumunu günceller (created, printed, shipped, archived)
    """
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    try:
        barcode = db.query(BarcodeHistory).filter(BarcodeHistory.store_id == store.id, BarcodeHistory.id == barcode_id).first()
        if not barcode:
            raise HTTPException(status_code=404, detail="Barkod bulunamadı")
        
        barcode.status = status
        if notes:
            barcode.notes = notes
        
        # Duruma göre tarih güncelle
        now = datetime.now()
        if status == "printed" and not barcode.printed_at:
            barcode.printed_at = now
        elif status == "shipped" and not barcode.shipped_at:
            barcode.shipped_at = now
        elif status == "archived" and not barcode.archived_at:
            barcode.archived_at = now
        
        barcode.updated_at = now
        db.commit()
        
        return {"message": "Durum güncellendi", "barcode_id": barcode_id, "status": status}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Durum güncelleme hatası: {str(e)}")


@router.post("/history/{barcode_id}/archive")
async def archive_barcode(
    barcode_id: int,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Barkodu arşivler
    """
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    try:
        barcode = db.query(BarcodeHistory).filter(BarcodeHistory.store_id == store.id, BarcodeHistory.id == barcode_id).first()
        if not barcode:
            raise HTTPException(status_code=404, detail="Barkod bulunamadı")
        
        barcode.status = "archived"
        barcode.archived_at = datetime.now()
        barcode.updated_at = datetime.now()
        db.commit()
        
        return {"message": "Barkod arşivlendi", "barcode_id": barcode_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Arşivleme hatası: {str(e)}")


@router.delete("/history/{barcode_id}/unarchive")
async def unarchive_barcode(
    barcode_id: int,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Barkodu arşivden geri getirir
    """
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    try:
        barcode = db.query(BarcodeHistory).filter(BarcodeHistory.store_id == store.id, BarcodeHistory.id == barcode_id).first()
        if not barcode:
            raise HTTPException(status_code=404, detail="Barkod bulunamadı")
        
        barcode.status = "created"
        barcode.archived_at = None
        barcode.updated_at = datetime.now()
        db.commit()
        
        return {"message": "Barkod arşivden geri getirildi", "barcode_id": barcode_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Geri getirme hatası: {str(e)}")


# ==================== BARKOD ŞABLONLARI ====================

class TemplateRequest(BaseModel):
    template_name: str
    description: Optional[str] = None
    template_config: Dict[str, Any]
    is_default: bool = False


@router.get("/templates")
async def get_templates(
    active_only: bool = True,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Tüm barkod şablonlarını getirir
    """
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    try:
        query = db.query(BarcodeTemplate).filter(BarcodeTemplate.store_id == store.id)
        if active_only:
            query = query.filter(BarcodeTemplate.is_active == True)
        
        templates = query.order_by(BarcodeTemplate.is_default.desc(), BarcodeTemplate.created_at.desc()).all()
        
        return {
            "templates": [
                {
                    "id": t.id,
                    "template_id": t.template_id,
                    "template_name": t.template_name,
                    "description": t.description,
                    "template_config": json.loads(t.template_config) if t.template_config else {},
                    "is_default": t.is_default,
                    "is_active": t.is_active,
                    "usage_count": t.usage_count,
                    "created_at": t.created_at.isoformat(),
                    "updated_at": t.updated_at.isoformat()
                }
                for t in templates
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Şablon getirme hatası: {str(e)}")


@router.post("/templates")
async def create_template(
    request: TemplateRequest,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Yeni barkod şablonu oluşturur
    """
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    try:
        # Eğer default olarak işaretleniyorsa, diğer default'ları kaldır
        if request.is_default:
            db.query(BarcodeTemplate).filter(BarcodeTemplate.store_id == store.id, BarcodeTemplate.is_default == True).update({"is_default": False})

        template_id = f"TEMPLATE_{uuid.uuid4().hex[:8].upper()}"
        template = BarcodeTemplate(
            store_id=store.id,
            template_id=template_id,
            template_name=request.template_name,
            description=request.description,
            template_config=json.dumps(request.template_config),
            is_default=request.is_default,
            is_active=True
        )
        
        db.add(template)
        db.commit()
        db.refresh(template)
        
        return {
            "message": "Şablon oluşturuldu",
            "template": {
                "id": template.id,
                "template_id": template.template_id,
                "template_name": template.template_name,
                "description": template.description,
                "template_config": json.loads(template.template_config),
                "is_default": template.is_default,
                "is_active": template.is_active
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Şablon oluşturma hatası: {str(e)}")


@router.put("/templates/{template_id}")
async def update_template(
    template_id: str,
    request: TemplateRequest,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Barkod şablonunu günceller
    """
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    try:
        template = db.query(BarcodeTemplate).filter(BarcodeTemplate.store_id == store.id, BarcodeTemplate.template_id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Şablon bulunamadı")

        # Eğer default olarak işaretleniyorsa, diğer default'ları kaldır
        if request.is_default and not template.is_default:
            db.query(BarcodeTemplate).filter(BarcodeTemplate.store_id == store.id, BarcodeTemplate.is_default == True).update({"is_default": False})
        
        template.template_name = request.template_name
        template.description = request.description
        template.template_config = json.dumps(request.template_config)
        template.is_default = request.is_default
        template.updated_at = datetime.now()
        
        db.commit()
        
        return {"message": "Şablon güncellendi", "template_id": template_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Şablon güncelleme hatası: {str(e)}")


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Barkod şablonunu siler (soft delete - is_active=False yapar)
    """
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    try:
        template = db.query(BarcodeTemplate).filter(BarcodeTemplate.store_id == store.id, BarcodeTemplate.template_id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Şablon bulunamadı")
        
        template.is_active = False
        template.updated_at = datetime.now()
        db.commit()
        
        return {"message": "Şablon silindi", "template_id": template_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Şablon silme hatası: {str(e)}")


# ==================== GELİŞMİŞ YAZDIRMA ====================

class PrintSettings(BaseModel):
    printer_name: Optional[str] = None
    paper_size: str = "4x6"  # "4x6", "A4", "custom"
    quality: str = "high"  # "low", "medium", "high"
    copies: int = 1
    orientation: str = "portrait"  # "portrait", "landscape"


@router.post("/print/settings")
async def get_print_settings():
    """
    Yazdırma ayarlarını döner (frontend'de kullanılacak)
    """
    return {
        "paper_sizes": ["4x6", "A4", "custom"],
        "qualities": ["low", "medium", "high"],
        "orientations": ["portrait", "landscape"],
        "default_settings": {
            "paper_size": "4x6",
            "quality": "high",
            "copies": 1,
            "orientation": "portrait"
        }
    }


# ==================== BATCH İŞLEMLERİ ====================

class BatchBarcodeRequest(BaseModel):
    order_ids: List[str]
    template_id: Optional[str] = None
    discount_code: Optional[str] = "TRENDYOL15"


@router.post("/batch/generate")
async def batch_generate_barcodes(
    request: BatchBarcodeRequest,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Seçili siparişler için toplu barkod oluşturur
    w3-bulk-label-perstore: per-store credential (env DEĞİL) — bağlı değilse resolve_trendyol_creds 409 fırlatır.
    Tekil sipariş sorgusu w3-scanorder-gateway'de kanıtlanan yeni gateway ucunu kullanır
    (eski /orders/{orderNumber} alt-yolu Cloudflare bot-korumasıyla 403 veriyordu).
    """
    import requests
    from utils.store_trendyol import resolve_trendyol_creds, _auth_headers

    creds = resolve_trendyol_creds(db, store)
    headers = _auth_headers(creds)
    orders_url = f"https://apigw.trendyol.com/integration/order/sellers/{creds.supplier_id}/v2/orders"

    try:
        barcodes = []
        errors = []

        for order_id in request.order_ids:
            try:
                # Sipariş detayını çek (orderNumber sorgu parametresiyle, tekil path-segment DEĞİL)
                response = requests.get(
                    orders_url,
                    headers=headers,
                    params={"orderNumber": order_id},
                    timeout=30
                )

                if response.status_code != 200:
                    errors.append({"order_id": order_id, "error": "Sipariş bulunamadı"})
                    continue

                content = (response.json() or {}).get("content", [])
                if not content:
                    errors.append({"order_id": order_id, "error": "Sipariş bulunamadı"})
                    continue
                order = content[0]
                order_lines = order.get("lines", [])
                
                # Sipariş ürünlerini formatla
                items = []
                for line in order_lines:
                    items.append(OrderItem(
                        product_id=str(line.get("productId", "")),
                        product_name=line.get("productName", "Ürün"),
                        quantity=line.get("quantity", 1),
                        price=float(line.get("price", 0) or 0),
                        sku=line.get("barcode", "")
                    ))
                
                if not items:
                    errors.append({"order_id": order_id, "error": "Ürün bulunamadı"})
                    continue
                
                # Barkod oluştur
                discount_code = request.discount_code or "TRENDYOL15"
                barcode_data = create_smart_barcode_data(order_id, items, discount_code)
                qr_image = generate_qr_code(barcode_data)
                barcode_image = generate_barcode(barcode_data[:50]) if len(barcode_data) <= 50 else None
                
                cargo_barcode = (
                    order.get("cargoTrackingNumber") or 
                    order.get("trackingNumber") or 
                    None
                )
                
                shipping_label = generate_shipping_label_sticker(
                    order_id,
                    items,
                    discount_code,
                    cargo_barcode
                )
                
                total_items = sum(item.quantity for item in items)
                total_value = sum(item.price * item.quantity for item in items)
                
                # Geçmişe kaydet (created olarak)
                if _db_available and db:
                    try:
                        # Mevcut kaydı kontrol et
                        existing = db.query(BarcodeHistory).filter(
                            BarcodeHistory.store_id == store.id,
                            BarcodeHistory.order_id == order_id
                        ).first()
                        
                        if existing:
                            # Mevcut kaydı güncelle
                            existing.barcode_data = barcode_data
                            existing.barcode_type = "both" if barcode_image else "qr"
                            existing.status = "created"
                            existing.total_items = total_items
                            existing.total_value = total_value
                            existing.discount_code = discount_code
                            existing.cargo_tracking_number = cargo_barcode
                            existing.updated_at = datetime.now()
                        else:
                            # Yeni kayıt oluştur
                            barcode_history = BarcodeHistory(
                                store_id=store.id,
                                order_id=order_id,
                                order_number=order.get("orderNumber", order_id),
                                barcode_data=barcode_data,
                                barcode_type="both" if barcode_image else "qr",
                                template_id=request.template_id,
                                status="created",
                                total_items=total_items,
                                total_value=total_value,
                                discount_code=discount_code,
                                cargo_tracking_number=cargo_barcode
                            )
                            db.add(barcode_history)
                    except Exception as e:
                        print(f"[Batch] Geçmiş kaydetme hatası: {e}")
                
                barcodes.append({
                    "order_id": order_id,
                    "order_date": _format_trendyol_date(order.get("orderDate", "")),
                    "barcode_image": barcode_image or qr_image,
                    "qr_code_image": qr_image,
                    "shipping_label": shipping_label,
                    "barcode_data": barcode_data,
                    "order_summary": {
                        "total_items": total_items,
                        "unique_products": len(items),
                        "total_value": total_value,
                        "discount_code": discount_code
                    }
                })
                
            except Exception as e:
                errors.append({"order_id": order_id, "error": str(e)})
        
        if _db_available:
            db.commit()
        
        return {
            "message": f"{len(barcodes)} barkod oluşturuldu",
            "barcodes": barcodes,
            "errors": errors,
            "total": len(request.order_ids),
            "success": len(barcodes),
            "failed": len(errors)
        }
    
    except Exception as e:
        if _db_available:
            db.rollback()
        raise HTTPException(status_code=500, detail=f"Toplu barkod oluşturma hatası: {str(e)}")


@router.post("/batch/print")
async def batch_print_barcodes(
    barcode_ids: List[int],
    print_settings: Optional[PrintSettings] = None,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Seçili barkodları toplu yazdırır
    """
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    try:
        barcodes = db.query(BarcodeHistory).filter(BarcodeHistory.store_id == store.id, BarcodeHistory.id.in_(barcode_ids)).all()
        
        if not barcodes:
            raise HTTPException(status_code=404, detail="Barkod bulunamadı")
        
        # Durumları güncelle
        now = datetime.now()
        for barcode in barcodes:
            if barcode.status != "printed":
                barcode.status = "printed"
                barcode.printed_at = now
                barcode.updated_at = now
        
        db.commit()
        
        return {
            "message": f"{len(barcodes)} barkod yazdırma için hazırlandı",
            "barcode_ids": [b.id for b in barcodes],
            "print_settings": print_settings.dict() if print_settings else None
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Toplu yazdırma hatası: {str(e)}")


@router.post("/batch/archive")
async def batch_archive_barcodes(
    barcode_ids: List[int],
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Seçili barkodları toplu arşivler
    """
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    try:
        barcodes = db.query(BarcodeHistory).filter(BarcodeHistory.store_id == store.id, BarcodeHistory.id.in_(barcode_ids)).all()
        
        if not barcodes:
            raise HTTPException(status_code=404, detail="Barkod bulunamadı")
        
        now = datetime.now()
        for barcode in barcodes:
            barcode.status = "archived"
            barcode.archived_at = now
            barcode.updated_at = now
        
        db.commit()
        
        return {
            "message": f"{len(barcodes)} barkod arşivlendi",
            "barcode_ids": [b.id for b in barcodes]
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Toplu arşivleme hatası: {str(e)}")


# ==================== OTOMATİK ARŞİVLEME ====================

@router.post("/auto-archive")
async def auto_archive_old_barcodes(
    days: int = 30,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    30 günden eski barkodları otomatik arşivler
    """
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    try:
        cutoff_date = datetime.now() - timedelta(days=days)

        barcodes = db.query(BarcodeHistory).filter(
            and_(
                BarcodeHistory.store_id == store.id,
                BarcodeHistory.status != "archived",
                BarcodeHistory.created_at < cutoff_date
            )
        ).all()
        
        now = datetime.now()
        archived_count = 0
        
        for barcode in barcodes:
            barcode.status = "archived"
            barcode.archived_at = now
            barcode.updated_at = now
            archived_count += 1
        
        db.commit()
        
        return {
            "message": f"{archived_count} barkod otomatik arşivlendi",
            "archived_count": archived_count,
            "cutoff_date": cutoff_date.isoformat()
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Otomatik arşivleme hatası: {str(e)}")


@router.get("/export/{format}")
async def export_barcode_history(
    format: str = "csv",  # "csv" veya "excel"
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Any = Depends(get_db) if _db_available else None
):
    """
    Barkod geçmişini CSV veya Excel formatında export eder
    """
    if not _db_available or db is None:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    try:
        query = db.query(BarcodeHistory).filter(BarcodeHistory.store_id == store.id)

        # Filtreler
        if status:
            query = query.filter(BarcodeHistory.status == status)
        
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(BarcodeHistory.created_at >= start_dt)
            except:
                pass
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(BarcodeHistory.created_at <= end_dt)
            except:
                pass
        
        barcodes = query.order_by(BarcodeHistory.created_at.desc()).all()
        
        # CSV Export
        if format.lower() == "csv":
            output = StringIO()
            writer = csv.writer(output)
            
            # Başlık
            writer.writerow([
                "Sipariş ID", "Sipariş No", "Barkod Tipi", "Durum", "Oluşturulma Tarihi", "Güncellenme Tarihi"
            ])
            
            # Veriler
            for barcode in barcodes:
                writer.writerow([
                    barcode.order_id or "",
                    barcode.order_number or "",
                    barcode.barcode_type or "",
                    barcode.status or "",
                    barcode.created_at.isoformat() if barcode.created_at else "",
                    barcode.updated_at.isoformat() if barcode.updated_at else ""
                ])
            
            output.seek(0)
            filename = f"barkod_gecmisi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            return StreamingResponse(
                iter([output.getvalue().encode('utf-8-sig')]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        
        # Excel Export
        elif format.lower() == "excel":
            try:
                import openpyxl
                from openpyxl import Workbook
                
                wb = Workbook()
                ws = wb.active
                ws.title = "Barkod Geçmişi"
                
                # Başlık
                ws.append([
                    "Sipariş ID", "Sipariş No", "Barkod Tipi", "Durum", "Oluşturulma Tarihi", "Güncellenme Tarihi"
                ])
                
                # Veriler
                for barcode in barcodes:
                    ws.append([
                        barcode.order_id or "",
                        barcode.order_number or "",
                        barcode.barcode_type or "",
                        barcode.status or "",
                        barcode.created_at.isoformat() if barcode.created_at else "",
                        barcode.updated_at.isoformat() if barcode.updated_at else ""
                    ])
                
                # Dosyayı memory'de oluştur
                output = BytesIO()
                wb.save(output)
                output.seek(0)
                
                filename = f"barkod_gecmisi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                
                return StreamingResponse(
                    output,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
            except ImportError:
                raise HTTPException(
                    status_code=500,
                    detail="Excel export için openpyxl paketi gerekli. 'pip install openpyxl' komutu ile yükleyin."
                )
        
        else:
            raise HTTPException(status_code=400, detail="Geçersiz format. 'csv' veya 'excel' olmalı.")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export hatası: {str(e)}")


@router.post("/import")
async def import_barcode_history(
    file: UploadFile = File(...),
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Any = Depends(get_db) if _db_available else None
):
    """
    CSV veya Excel dosyasından barkod geçmişi import eder
    """
    if not _db_available or db is None:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")
    
    try:
        
        content = await file.read()
        filename = file.filename or ""
        
        imported_count = 0
        errors = []
        
        # CSV Import
        if filename.endswith('.csv'):
            content_str = content.decode('utf-8-sig')
            reader = csv.DictReader(StringIO(content_str))
            
            for row in reader:
                try:
                    barcode = BarcodeHistory(
                        store_id=store.id,
                        order_id=row.get("Sipariş ID") or row.get("order_id", ""),
                        order_number=row.get("Sipariş No") or row.get("order_number", ""),
                        barcode_type=row.get("Barkod Tipi") or row.get("barcode_type", ""),
                        status=row.get("Durum") or row.get("status", "created"),
                        created_at=datetime.fromisoformat(row.get("Oluşturulma Tarihi") or row.get("created_at", datetime.now().isoformat())),
                        updated_at=datetime.fromisoformat(row.get("Güncellenme Tarihi") or row.get("updated_at", datetime.now().isoformat()))
                    )
                    db.add(barcode)
                    imported_count += 1
                except Exception as e:
                    errors.append(f"Satır hatası: {str(e)}")
        
        # Excel Import
        elif filename.endswith('.xlsx') or filename.endswith('.xls'):
            try:
                import openpyxl
                from openpyxl import load_workbook
                
                wb = load_workbook(BytesIO(content))
                ws = wb.active
                
                # İlk satır başlık, atla
                headers = [cell.value for cell in ws[1]]
                
                for row in ws.iter_rows(min_row=2, values_only=True):
                    try:
                        row_dict = dict(zip(headers, row))
                        barcode = BarcodeHistory(
                            store_id=store.id,
                            order_id=row_dict.get("Sipariş ID") or row_dict.get("order_id", ""),
                            order_number=row_dict.get("Sipariş No") or row_dict.get("order_number", ""),
                            barcode_type=row_dict.get("Barkod Tipi") or row_dict.get("barcode_type", ""),
                            status=row_dict.get("Durum") or row_dict.get("status", "created"),
                            created_at=row_dict.get("Oluşturulma Tarihi") or datetime.now(),
                            updated_at=row_dict.get("Güncellenme Tarihi") or datetime.now()
                        )
                        db.add(barcode)
                        imported_count += 1
                    except Exception as e:
                        errors.append(f"Satır hatası: {str(e)}")
            except ImportError:
                raise HTTPException(
                    status_code=500,
                    detail="Excel import için openpyxl paketi gerekli. 'pip install openpyxl' komutu ile yükleyin."
                )
        else:
            raise HTTPException(status_code=400, detail="Desteklenmeyen dosya formatı. CSV veya Excel (.xlsx) olmalı.")
        
        db.commit()
        
        return {
            "message": f"{imported_count} barkod kaydı başarıyla import edildi",
            "imported_count": imported_count,
            "errors": errors[:10] if errors else []  # İlk 10 hatayı göster
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import hatası: {str(e)}")


@router.get("/bulk-print-trendyol")
async def bulk_print_trendyol_labels(
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Kargoya gönderilmesi gereken tüm siparişlerin Trendyol kargo etiketlerini toplu çıkarır.
    Sadece Trendyol'un kendi kargo etiketlerini döndürür (ekstra etiket eklemeden).
    Per-store: bu mağazanın kendi bağlı Trendyol kimliğiyle çalışır (env fallback yok).
    """
    import base64
    from utils.store_trendyol import resolve_trendyol_creds, fetch_orders, fetch_common_label

    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    creds = resolve_trendyol_creds(db, store)

    # Kargoya hazır sipariş durumları
    ready_for_shipping_statuses = ["Created", "Picking", "Invoiced"]

    all_orders_raw = fetch_orders(creds, max_pages=50)
    all_orders = [
        o for o in all_orders_raw
        if o.get("status") in ready_for_shipping_statuses
        or o.get("orderStatus") in ready_for_shipping_statuses
    ]

    if not all_orders:
        return {
            "message": "Kargoya gönderilmesi gereken sipariş bulunamadı",
            "labels": [],
            "total_labels": 0,
            "total_orders": 0,
            "errors": [],
            "error_count": 0
        }

    # Her sipariş için Trendyol kargo etiketini çek
    labels = []
    errors = []

    for order in all_orders:
        try:
            order_id = order.get("orderNumber") or order.get("id", "")
            package_id = order.get("packageId") or order.get("shipmentPackageId") or order_id
            cargo_tracking_number = (
                order.get("cargoTrackingNumber") or
                order.get("trackingNumber") or
                order.get("shipmentPackageBarcode") or
                order.get("packageBarcode") or
                order.get("cargoBarcode") or
                None
            )

            if not cargo_tracking_number:
                errors.append({
                    "order_id": order_id,
                    "error": "Siparişte kargo takip numarası (cargoTrackingNumber) yok — kargo etiketi henüz atanmamış olabilir"
                })
                continue

            # Resmi Trendyol 'Ortak Etiket' (getCommonLabel/createCommonLabel) servisi —
            # developers.trendyol.com/reference/getcommonlabel. ZPL formatında düz metin döner
            # (PDF/PNG DEĞİL — eski /suppliers/.../shipment-packages/.../label ucu artık
            # Cloudflare bot-korumasıyla 403 veriyordu, bu servis resmi yerine geçen).
            zpl_label, error_reason = fetch_common_label(creds, str(cargo_tracking_number))

            if zpl_label:
                label_base64 = base64.b64encode(zpl_label.encode("utf-8")).decode("utf-8")
                content_type = "application/zpl"

                labels.append({
                    "order_id": order_id,
                    "package_id": package_id,
                    "order_date": _format_trendyol_date(order.get("orderDate", "")),
                    "label": f"data:{content_type};base64,{label_base64}",
                    "content_type": content_type,
                    "cargo_tracking_number": cargo_tracking_number,
                    "cargo_company": (
                        order.get("cargoProviderName") or
                        order.get("cargoCompany") or
                        order.get("shipmentCompany") or
                        None
                    )
                })
            else:
                errors.append({
                    "order_id": order_id,
                    "error": error_reason or "Trendyol kargo etiketi şu anda alınamadı"
                })

        except Exception as e:
            errors.append({
                "order_id": order.get("orderNumber", "bilinmeyen"),
                "error": str(e)
            })
            continue

    # ETİKET YOK durumu bir HATA değil — kullanıcıya 500 yerine anlamlı, boş-ama-açıklayıcı yanıt dön.
    if not labels:
        return {
            "message": (
                f"{len(all_orders)} kargoya hazır sipariş bulundu ama hiçbiri için Trendyol kargo etiketi "
                "alınamadı — muhtemelen henüz kargo ataması yapılmamış ya da Trendyol API'ye erişilemiyor. "
                "Detaylar için errors listesine bakın."
            ),
            "labels": [],
            "total_labels": 0,
            "total_orders": len(all_orders),
            "errors": errors,
            "error_count": len(errors)
        }

    return {
        "message": f"{len(labels)} sipariş için Trendyol kargo etiketleri hazırlandı",
        "labels": labels,
        "total_labels": len(labels),
        "total_orders": len(all_orders),
        "errors": errors,
        "error_count": len(errors)
    }


@router.post("/scan-order")
async def scan_order_barcode(
    request: ScanOrderRequest,
    store: Store = Depends(get_current_store) if _db_available else None
):
    """
    Barkod okutulduğunda sipariş detaylarını ve ürün listesini döndürür.
    Telefon ile barkod okutma için optimize edilmiştir.
    
    Request body:
    {
        "barcode_data": "barkod verisi (JSON string veya order_id veya kargo takip numarası)"
    }
    """
    # Import'ları en başta yap (exception handler'da kullanılabilir olmalı)
    import os
    import requests
    import base64
    import json  # JSON parsing için - local import
    from datetime import datetime
    
    barcode_data = request.barcode_data or request.barcode or ""
    
    if not barcode_data:
        raise HTTPException(status_code=400, detail="Barkod verisi gerekli")
    
    # API bilgilerini al
    api_key = os.getenv("TRENDYOL_API_KEY")
    api_secret = os.getenv("TRENDYOL_API_SECRET")
    supplier_id = os.getenv("TRENDYOL_SUPPLIER_ID")
    
    if not all([api_key, api_secret, supplier_id]):
        raise HTTPException(
            status_code=503,
            detail="Trendyol API bilgileri eksik"
        )
    
    try:
        # Barkod verisini parse et - JSON olabilir veya direkt order_id olabilir
        order_id = None
        
        # Önce JSON olarak parse etmeyi dene
        try:
            parsed_data = json.loads(barcode_data)
            order_id = parsed_data.get("order_id")
        except json.JSONDecodeError:
            # JSON değilse, direkt order_id olabilir
            order_id = str(barcode_data).strip()
        except AttributeError:
            # AttributeError durumunda da direkt order_id olarak kullan
            order_id = str(barcode_data).strip()
        
        if not order_id:
            raise HTTPException(status_code=400, detail="Barkod içinde sipariş ID bulunamadı")
        
        # Trendyol API'den sipariş detayını çek
        url = f"https://api.trendyol.com/sapigw/suppliers/{supplier_id}/orders"
        
        # Basic Authentication
        auth_string = f"{api_key}:{api_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json",
            "User-Agent": "Trendyol-AI-Assistant/1.0"
        }
        
        # Siparişi bul. DÜZELTME (2026-09-23, w3-scan-match-bug): eskiden `order_id`'nin
        # hane sayısına bakılıp SADECE orderNumber YA DA SADECE cargoTrackingNumber ile
        # dışlayıcı şekilde eşleştiriliyordu — gerçek Trendyol orderNumber'ları da 11 hane
        # olduğu için hep "tracking" moduna düşüp orderNumber'a hiç bakılmıyordu (üretilen
        # barkod order_id kodluyor → okutunca hep 404). Artık HER paket için hem orderNumber
        # hem tüm bilinen kargo-takip alanları TEK GEÇİŞTE denenir, hangisi tutarsa o kullanılır.
        found_order = None

        # Hızlı yol: değer bir orderNumber ise yeni gateway'in tekil sorgusu (v2/orders?orderNumber=)
        # tüm sayfaları taramadan doğrudan bulur (w3-scanorder-gateway'de doğrulanan uç).
        try:
            v2_url = f"https://apigw.trendyol.com/integration/order/sellers/{supplier_id}/v2/orders"
            v2_resp = requests.get(v2_url, headers=headers, params={"orderNumber": order_id}, timeout=30)
            if v2_resp.status_code == 200:
                v2_content = (v2_resp.json() or {}).get("content", [])
                if v2_content:
                    found_order = v2_content[0]
        except Exception:
            pass

        # Bulunamadıysa (kargo takip numarasıyla okutulmuş olabilir, ya da hızlı yol başarısız
        # oldu) — tüm sayfaları tarayıp hem orderNumber hem kargo-takip alanlarını dene.
        if not found_order:
            page = 0
            size = 200
            while True:
                response = requests.get(
                    url,
                    headers=headers,
                    params={"page": page, "size": size},
                    timeout=30
                )

                if response.status_code != 200:
                    break

                try:
                    data = response.json()
                    orders = data.get("content", [])

                    if not orders:
                        break

                    for order in orders:
                        current_order_number = str(order.get("orderNumber") or order.get("id", ""))
                        cargo_tracking = (
                            order.get("cargoTrackingNumber") or
                            order.get("trackingNumber") or
                            order.get("shipmentPackageBarcode") or
                            order.get("packageBarcode") or
                            order.get("cargoBarcode") or
                            ""
                        )
                        if current_order_number == str(order_id) or str(cargo_tracking) == str(order_id):
                            found_order = order
                            break

                    if found_order:
                        break

                    if len(orders) < size:
                        break

                    page += 1

                    # Güvenlik için maksimum sayfa limiti
                    if page > 50:
                        break

                except Exception:
                    break
        
        if not found_order:
            raise HTTPException(
                status_code=404,
                detail=f"Sipariş bulunamadı: {order_id} (Sipariş numarası veya kargo takip numarası ile arandı)"
            )
        
        # Sipariş detaylarını çek (daha fazla bilgi için)
        # Eğer sipariş numarası varsa, detaylı bilgi için tekrar API'ye istek at.
        # NOT (2026-09-23): eski `/suppliers/{id}/orders/{orderNumber}` alt-yolu Cloudflare
        # bot-korumasıyla 403 veriyordu (w3-scanorder-gateway ile doğrulandı — canlı test).
        # Yeni Order Integration API'de path-segment karşılığı yok; tekil sipariş detayı
        # `orderNumber` SORGU parametresiyle çıplak (liste) uca isteniyor — resmi dokümanla
        # doğrulandı (developers.trendyol.com/v3.0/docs/2-get-shipment-packages).
        order_number = found_order.get("orderNumber") or found_order.get("id")
        if order_number:
            import sys
            try:
                detail_url = f"https://apigw.trendyol.com/integration/order/sellers/{supplier_id}/v2/orders"
                detail_response = requests.get(
                    detail_url, headers=headers, params={"orderNumber": order_number}, timeout=30
                )
                if detail_response.status_code == 200:
                    content = (detail_response.json() or {}).get("content", [])
                    detailed_order = content[0] if content else None
                    # Detaylı siparişte daha fazla bilgi olabilir
                    if detailed_order and detailed_order.get("lines"):
                        found_order = detailed_order
                        print(f"[ScanOrder] Sipariş detayı çekildi, detaylı bilgiler mevcut", file=sys.stderr)
                else:
                    print(
                        f"[ScanOrder] Sipariş detay zenginleştirmesi atlandı — "
                        f"HTTP {detail_response.status_code}, liste verisiyle devam ediliyor",
                        file=sys.stderr,
                    )
            except Exception as e:
                # Detay çekilemezse mevcut veriyi kullan
                print(f"[ScanOrder] Sipariş detayı çekilemedi: {e}", file=sys.stderr)
        
        # Sipariş detaylarını hazırla
        order_lines = found_order.get("lines", []) or found_order.get("orderLines", []) or []
        
        # Tarih formatını düzelt
        order_date_str = found_order.get("orderDate") or found_order.get("order_date", "")
        if order_date_str:
            try:
                if isinstance(order_date_str, (int, float)):
                    # Trendyol orderDate epoch-ms (13 hane) gönderir, epoch-s DEĞİL —
                    # bu kontrol olmadan TypeError alıp ham int'i formatsız döndürüyordu.
                    _ts = float(order_date_str)
                    if _ts > 1e12:
                        _ts = _ts / 1000
                    order_date = datetime.fromtimestamp(_ts)
                elif 'T' in order_date_str:
                    order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00'))
                else:
                    order_date = datetime.strptime(order_date_str, "%Y-%m-%d")
                order_date_formatted = order_date.strftime("%d.%m.%Y %H:%M:%S")
            except:
                order_date_formatted = order_date_str
        else:
            order_date_formatted = ""
        
        # Ürün listesini hazırla (görseller, model numarası, beden vb. ile)
        items = []
        for line in order_lines:
            # Debug: Tüm alanları yazdır (sadece ilk satır için)
            if len(items) == 0:
                import sys
                print(f"[ScanOrder] Line keys: {list(line.keys())}", file=sys.stderr)
                print(f"[ScanOrder] Line tüm değerler:", file=sys.stderr)
                for k, v in line.items():
                    if isinstance(v, (str, int, float)) and len(str(v)) < 200:
                        print(f"  {k}: {v}", file=sys.stderr)
                    elif isinstance(v, (list, dict)):
                        print(f"  {k}: {type(v).__name__} (len={len(v) if hasattr(v, '__len__') else 'N/A'})", file=sys.stderr)
            
            # Ürün görsellerini çek - önce sipariş satırından, sonra API'den
            product_images = []
            
            # Önce direkt görsel alanlarını kontrol et (sipariş satırında olabilir)
            # Tüm olası alanları kontrol et (case-insensitive)
            image_fields = [
                "productImage", "imageUrl", "productImageUrl", "image", 
                "thumbnail", "thumbnailUrl", "mediaUrl", "images",
                "productImageList", "mediaUrls", "imageList", "productImages",
                "productMainImage", "mainImage", "productThumbnail",
                "imageUrls", "productImages", "mediaList"
            ]
            
            # Önce tüm key'leri kontrol et (case-insensitive)
            line_lower = {k.lower(): v for k, v in line.items()}
            for key, value in line.items():
                key_lower = key.lower()
                # Görsel ile ilgili alanları kontrol et
                if any(img_field.lower() in key_lower for img_field in image_fields) or "image" in key_lower or "media" in key_lower:
                    if value:
                        if isinstance(value, str) and value.startswith("http"):
                            if value not in product_images:
                                product_images.append(value)
                                if len(items) == 0:
                                    import sys
                                    print(f"[ScanOrder] Görsel bulundu ({key}): {value[:100]}", file=sys.stderr)
                        elif isinstance(value, list):
                            for img in value:
                                if isinstance(img, str) and img.startswith("http") and img not in product_images:
                                    product_images.append(img)
                                    if len(items) == 0:
                                        import sys
                                        print(f"[ScanOrder] Görsel bulundu (liste, {key}): {img[:100]}", file=sys.stderr)
                                elif isinstance(img, dict):
                                    img_url = (
                                        img.get("url") or 
                                        img.get("imageUrl") or 
                                        img.get("image") or
                                        img.get("mediaUrl") or
                                        img.get("src") or
                                        img.get("productImage") or
                                        img.get("thumbnail") or
                                        img.get("originalUrl") or
                                        img.get("zoomUrl")
                                    )
                                    if img_url and isinstance(img_url, str) and img_url.startswith("http") and img_url not in product_images:
                                        product_images.append(img_url)
                                        if len(items) == 0:
                                            import sys
                                            print(f"[ScanOrder] Görsel bulundu (dict, {key}): {img_url[:100]}", file=sys.stderr)
            
            # Nested objeleri de kontrol et (discountDetails, fastDeliveryOptions vb.)
            if not product_images:
                for key, value in line.items():
                    if isinstance(value, (list, dict)):
                        try:
                            def extract_urls_from_nested(obj, depth=0):
                                """Nested objelerden URL'leri çıkar"""
                                if depth > 3:  # Maksimum derinlik
                                    return []
                                urls = []
                                if isinstance(obj, dict):
                                    for k, v in obj.items():
                                        if isinstance(v, str) and v.startswith("http") and "cdn.dsmcdn.com" in v:
                                            urls.append(v)
                                        elif isinstance(v, (dict, list)):
                                            urls.extend(extract_urls_from_nested(v, depth + 1))
                                elif isinstance(obj, list):
                                    for item in obj:
                                        urls.extend(extract_urls_from_nested(item, depth + 1))
                                return urls
                            
                            nested_urls = extract_urls_from_nested(value)
                            for url in nested_urls:
                                if url not in product_images:
                                    product_images.append(url)
                                    if len(items) == 0:
                                        import sys
                                        print(f"[ScanOrder] Görsel bulundu (nested, {key}): {url[:100]}", file=sys.stderr)
                        except Exception:
                            pass
            
            # ÖNCE veritabanından görsel eşleştirmesini kontrol et (öncelikli)
            product_code = line.get("productCode") or line.get("productId")
            content_id = line.get("contentId")
            barcode = line.get("barcode") or line.get("sku")
            
            # Veritabanından görselleri çek (öncelikli)
            if product_code or content_id or barcode:
                try:
                    # Database'den görsel eşleştirmesini ara
                    if _db_available:
                        try:
                            from database.db import SessionLocal
                            from database.models import ProductImageMapping
                            from sqlalchemy import or_
                            import json
                            
                            # SessionLocal None olabilir, kontrol et
                            if SessionLocal is None:
                                import sys
                                print(f"[ScanOrder] SessionLocal mevcut değil, mapping atlanıyor", file=sys.stderr)
                            else:
                                db = SessionLocal()
                                try:
                                    query = db.query(ProductImageMapping).filter(ProductImageMapping.store_id == store.id, ProductImageMapping.is_active == True)
                                    
                                    conditions = []
                                    if product_code:
                                        conditions.append(ProductImageMapping.product_code == str(product_code))
                                    if barcode and barcode != "merchantSku":
                                        conditions.append(ProductImageMapping.barcode == str(barcode))
                                    if content_id:
                                        conditions.append(ProductImageMapping.content_id == str(content_id))
                                    
                                    if conditions:
                                        query = query.filter(or_(*conditions))
                                        mapping = query.first()
                                        
                                        if mapping:
                                            image_urls = json.loads(mapping.image_urls) if mapping.image_urls else []
                                            if image_urls:
                                                # Veritabanındaki görselleri kullan (öncelikli)
                                                product_images = image_urls
                                                if len(items) == 0:
                                                    import sys
                                                    print(f"[ScanOrder] DB'den {len(product_images)} görsel bulundu (product_code: {product_code})", file=sys.stderr)
                                except Exception as e:
                                    import sys
                                    print(f"[ScanOrder] Mapping arama hatası: {e}", file=sys.stderr)
                                    import traceback
                                    traceback.print_exc(file=sys.stderr)
                                finally:
                                    try:
                                        db.close()
                                    except:
                                        pass
                        except ImportError as ie:
                            import sys
                            print(f"[ScanOrder] Mapping import hatası (ProductImageMapping modeli bulunamadı): {ie}", file=sys.stderr)
                        except Exception as e:
                            import sys
                            print(f"[ScanOrder] Mapping genel hatası: {e}", file=sys.stderr)
                            import traceback
                            traceback.print_exc(file=sys.stderr)
                except Exception as e:
                    import sys
                    print(f"[ScanOrder] Mapping dış hata: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc(file=sys.stderr)
            
            # Eğer görsel bulunamadıysa, Trendyol Public API'den çekmeyi dene
            if not product_images:
                product_code = line.get("productCode") or line.get("productId")
                content_id = line.get("contentId")
                barcode = line.get("barcode") or line.get("sku")
                
                if len(items) == 0:
                    import sys
                    print(f"[ScanOrder] Görsel bulunamadı, Public API'den çekiliyor...", file=sys.stderr)
                    print(f"[ScanOrder] productCode: {product_code}, contentId: {content_id}, barcode: {barcode}", file=sys.stderr)
                
                # Trendyol Public API - ürün detay sayfasından görselleri çek
                # Format: https://public.trendyol.com/discovery-web-productgw-service/api/product/{barcode}
                # veya: https://www.trendyol.com/api/discovery-web-productgw-service/api/product/{barcode}
                
                search_terms = []
                # contentId katalog ile en tutarlı eşleşme; barkod / stok kodu bazen public API'de yok
                if content_id:
                    search_terms.append(("contentId", str(content_id)))
                if barcode and str(barcode).strip() and str(barcode).strip().lower() != "merchantsku":
                    search_terms.append(("barcode", str(barcode).strip()))
                if product_code:
                    search_terms.append(("productCode", str(product_code)))
                
                for search_type, search_value in search_terms:
                    try:
                        # Public / discovery uçları (productDetail genelde tam içerik + görseller)
                        public_urls = [
                            f"https://public.trendyol.com/discovery-web-productgw-service/api/productDetail/{search_value}?storefrontId=1&culture=tr-TR",
                            f"https://public.trendyol.com/discovery-web-productgw-service/api/product/{search_value}",
                            f"https://www.trendyol.com/api/discovery-web-productgw-service/api/product/{search_value}",
                            f"https://public.trendyol.com/discovery-web-productgw-service/api/product-detail/{search_value}",
                        ]
                        
                        for public_url in public_urls:
                            try:
                                if len(items) == 0:
                                    import sys
                                    print(f"[ScanOrder] Public API deneniyor: {public_url}", file=sys.stderr)
                                
                                public_response = requests.get(
                                    public_url,
                                    headers={
                                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                        "Accept": "application/json",
                                        "Referer": "https://www.trendyol.com/"
                                    },
                                    timeout=10
                                )
                                
                                if public_response.status_code == 200:
                                    public_data = public_response.json()
                                    
                                    # Görselleri çıkar - farklı yapılar olabilir
                                    result = public_data.get("result", {}) or public_data.get("data", {}) or public_data
                                    
                                    # Tüm olası görsel alanlarını kontrol et
                                    image_fields = [
                                        "images", "imageUrls", "productImages", "mediaUrls",
                                        "imageList", "productImageList", "mediaList",
                                        "listingImages", "allImages", "alternativeImages",
                                    ]
                                    
                                    for img_field in image_fields:
                                        img_data = result.get(img_field)
                                        if img_data:
                                            if isinstance(img_data, list):
                                                for img in img_data:
                                                    if isinstance(img, str) and img.startswith("http") and img not in product_images:
                                                        product_images.append(img)
                                                        if len(items) == 0:
                                                            import sys
                                                            print(f"[ScanOrder] Public API'den görsel bulundu ({img_field}): {img[:100]}", file=sys.stderr)
                                                    elif isinstance(img, dict):
                                                        for img_key in ["url", "imageUrl", "src", "originalUrl", "zoomUrl", "thumbnailUrl", "image"]:
                                                            img_url = img.get(img_key)
                                                            if img_url and isinstance(img_url, str) and img_url.startswith("http") and img_url not in product_images:
                                                                product_images.append(img_url)
                                                                if len(items) == 0:
                                                                    import sys
                                                                    print(f"[ScanOrder] Public API'den görsel bulundu ({img_field}.{img_key}): {img_url[:100]}", file=sys.stderr)
                                            
                                            elif isinstance(img_data, str) and img_data.startswith("http") and img_data not in product_images:
                                                product_images.append(img_data)
                                                if len(items) == 0:
                                                    import sys
                                                    print(f"[ScanOrder] Public API'den görsel bulundu ({img_field}): {img_data[:100]}", file=sys.stderr)

                                    # JSON içinde gömülü tüm DSM CDN adresleri (iç içe yapılar)
                                    for u in _extract_dsmcdn_urls_from_json(public_data):
                                        if u not in product_images:
                                            product_images.append(u)
                                            if len(items) == 0:
                                                import sys
                                                print(f"[ScanOrder] Public API (dsmcdn tarama): {u[:100]}", file=sys.stderr)
                                    
                                    # Eğer görsel bulunduysa dur
                                    if product_images:
                                        if len(items) == 0:
                                            import sys
                                            print(f"[ScanOrder] Public API'den {len(product_images)} görsel bulundu ({search_type}: {search_value})", file=sys.stderr)
                                        break
                                        
                            except Exception as e:
                                if len(items) == 0:
                                    import sys
                                    print(f"[ScanOrder] Public API hatası ({public_url}): {e}", file=sys.stderr)
                                continue
                        
                        if product_images:
                            break
                            
                    except Exception as e:
                        import sys
                        print(f"[ScanOrder] Public API çekme hatası ({search_type}): {e}", file=sys.stderr)
                        continue
                
                if not product_images:
                    # Son çare: contentId ile bilinen CDN mnresize şablonları
                    cid = line.get("contentId")
                    for u in _cdn_urls_for_trendyol_content_id(cid):
                        try:
                            h = requests.head(
                                u,
                                timeout=4,
                                allow_redirects=True,
                                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                            )
                            if h.status_code == 200:
                                product_images.append(u)
                                break
                        except Exception:
                            continue
                    if not product_images:
                        fallback = _cdn_urls_for_trendyol_content_id(cid)
                        if fallback:
                            product_images.append(fallback[0])
                    if len(items) == 0 and not product_images:
                        import sys
                        print(f"[ScanOrder] Hiçbir kaynaktan görsel bulunamadı.", file=sys.stderr)
            
            # Model numarası ve beden bilgileri
            try:
                variant_attributes = line.get("variantAttributes", []) or line.get("attributes", []) or []
                if not isinstance(variant_attributes, list):
                    variant_attributes = []
            except Exception:
                variant_attributes = []
            
            model_number = None
            size = None
            color = None
            
            for attr in variant_attributes:
                attr_name = attr.get("attributeName", "").lower() if isinstance(attr, dict) else ""
                attr_value = attr.get("attributeValue", "") if isinstance(attr, dict) else ""
                
                if "beden" in attr_name or "size" in attr_name:
                    size = attr_value
                elif "renk" in attr_name or "color" in attr_name:
                    color = attr_value
                elif "model" in attr_name:
                    model_number = attr_value
            
            # Eğer variantAttributes yoksa, başka alanlardan dene
            if not model_number:
                model_number = line.get("productCode") or line.get("merchantSku") or line.get("stockCode") or ""
            
            try:
                quantity = line.get("quantity", 0) or 0
                try:
                    quantity = int(quantity)
                except (ValueError, TypeError):
                    quantity = 0
                
                price_value = line.get("price") or line.get("salePrice") or line.get("unitPrice") or 0
                try:
                    price = round(float(price_value), 2)
                except (ValueError, TypeError):
                    price = 0.0
                
                items.append({
                    "product_id": str(line.get("contentId") or line.get("productId") or line.get("product_id") or ""),
                    "product_name": line.get("productName") or line.get("product_name") or line.get("name", "Ürün"),
                    "quantity": quantity,
                    "price": price,
                    "images": product_images if product_images else [],
                    "model_number": model_number or "",
                    "size": size or "",
                    "color": color or "",
                    "barcode": line.get("barcode") or line.get("productBarcode") or "",
                    "sku": line.get("merchantSku") or line.get("stockCode") or line.get("productCode") or "",
                    "category": line.get("categoryName") or line.get("category", "")
                })
            except Exception as e:
                import sys
                print(f"[ScanOrder] Ürün ekleme hatası: {e}", file=sys.stderr)
                # Hatalı ürünü atla, diğerlerini eklemeye devam et
                continue
        
        # Toplam tutarı hesapla
        try:
            total_price = found_order.get("totalPrice") or found_order.get("totalPriceValue") or found_order.get("totalAmount") or 0.0
            if isinstance(total_price, str):
                total_price = float(total_price.replace(",", "."))
            else:
                total_price = float(total_price) if total_price else 0.0
        except (ValueError, TypeError):
            total_price = 0.0
        
        # Kargo bilgileri
        cargo_tracking = (
            found_order.get("cargoTrackingNumber") or 
            found_order.get("trackingNumber") or
            (found_order.get("shipment", {}).get("cargoTrackingNumber") if isinstance(found_order.get("shipment"), dict) else None) or
            ""
        )
        
        cargo_company = (
            found_order.get("cargoProviderName") or
            found_order.get("cargoCompany") or
            found_order.get("shipmentCompany") or
            None
        )
        
        return {
            "success": True,
            "order_id": str(order_id),
            "order_number": str(order_id),
            "order_date": order_date_formatted,
            "orderDate": order_date_str,
            "status": found_order.get("status") or found_order.get("orderStatus", ""),
            "total_amount": round(float(total_price), 2),
            "total_items": sum(item["quantity"] for item in items),
            "items": items,
            "customer": {
                "first_name": found_order.get("customerFirstName", ""),
                "last_name": found_order.get("customerLastName", ""),
                "email": found_order.get("customerEmail", ""),
                "phone": found_order.get("customerPhone", "")
            },
            "cargo": {
                "tracking_number": cargo_tracking,
                "company": cargo_company
            },
            "shipment": found_order.get("shipment", {})
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import sys
        import traceback
        error_details = traceback.format_exc()
        print(f"[ScanOrder] 500 Hatası: {str(e)}", file=sys.stderr)
        print(f"[ScanOrder] Traceback:\n{error_details}", file=sys.stderr)
        raise HTTPException(
            status_code=500,
            detail=f"Barkod okuma hatası: {str(e)}"
        )


@router.get("/")
async def barcode_info():
    return {"message": "Barcode operations endpoint"}

