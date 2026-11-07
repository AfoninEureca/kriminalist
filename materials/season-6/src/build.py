import glob,re
e=open('hq/engine.html',encoding='utf8').read()
parts=[]
for f in sorted(glob.glob('hq/ep[0-9]*.js')):
    n=re.search(r'ep(\d+)\.js',f).group(1)
    body=open(f,encoding='utf8').read()
    parts.append(f'EPS[{n}]=function(){{\n{body}\nreturn {{HY,MS,DOS,RULES,CONCL,NODES,EDGES,DEPT,INTRO,BR1,EP}};}};')
block=open('hq/prelude.js',encoding='utf8').read()+'\nconst EPS={};\n'+'\n'.join(parts)
open('hq_all.html','w',encoding='utf8').write(e.replace('/*__EPISODE__*/',block))
