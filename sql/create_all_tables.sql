-- ============================================================
-- Blog Writer - 전체 테이블 생성 DDL
-- 실행 순서: articles → keywords → publish_logs → blog_archive
-- ============================================================

-- 1. articles 테이블
CREATE TABLE IF NOT EXISTS articles (
    id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    -- 핵심 콘텐츠
    keyword             TEXT NOT NULL,
    title               TEXT NOT NULL,
    content             TEXT NOT NULL,
    meta_description    TEXT DEFAULT '',
    tags                JSONB DEFAULT '[]'::jsonb,
    sections            JSONB DEFAULT '[]'::jsonb,

    -- 설정
    template            TEXT DEFAULT 'personal_story',
    tone                TEXT DEFAULT 'emotional',
    domain              TEXT DEFAULT 'cctv',

    -- 품질 점수
    quality_score       FLOAT DEFAULT 0.0,
    seo_score           FLOAT DEFAULT 0.0,
    readability_score   FLOAT DEFAULT 0.0,
    word_count          INTEGER DEFAULT 0,

    -- 상태
    status              TEXT DEFAULT 'draft',

    -- 발행 정보
    blog_url            TEXT,
    blog_post_id        TEXT,
    published_at        TIMESTAMPTZ,

    -- 캠페인 연동
    campaign_id         TEXT,

    -- AI 생성 메타
    generation_config   JSONB DEFAULT '{}'::jsonb,
    ai_model            TEXT DEFAULT 'deepseek-chat',
    generation_tokens   INTEGER DEFAULT 0,

    -- 타임스탬프
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_keyword ON articles(keyword);
CREATE INDEX IF NOT EXISTS idx_articles_domain ON articles(domain);
CREATE INDEX IF NOT EXISTS idx_articles_created ON articles(created_at DESC);


-- 2. keywords 테이블
CREATE TABLE IF NOT EXISTS keywords (
    id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    keyword             TEXT NOT NULL UNIQUE,
    domain              TEXT DEFAULT 'cctv',
    category            TEXT,

    -- 검색량/경쟁도
    search_volume       INTEGER,
    competition_level   TEXT,

    -- 사용 현황
    articles_count      INTEGER DEFAULT 0,
    last_used_at        TIMESTAMPTZ,

    -- 상태
    is_active           BOOLEAN DEFAULT TRUE,
    priority            INTEGER DEFAULT 0,

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_keywords_domain ON keywords(domain);
CREATE INDEX IF NOT EXISTS idx_keywords_active ON keywords(is_active);
CREATE INDEX IF NOT EXISTS idx_keywords_priority ON keywords(priority DESC);


-- 3. publish_logs 테이블
CREATE TABLE IF NOT EXISTS publish_logs (
    id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    article_id          UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    blog_id             TEXT NOT NULL,
    status              TEXT DEFAULT 'pending',
    success             BOOLEAN DEFAULT FALSE,

    blog_url            TEXT,
    error_message       TEXT,
    screenshots         JSONB DEFAULT '[]'::jsonb,
    logs                TEXT,
    publish_config      JSONB DEFAULT '{}'::jsonb,

    started_at          TIMESTAMPTZ DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_publish_logs_article ON publish_logs(article_id);
CREATE INDEX IF NOT EXISTS idx_publish_logs_status ON publish_logs(status);


-- 4. blog_archive 테이블
CREATE TABLE IF NOT EXISTS blog_archive (
    id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    -- 원본 보존
    original_title      TEXT NOT NULL,
    original_content    TEXT NOT NULL,

    -- SEO 메모 분리
    seo_memo            TEXT,
    clean_content       TEXT NOT NULL,

    -- 파일에서 추출한 메타데이터
    photo_count         INTEGER DEFAULT 0,
    original_date       DATE NOT NULL,
    view_count          INTEGER DEFAULT 0,

    -- 자동 분류
    category            TEXT NOT NULL DEFAULT 'general',
    tags                JSONB DEFAULT '[]'::jsonb,
    primary_keyword     TEXT,

    -- 콘텐츠 분석
    word_count          INTEGER DEFAULT 0,
    has_seo_memo        BOOLEAN DEFAULT FALSE,
    content_type        TEXT DEFAULT 'article',

    -- articles 테이블 연결
    article_id          UUID REFERENCES articles(id) ON DELETE SET NULL,
    migration_status    TEXT DEFAULT 'archived',

    -- 소스 추적
    source_file         TEXT DEFAULT 'blog-cctv.txt',
    source_line         INTEGER,
    parse_order         INTEGER,
    import_batch_id     TEXT,

    -- 타임스탬프
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(original_title)
);

CREATE INDEX IF NOT EXISTS idx_archive_category ON blog_archive(category);
CREATE INDEX IF NOT EXISTS idx_archive_keyword ON blog_archive(primary_keyword);
CREATE INDEX IF NOT EXISTS idx_archive_date ON blog_archive(original_date);
CREATE INDEX IF NOT EXISTS idx_archive_status ON blog_archive(migration_status);
CREATE INDEX IF NOT EXISTS idx_archive_batch ON blog_archive(import_batch_id);


-- ============================================================
-- updated_at 자동 갱신 트리거
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- articles
DROP TRIGGER IF EXISTS trigger_articles_updated_at ON articles;
CREATE TRIGGER trigger_articles_updated_at
    BEFORE UPDATE ON articles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- blog_archive
DROP TRIGGER IF EXISTS trigger_blog_archive_updated_at ON blog_archive;
CREATE TRIGGER trigger_blog_archive_updated_at
    BEFORE UPDATE ON blog_archive
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ============================================================
-- RLS (Row Level Security) - 서비스 키 사용시 bypass
-- ============================================================

ALTER TABLE articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE keywords ENABLE ROW LEVEL SECURITY;
ALTER TABLE publish_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE blog_archive ENABLE ROW LEVEL SECURITY;

-- service_role은 모든 작업 허용
CREATE POLICY "Service role full access" ON articles FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON keywords FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON publish_logs FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON blog_archive FOR ALL USING (true) WITH CHECK (true);
