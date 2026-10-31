const fs=require('fs'),path=require('path'),sharp=require('sharp');
const base=__dirname,out=path.join(base,'payload/assets');fs.mkdirSync(out,{recursive:true});
const svg=(s,w,h)=>`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${s}</svg>`;
(async()=>{
 const guardian=path.resolve(base,'../../src/assets/guardian-anime-v1.png');
 await sharp(guardian).resize(84,84,{fit:'contain'}).png().toFile(path.join(out,'device_guard.png'));
 await sharp(guardian).resize(42,42,{fit:'contain'}).png().toFile(path.join(out,'crest.png'));
 const shapes={back:'M21 12H5L11 6M5 12L11 18',home:'M3 11L12 3L21 11M6 10V21H18V10M10 21V15H14V21',tasks:'M4 5H18V21H4ZM8 2H21V17'};
 for(const [name,d] of Object.entries(shapes))await sharp(Buffer.from(svg(`<path d="${d}" transform="translate(4,4)" stroke="#e1c29a" stroke-width="1.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`,32,32))).resize(64,64).png().toFile(path.join(out,'nav-'+name+'.png'));
 await sharp(Buffer.from(svg('<text x="1" y="34" font-family="KaiTi,STKaiti,serif" font-size="28" fill="#f4dfbd" letter-spacing="5">设备桌面</text>',250,44))).png().toFile(path.join(out,'desktop-title.png'));
 const wallpaper=path.join(base,'art/wallpaper.png');
 await sharp(fs.existsSync(wallpaper)?wallpaper:path.resolve(base,'../../src/assets/hud/background.jpg')).resize(952,600,{fit:'cover'}).jpeg({quality:91,chromaSubsampling:'4:4:4'}).toFile(path.join(out,'wallpaper.jpg'));
 for(const name of fs.readdirSync(path.join(base,'art'))){if(!name.endsWith('.png')||name==='wallpaper.png')continue;await sharp(path.join(base,'art',name)).resize(84,84,{fit:'contain'}).png().toFile(path.join(out,name));}
 console.log(out);
})().catch(e=>{console.error(e);process.exit(1)});
