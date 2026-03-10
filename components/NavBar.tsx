'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAuth } from '@/lib/hooks/useAuth'
import { useNotifications } from '@/lib/hooks/useNotifications'

const navItems = [
  { href: '/dashboard', label: 'ホーム', icon: '🏠' },
  { href: '/users', label: '探す', icon: '🔍' },
  { href: '/matches', label: 'マッチ', icon: '🤝' },
  { href: '/notifications', label: '通知', icon: '🔔' },
]

export default function NavBar() {
  const pathname = usePathname()
  const { user, signOut } = useAuth()
  const { unreadCount } = useNotifications(user?.id)

  return (
    <>
      {/* PC サイドバー */}
      <nav className="hidden md:flex fixed left-0 top-0 h-full w-56 bg-white border-r border-gray-200 flex-col z-50">
        <div className="p-6">
          <h1 className="text-xl font-bold text-amber-600">Friend Match</h1>
          <p className="text-xs text-gray-400 mt-1">社内友達マッチング</p>
        </div>
        <div className="flex-1 px-3 space-y-1">
          {navItems.map(item => (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm transition-colors ${
                pathname.startsWith(item.href)
                  ? 'bg-amber-50 text-amber-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              <span className="text-lg">{item.icon}</span>
              <span>{item.label}</span>
              {item.href === '/notifications' && unreadCount > 0 && (
                <span className="ml-auto bg-red-500 text-white text-xs rounded-full px-2 py-0.5 min-w-[20px] text-center">
                  {unreadCount}
                </span>
              )}
            </Link>
          ))}
        </div>
        <div className="p-3 border-t border-gray-200">
          <Link
            href={user ? `/profile/${user.id}` : '#'}
            className="flex items-center gap-3 px-4 py-3 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
          >
            <span className="text-lg">👤</span>
            <span>マイページ</span>
          </Link>
          <button
            onClick={signOut}
            className="flex items-center gap-3 px-4 py-3 rounded-lg text-sm text-gray-400 hover:bg-gray-50 w-full text-left"
          >
            <span className="text-lg">🚪</span>
            <span>ログアウト</span>
          </button>
        </div>
      </nav>

      {/* モバイル ボトムナビ */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 z-50 safe-bottom">
        <div className="flex justify-around py-2">
          {navItems.map(item => (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-col items-center gap-0.5 px-3 py-1 text-xs relative ${
                pathname.startsWith(item.href)
                  ? 'text-amber-600'
                  : 'text-gray-400'
              }`}
            >
              <span className="text-xl">{item.icon}</span>
              <span>{item.label}</span>
              {item.href === '/notifications' && unreadCount > 0 && (
                <span className="absolute -top-1 right-0 bg-red-500 text-white text-[10px] rounded-full w-5 h-5 flex items-center justify-center">
                  {unreadCount}
                </span>
              )}
            </Link>
          ))}
          <Link
            href={user ? `/profile/${user.id}` : '#'}
            className={`flex flex-col items-center gap-0.5 px-3 py-1 text-xs ${
              pathname.startsWith('/profile') ? 'text-amber-600' : 'text-gray-400'
            }`}
          >
            <span className="text-xl">👤</span>
            <span>マイページ</span>
          </Link>
        </div>
      </nav>
    </>
  )
}
