"""
一回限りのLINE一斉配信スクリプト: 山背風フェーン補正の改善報告（PR #19）。

対象: LINE通知登録済みの利用者全員（load_subscriptions() の全件、通知ON/OFF問わず）。
既存の notify_all()（毎日の予報配信）と同じ push_text() / load_subscriptions() を再利用しており、
line_integration.py 本体のロジックは一切変更していない。

実行方法（本番のUpstash/LINE認証情報が必要なため、ローカルではなくRenderのShellタブで実行する）:
    python scripts/broadcast_foehn_fix_announcement.py --dry-run   # まず件数だけ確認
    python scripts/broadcast_foehn_fix_announcement.py             # 実際に送信

送信後、このファイルは削除してよい（再利用しない一回限りのスクリプトのため）。
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from line_integration import load_subscriptions, push_text, _mask_id  # noqa: E402

MESSAGE = """利尻島昆布干場予報システムをご利用いただき、ありがとうございます。

先日、利用者の方から「南西の風の日、鴛泊側は曇り予報でも実際は晴れて乾く」
「北東の風の日は逆に沓形側が晴れる」というお声をいただきました。

利尻山は大きな一つの山なので、風がその山を越えると、風下側では雲が
払われて晴れやすくなることがあります。これまでのアプリはこの「山の
おかげで風下側だけ晴れる」効果をうまく取り込めておらず、実際は乾く
日でも曇り扱いにしてしまうことがありました。

今回、風向きと利尻山頂の気象データをもとに、この効果を予報スコアに
反映できるよう改善しました。風上側（山に向かって風が吹く側）の予報
は変わりません。

本日から、この改善を反映した予報が届くようになります。貴重なお声を
いただき、ありがとうございました。

このような改善案やお気づきの点があれば、こちらからお知らせください。
https://docs.google.com/forms/d/e/1FAIpQLSfaMVTptw9B680fBsZjRdrIvVpJVs1HNxgiDp92hMBHuTJG-A/viewform?usp=dialog"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--dry-run', action='store_true',
        help='送信せず、対象人数と文面だけ表示する',
    )
    args = parser.parse_args()

    print(f'--- 送信文面（{len(MESSAGE)}文字） ---')
    print(MESSAGE)
    print('--- ここまで ---\n')

    subs = load_subscriptions()
    targets = [
        (key, sub) for key, sub in subs.items()
        if sub.get('source_id')
    ]
    print(f'対象件数: {len(targets)}件（登録済み利用者全員、通知ON/OFF問わず）')

    if args.dry_run:
        print('--dry-run のため送信はしていません。')
        return

    confirm = input('この内容で本当に送信しますか？ [yes/N]: ').strip().lower()
    if confirm != 'yes':
        print('中止しました。')
        return

    sent, failed = 0, 0
    for key, sub in targets:
        source_id = sub['source_id']
        ok = push_text(source_id, MESSAGE)
        if ok:
            sent += 1
        else:
            failed += 1
            print(f'  送信失敗: {_mask_id(source_id)}')
        time.sleep(0.3)  # LINE APIへの負荷を抑えるための小休止

    print(f'\n完了: 成功={sent} 失敗={failed} 対象={len(targets)}')


if __name__ == '__main__':
    main()
