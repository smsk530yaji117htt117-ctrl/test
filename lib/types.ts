export interface Profile {
  id: string
  user_id: string
  name: string
  department: string
  bio: string
  avatar_url: string | null
  created_at: string
  updated_at: string
  tags?: Tag[]
}

export interface Tag {
  id: string
  name: string
}

export interface Like {
  id: string
  from_user_id: string
  to_user_id: string
  created_at: string
}

export interface Match {
  id: string
  user1_id: string
  user2_id: string
  created_at: string
  partner?: Profile
}

export interface Message {
  id: string
  match_id: string
  sender_id: string
  content: string
  is_read: boolean
  created_at: string
}

export interface Notification {
  id: string
  user_id: string
  type: 'match' | 'message'
  ref_id: string | null
  is_read: boolean
  created_at: string
}
