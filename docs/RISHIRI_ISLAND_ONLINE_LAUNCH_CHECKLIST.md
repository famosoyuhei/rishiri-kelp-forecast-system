# 利尻島内向けオンライン開始チェックリスト

## 目的

現地訪問が難しい場合でも、経費をかけずにオンラインで島内向けの案内を始める。

---

## 1. 相談フォームを作る

- [ ] Google Sheetsを新規作成する
- [ ] Apps Scriptに `docs/google_forms_rishiri_contact_setup.gs` を貼り付ける
- [ ] `ADMIN_EMAIL` を自分のメールアドレスに変更する
- [ ] `setupRishiriContactForm()` を実行する
- [ ] `contact_setup` タブに出た「フォーム公開URL」を控える
- [ ] テスト回答を1件送る
- [ ] 自分宛に通知メールが届くことを確認する
- [ ] 自動返信が必要な場合、返信先メールを入れて確認する

---

## 2. LPにフォームURLを設定する

`rishiri_island_lp.html` の以下を差し替える。

```javascript
const CONSULT_FORM_URL = "https://forms.gle/REPLACE_WITH_FORM_URL";
```

差し替え後:

```javascript
const CONSULT_FORM_URL = "Googleフォームの公開URL";
```

---

## 3. LPを確認する

- [ ] `/rishiri-island` が開く
- [ ] 「自分の干場を見る」でアプリ本体へ移動する
- [ ] 「LINEで家族に送る」が開く
- [ ] 「相談フォームを開く」でGoogleフォームが開く
- [ ] 干し記録協力依頼が表示されている
- [ ] 島内向けは9月末まで自由使用、相談は任意だとわかる
- [ ] 電話対応なしの記載がある
- [ ] 9月末で島内宣伝を一旦終了する記載がある

---

## 4. 初回投稿を準備する

使う素材:

- `docs/RISHIRI_ISLAND_SNS_LAUNCH_KIT.md`
- `docs/SNS_CONTENT_CALENDAR_4WEEK.md`

最初に出す投稿:

```text
利尻島で昆布を干す方へ

干場ごとの7日間乾燥予報をスマホで確認できます。
地図から自分の干場を選んで、明日の段取りの判断材料にしてください。

予報は補助情報です。最終判断は現地の天気を確認してください。
```

---

## 5. 9月末の終了ルール

- [ ] 9月末で島内向けSNS広告・投稿強化を一旦終了する
- [ ] 10月以降は干し記録の集計と精度分析に移る
- [ ] 全国一次産業向け発信は継続する
