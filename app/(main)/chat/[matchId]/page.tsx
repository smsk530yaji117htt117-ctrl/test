'use client'

import { useState, useRef, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useAuth } from '@/lib/hooks/useAuth'
import { useMessages } from '@/lib/hooks/useMessages'
import ChatBubble from '@/components/ChatBubble'
import { createClient } from '@/lib/supabase'
import type { Profile } from '@/lib/types'

export default function ChatPage() {
  const { matchId } = useParams<{ matchId: string }>()
  const { user } = useAuth()
  const { messages, loading, sendMessage } = useMessages(matchId, user?.id)
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [partner, setPartner] = useState<Profile | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const router = useRouter()
  const supabase = createClient()

  // マッチの相手情報を取得
  useEffect(() => {
    if (!user || !matchId) return
    const fetchPartner = async () => {
      const { data: match } = await supabase
        .from('matches')
        .select('*')
        .eq('id', matchId)
        .single()

      if (!match) return

      const partnerId = match.user1_id === user.id ? match.user2_id : match.user1_id
      const { data: profile } = await supabase
        .from('profiles')
        .select('*')
        .eq('user_id', partnerId)
        .single()

      if (profile) setPartner(profile)
    }
    fetchPartner()
  }, [user, matchId, supabase])

  // 新メッセージ時に自動スクロール
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || sending) return
    setSending(true)
    await sendMessage(input)
    setInput('')
    setSending(false)
  }

  const formatTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className="flex flex-col h-screen md:h-[calc(100vh)] md:ml-0">
      {/* ヘッダー */}
      <div className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3 flex-shrink-0">
        <button onClick={() => router.push('/matches')} className="text-gray-500 hover:text-gray-700">
          ←
        </button>
        <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center overflow-hidden flex-shrink-0">
          {partner?.avatar_url ? (
            <img src={partner.avatar_url} alt="" className="w-full h-full object-cover" />
          ) : (
            <span className="text-lg">👤</span>
          )}
        </div>
        <div>
          <h1 className="font-semibold text-gray-800 text-sm">{partner?.name || '...'}</h1>
          <p className="text-xs text-gray-400">{partner?.department}</p>
        </div>
      </div>

      {/* メッセージ一覧 */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-1">
        {loading ? (
          <p className="text-center text-gray-400 mt-8">読み込み中...</p>
        ) : messages.length === 0 ? (
          <div className="text-center mt-16">
            <span className="text-4xl block mb-2">👋</span>
            <p className="text-gray-400 text-sm">メッセージを送って会話を始めましょう！</p>
          </div>
        ) : (
          messages.map(msg => (
            <ChatBubble
              key={msg.id}
              content={msg.content}
              isMine={msg.sender_id === user?.id}
              time={formatTime(msg.created_at)}
            />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {/* 入力エリア */}
      <form onSubmit={handleSend} className="bg-white border-t border-gray-200 px-4 py-3 flex gap-2 mb-16 md:mb-0 flex-shrink-0">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="メッセージを入力..."
          className="flex-1 px-4 py-2.5 border border-gray-200 rounded-full focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent text-sm"
        />
        <button
          type="submit"
          disabled={!input.trim() || sending}
          className="px-5 py-2.5 bg-amber-500 text-white rounded-full text-sm font-medium hover:bg-amber-600 transition-colors disabled:opacity-50"
        >
          送信
        </button>
      </form>
    </div>
  )
}
