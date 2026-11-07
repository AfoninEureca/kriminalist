const {chromium}=require('playwright');const fs=require('fs');
(async()=>{const s=process.argv[2];const b=await chromium.launch();const p=await b.newPage({viewport:{width:1280,height:720}});
p.on('pageerror',e=>console.log('ERR',e.message));
await p.goto('file://'+process.cwd()+'/clip.html?s='+s);await p.evaluate(()=>window.READY);
fs.mkdirSync('f'+s,{recursive:true});
const only=process.argv[3]?process.argv[3].split(',').map(Number):null;
const frames=only||Array.from({length:480},(_,i)=>i);
for(const i of frames){const d=await p.evaluate(i=>window.frame(i),i);fs.writeFileSync(`f${s}/${String(i).padStart(4,'0')}.jpg`,Buffer.from(d.split(',')[1],'base64'))}
await b.close()})();
