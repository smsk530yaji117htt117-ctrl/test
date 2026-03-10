'use client'

import Link from 'next/link'
import type { Notification } from '@/lib/types'

interface NotificationItemProps {
  notification: Notification
  onMarkRead: (id: string) => void
}

export default function NotificationItem({ notification, onMarkRead }: NotificationItemProps) {
  const isMatch = notification.type === 'match'
  const icon = isMatch ? '🎉' : '💬'
  const text = isMatch ? '新しいマッチングが成立しました！' : '新しいメッセージが届きました'
  const href = isMatch ? '/matches' : `/chat/${notification.ref_id}`
  const time = new Date(notification.created_at).toLocaleString('ja-JP', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
  })

  return (
    <Link
      href={href}
      onClick={() => !notification.is_read && onMarkRead(notification.id)}
      className={`block p-4 border-b border-gray-100 transition-colors ${
        notification.is_read ? 'bg-white' : 'bg-amber-50'
      } hover:bg-gray-50`}
    >
      <div className="flex items-start gap-3">
        <span className="text-2xl flex-shrink-0">{icon}</span>
        <div className="min-w-0 flex-1">
          <p className={`text-sm ${notification.is_read ? 'text-gray-600' : 'text-gray-800 font-medium'}`}>
            {text}
          </p>
          <p className="text-xs text-gray-400 mt-1">{time}</p>
        </div>
        {!notification.is_read && (
          <span className="w-2.5 h-2.5 bg-amber-500 rounded-full flex-shrink-0 mt-1.5" />
        )}
      </div>
    </Link>
  )
}
