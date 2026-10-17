---
layout: site
title: 開発進捗 | Sado Investment Lab
description: Issue 867 / PR 860 の証跡ベース進捗
permalink: /ops/progress/
---

<style>
.pv{max-width:1040px;margin:auto;color:inherit}.pv h1{font-size:clamp(1.45rem,4vw,2.1rem)}.pv .sub{color:#64748b}.pv .cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.7rem}.pv .card,.pv details{border:1px solid #94a3b850;border-radius:14px;padding:1rem;margin:.6rem 0;background:color-mix(in srgb,Canvas 96%,#94a3b8)}.pv .metric{font-size:1.6rem;font-weight:750}.pv .warn{border-left:4px solid #e09b32;padding:.7rem;background:#e09b3217}.pv .tag{font-size:.78rem;padding:.2rem .55rem;border-radius:30px;background:#64748b22}.pv summary{cursor:pointer;display:flex;justify-content:space-between;gap:.5rem;align-items:center;list-style:none}.pv summary::-webkit-details-marker{display:none}.pv summary strong{font-size:.95rem}.pv .meta{display:flex;flex-wrap:wrap;gap:.45rem;margin:.6rem 0}.pv dl{display:grid;grid-template-columns:7rem 1fr;gap:.4rem;font-size:.9rem;overflow-wrap:anywhere}.pv dt{font-weight:650}.pv dd{margin:0}.pv a{overflow-wrap:anywhere}.pv .section{margin-top:2rem}.pv .small{font-size:.82rem}.pv .pill{border-radius:20px;padding:.3rem .6rem;background:#64748b22}.pv .links{display:flex;flex-wrap:wrap;gap:.75rem}.pv .unknown{color:#946c25}@media(min-width:700px){.pv .cards{grid-template-columns:repeat(4,minmax(0,1fr))}}@media(max-width:350px){.pv .card{padding:.65rem}.pv dl{grid-template-columns:1fr}.pv dt{margin-top:.4rem}}
</style>
<section class="pv" aria-label="開発進捗">
<h1>開発進捗ダッシュボード</h1>
<p class="sub">2026年10月12日〜18日 JST ／ <a href="https://github.com/sadouninc/Sado-Investment-Lab/issues/867">週間計画 #867</a> ／ <a href="https://github.com/sadouninc/Sado-Investment-Lab/pull/860">実装 PR #860</a></p>
<p class="warn"><strong>証跡の取り扱い：</strong>これは2026-10-17に確認したGitHub記録に基づくスナップショットです。リアルタイム集計ではありません。未確認は成功扱いしません。各項目の完了判定はcommit・テスト・CI・承認の照合後に更新します。</p>
<div class="cards" aria-label="集計">
<div class="card"><div class="metric">9件</div><div>マージ前課題</div><div class="small sub">完了数は未検証</div></div>
<div class="card"><div class="metric">2件</div><div>後続候補</div><div class="small sub">初回マージ対象外候補</div></div>
<div class="card"><div class="metric">未集計</div><div>今週のマージ</div><div class="small sub">目標4+／挑戦6〜8</div></div>
<div class="card"><div class="metric">未実証</div><div>自然closed-loop</div><div class="small sub">目標1件以上</div></div>
</div>
<p class="small">※ 「未集計」は0件ではありません。#867の週内merge SHA照合が必要です。</p>
<div class="section"><h2>PR #860の進捗と残Blocker</h2><p>課題を開くと完了条件・担当・証跡を確認できます。先頭9件はマージ前の検証対象、最後2件は後続候補です。</p><div id="pv-list"></div></div>
<div class="section"><h2>直近の検証記録</h2><div class="card"><strong>CIで構文エラーを検出</strong><p>報告されたhead: <code>7ab5cfe2c4648bcc875a78ecc76ccc762e85fb91</code>。Actions run <a href="https://github.com/sadouninc/Sado-Investment-Lab/actions/runs/38955714503">38955714503</a>、<a href="https://github.com/sadouninc/Sado-Investment-Lab/actions/runs/38955714434">38955714434</a> は失敗報告。<code>scripts/recovery_rev2_evidence_adapter.py:20</code> のSyntaxError。修正後の最新head/CIは未確認です。<a href="https://github.com/sadouninc/Sado-Investment-Lab/pull/860#issuecomment-6223216216">診断証跡</a></p><p><strong>merge SHA:</strong> PR #860は未確認（OPEN時点）。<strong>次:</strong> ソラの修正commitとCI再検証。</p></div></div>
<div class="section"><h2>自然closed-loopの証明</h2><p>READY → lease/comment ID → ACK → 実装commit → PR → CI/review → merge SHA → NEXT_AUTO を同一workで連続照合する必要があります。現時点では全区間を結ぶ証跡が未確認のため<strong>未実証</strong>です。</p></div>
<p class="small sub">根拠: <a href="https://github.com/sadouninc/Sado-Investment-Lab/issues/867#issuecomment-6214081524">9+2 baseline</a> / <a href="https://github.com/sadouninc/Sado-Investment-Lab/issues/867#issuecomment-6231862060">Design Contract v0.2</a>。課題名はbaselineを日本語要約した表示名で、正式IDの新設ではありません。</p>
</section>
<script>
(function(){
const rows=[["01","Writer→Readerのイベント形式統一","🪐ソラ","work/lease/attemptの整合と曖昧入力拒否"],["02","GitHubコメント証跡の照合","🪐ソラ","comment ID・run ID・全履歴の真正性"],["03","POST前のReader接続","🪐ソラ","workflow内でReader実行の証跡"],["04","POST前のGuard接続","🪐ソラ","関連Issue/PR/コメントの完全取得"],["05","担当・競合・終端状態の再検証","🪐ソラ","UNKNOWN時の配車禁止"],["06","P0/P1候補の継続探索","🪐ソラ","先頭候補不適格でも次候補へ"],["07","安全性回帰テスト","🪐ソラ","ACK/PR/MERGED/不正入力/#79を検証"],["08","最新head CIとOwner Gate","🪐ソラ・🌙ルナ","CI・レビュー・マージ権限の証跡"],["09","差分全体の未発見Blocker調査","🌙ルナ・🪐ソラ","全変更ファイルとreviewの照合"],["10","期限切れ後の安全な自動再配車","未割当","後続候補・Ownerのscope判断待ち"],["11","高度なRecovery監視・最適化","未割当","後続候補・Ownerのscope判断待ち"]];
const list=document.getElementById('pv-list');
rows.forEach(function(row,i){
 const d=document.createElement('details');const s=document.createElement('summary');const title=document.createElement('strong');title.textContent=row[0]+' '+row[1];const tag=document.createElement('span');tag.className='tag';tag.textContent=i<9?'マージ前':'後続候補';s.append(title,tag);d.append(s);
 const meta=document.createElement('div');meta.className='meta';const owner=document.createElement('span');owner.className='pill';owner.textContent='担当: '+row[2];const state=document.createElement('span');state.className='pill';state.textContent='状態: 証跡照合待ち';meta.append(owner,state);d.append(meta);
 const dl=document.createElement('dl');[['残Blocker',row[3]],['完了条件',row[3]+'をテスト・CI・実証跡で確認'],['次のアクション',i<9?'PR #860の最新headと該当テスト・CIを照合':'🌙ルナが後続scopeと担当を確定'],['commit SHA','項目単位の対応は未確認'],['CI','項目単位の成功は未確認'],['PR','#{860}（OPEN時点）'.replace('#{860}','#860')],['merge SHA','未確認']].forEach(function(p){const dt=document.createElement('dt');dt.textContent=p[0];const dd=document.createElement('dd');dd.textContent=p[1];dl.append(dt,dd)});d.append(dl);const a=document.createElement('a');a.href='https://github.com/sadouninc/Sado-Investment-Lab/pull/860';a.textContent='PR #860 の証跡を見る →';d.append(a);list.append(d);
});
})();
</script>
