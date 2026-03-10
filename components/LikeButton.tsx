'use client'

import { useState } from 'react'
import { createClient } from '@/lib/supabase'

interface LikeButtonProps {
  fromUserId: string
  toUserId: string
  initialLiked: boolean
  onToggle?: (liked: boolean) => void
}

export default function LikeButton({ fromUserId, toUserId, initialLiked, onToggle }: LikeButtonProps) {
  const [liked, setLiked] = useState(initialLiked)
  const [loading, setLoading] = useState(false)
  const supabase = createClient()

  const handleToggle = async () => {
    setLoading(true)
    if (liked) {
      await supabase
        .from('likes')
        .delete()
        .eq('from_user_id', fromUserId)
        .eq('to_user_id', toUserId)
      setLiked(false)
      onToggle?.(false)
    } else {
      await supabase
        .from('likes')
        .insert({ from_user_id: fromUserId, to_user_id: toUserId })
      setLiked(true)
      onToggle?.(true)
    }
    setLoading(false)
  }

  return (
    <button
      onClick={handleToggle}
      disabled={loading}
      className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
        liked
          ? 'bg-amber-100 text-amber-700 border border-amber-300 hover:bg-amber-200'
          : 'bg-amber-500 text-white hover:bg-amber-600'
      } disabled:opacity-50`}
    >
      {liked ? '✓ いいね済み' : '♡ いいね'}
    </button>
  )
}
