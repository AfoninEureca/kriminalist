const NP={U1:[1,1],U2:[0,1],U3:[1,0],U4:[2,1],U5:[2,0],U6:[1,2],U7:[2,2],U8:[0,2],U9:[0,0]};
const STD_EDGES=[['U1','U3'],['U1','U4'],['U1','U6'],['U3','U4'],['U4','U5'],['U5','U7'],['U6','U7'],['U4','U8'],['U2','U1'],['U9','U5'],['U9','U2']];
const p2=i=>String(i+1).padStart(2,'0');
function mkNodes(a){const o={};Object.keys(NP).forEach((k,i)=>o[k]=[a[i],...NP[k]]);return o}
function mkHY(a){const S=[{id:'H1',lab:'dt',ok:1,n:'U1'},{id:'H2',lab:'dt',ok:0,ins:1,n:'U1'},{id:'H3',lab:'dt',ok:1,n:'U3',preRej:'H2'},{id:'H4',lab:'hw',ok:1,n:'U4',pre:'H3'},{id:'H5',lab:'sw',ok:1,n:'U5',pre:'H3'},{id:'H6',lab:'sw',ok:1,n:'U7',pre:'H5'},{id:'H7',lab:'dt',ok:0,legal:1,n:'U8'},{id:'H8',lab:'sw',ok:0,n:'U1'},{id:'H9',lab:'dt',ok:1,key:'K2',n:'U2'},{id:'H10',lab:'dt',ok:1,key:'K3',n:'U9'},{id:'H11',lab:'sw',ok:1,n:'U7',pre:'H6'},{id:'H12',lab:'sw',ok:1,n:'U6',pre:'H1'}];
 return S.map((s,i)=>Object.assign({c:'Г-'+p2(i),t:a[i][0],who:a[i][1],say:a[i][2],r:a[i][3]},s))}
function mkMS(a,v){const S=[{needs:'H1'},{needs:null},{needs:'H3',pre:['M2'],v:['В-01',v[0],{t:60,i:10}]},{needs:'H6',pre:['M3'],v:['В-02',v[1],{r:1}]},{needs:'H12'},{needs:'H5'},{needs:'H4',pre:['M2'],v:['В-03',v[2],{i:15}]},{needs:'H11'},{needs:'H4'},{needs:null,decoy:1},{needs:'H5'},{needs:'H9'}];
 return S.map((s,i)=>Object.assign({id:'M'+(i+1),c:'М-'+p2(i),t:a[i][0],who:a[i][1],say:a[i][2]},s))}
function mkDOS(a){const af={7:'H4',8:'H9',9:'H6'};return a.map((x,i)=>Object.assign({id:'D'+(i+1),k:x[0],ep:x[1],t:x[2]},af[i]?{after:af[i]}:{}))}
function mkRULES(a){const ids=[['D5','D6'],['D1','D2'],['D3','D4'],['D8','D9'],['D10','D5'],['D7','D2']];return ids.map((x,i)=>Object.assign({k:'K'+(i+1),ids:x,t:a[i]+(i===1?' Открыта Г-09.':i===2?' Открыта Г-10.':'')},i===1?{unlock:'H9'}:i===2?{unlock:'H10'}:{}))}
function mkCONCL(a){return a.map((t,i)=>Object.assign({id:'c'+(i+1),t},i===0?{ok:1}:{}))}
function mkDEPT(o){const r={};Object.keys(o).forEach(k=>r[k]={v:o[k][0],do:o[k].slice(1)});return r}
function mkEP(o){return Object.assign({need:['M1','M2','M3','M4','M5','M6','M7','M8'],total:865,half:432,decoyId:'M10',days:['Пн','Вт']},o)}
