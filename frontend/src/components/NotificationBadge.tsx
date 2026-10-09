import { useState, useEffect } from 'react'
import apiClient from '../config/api'

interface NotificationBadgeProps {
  className?: string
}

export default function NotificationBadge({ className = '' }: NotificationBadgeProps) {
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    const fetchUnreadCount = async () => {
      try {
        const response = await apiClient.get('/notifications/')
        setUnreadCount(response.data.unread_count || 0)
      } catch (err) {
        console.error('Bildirim sayısı alınamadı:', err)
      }
    }

    fetchUnreadCount()
    // Her 10 saniyede bir güncelle
    const interval = setInterval(fetchUnreadCount, 10000)
    return () => clearInterval(interval)
  }, [])

  if (unreadCount === 0) return null

  return (
    <span
      className={`absolute -top-1 -right-1 bg-red-500 text-white text-xs font-bold rounded-full h-5 w-5 flex items-center justify-center ${className}`}
    >
      {unreadCount > 99 ? '99+' : unreadCount}
    </span>
  )
}


