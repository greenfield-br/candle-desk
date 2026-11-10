'use strict';
const $=id=>document.getElementById(id), canvas=$('chart'), ctx=canvas.getContext('2d');
let renderCandles=true;
let all=[],data=[],catalog=[],sid=null,end=0,count=65,showVolume=true,log=false,levels=[],placing=false,hover=null,drag=null,geom=null;
const seriesCache=new Map();
const fmt=n=>n==null?'—':new Intl.NumberFormat('en-US',{maximumFractionDigits:Math.abs(n)<1?6:2}).format(n);
const axisFmt=n=>Math.abs(n)>=1e6?new Intl.NumberFormat('en-US',{notation:'compact',maximumFractionDigits:2}).format(n):fmt(n);
function status(t){$('status').textContent=t;}
async function api(path,body){const r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});const v=await r.json();if(!r.ok)throw Error(v.error||r.statusText);return v;}
function aggregate(rows,frame){if(frame==='D')return rows;const map=new Map();for(const r of rows){let date=new Date(r.date+'T00:00:00Z'),key=r.date.slice(0,7);if(frame==='W'){date.setUTCDate(date.getUTCDate()-((date.getUTCDay()+6)%7));key=date.toISOString().slice(0,10);}let b=map.get(key);if(!b){b={...r,_full:r.open!=null,_volume:r.volume!=null};map.set(key,b);}else{b.high=b.high==null||r.high==null?null:Math.max(b.high,r.high);b.low=b.low==null||r.low==null?null:Math.min(b.low,r.low);b.close=r.close;b._full=b._full&&r.open!=null;b._volume=b._volume&&r.volume!=null;b.volume=b._volume?b.volume+r.volume:null;}if(!b._full)b.open=b.high=b.low=null;}return [...map.values()];}
async function refresh(id){seriesCache.clear();catalog=await api('/api/series');$('series').replaceChildren(...catalog.map(s=>{let o=document.createElement('option');o.value=s.id;o.textContent=`${s.display_symbol||s.symbol} · ${s.source} · ${s.bars} bars`;return o;}));renderSymbols();if(catalog.length){$('series').value=id||catalog[0].id;await load();}else draw();}
async function load(){sid=Number($('series').value);let s=catalog.find(s=>s.id===sid);renderCandles=s.chart_type==='candles';$('sumControls').hidden=sid!==-1;const assets=selectedStablecoins();if(sid===-1&&!assets.length){data=[];status('Select at least one stablecoin');draw();return;}const suffix=sid===-1?'&assets='+assets.join(','):'';const key=sid===-1?sid+suffix:sid;if(!seriesCache.has(key))seriesCache.set(key,await api('/api/bars?id='+sid+suffix));all=seriesCache.get(key);if(sid===-1)s={...s,first:all[0]?.date,last:all[all.length-1]?.date,bars:all.length,basis:assets.join('+')+'; USD market cap; common dates only'};status('');showVolume=all.some(r=>r.volume!=null);data=aggregate(all,$('frame').value);end=data.length;hover=null;try{levels=JSON.parse(localStorage.getItem('levels-'+sid)||'[]').filter(Number.isFinite);}catch{levels=[];}$('title').textContent=sid===-1?assets.join('+')+' market cap':(s.display_symbol||s.symbol);const snapshot=s.latest_state==='provisional'||(!s.latest_state&&all[all.length-1]?.date===new Date().toISOString().slice(0,10));$('subtitle').textContent=`${s.source.toUpperCase()} · Daily · ${snapshot?'LATEST AVAILABLE: SNAPSHOT':'EOD'}`;$('coverage').textContent=`${s.first} → ${s.last} · ${s.bars.toLocaleString()} bars · volume on ${s.volume_bars.toLocaleString()} bars. ${s.basis}`;$('sourceTag').textContent=s.source.toUpperCase();$('export').href='/api/export?id='+sid+suffix;$('symbolSearch').value=symbolLabel(s);renderSymbols();draw();}
function bound(){count=Math.max(8,Math.min(Math.max(8,data.length),Math.round(count)));end=Math.max(Math.min(count,data.length),Math.min(data.length,Math.round(end)));}
function text(t,x,y,color='#859ab9',align='left'){ctx.fillStyle=color;ctx.textAlign=align;ctx.fillText(t,x,y);}
function line(x1,y1,x2,y2,color){ctx.strokeStyle=color;ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();}
function draw(){const w=canvas.clientWidth,h=canvas.clientHeight,dpr=window.devicePixelRatio||1;if(!w||!h)return;canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);ctx.scale(dpr,dpr);ctx.fillStyle='#0c1422';ctx.fillRect(0,0,w,h);ctx.font='11px ui-monospace,monospace';bound();geom=null;
 if(!data.length){text('No local history for this selection',w/2,h/2,'#8ba1bf','center');return;}
 const start=Math.max(0,end-count),view=data.slice(start,end),left=12,right=w-84,top=16,bottom=h-(showVolume?Math.max(100,h*.18):32),step=(right-left)/count;
 const prices=view.flatMap(b=>[b.low??b.close,b.high??b.close]);let mn=Math.min(...prices),mx=Math.max(...prices);
 const useLog=log&&mn>0,T=v=>useLog?Math.log(v):v,I=v=>useLog?Math.exp(v):v;let lo=T(mn),hi=T(mx),pad=(hi-lo)*.08||Math.max(Math.abs(hi)*.01,.01);lo-=pad;hi+=pad;
 const Y=v=>top+(hi-T(v))/(hi-lo)*(bottom-top),P=y=>I(hi-(y-top)/(bottom-top)*(hi-lo));geom={left,right,top,bottom,step,start,Y,P};
 for(let i=0;i<=6;i++){let y=top+(bottom-top)*i/6;line(left,y,right,y,'#1b2a40');text(axisFmt(P(y)),right+8,y+4);}
 ctx.save();ctx.beginPath();ctx.rect(left,top,right-left,bottom-top);ctx.clip();
 view.forEach((b,j)=>{const x=left+(j+.5)*step,col=b.open==null?'#a6bedc':b.close>=b.open?'#50d5b3':'#ed7185';if(renderCandles&&b.open!=null){line(x,Y(b.high),x,Y(b.low),col);ctx.fillStyle=col;ctx.fillRect(x-Math.max(1,step*.64)/2,Math.min(Y(b.open),Y(b.close)),Math.max(1,step*.64),Math.max(1,Math.abs(Y(b.open)-Y(b.close))));}else if(!renderCandles&&j&&view[j-1]){line(x-step,Y(view[j-1].close),x,Y(b.close),col);}else if(!renderCandles){ctx.fillStyle=col;ctx.fillRect(x-2,Y(b.close)-2,4,4);}});
 levels.forEach(p=>{if(!useLog||p>0){ctx.setLineDash([6,4]);line(left,Y(p),right,Y(p),'#f5c575');ctx.setLineDash([]);}});ctx.restore();
 levels.forEach(p=>{if((!useLog||p>0)&&Y(p)>=top&&Y(p)<=bottom)text(axisFmt(p),right+8,Y(p)-3,'#f5c575');});
 const last=view[view.length-1];ctx.setLineDash([3,4]);line(left,Y(last.close),right,Y(last.close),'#4b778f');ctx.setLineDash([]);
 if(showVolume){const vs=view.map(b=>b.volume).filter(v=>v!=null),vmax=Math.max(1,...vs),vb=h-30,vt=bottom+28;line(left,vt-12,right,vt-12,'#223148');text(vs.length?'VOLUME · missing bars left blank':'VOLUME UNAVAILABLE',left,vt-17);view.forEach((b,j)=>{if(b.volume!=null){ctx.fillStyle=b.open!=null&&b.close<b.open?'#923e56':'#246c67';const vh=(vb-vt)*b.volume/vmax;ctx.fillRect(left+j*step+step*.15,vb-vh,step*.7,vh);}});}
 [0,.5,1].forEach((t,i)=>{const j=Math.round((view.length-1)*t),x=left+(j+.5)*step;text(view[j].date,x,h-9,'#91a6c3',i===0?'left':i===2?'right':'center');});
 let selected=last;if(hover&&hover.x>=left&&hover.x<=right){const j=Math.max(0,Math.min(view.length-1,Math.floor((hover.x-left)/step)));selected=view[j];ctx.setLineDash([3,4]);line(left+(j+.5)*step,top,left+(j+.5)*step,h-28,'#7991b3');if(hover.y<=bottom&&hover.y>=top){line(left,hover.y,right,hover.y,'#7991b3');text(axisFmt(P(hover.y)),right+8,hover.y-5,'#fff');}ctx.setLineDash([]);}
 $('readout').textContent=`${selected.date}  O ${fmt(selected.open)}  H ${fmt(selected.high)}\nL ${fmt(selected.low)}  C ${fmt(selected.close)}  V ${fmt(selected.volume)}`;$('readout').style.whiteSpace='pre-line';$('range').textContent=`${view[0].date} — ${last.date}`;
 if(log&&!useLog)text('Log unavailable: non-positive price',left,top+14,'#f5c575');
}
function pan(n){end+=n;hover=null;draw();}function zoom(f){count*=f;draw();}
$('series').onchange=()=>load().catch(e=>status(e.message));$('frame').onchange=()=>{data=aggregate(all,$('frame').value);end=data.length;hover=null;const s=catalog.find(s=>s.id===sid);renderCandles=s.chart_type==='candles';if(s){const snapshot=s.latest_state==='provisional'||(!s.latest_state&&all[all.length-1]?.date===new Date().toISOString().slice(0,10));$('subtitle').textContent=`${s.source.toUpperCase()} · Daily · ${snapshot?'LATEST AVAILABLE: SNAPSHOT':'EOD'}`;}draw();};
$('older').onclick=()=>pan(-Math.max(1,Math.round(count*.2)));$('newer').onclick=()=>pan(Math.max(1,Math.round(count*.2)));$('latest').onclick=()=>{end=data.length;draw();};$('zoomIn').onclick=()=>zoom(.8);$('zoomOut').onclick=()=>zoom(1.25);$('volume').onclick=()=>{showVolume=!showVolume;draw();};$('scale').onclick=()=>{log=!log;draw();};
function keepLevels(){localStorage.setItem('levels-'+sid,JSON.stringify(levels));}
$('line').onclick=()=>{placing=!placing;$('line').classList.toggle('active',placing);};$('undo').onclick=()=>{levels.pop();keepLevels();draw();};
canvas.onpointerdown=e=>{if(!geom)return;const rect=canvas.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;if(placing){if(y>=geom.top&&y<=geom.bottom&&x<=geom.right){levels.push(geom.P(y));keepLevels();placing=false;$('line').classList.remove('active');draw();}return;}drag={x:e.clientX,end};canvas.setPointerCapture(e.pointerId);};
canvas.onpointermove=e=>{const r=canvas.getBoundingClientRect();hover={x:e.clientX-r.left,y:e.clientY-r.top};if(drag&&geom)end=drag.end-Math.round((e.clientX-drag.x)/geom.step);draw();};canvas.onpointerup=canvas.onpointercancel=()=>drag=null;canvas.onpointerleave=()=>{if(!drag){hover=null;draw();}};
canvas.addEventListener('wheel',e=>{e.preventDefault();if(e.shiftKey)pan(e.deltaY>0?5:-5);else zoom(e.deltaY>0?1.12:1/1.12);},{passive:false});
function obs(on){document.body.classList.toggle('obs',on);requestAnimationFrame(draw);}
$('broadcast').onclick=()=>obs(true);$('exit').onclick=()=>obs(false);
window.onkeydown=e=>{if(/INPUT|SELECT|TEXTAREA/.test(e.target.tagName))return;if(['ArrowLeft','ArrowRight','Home','End','Escape'].includes(e.key))e.preventDefault();if(e.key==='ArrowLeft')pan(-5);if(e.key==='ArrowRight')pan(5);if(e.key==='Home'){end=count;draw();}if(e.key==='End'){end=data.length;draw();}if(e.key==='Escape')obs(false);};
new ResizeObserver(draw).observe(canvas);api('/api/stablecoins').then(cfg=>{for(const a of ['USDT','USDC','OUSD'])$('sum'+a).checked=cfg.default_selection.includes(a);return refresh();}).catch(e=>status(e.message));

function favouriteIds(){try{return JSON.parse(localStorage.getItem('favourite-series')||'[]').filter(Number.isInteger);}catch{return [];}}
function symbolLabel(s){return `${s.display_symbol||s.symbol} · ${s.source} · #${s.id}`;}
function renderSymbols(){
 const pins=favouriteIds();
 $('symbols').replaceChildren(...[...catalog].sort((a,b)=>Number(pins.includes(b.id))-Number(pins.includes(a.id))).map(s=>{const o=document.createElement('option');o.value=symbolLabel(s);return o;}));
 $('favourites').replaceChildren(...catalog.filter(s=>pins.includes(s.id)).map(s=>{const b=document.createElement('button');b.textContent=`★ ${s.display_symbol||s.symbol} · ${s.source}`;b.onclick=()=>{$('series').value=s.id;load().catch(e=>status(e.message));};return b;}));
 $('pin').textContent=pins.includes(sid)?'★ Unpin favourite':'☆ Pin favourite';
}
$('symbolSearch').onchange=()=>{const s=catalog.find(s=>symbolLabel(s)===$('symbolSearch').value);if(s){$('series').value=s.id;load().catch(e=>status(e.message));}};
$('pin').onclick=()=>{if(!sid)return;let pins=favouriteIds();pins=pins.includes(sid)?pins.filter(id=>id!==sid):[...pins,sid];localStorage.setItem('favourite-series',JSON.stringify(pins));renderSymbols();};

function selectedStablecoins(){return ['USDT','USDC','OUSD'].filter(a=>$('sum'+a).checked);}
for(const a of ['USDT','USDC','OUSD'])$('sum'+a).onchange=()=>{load().catch(e=>{data=[];draw();status(e.message);});};
