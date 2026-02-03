-- blog_archive 테이블 생성
-- 네이버 블로그 원본 콘텐츠 보존용

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

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_archive_category ON blog_archive(category);
CREATE INDEX IF NOT EXISTS idx_archive_keyword ON blog_archive(primary_keyword);
CREATE INDEX IF NOT EXISTS idx_archive_date ON blog_archive(original_date);
CREATE INDEX IF NOT EXISTS idx_archive_status ON blog_archive(migration_status);
CREATE INDEX IF NOT EXISTS idx_archive_batch ON blog_archive(import_batch_id);

-- updated_at 자동 갱신 트리거
CREATE OR REPLACE FUNCTION update_blog_archive_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_blog_archive_updated_at ON blog_archive;
CREATE TRIGGER trigger_blog_archive_updated_at
    BEFORE UPDATE ON blog_archive
    FOR EACH ROW
    EXECUTE FUNCTION update_blog_archive_updated_at();
