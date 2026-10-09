"""
Database Repository - Veri erişim katmanı
"""
from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete, func, desc
from database.models import Product, Order, OrderLine, CompetitorPrice
from typing import List, Optional, Dict
from datetime import datetime, timedelta


class ProductRepository:
    """Ürün veritabanı işlemleri"""
    
    @staticmethod
    def get_all(db: Session, limit: Optional[int] = None) -> List[Product]:
        """Tüm ürünleri getir"""
        query = db.query(Product)
        if limit:
            query = query.limit(limit)
        return query.all()
    
    @staticmethod
    def get_by_id(db: Session, product_id: str) -> Optional[Product]:
        """ID'ye göre ürün getir"""
        return db.query(Product).filter(Product.product_id == product_id).first()
    
    @staticmethod
    def get_by_category(db: Session, category: str) -> List[Product]:
        """Kategoriye göre ürünleri getir"""
        return db.query(Product).filter(Product.category == category).all()
    
    @staticmethod
    def search(db: Session, search_term: str) -> List[Product]:
        """Ürün adında arama yap"""
        return db.query(Product).filter(
            Product.product_name.ilike(f"%{search_term}%")
        ).all()
    
    @staticmethod
    def get_price(db: Session, product_id: str) -> Optional[float]:
        """Ürün fiyatını getir"""
        product = ProductRepository.get_by_id(db, product_id)
        return product.current_price if product else None


class OrderRepository:
    """Sipariş veritabanı işlemleri"""
    
    @staticmethod
    def get_all(db: Session, limit: Optional[int] = None, days: Optional[int] = None) -> List[Order]:
        """Tüm siparişleri getir"""
        query = db.query(Order)
        
        if days:
            cutoff_date = datetime.now() - timedelta(days=days)
            query = query.filter(Order.order_date >= cutoff_date)
        
        if limit:
            query = query.limit(limit)
        
        return query.order_by(desc(Order.order_date)).all()
    
    @staticmethod
    def get_by_id(db: Session, order_id: str) -> Optional[Order]:
        """ID'ye göre sipariş getir"""
        return db.query(Order).filter(Order.order_id == order_id).first()
    
    @staticmethod
    def get_by_status(db: Session, status: str) -> List[Order]:
        """Duruma göre siparişleri getir"""
        return db.query(Order).filter(Order.status == status).all()
    
    @staticmethod
    def get_recent(db: Session, days: int = 7) -> List[Order]:
        """Son N günün siparişlerini getir"""
        cutoff_date = datetime.now() - timedelta(days=days)
        return db.query(Order).filter(
            Order.order_date >= cutoff_date
        ).order_by(desc(Order.order_date)).all()


class OrderLineRepository:
    """Sipariş satırı veritabanı işlemleri"""
    
    @staticmethod
    def get_by_order(db: Session, order_id: str) -> List[OrderLine]:
        """Siparişe ait satırları getir"""
        return db.query(OrderLine).filter(OrderLine.order_id == order_id).all()
    
    @staticmethod
    def get_by_product(db: Session, product_id: str) -> List[OrderLine]:
        """Ürüne ait sipariş satırlarını getir"""
        return db.query(OrderLine).filter(OrderLine.product_id == product_id).all()
    
    @staticmethod
    def get_product_sales(db: Session, product_id: str, days: Optional[int] = None) -> Dict:
        """Ürün satış istatistikleri"""
        query = db.query(OrderLine).filter(OrderLine.product_id == product_id)
        
        if days:
            cutoff_date = datetime.now() - timedelta(days=days)
            query = query.join(Order).filter(Order.order_date >= cutoff_date)
        
        lines = query.all()
        
        total_quantity = sum(line.quantity for line in lines)
        total_revenue = sum(line.total_price for line in lines)
        order_count = len(set(line.order_id for line in lines))
        
        return {
            "total_quantity": total_quantity,
            "total_revenue": total_revenue,
            "order_count": order_count,
            "average_price": total_revenue / total_quantity if total_quantity > 0 else 0
        }


class CompetitorPriceRepository:
    """Rakip fiyat veritabanı işlemleri"""
    
    @staticmethod
    def get_by_product(db: Session, product_id: str) -> List[CompetitorPrice]:
        """Ürüne ait rakip fiyatları getir"""
        return db.query(CompetitorPrice).filter(
            CompetitorPrice.product_id == product_id
        ).order_by(desc(CompetitorPrice.last_updated)).all()
    
    @staticmethod
    def upsert(db: Session, product_id: str, competitor_name: str, price: float, similarity_score: float = 0.0):
        """Rakip fiyatı ekle veya güncelle"""
        existing = db.query(CompetitorPrice).filter(
            CompetitorPrice.product_id == product_id,
            CompetitorPrice.competitor_name == competitor_name
        ).first()
        
        if existing:
            existing.price = price
            existing.similarity_score = similarity_score
            existing.last_updated = datetime.now()
        else:
            new_price = CompetitorPrice(
                product_id=product_id,
                competitor_name=competitor_name,
                price=price,
                similarity_score=similarity_score
            )
            db.add(new_price)
        
        db.commit()


