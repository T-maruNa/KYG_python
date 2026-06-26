CREATE TABLE IF NOT EXISTS t_blog_post_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_date TEXT NOT NULL,
    post_type TEXT NOT NULL DEFAULT 'daily',
    title TEXT,
    content TEXT,
    wp_post_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    insert_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(post_date, post_type)
)
