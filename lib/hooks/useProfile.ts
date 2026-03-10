'use client'

import { useEffect, useState, useCallback } from 'react'
import { createClient } from '@/lib/supabase'
import type { Profile, Tag } from '@/lib/types'

export function useProfile(userId?: string) {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [loading, setLoading] = useState(true)
  const supabase = createClient()

  const fetchProfile = useCallback(async () => {
    if (!userId) { setLoading(false); return }
    setLoading(true)

    const { data: profileData } = await supabase
      .from('profiles')
      .select('*')
      .eq('user_id', userId)
      .single()

    if (profileData) {
      const { data: tagData } = await supabase
        .from('profile_tags')
        .select('tag_id, tags(id, name)')
        .eq('profile_id', profileData.id)

      const tags: Tag[] = tagData?.map((pt: { tags: Tag | Tag[] }) => {
        const t = pt.tags
        return Array.isArray(t) ? t[0] : t
      }).filter(Boolean) ?? []

      setProfile({ ...profileData, tags })
    }

    setLoading(false)
  }, [userId, supabase])

  useEffect(() => { fetchProfile() }, [fetchProfile])

  const updateProfile = async (updates: Partial<Profile>, tagIds?: string[]) => {
    if (!profile) return

    const { error } = await supabase
      .from('profiles')
      .update({ name: updates.name, department: updates.department, bio: updates.bio, avatar_url: updates.avatar_url })
      .eq('id', profile.id)

    if (error) return { error }

    if (tagIds !== undefined) {
      await supabase.from('profile_tags').delete().eq('profile_id', profile.id)
      if (tagIds.length > 0) {
        await supabase.from('profile_tags').insert(
          tagIds.map(tag_id => ({ profile_id: profile.id, tag_id }))
        )
      }
    }

    await fetchProfile()
    return { error: null }
  }

  const uploadAvatar = async (file: File) => {
    if (!userId) return null
    const ext = file.name.split('.').pop()
    const path = `${userId}/${Date.now()}.${ext}`

    const { error } = await supabase.storage.from('avatars').upload(path, file, { upsert: true })
    if (error) return null

    const { data: { publicUrl } } = supabase.storage.from('avatars').getPublicUrl(path)
    return publicUrl
  }

  return { profile, loading, fetchProfile, updateProfile, uploadAvatar }
}
