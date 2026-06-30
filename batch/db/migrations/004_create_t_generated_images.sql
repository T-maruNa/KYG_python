-- 自動生成画像の管理テーブル
CREATE TABLE IF NOT EXISTS t_generated_images (
    id                SERIAL PRIMARY KEY,
    target_date       DATE        NOT NULL,
    post_type         VARCHAR(30) NOT NULL,  -- prediction_daily / result_daily
    image_type        VARCHAR(40) NOT NULL,  -- morning_scene / morning_sub_scene / hero_scene / night_reflection_scene / highlight_scene
    character_key     VARCHAR(10),           -- rei / mirai / ritu / NULL（集合シーン）
    provider          VARCHAR(30),           -- openai など
    model             VARCHAR(50),           -- gpt-image-1 など
    image_url         TEXT,                  -- 生成・アップロード後のURL
    prompt            TEXT,                  -- 生成に使ったプロンプト
    generation_status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending / success / failed / skipped
    error_message     TEXT,                  -- 失敗時のエラー内容
    created_at        TIMESTAMP   NOT NULL DEFAULT NOW(),

    UNIQUE(target_date, post_type, image_type, character_key)
);

CREATE INDEX IF NOT EXISTS idx_generated_images_date ON t_generated_images(target_date);
CREATE INDEX IF NOT EXISTS idx_generated_images_status ON t_generated_images(generation_status);
