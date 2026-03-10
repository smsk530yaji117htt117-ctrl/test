'use client'

import { useEffect, useState, useCallback } from 'react'
import { createClient } from '@/lib/supabase'
import type { Match, Profile, Tag } from '@/lib/types'

export function useMatches(userId?: string) {
  const [matches, setMatches] = useState<Match[]>([])
  const [loading, setLoading] = useState(true)
  const supabase = createClient()

  const fetchMatches = useCallback(async () => {
    if (!userId) { setLoading(false); return }

    const { data } = await supabase
      .from('matches')
      .select('*')
      .or(`user1_id.eq.${userId},user2_id.eq.${userId}`)
      .order('created_at', { ascending: false })

    if (!data) { setLoading(false); return }

    const partnerIds = data.map(m =>
      m.user1_id === userId ? m.user2_id : m.user1_id
    )

    if (partnerIds.length === 0) {
      setMatches([])
      setLoading(false)
      return
    }

    const { data: profiles } = await supabase
      .from('profiles')
      .select('*')
      .in('user_id', partnerIds)

    // タグも取得
    const profileIds = profiles?.map(p => p.id) ?? []
    const { data: tagData } = profileIds.length > 0
      ? await supabase.from('profile_tags').select('profile_id, tags(id, name)').in('profile_id', profileIds)
      : { data: [] }

    const tagMap: Record<string, Tag[]> = {}
    tagData?.forEach((pt: { profile_id: string; tags: Tag | Tag[] }) => {
      const t = Array.isArray(pt.tags) ? pt.tags[0] : pt.tags
      if (t) {
        if (!tagMap[pt.profile_id]) tagMap[pt.profile_id] = []
        tagMap[pt.profile_id].push(t)
      }
    })

    const profileMap = new Map<string, Profile>()
    profiles?.forEach(p => {
      profileMap.set(p.user_id, { ...p, tags: tagMap[p.id] ?? [] })
    })

    const matchesWithPartner: Match[] = data.map(m => ({
      ...m,
      partner: profileMap.get(
        m.user1_id === userId ? m.user2_id : m.user1_id
      ),
    }))

    setMatches(matchesWithPartner)
    setLoading(false)
  }, [userId, supabase])

  useEffect(() => { fetchMatches() }, [fetchMatches])

  return { matches, loading, fetchMatches }
}
