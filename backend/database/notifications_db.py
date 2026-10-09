"""
Bildirim Veritabanı Yönetimi
SQLite kullanarak bildirim geçmişini saklar
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'notifications.db')

def get_db_connection():
    """Veritabanı bağlantısı oluştur"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Veritabanını başlat"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            priority TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            read INTEGER DEFAULT 0,
            action_url TEXT,
            metadata TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_timestamp ON notifications(timestamp DESC)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_read ON notifications(read)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_type ON notifications(type)
    ''')
    
    conn.commit()
    conn.close()

def save_notification(notification: Dict[str, Any]) -> bool:
    """Bildirimi kaydet"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO notifications 
            (id, type, title, message, priority, timestamp, read, action_url, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            notification.get('id'),
            notification.get('type'),
            notification.get('title'),
            notification.get('message'),
            notification.get('priority'),
            notification.get('timestamp'),
            1 if notification.get('read', False) else 0,
            notification.get('action_url'),
            json.dumps(notification.get('metadata', {}))
        ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Bildirim kaydetme hatası: {str(e)}")
        return False

def get_notifications(
    limit: int = 100,
    offset: int = 0,
    type_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
    read_filter: Optional[bool] = None,
    search_query: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Bildirimleri getir (filtreleme ile)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM notifications WHERE 1=1"
        params = []
        
        if type_filter:
            query += " AND type = ?"
            params.append(type_filter)
        
        if priority_filter:
            query += " AND priority = ?"
            params.append(priority_filter)
        
        if read_filter is not None:
            query += " AND read = ?"
            params.append(1 if read_filter else 0)
        
        if search_query:
            query += " AND (title LIKE ? OR message LIKE ?)"
            params.extend([f"%{search_query}%", f"%{search_query}%"])
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        notifications = []
        for row in rows:
            notification = dict(row)
            notification['read'] = bool(notification['read'])
            if notification.get('metadata'):
                try:
                    notification['metadata'] = json.loads(notification['metadata'])
                except:
                    notification['metadata'] = {}
            notifications.append(notification)
        
        conn.close()
        return notifications
    except Exception as e:
        print(f"Bildirim getirme hatası: {str(e)}")
        return []

def mark_as_read(notification_id: str) -> bool:
    """Bildirimi okundu olarak işaretle"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE notifications SET read = 1 WHERE id = ?', (notification_id,))
        
        conn.commit()
        conn.close()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Bildirim okundu işaretleme hatası: {str(e)}")
        return False

def mark_all_as_read() -> int:
    """Tüm bildirimleri okundu olarak işaretle"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE notifications SET read = 1 WHERE read = 0')
        
        conn.commit()
        count = cursor.rowcount
        conn.close()
        return count
    except Exception as e:
        print(f"Tüm bildirimleri okundu işaretleme hatası: {str(e)}")
        return 0

def delete_notifications(notification_ids: List[str]) -> int:
    """Bildirimleri sil"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        placeholders = ','.join(['?'] * len(notification_ids))
        cursor.execute(f'DELETE FROM notifications WHERE id IN ({placeholders})', notification_ids)
        
        conn.commit()
        count = cursor.rowcount
        conn.close()
        return count
    except Exception as e:
        print(f"Bildirim silme hatası: {str(e)}")
        return 0

def get_notification_stats() -> Dict[str, Any]:
    """Bildirim istatistikleri"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Toplam bildirim sayısı
        cursor.execute('SELECT COUNT(*) as total FROM notifications')
        total = cursor.fetchone()['total']
        
        # Okunmamış bildirim sayısı
        cursor.execute('SELECT COUNT(*) as unread FROM notifications WHERE read = 0')
        unread = cursor.fetchone()['unread']
        
        # Tip bazında sayılar
        cursor.execute('SELECT type, COUNT(*) as count FROM notifications GROUP BY type')
        type_counts = {row['type']: row['count'] for row in cursor.fetchall()}
        
        # Öncelik bazında sayılar
        cursor.execute('SELECT priority, COUNT(*) as count FROM notifications GROUP BY priority')
        priority_counts = {row['priority']: row['count'] for row in cursor.fetchall()}
        
        # Günlük bildirim sayıları (son 7 gün)
        cursor.execute('''
            SELECT DATE(timestamp) as date, COUNT(*) as count 
            FROM notifications 
            WHERE timestamp >= datetime('now', '-7 days')
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        ''')
        daily_counts = [{'date': row['date'], 'count': row['count']} for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            'total': total,
            'unread': unread,
            'read': total - unread,
            'type_counts': type_counts,
            'priority_counts': priority_counts,
            'daily_counts': daily_counts
        }
    except Exception as e:
        print(f"İstatistik getirme hatası: {str(e)}")
        return {
            'total': 0,
            'unread': 0,
            'read': 0,
            'type_counts': {},
            'priority_counts': {},
            'daily_counts': []
        }

# Veritabanını başlat
init_db()











