'use client'

import { useAuth } from '@/lib/hooks/useAuth'
import { useNotifications } from '@/lib/hooks/useNotifications'
import NotificationItem from '@/components/NotificationItem'

export default function NotificationsPage() {
  const { user } = useAuth()
  const { notifications, unreadCount, markAsRead, markAllAsRead } = useNotifications(user?.id)

  return (
    <div className="max-w-2xl mx-auto px-4 pt-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">通知</h1>
        {unreadCount > 0 && (
          <button
            onClick={markAllAsRead}
            className="text-sm text-amber-600 hover:underline"
          >
            すべて既読にする
          </button>
        )}
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        {notifications.length === 0 ? (
          <div className="text-center py-16">
            <span className="text-4xl block mb-2">🔔</span>
            <p className="text-gray-400">通知はまだありません</p>
          </div>
        ) : (
          notifications.map(n => (
            <NotificationItem
              key={n.id}
              notification={n}
              onMarkRead={markAsRead}
            />
          ))
        )}
      </div>
    </div>
  )
}
