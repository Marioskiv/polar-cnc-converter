/*
 * Polar CNC — validation sweeps (not part of `npm test`; takes ~1 minute)
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 *
 * Run after any change to the converter:   node tools/sweeps.js
 * 1) 3,000 random arcs (I/J and R, near and far from the pole, flat and helical)
 * 2) 1,424 lines passing 0..3 mm from the pole, flat and ramping, 4 angles, X Min 0 and -18
 * 3) 800 random polylines with tiny segments and sharp corners
 * Pass criterion: worst G1 deviation <= chord tolerance (0.025 mm) + 0.001 mm.
 */
'use strict';
const {convert}=require(require('path').join(__dirname,'..','src','core','converter.js')); const {analyse}=require(require('path').join(__dirname,'..','tests','lib','replay.js'));
// 1. random arcs (I/J and R, near and far from the pole, flat and helical)
let seed=12345; const rnd=()=>{seed=(seed*1103515245+12345)%2147483648; return seed/2147483648;};
let w=[0,''], n=0, over=0, blocks=0;
for (let i=0;i<1500;i++) {
  const R=0.5+rnd()*40, cx=(rnd()-0.5)*2*(rnd()<0.3?R:60), cy=(rnd()-0.5)*2*(rnd()<0.3?R:60);
  const a0=rnd()*2*Math.PI, sweep=(0.2+rnd()*1.7)*Math.PI*(rnd()<0.5?1:-1);
  const x0=cx+R*Math.cos(a0), y0=cy+R*Math.sin(a0), x1=cx+R*Math.cos(a0+sweep), y1=cy+R*Math.sin(a0+sweep);
  const G=sweep<0?'G2':'G3'; const useR=rnd()<0.4;
  const arc = useR ? G+' X'+x1.toFixed(4)+' Y'+y1.toFixed(4)+' R'+(Math.abs(sweep)>Math.PI?-R:R).toFixed(4)
                   : G+' X'+x1.toFixed(4)+' Y'+y1.toFixed(4)+' I'+(cx-x0).toFixed(4)+' J'+(cy-y0).toFixed(4);
  const g='G21 G90\nG0 X'+x0.toFixed(4)+' Y'+y0.toFixed(4)+' Z2\nG1 Z-1 F300\n'+arc+' Z'+(rnd()<0.5?-1:-2.5)+' F500\nG0 Z5\nM30';
  for (const xm of [0,-18]) { const r=analyse('a',g,convert(g,{xMin:xm,xMax:125}),{},true); n++; blocks+=r.g1;
    if (r.maxDevG1>0.026) over++; if (r.maxDevG1>w[0]) w=[r.maxDevG1,arc]; }
}
console.log('random arcs  :',n,'| over 0.026:',over,'| worst',w[0].toFixed(4),'mm');
// 2. dense near-pole line sweep
w=[0,'']; n=0; over=0; const ds=[]; for(let d=0; d<=0.06; d+=0.001) ds.push(+d.toFixed(3)); for(let d=0.1; d<=3; d+=0.1) ds.push(+d.toFixed(2));
for (const xm of [0,-18]) for (const d of ds) for (const ang of [0,37,90,211]) for (const z of [[-1,-1],[-0.5,-2]]) {
  const a=ang*Math.PI/180, c=Math.cos(a), s=Math.sin(a); const P=(u,v)=>[u*c-v*s, u*s+v*c]; const [x0,y0]=P(40,d), [x1,y1]=P(-40,d);
  const g='G21 G90\nG0 X'+x0.toFixed(4)+' Y'+y0.toFixed(4)+' Z2\nG1 Z'+z[0]+' F300\nG1 X'+x1.toFixed(4)+' Y'+y1.toFixed(4)+' Z'+z[1]+' F500\nG0 Z5\nM30';
  const r=analyse('x',g,convert(g,{xMin:xm,xMax:113}),{},true); n++; if (r.maxDevG1>0.026) over++; if (r.maxDevG1>w[0]) w=[r.maxDevG1,'d='+d];
}
console.log('near-pole lines:',n,'| over 0.026:',over,'| worst',w[0].toFixed(4),'mm');
// 3. random polylines with sharp corners and tiny CAM segments (the corner-cutting case)
seed=777; w=[0,'']; n=0; over=0;
for (let i=0;i<400;i++) {
  let x=(rnd()-0.5)*80, y=(rnd()-0.5)*80; const L=['G21 G90','G0 X'+x.toFixed(4)+' Y'+y.toFixed(4)+' Z2','G1 Z-1 F300'];
  for (let k=0;k<25;k++) { const step = rnd()<0.5 ? 0.01+rnd()*0.12 : 0.5+rnd()*8; const a=rnd()*2*Math.PI;
    x+=step*Math.cos(a); y+=step*Math.sin(a); L.push('G1 X'+x.toFixed(4)+' Y'+y.toFixed(4)+' F500'); }
  L.push('G0 Z5','M30'); const g=L.join('\n');
  for (const xm of [0,-18]) { const r=analyse('p',g,convert(g,{xMin:xm,xMax:125}),{},true); n++; if (r.maxDevG1>0.026) over++; if (r.maxDevG1>w[0]) w=[r.maxDevG1,'poly '+i]; }
}
console.log('random polylines with tiny segments + sharp corners:',n,'| over 0.026:',over,'| worst',w[0].toFixed(4),'mm');
