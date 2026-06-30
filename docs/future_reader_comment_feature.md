# 夢機能設計メモ：推しキャラ応援コメント

> **ステータス：Phase 2以降 / MVP非必須**
> この文書は将来の拡張設計メモです。MVP段階では実装しません。

---

## 概要

読者が推しキャラを選んでコメントを送り、採用されたコメントに対してそのキャラが記事内で反応する参加型機能。
「読者が毎日記事を見に来る理由」を作ることが目的。

---

## フェーズ計画

| Phase | 内容 | 条件 |
|-------|------|------|
| **Phase 1** | MVP（朝記事/夜記事/画像/ランキング/WordPress投稿） | 現在対応中 |
| **Phase 2** | 読者コメント受付・モデレーション・キャラ反応 | Phase 1 安定後 |
| **Phase 3** | いいね/応援ポイントによる採用スコア重み付け・課金検討 | Phase 2 安定後 |

---

## ユーザー体験の流れ

```
1. 読者が推しキャラを選ぶ（rei / mirai / ritu）
2. キャラへのコメントを投稿する
3. 管理側でモデレーション（承認 / 除外）
4. バッチが採用スコアで1件選ぶ
5. 夜記事の「💌 今日届いた応援コメント」セクションでキャラが反応
6. 翌日、採用コメントを送った読者が記事を見に来る
```

---

## DB設計（Phase 2で追加予定）

### `t_reader_comments`

```sql
CREATE TABLE IF NOT EXISTS t_reader_comments (
    id                SERIAL PRIMARY KEY,
    target_date       DATE          NOT NULL,         -- 送ったコメントが対象とする日付
    post_type         VARCHAR(30)   NOT NULL,          -- result_daily など
    character_key     VARCHAR(10)   NOT NULL,          -- rei / mirai / ritu
    nickname          VARCHAR(50)   NOT NULL,          -- 読者の表示名
    comment_body      TEXT          NOT NULL,          -- コメント本文
    like_count        INT           NOT NULL DEFAULT 0,
    support_point     INT           NOT NULL DEFAULT 0, -- Phase 3: 応援ポイント（将来課金連携）
    moderation_status VARCHAR(20)   NOT NULL DEFAULT 'pending',
                                                       -- pending / approved / rejected
    selected_flag     BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMP     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_moderation_status
        CHECK (moderation_status IN ('pending', 'approved', 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_reader_comments_date     ON t_reader_comments(target_date);
CREATE INDEX IF NOT EXISTS idx_reader_comments_char     ON t_reader_comments(character_key);
CREATE INDEX IF NOT EXISTS idx_reader_comments_status   ON t_reader_comments(moderation_status);
CREATE INDEX IF NOT EXISTS idx_reader_comments_selected ON t_reader_comments(selected_flag);
```

### `t_selected_comment_reactions`

```sql
CREATE TABLE IF NOT EXISTS t_selected_comment_reactions (
    id                SERIAL PRIMARY KEY,
    target_date       DATE        NOT NULL,
    source_comment_id INT         NOT NULL REFERENCES t_reader_comments(id),
    character_key     VARCHAR(10) NOT NULL,            -- 反応するキャラ
    reaction_text     TEXT        NOT NULL,            -- AI生成したキャラのセリフ
    selection_reason  TEXT,                            -- 採用理由メモ（管理用）
    created_at        TIMESTAMP   NOT NULL DEFAULT NOW(),

    UNIQUE (target_date, character_key)                -- 1日1キャラにつき1反応
);
```

---

## コメント採用スコアロジック

Phase 2 初期は以下の重み付きランダムで1件採用する。

```python
def calc_adoption_score(comment: dict) -> float:
    score = random.uniform(0.0, 1.0)          # ランダム基礎点
    score += comment['like_count'] * 0.1       # いいね数ボーナス
    if comment['is_first_comment']:            # 初コメントボーナス
        score += 0.3
    if not comment['was_recently_selected']:   # 直近未採用ボーナス
        score += 0.2
    if comment['was_selected_last_time']:      # 直近採用済みペナルティ
        score -= 0.5
    # Phase 3以降: support_point を加算（例: score += support_point * 0.05）
    return score
```

> **課金方針メモ（Phase 3）**
> - 「課金したら必ず採用」は避ける
> - 「応援ポイントで採用確率がアップ」程度に留める
> - 初期（Phase 2）は無料コメント＋ランダム採用で十分

---

## キャラ反応の生成仕様

### AIプロンプト方針

- コメント本文をそのまま無制限にAIへ渡さない
- 以下を通してからプロンプトに含める：
  - NGワードフィルタ（誹謗中傷・投資助言・個人情報など）
  - 文字数制限（最大200文字程度）
  - モデレーション通過済みフラグ確認

### 反応生成の入力

```python
{
    "character_key": "mirai",
    "comment_body": "みらいちゃん、今日は悔しかったね。でも明日はきっと大丈夫！",
    "today_result": {"win_count": 1, "lose_count": 2, "total_profit_loss": -8200},
    "character_personality": "...",  # character_profile.md から
}
```

### 反応生成のプロンプト方針

- キャラの性格・口調を守る（character_profile.md 参照）
- セリフ1〜2文で完結
- 読者コメントの内容を自然に受け止めて反応する
- 泣かせすぎない（みらいは悔しがるが強い子として扱う）
- 投資助言につながる言い方をしない

### 反応例

```
読者コメント：
「みらいちゃん、今日は負けちゃったけど明日は巻き返せるよ！」

みらい：
「うう……ありがとう。ちょっと泣きそうだけど、明日はちゃんと前を向くね。」
```

---

## 夜記事への組み込み

### セクション配置

```
🌙 今日の反省会
✨ 今日の名場面
💌 今日届いた応援コメント    ← Phase 2で追加
🏆 今月のランキング
次回へのひとこと
```

### HTMLセクションのイメージ

```html
<section class="reader-comment-section">
  <h2>💌 今日届いた応援コメント</h2>
  <p class="section-lead">今日は、みらいへの応援コメントが届きました。</p>
  <div class="reader-comment-box">
    <p class="reader-comment-label">読者コメント</p>
    <p class="reader-comment-body">「みらいちゃん、今日は悔しかったね。でも明日はきっと大丈夫！」</p>
  </div>
  <div class="char-reaction mirai">
    <p>みらい：</p>
    <p>「うう……ありがとう。ちょっと泣きそうだけど、明日はちゃんと前を向くね。」</p>
  </div>
</section>
```

> **MVP段階では非表示。** `blog_generator.py` の `generate_result()` で
> `selected_comment` が `None` のときはセクションを出力しない設計にする。

---

## モデレーション方針

### 採用しないコメント

| カテゴリ | 例 |
|----------|----|
| 誹謗中傷 | 他キャラや読者を攻撃する内容 |
| 投資助言 | 「〇〇を買うべき」「今が買い時」など |
| 個人情報 | 本名・住所・連絡先を含む内容 |
| 実在企業への断定 | 「〇〇株は絶対上がる」など |
| 公序良俗違反 | 差別・暴力・性的内容 |
| キャラ設定破壊 | キャラの設定に矛盾する内容 |
| スパム | 同一内容の連投・URL貼り付けなど |

### 実装時の留意点

- `moderation_status = 'pending'` のコメントは採用対象外
- 管理画面（または管理CLIスクリプト）で `approved` に変更してから採用ロジックを走らせる
- Phase 2 初期はモデレーションを手動で行い、Phase 3以降でAI自動判定を検討する

---

## 将来の拡張余地

- **WordPress コメント連携**：WordPressのコメント欄から取り込む（REST API経由）
- **専用フォーム**：WordPress内にショートコードで投稿フォームを設置
- **複数コメント対応**：1日3キャラ × 各1件まで採用など
- **コメント履歴ページ**：採用コメント一覧を読者が見られるアーカイブページ
- **読者ランキング**：採用回数が多い読者を表彰する仕組み（任意）
