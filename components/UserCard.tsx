'use client'

import Link from 'next/link'
import type { Profile } from '@/lib/types'
import TagBadge from './TagBadge'
import LikeButton from './LikeButton'

interface UserCardProps {
  profile: Profile
  currentUserId: string
  isLiked: boolean
}

export default function UserCard({ profile, currentUserId, isLiked }: UserCardProps) {
  const isMe = profile.user_id === currentUserId

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 hover:shadow-md transition-shadow">
      <Link href={`/profile/${profile.user_id}`} className="block">
        <div className="flex items-center gap-4 mb-3">
          <div className="w-14 h-14 rounded-full bg-amber-100 flex items-center justify-center overflow-hidden flex-shrink-0">
            {profile.avatar_url ? (
              <img src={profile.avatar_url} alt="" className="w-full h-full object-cover" />
            ) : (
              <span className="text-2xl">👤</span>
            )}
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-gray-800 truncate">{profile.name || '未設定'}</h3>
            <p className="text-sm text-gray-500">{profile.department || '部署未設定'}</p>
          </div>
        </div>
        {profile.bio && (
          <p className="text-sm text-gray-600 mb-3 line-clamp-2">{profile.bio}</p>
        )}
        {profile.tags && profile.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-3">
            {profile.tags.slice(0, 4).map(tag => (
              <TagBadge key={tag.id} name={tag.name} />
            ))}
            {profile.tags.length > 4 && (
              <span className="text-xs text-gray-400 self-center">+{profile.tags.length - 4}</span>
            )}
          </div>
        )}
      </Link>
      {!isMe && (
        <div className="pt-2 border-t border-gray-50">
          <LikeButton
            fromUserId={currentUserId}
            toUserId={profile.user_id}
            initialLiked={isLiked}
          />
        </div>
      )}
    </div>
  )
}
