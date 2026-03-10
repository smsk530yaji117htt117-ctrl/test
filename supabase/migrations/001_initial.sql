-- ============================================
-- 社内友達マッチングアプリ - DB初期設定
-- ============================================

-- プロフィールテーブル
CREATE TABLE profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL UNIQUE,
  name TEXT NOT NULL DEFAULT '',
  department TEXT NOT NULL DEFAULT '',
  bio TEXT NOT NULL DEFAULT '',
  avatar_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- タグテーブル
CREATE TABLE tags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE
);

-- プロフィール × タグ 中間テーブル
CREATE TABLE profile_tags (
  profile_id UUID REFERENCES profiles(id) ON DELETE CASCADE NOT NULL,
  tag_id UUID REFERENCES tags(id) ON DELETE CASCADE NOT NULL,
  PRIMARY KEY (profile_id, tag_id)
);

-- いいねテーブル
CREATE TABLE likes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  from_user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  to_user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (from_user_id, to_user_id),
  CHECK (from_user_id != to_user_id)
);

-- マッチングテーブル（相互いいね成立時に自動生成）
CREATE TABLE matches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user1_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  user2_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user1_id, user2_id),
  CHECK (user1_id < user2_id) -- 順序を統一して重複防止
);

-- メッセージテーブル
CREATE TABLE messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  match_id UUID REFERENCES matches(id) ON DELETE CASCADE NOT NULL,
  sender_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  content TEXT NOT NULL,
  is_read BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 通知テーブル
CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('match', 'message')),
  ref_id UUID,
  is_read BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================
-- インデックス
-- ============================================
CREATE INDEX idx_profiles_user_id ON profiles(user_id);
CREATE INDEX idx_likes_from_user ON likes(from_user_id);
CREATE INDEX idx_likes_to_user ON likes(to_user_id);
CREATE INDEX idx_matches_user1 ON matches(user1_id);
CREATE INDEX idx_matches_user2 ON matches(user2_id);
CREATE INDEX idx_messages_match ON messages(match_id);
CREATE INDEX idx_messages_created ON messages(match_id, created_at);
CREATE INDEX idx_notifications_user ON notifications(user_id, is_read);

-- ============================================
-- updated_at 自動更新トリガー
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER profiles_updated_at
  BEFORE UPDATE ON profiles
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================
-- マッチング自動生成トリガー
-- いいねが双方向になったらmatchesに挿入 + 通知作成
-- ============================================
CREATE OR REPLACE FUNCTION handle_new_like()
RETURNS TRIGGER AS $$
DECLARE
  match_exists BOOLEAN;
  new_match_id UUID;
  u1 UUID;
  u2 UUID;
BEGIN
  -- 相手から自分へのいいねが存在するかチェック
  SELECT EXISTS(
    SELECT 1 FROM likes
    WHERE from_user_id = NEW.to_user_id
      AND to_user_id = NEW.from_user_id
  ) INTO match_exists;

  IF match_exists THEN
    -- user1_id < user2_id の順序で格納
    IF NEW.from_user_id < NEW.to_user_id THEN
      u1 := NEW.from_user_id;
      u2 := NEW.to_user_id;
    ELSE
      u1 := NEW.to_user_id;
      u2 := NEW.from_user_id;
    END IF;

    -- マッチング作成（重複時はスキップ）
    INSERT INTO matches (user1_id, user2_id)
    VALUES (u1, u2)
    ON CONFLICT (user1_id, user2_id) DO NOTHING
    RETURNING id INTO new_match_id;

    -- 新規マッチングの場合のみ通知を送信
    IF new_match_id IS NOT NULL THEN
      INSERT INTO notifications (user_id, type, ref_id)
      VALUES
        (NEW.from_user_id, 'match', new_match_id),
        (NEW.to_user_id, 'match', new_match_id);
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_new_like
  AFTER INSERT ON likes
  FOR EACH ROW EXECUTE FUNCTION handle_new_like();

-- ============================================
-- メッセージ送信時の通知トリガー
-- ============================================
CREATE OR REPLACE FUNCTION handle_new_message()
RETURNS TRIGGER AS $$
DECLARE
  other_user_id UUID;
BEGIN
  -- マッチの相手を特定
  SELECT CASE
    WHEN m.user1_id = NEW.sender_id THEN m.user2_id
    ELSE m.user1_id
  END INTO other_user_id
  FROM matches m WHERE m.id = NEW.match_id;

  IF other_user_id IS NOT NULL THEN
    INSERT INTO notifications (user_id, type, ref_id)
    VALUES (other_user_id, 'message', NEW.match_id);
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_new_message
  AFTER INSERT ON messages
  FOR EACH ROW EXECUTE FUNCTION handle_new_message();

-- ============================================
-- Row Level Security (RLS)
-- ============================================

-- profiles
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "profiles_select" ON profiles FOR SELECT USING (true);
CREATE POLICY "profiles_insert" ON profiles FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "profiles_update" ON profiles FOR UPDATE USING (auth.uid() = user_id);

-- tags
ALTER TABLE tags ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tags_select" ON tags FOR SELECT USING (true);
CREATE POLICY "tags_insert" ON tags FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

-- profile_tags
ALTER TABLE profile_tags ENABLE ROW LEVEL SECURITY;
CREATE POLICY "profile_tags_select" ON profile_tags FOR SELECT USING (true);
CREATE POLICY "profile_tags_insert" ON profile_tags FOR INSERT
  WITH CHECK (
    EXISTS (SELECT 1 FROM profiles WHERE id = profile_id AND user_id = auth.uid())
  );
CREATE POLICY "profile_tags_delete" ON profile_tags FOR DELETE
  USING (
    EXISTS (SELECT 1 FROM profiles WHERE id = profile_id AND user_id = auth.uid())
  );

-- likes
ALTER TABLE likes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "likes_select" ON likes FOR SELECT USING (
  auth.uid() = from_user_id OR auth.uid() = to_user_id
);
CREATE POLICY "likes_insert" ON likes FOR INSERT WITH CHECK (auth.uid() = from_user_id);
CREATE POLICY "likes_delete" ON likes FOR DELETE USING (auth.uid() = from_user_id);

-- matches
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;
CREATE POLICY "matches_select" ON matches FOR SELECT USING (
  auth.uid() = user1_id OR auth.uid() = user2_id
);

-- messages
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY "messages_select" ON messages FOR SELECT USING (
  EXISTS (
    SELECT 1 FROM matches
    WHERE id = match_id AND (user1_id = auth.uid() OR user2_id = auth.uid())
  )
);
CREATE POLICY "messages_insert" ON messages FOR INSERT WITH CHECK (
  auth.uid() = sender_id AND
  EXISTS (
    SELECT 1 FROM matches
    WHERE id = match_id AND (user1_id = auth.uid() OR user2_id = auth.uid())
  )
);
CREATE POLICY "messages_update" ON messages FOR UPDATE USING (
  EXISTS (
    SELECT 1 FROM matches
    WHERE id = match_id AND (user1_id = auth.uid() OR user2_id = auth.uid())
  )
);

-- notifications
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
CREATE POLICY "notifications_select" ON notifications FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "notifications_update" ON notifications FOR UPDATE USING (auth.uid() = user_id);

-- ============================================
-- Realtime 有効化
-- ============================================
ALTER PUBLICATION supabase_realtime ADD TABLE messages;
ALTER PUBLICATION supabase_realtime ADD TABLE notifications;
ALTER PUBLICATION supabase_realtime ADD TABLE likes;

-- ============================================
-- 初期タグデータ
-- ============================================
INSERT INTO tags (name) VALUES
  ('ゲーム'), ('映画'), ('音楽'), ('読書'), ('料理'),
  ('スポーツ'), ('旅行'), ('写真'), ('プログラミング'), ('デザイン'),
  ('アニメ'), ('カフェ巡り'), ('キャンプ'), ('ヨガ'), ('ランニング'),
  ('ボードゲーム'), ('DIY'), ('ペット'), ('ガーデニング'), ('語学学習');

-- ============================================
-- Storage バケット (アバター画像用)
-- ============================================
INSERT INTO storage.buckets (id, name, public) VALUES ('avatars', 'avatars', true)
ON CONFLICT (id) DO NOTHING;

CREATE POLICY "avatars_select" ON storage.objects FOR SELECT USING (bucket_id = 'avatars');
CREATE POLICY "avatars_insert" ON storage.objects FOR INSERT
  WITH CHECK (bucket_id = 'avatars' AND auth.uid() IS NOT NULL);
CREATE POLICY "avatars_update" ON storage.objects FOR UPDATE
  USING (bucket_id = 'avatars' AND auth.uid()::text = (storage.foldername(name))[1]);
CREATE POLICY "avatars_delete" ON storage.objects FOR DELETE
  USING (bucket_id = 'avatars' AND auth.uid()::text = (storage.foldername(name))[1]);
