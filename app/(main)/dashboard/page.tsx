'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/lib/hooks/useAuth'
import { useProfile } from '@/lib/hooks/useProfile'
import { useMatches } from '@/lib/hooks/useMatches'
import { useNotifications } from '@/lib/hooks/useNotifications'
import { useRouter } from 'next/navigation'

export default function DashboardPage() {
  const { user, loading: authLoading } = useAuth()
  const { profile, loading: profileLoading } = useProfile(user?.id)
  const { matches } = useMatches(user?.id)
  const { unreadCount } = useNotifications(user?.id)
  const router = useRouter()
  const [mounted, setMounted] = useState(false)

  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    if (!authLoading && !profileLoading && user && !profile) {
      router.push('/onboarding')
    }
  }, [authLoading, profileLoading, user, profile, router])

  if (!mounted || authLoading || profileLoading) {
    return <div className="flex items-center justify-center min-h-screen"><p className="text-gray-400">読み込み中...</p></div>
  }

  if (!profile) return null

  return (
    <div className="max-w-2xl mx-auto px-4 pt-8">
      {/* ウェルカム */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 mb-6">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-amber-100 flex items-center justify-center overflow-hidden flex-shrink-0">
            {profile.avatar_url ? (
              <img src={profile.avatar_url} alt="" className="w-full h-full object-cover" />
            ) : (
              <span className="text-3xl">👤</span>
            )}
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-800">
              こんにちは、{profile.name}さん！
            </h1>
            <p className="text-sm text-gray-500">{profile.department}</p>
          </div>
        </div>
      </div>

      {/* クイックアクション */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <Link
          href="/users"
          className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 hover:shadow-md transition-shadow text-center"
        >
          <span className="text-3xl block mb-2">🔍</span>
          <span className="text-sm font-medium text-gray-700">仲間を探す</span>
        </Link>
        <Link
          href="/matches"
          className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 hover:shadow-md transition-shadow text-center relative"
        >
          <span className="text-3xl block mb-2">🤝</span>
          <span className="text-sm font-medium text-gray-700">マッチ一覧</span>
          {matches.length > 0 && (
            <span className="absolute top-3 right-3 bg-amber-500 text-white text-xs rounded-full px-2 py-0.5">
              {matches.length}
            </span>
          )}
        </Link>
        <Link
          href="/notifications"
          className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 hover:shadow-md transition-shadow text-center relative"
        >
          <span className="text-3xl block mb-2">🔔</span>
          <span className="text-sm font-medium text-gray-700">通知</span>
          {unreadCount > 0 && (
            <span className="absolute top-3 right-3 bg-red-500 text-white text-xs rounded-full px-2 py-0.5">
              {unreadCount}
            </span>
          )}
        </Link>
        <Link
          href={`/profile/${user?.id}`}
          className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 hover:shadow-md transition-shadow text-center"
        >
          <span className="text-3xl block mb-2">✏️</span>
          <span className="text-sm font-medium text-gray-700">プロフィール</span>
        </Link>
      </div>

      {/* 最近のマッチ */}
      {matches.length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">最近のマッチ</h2>
          <div className="flex gap-4 overflow-x-auto pb-2">
            {matches.slice(0, 5).map(match => (
              <Link
                key={match.id}
                href={`/chat/${match.id}`}
                className="flex-shrink-0 flex flex-col items-center gap-2"
              >
                <div className="w-14 h-14 rounded-full bg-amber-100 flex items-center justify-center overflow-hidden">
                  {match.partner?.avatar_url ? (
                    <img src={match.partner.avatar_url} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <span className="text-xl">👤</span>
                  )}
                </div>
                <span className="text-xs text-gray-600 w-16 text-center truncate">
                  {match.partner?.name || '???'}
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
