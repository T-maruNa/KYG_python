-- t_blog_post_history に title / content カラムを追加する
ALTER TABLE t_blog_post_history ADD COLUMN title TEXT;
ALTER TABLE t_blog_post_history ADD COLUMN content TEXT;
