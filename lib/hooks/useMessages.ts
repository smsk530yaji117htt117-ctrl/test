'use client'

import { useEffect, useState, useCallback } from 'react'
import { createClient } from '@/lib/supabase'
import type { Message } from '@/lib/types'

export function useMessages(matchId?: string, userId?: string) {
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(true)
  const supabase = createClient()

  const fetchMessages = useCallback(async () => {
    if (!matchId) { setLoading(false); return }

    const { data } = await supabase
      .from('messages')
      .select('*')
      .eq('match_id', matchId)
      .order('created_at', { ascending: true })

    if (data) setMessages(data)
    setLoading(false)
  }, [matchId, supabase])

  useEffect(() => {
    fetchMessages()

    if (!matchId) return

    const channel = supabase
      .channel(`messages:${matchId}`)
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'messages', filter: `match_id=eq.${matchId}` },
        (payload) => {
          const newMsg = payload.new as Message
          setMessages(prev => [...prev, newMsg])
        }
      )
      .subscribe()

    return () => { supabase.removeChannel(channel) }
  }, [matchId, supabase, fetchMessages])

  // 未読を既読にする
  useEffect(() => {
    if (!matchId || !userId || messages.length === 0) return

    const unread = messages.filter(m => !m.is_read && m.sender_id !== userId)
    if (unread.length === 0) return

    supabase
      .from('messages')
      .update({ is_read: true })
      .eq('match_id', matchId)
      .neq('sender_id', userId)
      .eq('is_read', false)
      .then(() => {
        setMessages(prev =>
          prev.map(m => m.sender_id !== userId ? { ...m, is_read: true } : m)
        )
      })
  }, [matchId, userId, messages, supabase])

  const sendMessage = async (content: string) => {
    if (!matchId || !userId || !content.trim()) return

    const { error } = await supabase.from('messages').insert({
      match_id: matchId,
      sender_id: userId,
      content: content.trim(),
    })

    return { error }
  }

  return { messages, loading, sendMessage }
}
