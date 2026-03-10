'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useAuth } from '@/lib/hooks/useAuth'
import { useProfile } from '@/lib/hooks/useProfile'
import LikeButton from '@/components/LikeButton'
import TagBadge from '@/components/TagBadge'
import Link from 'next/link'
import { createClient } from '@/lib/supabase'

export default function ProfileDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const { profile, loading } = useProfile(id)
  const [isLiked, setIsLiked] = useState(false)
  const router = useRouter()
  const supabase = createClient()
  const isMe = user?.id === id

  useEffect(() => {
    if (!user || isMe) return
    const checkLike = async () => {
      const { data } = await supabase
        .from('likes')
        .select('id')
        .eq('from_user_id', user.id)
        .eq('to_user_id', id)
        .maybeSingle()
      setIsLiked(!!data)
    }
    checkLike()
  }, [user, id, isMe, supabase])

  if (loading) {
    return <div className="flex items-center justify-center min-h-screen"><p className="text-gray-400">読み込み中...</p></div>
  }

  if (!profile) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <p className="text-gray-400 mb-4">プロフィールが見つかりません</p>
          <button onClick={() => router.back()} className="text-amber-600 hover:underline text-sm">戻る</button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-xl mx-auto px-4 pt-8">
      <button onClick={() => router.back()} className="text-sm text-gray-500 hover:text-gray-700 mb-6 block">
        ← 戻る
      </button>

      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
        {/* アバター + 基本情報 */}
        <div className="flex flex-col items-center mb-6">
          <div className="w-28 h-28 rounded-full bg-amber-100 flex items-center justify-center overflow-hidden mb-4">
            {profile.avatar_url ? (
              <img src={profile.avatar_url} alt="" className="w-full h-full object-cover" />
            ) : (
              <span className="text-5xl">👤</span>
            )}
          </div>
          <h1 className="text-2xl font-bold text-gray-800">{profile.name}</h1>
          <p className="text-gray-500">{profile.department || '部署未設定'}</p>
        </div>

        {/* 自己紹介 */}
        {profile.bio && (
          <div className="mb-6">
            <h2 className="text-sm font-medium text-gray-500 mb-2">自己紹介</h2>
            <p className="text-gray-700 whitespace-pre-wrap">{profile.bio}</p>
          </div>
        )}

        {/* タグ */}
        {profile.tags && profile.tags.length > 0 && (
          <div className="mb-6">
            <h2 className="text-sm font-medium text-gray-500 mb-2">興味・趣味</h2>
            <div className="flex flex-wrap gap-2">
              {profile.tags.map(tag => (
                <TagBadge key={tag.id} name={tag.name} />
              ))}
            </div>
          </div>
        )}

        {/* アクション */}
        <div className="pt-4 border-t border-gray-100 flex justify-center gap-3">
          {isMe ? (
            <Link
              href="/profile/edit"
              className="px-6 py-2 bg-amber-500 text-white rounded-full text-sm font-medium hover:bg-amber-600 transition-colors"
            >
              プロフィールを編集
            </Link>
          ) : user && (
            <LikeButton
              fromUserId={user.id}
              toUserId={id}
              initialLiked={isLiked}
            />
          )}
        </div>
      </div>
    </div>
  )
}
