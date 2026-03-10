'use client'

import { useEffect, useState, useMemo } from 'react'
import { useAuth } from '@/lib/hooks/useAuth'
import { createClient } from '@/lib/supabase'
import UserCard from '@/components/UserCard'
import TagBadge from '@/components/TagBadge'
import type { Profile, Tag } from '@/lib/types'

export default function UsersPage() {
  const { user } = useAuth()
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [tags, setTags] = useState<Tag[]>([])
  const [likedUserIds, setLikedUserIds] = useState<Set<string>>(new Set())
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [selectedDept, setSelectedDept] = useState('')
  const [loading, setLoading] = useState(true)
  const supabase = createClient()

  useEffect(() => {
    if (!user) return

    const fetchData = async () => {
      // プロフィール一覧
      const { data: profilesData } = await supabase
        .from('profiles')
        .select('*')
        .order('created_at', { ascending: false })

      // タグ一覧
      const { data: tagsData } = await supabase.from('tags').select('*').order('name')

      // 全profile_tags
      const profileIds = profilesData?.map(p => p.id) ?? []
      const { data: ptData } = profileIds.length > 0
        ? await supabase.from('profile_tags').select('profile_id, tags(id, name)').in('profile_id', profileIds)
        : { data: [] }

      const tagMap: Record<string, Tag[]> = {}
      ptData?.forEach((pt: { profile_id: string; tags: Tag | Tag[] }) => {
        const t = Array.isArray(pt.tags) ? pt.tags[0] : pt.tags
        if (t) {
          if (!tagMap[pt.profile_id]) tagMap[pt.profile_id] = []
          tagMap[pt.profile_id].push(t)
        }
      })

      const enriched = profilesData?.map(p => ({ ...p, tags: tagMap[p.id] ?? [] })) ?? []
      setProfiles(enriched)
      setTags(tagsData ?? [])

      // 自分のいいね
      const { data: likesData } = await supabase
        .from('likes')
        .select('to_user_id')
        .eq('from_user_id', user.id)

      setLikedUserIds(new Set(likesData?.map(l => l.to_user_id) ?? []))
      setLoading(false)
    }

    fetchData()
  }, [user, supabase])

  const departments = useMemo(() => {
    const depts = new Set(profiles.map(p => p.department).filter(Boolean))
    return Array.from(depts).sort()
  }, [profiles])

  const filtered = useMemo(() => {
    return profiles.filter(p => {
      if (selectedDept && p.department !== selectedDept) return false
      if (selectedTags.length > 0) {
        const pTagIds = p.tags?.map(t => t.id) ?? []
        if (!selectedTags.some(tid => pTagIds.includes(tid))) return false
      }
      return true
    })
  }, [profiles, selectedDept, selectedTags])

  const toggleTag = (tagId: string) => {
    setSelectedTags(prev =>
      prev.includes(tagId) ? prev.filter(id => id !== tagId) : [...prev, tagId]
    )
  }

  if (loading) {
    return <div className="flex items-center justify-center min-h-screen"><p className="text-gray-400">読み込み中...</p></div>
  }

  return (
    <div className="max-w-4xl mx-auto px-4 pt-8">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">仲間を探す</h1>

      {/* フィルター */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 mb-6 space-y-4">
        <div>
          <label className="text-sm font-medium text-gray-700 block mb-2">部署で絞り込み</label>
          <select
            value={selectedDept}
            onChange={e => setSelectedDept(e.target.value)}
            className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
          >
            <option value="">すべての部署</option>
            {departments.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        <div>
          <label className="text-sm font-medium text-gray-700 block mb-2">タグで絞り込み</label>
          <div className="flex flex-wrap gap-2">
            {tags.map(tag => (
              <TagBadge
                key={tag.id}
                name={tag.name}
                selected={selectedTags.includes(tag.id)}
                onClick={() => toggleTag(tag.id)}
              />
            ))}
          </div>
        </div>
      </div>

      {/* ユーザー一覧 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map(profile => (
          <UserCard
            key={profile.id}
            profile={profile}
            currentUserId={user?.id ?? ''}
            isLiked={likedUserIds.has(profile.user_id)}
          />
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-16">
          <p className="text-gray-400">条件に合うユーザーが見つかりませんでした</p>
        </div>
      )}
    </div>
  )
}
