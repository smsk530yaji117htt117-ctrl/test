'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/hooks/useAuth'
import { useProfile } from '@/lib/hooks/useProfile'
import TagBadge from '@/components/TagBadge'
import { createClient } from '@/lib/supabase'
import type { Tag } from '@/lib/types'

export default function ProfileEditPage() {
  const { user } = useAuth()
  const { profile, loading, updateProfile, uploadAvatar } = useProfile(user?.id)
  const [name, setName] = useState('')
  const [department, setDepartment] = useState('')
  const [bio, setBio] = useState('')
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null)
  const [tags, setTags] = useState<Tag[]>([])
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const router = useRouter()
  const supabase = createClient()

  useEffect(() => {
    const fetchTags = async () => {
      const { data } = await supabase.from('tags').select('*').order('name')
      if (data) setTags(data)
    }
    fetchTags()
  }, [supabase])

  useEffect(() => {
    if (profile) {
      setName(profile.name)
      setDepartment(profile.department)
      setBio(profile.bio)
      setAvatarPreview(profile.avatar_url)
      setSelectedTags(profile.tags?.map(t => t.id) ?? [])
    }
  }, [profile])

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setAvatarPreview(URL.createObjectURL(file))
    const url = await uploadAvatar(file)
    if (url) {
      await updateProfile({ avatar_url: url })
      setMessage('アイコンを更新しました')
      setTimeout(() => setMessage(''), 3000)
    }
  }

  const toggleTag = (tagId: string) => {
    setSelectedTags(prev =>
      prev.includes(tagId) ? prev.filter(id => id !== tagId) : [...prev, tagId]
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setMessage('')

    const result = await updateProfile(
      { name: name.trim(), department: department.trim(), bio: bio.trim() },
      selectedTags
    )

    if (result?.error) {
      setMessage('更新に失敗しました')
    } else {
      setMessage('プロフィールを更新しました')
      setTimeout(() => router.push(`/profile/${user?.id}`), 1000)
    }
    setSaving(false)
  }

  if (loading) {
    return <div className="flex items-center justify-center min-h-screen"><p className="text-gray-400">読み込み中...</p></div>
  }

  return (
    <div className="max-w-lg mx-auto px-4 pt-8">
      <button onClick={() => router.back()} className="text-sm text-gray-500 hover:text-gray-700 mb-6 block">
        ← 戻る
      </button>

      <h1 className="text-2xl font-bold text-gray-800 mb-6">プロフィール編集</h1>

      <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 space-y-6">
        {message && (
          <div className={`text-sm p-3 rounded-lg ${message.includes('失敗') ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-600'}`}>
            {message}
          </div>
        )}

        {/* アバター */}
        <div className="flex flex-col items-center">
          <label className="cursor-pointer group">
            <div className="w-24 h-24 rounded-full bg-amber-100 flex items-center justify-center overflow-hidden group-hover:ring-4 ring-amber-200 transition-all">
              {avatarPreview ? (
                <img src={avatarPreview} alt="" className="w-full h-full object-cover" />
              ) : (
                <span className="text-4xl">📷</span>
              )}
            </div>
            <input type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
          </label>
          <p className="text-xs text-gray-400 mt-2">タップして変更</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">名前</label>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            required
            className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">部署</label>
          <input
            type="text"
            value={department}
            onChange={e => setDepartment(e.target.value)}
            className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">自己紹介</label>
          <textarea
            value={bio}
            onChange={e => setBio(e.target.value)}
            rows={4}
            className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent resize-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">興味のあるタグ</label>
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

        <button
          type="submit"
          disabled={saving}
          className="w-full bg-amber-500 text-white py-2.5 rounded-lg font-medium hover:bg-amber-600 transition-colors disabled:opacity-50"
        >
          {saving ? '保存中...' : '保存する'}
        </button>
      </form>
    </div>
  )
}
