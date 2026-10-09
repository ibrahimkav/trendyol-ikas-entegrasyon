"""
SEO ve Ürün Optimizasyonu Router
AI destekli SEO önerileri ve ürün optimizasyonu
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import os

router = APIRouter(prefix="/seo", tags=["SEO Optimization"])

# Groq API client (opsiyonel)
try:
    from groq import Groq
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY")) if os.getenv("GROQ_API_KEY") else None
except ImportError:
    groq_client = None
    if os.getenv("GROQ_API_KEY"):
        print("⚠️ Groq paketi yüklü değil. 'pip install groq' komutu ile yükleyin.")


class SEOAnalysisRequest(BaseModel):
    """SEO analizi isteği"""
    product_id: str
    product_name: str
    product_description: Optional[str] = None
    category: Optional[str] = None
    current_keywords: Optional[List[str]] = None


class SEORecommendation(BaseModel):
    """SEO önerisi"""
    type: str  # "title", "description", "keyword", "image", etc.
    priority: str  # "high", "medium", "low"
    current_value: Optional[str] = None
    recommended_value: str
    reason: str
    impact_score: float  # 0-100


class SEOAnalysisResponse(BaseModel):
    """SEO analizi yanıtı"""
    product_id: str
    product_name: str
    seo_score: float  # 0-100
    recommendations: List[SEORecommendation]
    keyword_suggestions: List[str]
    competitor_analysis: Optional[Dict[str, Any]] = None
    created_at: str


class ProductOptimizationRequest(BaseModel):
    """Ürün optimizasyonu isteği"""
    product_id: str
    product_name: str
    product_description: Optional[str] = None
    category: Optional[str] = None
    target_audience: Optional[str] = None


class OptimizedProduct(BaseModel):
    """Optimize edilmiş ürün bilgileri"""
    product_id: str
    optimized_title: str
    optimized_description: str
    suggested_keywords: List[str]
    seo_score: float
    improvements: List[str]
    created_at: str


def calculate_seo_score(
    title: str,
    description: Optional[str] = None,
    keywords: Optional[List[str]] = None
) -> float:
    """
    SEO skoru hesaplar (0-100)
    """
    score = 0.0
    
    # Başlık analizi (40 puan)
    if title:
        title_length = len(title)
        if 30 <= title_length <= 60:
            score += 20  # Optimal uzunluk
        elif 20 <= title_length < 30 or 60 < title_length <= 70:
            score += 15  # İyi
        else:
            score += 5  # Çok kısa veya uzun
        
        # Anahtar kelime başlıkta mı?
        if keywords:
            keyword_in_title = any(kw.lower() in title.lower() for kw in keywords)
            if keyword_in_title:
                score += 20
        else:
            score += 10  # Anahtar kelime yoksa kısmi puan
    
    # Açıklama analizi (40 puan)
    if description:
        desc_length = len(description)
        if 120 <= desc_length <= 300:
            score += 20  # Optimal uzunluk
        elif 80 <= desc_length < 120 or 300 < desc_length <= 400:
            score += 15
        else:
            score += 5
        
        # Anahtar kelime açıklamada mı?
        if keywords:
            keyword_in_desc = any(kw.lower() in description.lower() for kw in keywords)
            if keyword_in_desc:
                score += 20
        else:
            score += 10
    
    # Anahtar kelime analizi (20 puan)
    if keywords and len(keywords) >= 3:
        score += 20
    elif keywords and len(keywords) >= 1:
        score += 10
    
    return min(score, 100.0)


async def get_ai_seo_recommendations(
    product_name: str,
    product_description: Optional[str] = None,
    category: Optional[str] = None,
    current_keywords: Optional[List[str]] = None
) -> List[SEORecommendation]:
    """
    AI destekli SEO önerileri alır
    """
    recommendations = []
    
    # Kural tabanlı öneriler
    # Başlık önerileri
    title_length = len(product_name) if product_name else 0
    if title_length < 30:
        recommendations.append(SEORecommendation(
            type="title",
            priority="high",
            current_value=product_name,
            recommended_value=f"{product_name} - En İyi Fiyat ve Kalite Garantisi",
            reason="Başlık çok kısa. SEO için 30-60 karakter arası önerilir.",
            impact_score=25.0
        ))
    elif title_length > 60:
        recommendations.append(SEORecommendation(
            type="title",
            priority="medium",
            current_value=product_name,
            recommended_value=product_name[:60].strip(),
            reason="Başlık çok uzun. 60 karakterden kısa olmalı.",
            impact_score=15.0
        ))
    
    # Açıklama önerileri
    if not product_description or len(product_description) < 120:
        recommendations.append(SEORecommendation(
            type="description",
            priority="high",
            current_value=product_description or "Yok",
            recommended_value=f"{product_name} hakkında detaylı bilgi. Yüksek kalite, uygun fiyat ve hızlı kargo ile kapınızda. Müşteri memnuniyeti garantisi.",
            reason="Ürün açıklaması eksik veya çok kısa. SEO için 120-300 karakter arası önerilir.",
            impact_score=30.0
        ))
    elif len(product_description) > 300:
        recommendations.append(SEORecommendation(
            type="description",
            priority="medium",
            current_value=product_description[:100] + "...",
            recommended_value=product_description[:300].strip(),
            reason="Açıklama çok uzun. 300 karakterden kısa olmalı.",
            impact_score=10.0
        ))
    
    # Anahtar kelime önerileri
    if not current_keywords or len(current_keywords) < 3:
        suggested_keywords = []
        if category:
            suggested_keywords.append(category.lower())
        if product_name:
            words = product_name.lower().split()
            suggested_keywords.extend([w for w in words if len(w) > 3][:3])
        
        recommendations.append(SEORecommendation(
            type="keyword",
            priority="high",
            current_value=", ".join(current_keywords) if current_keywords else "Yok",
            recommended_value=", ".join(suggested_keywords[:5]),
            reason="Yeterli anahtar kelime yok. En az 3-5 anahtar kelime önerilir.",
            impact_score=20.0
        ))
    
    # AI önerileri (Groq API varsa)
    if groq_client:
        try:
            prompt = f"""
            Trendyol satıcısı için SEO önerileri yap:
            
            Ürün: {product_name}
            Kategori: {category or "Belirtilmemiş"}
            Mevcut Açıklama: {product_description or "Yok"}
            Mevcut Anahtar Kelimeler: {", ".join(current_keywords) if current_keywords else "Yok"}
            
            Şu konularda öneriler yap:
            1. Başlık optimizasyonu (30-60 karakter)
            2. Açıklama optimizasyonu (120-300 karakter)
            3. Anahtar kelime önerileri (5-7 kelime)
            4. Görsel alt text önerileri
            
            Kısa ve öz öneriler yap. Türkçe yanıt ver.
            """
            
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "Sen bir e-ticaret SEO uzmanısın. Türkçe yanıt ver."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.7
            )
            
            ai_suggestions = response.choices[0].message.content
            
            # AI önerilerini parse et ve ekle
            if "başlık" in ai_suggestions.lower() or "title" in ai_suggestions.lower():
                recommendations.append(SEORecommendation(
                    type="title",
                    priority="medium",
                    current_value=product_name,
                    recommended_value=product_name,  # AI'dan gelen öneri parse edilebilir
                    reason=f"AI Önerisi: {ai_suggestions[:200]}",
                    impact_score=15.0
                ))
        except Exception as e:
            print(f"⚠️ Groq API hatası: {e}")
    
    return recommendations


@router.post("/analyze", response_model=SEOAnalysisResponse)
async def analyze_seo(request: SEOAnalysisRequest):
    """
    Ürün için SEO analizi yapar ve öneriler sunar
    """
    try:
        # SEO skoru hesapla
        seo_score = calculate_seo_score(
            request.product_name,
            request.product_description,
            request.current_keywords
        )
        
        # AI önerileri al
        recommendations = await get_ai_seo_recommendations(
            request.product_name,
            request.product_description,
            request.category,
            request.current_keywords
        )
        
        # Anahtar kelime önerileri
        keyword_suggestions = []
        if request.category:
            keyword_suggestions.append(request.category.lower())
        if request.product_name:
            words = request.product_name.lower().split()
            keyword_suggestions.extend([w for w in words if len(w) > 3])
        
        # Rakip analizi (basit)
        competitor_analysis = None
        if request.category:
            competitor_analysis = {
                "category": request.category,
                "avg_title_length": 45,
                "avg_description_length": 200,
                "common_keywords": keyword_suggestions[:5]
            }
        
        return SEOAnalysisResponse(
            product_id=request.product_id,
            product_name=request.product_name,
            seo_score=seo_score,
            recommendations=recommendations,
            keyword_suggestions=keyword_suggestions[:10],
            competitor_analysis=competitor_analysis,
            created_at=datetime.now().isoformat()
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"SEO analizi hatası: {str(e)}"
        )


@router.post("/optimize", response_model=OptimizedProduct)
async def optimize_product(request: ProductOptimizationRequest):
    """
    Ürün bilgilerini AI ile optimize eder
    """
    try:
        # Optimize edilmiş başlık
        optimized_title = request.product_name
        if len(optimized_title) < 30:
            optimized_title = f"{optimized_title} - En İyi Fiyat ve Kalite"
        elif len(optimized_title) > 60:
            optimized_title = optimized_title[:60].strip()
        
        # Optimize edilmiş açıklama
        optimized_description = request.product_description or ""
        if len(optimized_description) < 120:
            optimized_description = f"{request.product_name} hakkında detaylı bilgi. Yüksek kalite, uygun fiyat ve hızlı kargo ile kapınızda. Müşteri memnuniyeti garantisi. {request.category or ''} kategorisinde en çok tercih edilen ürünlerden biri."
        elif len(optimized_description) > 300:
            optimized_description = optimized_description[:300].strip()
        
        # Anahtar kelime önerileri
        suggested_keywords = []
        if request.category:
            suggested_keywords.append(request.category.lower())
        if request.product_name:
            words = request.product_name.lower().split()
            suggested_keywords.extend([w for w in words if len(w) > 3][:5])
        
        # SEO skoru
        seo_score = calculate_seo_score(
            optimized_title,
            optimized_description,
            suggested_keywords
        )
        
        # İyileştirmeler
        improvements = []
        if len(request.product_name) != len(optimized_title):
            improvements.append("Başlık uzunluğu optimize edildi")
        if request.product_description != optimized_description:
            improvements.append("Açıklama optimize edildi")
        if not request.current_keywords or len(request.current_keywords) < len(suggested_keywords):
            improvements.append("Anahtar kelimeler eklendi")
        
        # AI optimizasyonu (Groq API varsa)
        if groq_client:
            try:
                prompt = f"""
                Trendyol ürünü için optimize edilmiş başlık ve açıklama öner:
                
                Ürün: {request.product_name}
                Kategori: {request.category or "Belirtilmemiş"}
                Hedef Kitle: {request.target_audience or "Genel"}
                
                SEO kurallarına uygun:
                - Başlık: 30-60 karakter
                - Açıklama: 120-300 karakter
                - Anahtar kelimeleri doğal şekilde kullan
                
                Türkçe yanıt ver. Sadece başlık ve açıklama öner.
                """
                
                response = groq_client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": "Sen bir e-ticaret SEO uzmanısın. Türkçe yanıt ver."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=200,
                    temperature=0.7
                )
                
                ai_suggestion = response.choices[0].message.content
                # AI önerisini parse et (basit)
                if "başlık" in ai_suggestion.lower():
                    lines = ai_suggestion.split("\n")
                    for line in lines:
                        if len(line) > 20 and len(line) < 70:
                            optimized_title = line.strip()
                            break
                
                improvements.append("AI destekli optimizasyon uygulandı")
            except Exception as e:
                print(f"⚠️ Groq API hatası: {e}")
        
        return OptimizedProduct(
            product_id=request.product_id,
            optimized_title=optimized_title,
            optimized_description=optimized_description,
            suggested_keywords=suggested_keywords,
            seo_score=seo_score,
            improvements=improvements,
            created_at=datetime.now().isoformat()
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ürün optimizasyonu hatası: {str(e)}"
        )


@router.get("/keywords/{category}")
async def get_keyword_suggestions(category: str):
    """
    Kategoriye göre anahtar kelime önerileri
    """
    # Basit anahtar kelime önerileri
    keyword_map = {
        "giyim": ["moda", "trend", "stil", "kombin", "outfit"],
        "elektronik": ["teknoloji", "akıllı", "hızlı", "kaliteli", "garantili"],
        "ev": ["dekorasyon", "şık", "modern", "pratik", "kaliteli"],
        "kozmetik": ["doğal", "organik", "sağlıklı", "etkili", "güvenli"],
    }
    
    category_lower = category.lower()
    suggestions = keyword_map.get(category_lower, ["kaliteli", "uygun fiyat", "hızlı kargo", "güvenli alışveriş"])
    
    return {
        "category": category,
        "suggestions": suggestions,
        "total": len(suggestions)
    }




