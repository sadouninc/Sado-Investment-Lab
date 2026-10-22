---
layout: site
title: 開発進捗 | Sado Investment Lab
description: Issue 867 / PR 860 の証跡ベース進捗
permalink: /ops/progress/
---

<style>
.pv{max-width:1040px;margin:auto;color:inherit}.pv h1{font-size:clamp(1.45rem,4vw,2.1rem)}.pv .sub{color:#64748b}.pv .cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.7rem}.pv .card,.pv details{border:1px solid #94a3b850;border-radius:14px;padding:1rem;margin:.6rem 0;background:color-mix(in srgb,Canvas 96%,#94a3b8)}.pv .metric{font-size:clamp(1.1rem,4.2vw,1.6rem);font-weight:750;overflow-wrap:anywhere}.pv .card{min-width:0}.pv .warn{border-left:4px solid #e09b32;padding:.7rem;background:#e09b3217}.pv .tag{font-size:.78rem;padding:.2rem .55rem;border-radius:30px;background:#64748b22}.pv summary{cursor:pointer;display:flex;justify-content:space-between;gap:.5rem;align-items:center;list-style:none}.pv summary::-webkit-details-marker{display:none}.pv summary strong{font-size:.95rem}.pv .meta{display:flex;flex-wrap:wrap;gap:.45rem;margin:.6rem 0}.pv dl{display:grid;grid-template-columns:7rem 1fr;gap:.4rem;font-size:.9rem;overflow-wrap:anywhere}.pv dt{font-weight:650}.pv dd{margin:0}.pv a{overflow-wrap:anywhere}.pv .section{margin-top:2rem}.pv .small{font-size:.82rem}.pv .pill{border-radius:20px;padding:.3rem .6rem;background:#64748b22}.pv .links{display:flex;flex-wrap:wrap;gap:.75rem}.pv .unknown{color:#946c25}@media(min-width:700px){.pv .cards{grid-template-columns:repeat(4,minmax(0,1fr))}}@media(max-width:350px){.pv .cards{grid-template-columns:minmax(0,1fr)}.pv .card{padding:.65rem}.pv dl{grid-template-columns:1fr}.pv dt{margin-top:.4rem}}
</style>
<section class="pv" aria-label="開発進捗">
<h1>開発進捗ダッシュボード</h1>
<p class="sub">2026年10月12日〜18日 JST ／ <a href="https://github.com/sadouninc/Sado-Investment-Lab/issues/867">週間計画 #867</a> ／ <a href="https://github.com/sadouninc/Sado-Investment-Lab/pull/860">実装 PR #860</a></p>
<p class="warn"><strong>証跡の取り扱い：</strong>これは2026-10-17の暫定台帳を基礎に、2026-10-23確認のPR #860マージ証跡のみ追記した静的スナップショットです。リアルタイム集計ではありません。未確認は成功扱いしません。各項目の完了判定はcommit・テスト・CI・承認の照合後に更新します。</p>
<div class="cards" aria-label="集計">
<div class="card"><div class="metric">9件</div><div>マージ前課題</div><div class="small sub">完了数は未検証</div></div>
<div class="card"><div class="metric">2件</div><div>後続候補</div><div class="small sub">初回マージ対象外候補</div></div>
<div class="card"><div class="metric">未集計</div><div>今週のマージ</div><div class="small sub">目標4+／挑戦6〜8</div></div>
<div class="card"><div class="metric">未実証</div><div>自然closed-loop</div><div class="small sub">目標1件以上</div></div>
</div>
<p class="small">※ 「未集計」は0件ではありません。#867の週内merge SHA照合が必要です。</p>
<div class="section"><h2>PR #860の進捗と残Blocker</h2><p>課題を開くと完了条件・担当・証跡を確認できます。先頭9件はマージ前の検証対象、最後2件は後続候補です。</p><div id="pv-list"></div></div>
<div class="section"><h2>直近の検証記録</h2><div class="card"><strong>CIで構文エラーを検出</strong><p>報告されたhead: <code>7ab5cfe2c4648bcc875a78ecc76ccc762e85fb91</code>。Actions run <a href="https://github.com/sadouninc/Sado-Investment-Lab/actions/runs/38955714503">38955714503</a>、<a href="https://github.com/sadouninc/Sado-Investment-Lab/actions/runs/38955714434">38955714434</a> は失敗報告。<code>scripts/recovery_rev2_evidence_adapter.py:20</code> のSyntaxError。この失敗は過去headの履歴であり、マージ済みの最終結果とは区別します。現在headのSHA・CI結果はこのスナップショットではUNKNOWNです。<a href="https://github.com/sadouninc/Sado-Investment-Lab/pull/860#issuecomment-6223216216">診断証跡</a></p><p><strong>merge SHA:</strong> PR #860は2026-10-17 22:36 JSTにマージ済み。<strong>merge SHA:</strong> <a href="https://github.com/sadouninc/Sado-Investment-Lab/commit/ac378e389e1cd0f3ae6d85a1d37bfc4b99fe2e7a"><code>ac378e389e1cd0f3ae6d85a1d37bfc4b99fe2e7a</code></a>。<strong>注意:</strong> マージ確認は自然closed-loopの全段階実証を意味しません。</p></div></div>
<div class="section"><h2>自然closed-loopの証明</h2><p>READY → lease/comment ID → ACK → 実装commit → PR → CI/review → merge SHA → NEXT_AUTO を同一workで連続照合する必要があります。現時点では全区間を結ぶ証跡が未確認のため<strong>未実証</strong>です。</p></div>
<p class="small sub">根拠: <a href="https://github.com/sadouninc/Sado-Investment-Lab/issues/867#issuecomment-6214081524">9+2 baseline</a> / <a href="https://github.com/sadouninc/Sado-Investment-Lab/issues/867#issuecomment-6231862060">Design Contract v0.2</a>。課題名はbaselineを日本語要約した表示名で、正式IDの新設ではありません。</p>

<div class="section" id="pv-contract" aria-label="受入条件台帳">
<h2>定量進捗・受入条件台帳（暫定）</h2>
<p class="warn">この台帳は静的な手動スナップショットです。11課題の正式criterion分解・合否・母数は🌙ルナの証跡判定待ちです。UNKNOWNはPASSではありません。暫定task_idはこのスナップショット内で固定し、canonical IDの承認を意味しません。</p>
<div class="cards">
<div class="card"><div class="metric">UNKNOWN</div><div>実装 criteria PASS / 確定総数</div></div>
<div class="card"><div class="metric">UNKNOWN</div><div>検証 criteria PASS / 確定総数</div></div>
<div class="card"><div class="metric">UNKNOWN</div><div>本番実証 criteria PASS / 確定総数</div></div>
<div class="card"><div class="metric">UNKNOWN</div><div>同一scope前回差分</div></div>
</div>
<p class="small">as_of: 2026-10-18 JST（台帳仕様追加時点）。scope_version: <code>PROVISIONAL-867-v1</code>。source: <a href="https://github.com/sadouninc/Sado-Investment-Lab/issues/867">#867</a>、<a href="https://github.com/sadouninc/Sado-Investment-Lab/pull/870">#870</a>。#860の最新head SHA・実績の自動取得は行いません。進捗率は確定母数がないためUNKNOWNです。</p>
<p class="small">delta（同一scope_versionのみ）: newly_passed UNKNOWN / regressed UNKNOWN / new_blockers UNKNOWN / resolved_blockers UNKNOWN / remaining_blockers UNKNOWN。scope_delta（追加・削除）: UNKNOWN。過去headのCI成功は現在headのPASSに流用しません。</p>
<div id="pv-criteria"></div>
</div>
<div class="section" aria-label="スナップショット更新手順">
<h2>スナップショット更新・判定手順</h2>
<p class="small">この画面はGitHubの情報を自動取得しません。SSoTは <a href="https://github.com/sadouninc/Sado-Investment-Lab/issues/867">Issue #867</a>・<a href="https://github.com/sadouninc/Sado-Investment-Lab/pull/860">PR #860</a>・対応するActions runとreviewの原本です。ダッシュボードは証跡の写しであり、承認やマージ権限を持ちません。</p>
<ol class="small">
<li>🌙ルナがcanonical task_id・atomic criterion_id・担当・区分・確定母数・scope_versionを原本に基づき承認する。未承認はUNKNOWNのまま。</li>
<li>各criterionに必要なcommit SHA、run ID、review ID、merge SHA、production event IDを紐づけ、証跡URLと同一headを照合する。過去headの成功は現在headのPASSにしない。</li>
<li>前回と今回のsnapshotを同じscope_versionで比較する。基準の追加・削除はscope_deltaとして別管理し、進捗deltaに混ぜない。</li>
<li>as_of（JST）、source/head SHA、更新担当、確認済みPASS/FAIL/BLOCKED/UNKNOWNを記録し、静的ページを再生成してCIとプレビューを確認する。</li>
<li>自然closed-loopは同一work_ref・lease_idの9工程を個別に照合し、完全1セットの成立を別判定する。追加2セットは任意。</li>
</ol>
<p class="small">更新担当: ⭐️ミナ（画面反映）／証跡とscope判定: 🌙ルナ（Product受入）／本番操作: Owner Gate準拠。正式母数未確定の間は百分率を出しません。</p>
</div>
<div class="section" aria-label="自然実行9工程">
<h2>自然closed-loop 9工程：同一workの連続証跡</h2>
<p>確認済み工程 <strong>0/9（PASS証跡未登録）</strong> ／ 完全成功セット <strong>0/1（未実証）</strong>。0/9は「未検証9項目」の表示であり、失敗9件を意味しません。公式最低目標は完全1セット。追加2セットは推奨であり必須Gateではありません。</p>
<p class="small">work_ref: UNKNOWN ／ lease_id: UNKNOWN ／ source/head SHA: UNKNOWN ／ 実行時刻: UNKNOWN。異なるworkの証跡を合算しません。</p>
<ol id="pv-loop"></ol>
<p class="small">#860のArtifact→Reader→Guard→POST技術統合・安全性テスト・CIは、この自然closed-loop本番実証とは別の受入条件です。#79 hard deny、Owner Gate、AUTO_GREENを変更しません。</p>
</div>
</section>
<script>
(function(){

const taskNames=["Writer→Readerのイベント形式統一","GitHubコメント証跡の照合","POST前のReader接続","POST前のGuard接続","担当・競合・終端状態の再検証","P0/P1候補の継続探索","安全性回帰テスト","最新head CIとOwner Gate","差分全体の未発見Blocker調査","期限切れ後の安全な自動再配車","高度なRecovery監視・最適化"];
// Provisional data contract. All criteria remain unfinalized until Luna approval.
const snapshot={scope_version:'PROVISIONAL-867-v1',criteria:[],previous:null,work_ref:null,lease_id:null};
function validateSnapshot(data){
 if(!data||typeof data.scope_version!=='string'||!data.scope_version)
  throw new Error('missing scope_version');
 if(!Array.isArray(data.criteria))throw new Error('criteria must be a list');
 const seen=new Set();
 data.criteria.forEach(function(c){
  if(!c||typeof c!=='object'||typeof c.criterion_id!=='string'||!c.criterion_id)
   throw new Error('missing criterion_id');
  if(seen.has(c.criterion_id))throw new Error('duplicate criterion_id');
  seen.add(c.criterion_id);
  if(!['implementation','verification','production'].includes(c.dimension))
   throw new Error('invalid dimension');
  if(!['PASS','FAIL','BLOCKED','UNKNOWN'].includes(c.state))
   throw new Error('invalid state');
  if(typeof c.finalized!=='boolean')throw new Error('finalized must be boolean');
  if(c.evidence_url!=null&&(typeof c.evidence_url!=='string'||!c.evidence_url.startsWith('https://')))
   throw new Error('invalid evidence_url');
 });
 return data;
}
let snapshotValid=true;
try{validateSnapshot(snapshot)}catch(error){snapshotValid=false;console.error('Progress snapshot invalid:',error.message)}
function latestHeadCI(evidenceHead,currentHead,conclusion,runId){
 if(!evidenceHead||!currentHead||!runId)return {status:'UNKNOWN',reason:'MISSING_EVIDENCE'};
 if(evidenceHead!==currentHead)return {status:'UNKNOWN',reason:'STALE_HEAD'};
 if(conclusion==='success')return {status:'PASS',reason:'LATEST_HEAD_SUCCESS'};
 if(['failure','timed_out','cancelled','action_required'].includes(conclusion))
  return {status:'FAIL',reason:'LATEST_HEAD_NOT_SUCCESS'};
 return {status:'UNKNOWN',reason:'RUN_NOT_COMPLETE'};
}
function metricFor(dimension){
 const entries=snapshot.criteria.filter(function(c){return c.dimension===dimension});
 if(!entries.length||entries.some(function(c){return !c.finalized}))return 'UNKNOWN';
 const ids=entries.map(function(c){return c.criterion_id});
 if(new Set(ids).size!==ids.length)throw new Error('duplicate criterion_id');
 if(entries.some(function(c){return !['PASS','FAIL','BLOCKED','UNKNOWN'].includes(c.state)}))throw new Error('invalid state');
 const passed=entries.filter(function(c){return c.state==='PASS'&&Boolean(c.evidence_url)}).length;
 return passed+'/'+entries.length+' ('+(100*passed/entries.length).toFixed(1)+'%)';
}
function deltaFor(previous,current){
 if(!previous)return {status:'UNKNOWN',newly_passed:null,regressed:null,new_blockers:null,resolved_blockers:null,remaining_blockers:null,scope_delta:null};
 const oldMap=new Map(previous.criteria.map(function(c){return [c.criterion_id,c]}));
 const newMap=new Map(current.criteria.map(function(c){return [c.criterion_id,c]}));
 const added=[...newMap.keys()].filter(function(id){return !oldMap.has(id)}).sort();
 const removed=[...oldMap.keys()].filter(function(id){return !newMap.has(id)}).sort();
 if(previous.scope_version!==current.scope_version||added.length||removed.length){
  return {status:'SCOPE_CHANGED',scope_delta:{added:added,removed:removed}};
 }
 const verified=function(c){return c.state==='PASS'&&Boolean(c.evidence_url)};
 const blocked=function(c){return c.state==='BLOCKED'};
 const changed=function(predicate){return [...newMap.keys()].filter(function(id){return predicate(oldMap.get(id),newMap.get(id))}).sort()};
 return {status:'COMPARABLE',scope_delta:{added:[],removed:[]},
  newly_passed:changed(function(oldItem,newItem){return !verified(oldItem)&&verified(newItem)}),
  regressed:changed(function(oldItem,newItem){return verified(oldItem)&&!verified(newItem)}),
  new_blockers:changed(function(oldItem,newItem){return !blocked(oldItem)&&blocked(newItem)}),
  resolved_blockers:changed(function(oldItem,newItem){return blocked(oldItem)&&!blocked(newItem)}),
  remaining_blockers:changed(function(oldItem,newItem){return blocked(newItem)})};
}
const metrics=document.querySelectorAll('#pv-contract .cards .metric');
['implementation','verification','production'].forEach(function(dimension,i){metrics[i].textContent=snapshotValid?metricFor(dimension):'UNKNOWN'});
let previousValid=snapshotValid;
if(snapshotValid&&snapshot.previous!==null){
 try{validateSnapshot(snapshot.previous)}catch(error){previousValid=false;console.error('Previous progress snapshot invalid:',error.message)}
}
const delta=previousValid?deltaFor(snapshot.previous,snapshot):{status:'UNKNOWN'};
metrics[3].textContent=delta.status==='COMPARABLE'?'PASS増加 '+delta.newly_passed.length+' / 後退 '+delta.regressed.length:delta.status==='SCOPE_CHANGED'?'SCOPE_CHANGED':'UNKNOWN';
const criterionRoot=document.getElementById('pv-criteria');
taskNames.forEach(function(name,i){
 const taskId='PV867-T'+String(i+1).padStart(2,'0');
 const d=document.createElement('details');const summary=document.createElement('summary');summary.textContent=taskId+' '+name+' — UNKNOWN / 確定母数 UNKNOWN';d.append(summary);
 const p=document.createElement('p');p.textContent='区分: '+(i<9?'マージ前候補':'後続候補')+' ／ 担当: '+(i<9?'🪐ソラ（暫定、T08/T09は🌙ルナ共同）':'未割当')+' ／ criterion_id: UNKNOWN（分解待ち） ／ 状態: UNKNOWN ／ required evidence: commit SHA / Actions run ID / review ID / merge SHA / 本番event ID（該当するものをルナが確定） ／ 残Blocker: 証跡と受入条件の未確定 ／ NEXT: #860の同一head証跡とcanonical criterionを照合';d.append(p);
 const a=document.createElement('a');a.href='https://github.com/sadouninc/Sado-Investment-Lab/pull/860';a.textContent='証跡候補 PR #860（PASS認定ではありません）';d.append(a);criterionRoot.append(d);
});
const loopNames=['READY検出','lease発行','ACK','実装commit','PR','最新head CI','review/安全Gate','merge SHA','NEXT_AUTO'];
const loopRoot=document.getElementById('pv-loop');
loopNames.forEach(function(name,i){const li=document.createElement('li');li.textContent=String(i+1)+'. '+name+' — UNKNOWN（work_ref・lease_id・個別evidence URL未確認）';loopRoot.append(li)});
const rows=[["01","Writer→Readerのイベント形式統一","🪐ソラ","work/lease/attemptの整合と曖昧入力拒否"],["02","GitHubコメント証跡の照合","🪐ソラ","comment ID・run ID・全履歴の真正性"],["03","POST前のReader接続","🪐ソラ","workflow内でReader実行の証跡"],["04","POST前のGuard接続","🪐ソラ","関連Issue/PR/コメントの完全取得"],["05","担当・競合・終端状態の再検証","🪐ソラ","UNKNOWN時の配車禁止"],["06","P0/P1候補の継続探索","🪐ソラ","先頭候補不適格でも次候補へ"],["07","安全性回帰テスト","🪐ソラ","ACK/PR/MERGED/不正入力/#79を検証"],["08","最新head CIとOwner Gate","🪐ソラ・🌙ルナ","CI・レビュー・マージ権限の証跡"],["09","差分全体の未発見Blocker調査","🌙ルナ・🪐ソラ","全変更ファイルとreviewの照合"],["10","期限切れ後の安全な自動再配車","未割当","後続候補・Ownerのscope判断待ち"],["11","高度なRecovery監視・最適化","未割当","後続候補・Ownerのscope判断待ち"]];
const list=document.getElementById('pv-list');
rows.forEach(function(row,i){
 const d=document.createElement('details');const s=document.createElement('summary');const title=document.createElement('strong');title.textContent=row[0]+' '+row[1];const tag=document.createElement('span');tag.className='tag';tag.textContent=i<9?'マージ前':'後続候補';s.append(title,tag);d.append(s);
 const meta=document.createElement('div');meta.className='meta';const owner=document.createElement('span');owner.className='pill';owner.textContent='担当: '+row[2];const state=document.createElement('span');state.className='pill';state.textContent='状態: 証跡照合待ち';meta.append(owner,state);d.append(meta);
 const dl=document.createElement('dl');[['残Blocker',row[3]],['完了条件',row[3]+'をテスト・CI・実証跡で確認'],['次のアクション',i<9?'PR #860の最新headと該当テスト・CIを照合':'🌙ルナが後続scopeと担当を確定'],['commit SHA','項目単位の対応は未確認'],['CI','項目単位の成功は未確認'],['PR','#{860}（OPEN時点）'.replace('#{860}','#860')],['merge SHA','未確認']].forEach(function(p){const dt=document.createElement('dt');dt.textContent=p[0];const dd=document.createElement('dd');dd.textContent=p[1];dl.append(dt,dd)});d.append(dl);const a=document.createElement('a');a.href='https://github.com/sadouninc/Sado-Investment-Lab/pull/860';a.textContent='PR #860 の証跡を見る →';d.append(a);list.append(d);
});
})();
</script>
