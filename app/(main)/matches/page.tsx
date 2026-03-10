'use client'

import Link from 'next/link'
import { useAuth } from '@/lib/hooks/useAuth'
import { useMatches } from '@/lib/hooks/useMatches'

export default function MatchesPage() {
  const { user } = useAuth()
  const { matches, loading } = useMatches(user?.id)

  if (loading) {
    return <div className="flex items-center justify-center min-h-screen"><p className="text-gray-400">読み込み中...</p></div>
  }

  return (
    <div className="max-w-2xl mx-auto px-4 pt-8">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">マッチング一覧</h1>

      {matches.length === 0 ? (
        <div className="text-center py-16">
          <span className="text-5xl block mb-4">🤝</span>
          <p className="text-gray-400 mb-2">まだマッチングがありません</p>
          <Link href="/users" className="text-amber-600 hover:underline text-sm">仲間を探す →</Link>
        </div>
      ) : (
        <div className="space-y-3">
          {matches.map(match => {
            const partner = match.partner
            const matchDate = new Date(match.created_at).toLocaleDateString('ja-JP', {
              year: 'numeric', month: 'short', day: 'numeric'
            })

            return (
              <div key={match.id} className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 hover:shadow-md transition-shadow">
                <div className="flex items-center gap-4">
                  <Link href={`/profile/${partner?.user_id}`} className="flex-shrink-0">
                    <div className="w-14 h-14 rounded-full bg-amber-100 flex items-center justify-center overflow-hidden">
                      {partner?.avatar_url ? (
                        <img src={partner.avatar_url} alt="" className="w-full h-full object-cover" />
                      ) : (
                        <span className="text-2xl">👤</span>
                      )}
                    </div>
                  </Link>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-gray-800 truncate">{partner?.name || '???'}</h3>
                    <p className="text-sm text-gray-500">{partner?.department}</p>
                    <p className="text-xs text-gray-400 mt-0.5">マッチ日: {matchDate}</p>
                  </div>
                  <Link
                    href={`/chat/${match.id}`}
                    className="px-4 py-2 bg-amber-500 text-white rounded-full text-sm font-medium hover:bg-amber-600 transition-colors flex-shrink-0"
                  >
                    チャット
                  </Link>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
