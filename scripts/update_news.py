<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>CALTA — Центрально-Азиатская логистическая транспортная ассоциация</title>
<meta name="description" content="CALTA — независимая платформа для развития логистики, международной торговли и цифровой трансформации в Центральной Азии." />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
  --navy:#101B33;
  --navy-2:#17223F;
  --navy-3:#1F2C4D;
  --red-1:#300309;
  --red-2:#3F1717;
  --red-3:#4D1F1F;
  --red-bright:#BD0F26;
  --red-card:#5F0712;
  --red-card-2:#8F0A1C;
  --green-1:#042F0B;
  --green-bright:#0FBD2B;
  --green-card:#0A521B;
  --green-card-2:#137A29;
  --gold-1:#022331;
  --gold-bright:#0F87BD;
  --gold-card:#034563;
  --gold-card-2:#056894;
  --amber-1:#2B1B02;
  --amber-2:#3D2705;
  --amber-bright:#D99A3D;
  --amber-card:#4A2E05;
  --amber-card-2:#6E4A12;
  --up:#6FCF8E;
  --down:#E38080;
  --sand:#E7E0CC;
  --sand-2:#F4F0E4;
  --turquoise:#14958C;
  --turquoise-light:#4FB8AF;
  --ochre:#C6862E;
  --ink:#171712;
  --cream:#F3EFE2;
  --line:rgba(23,23,18,0.14);
  --line-dark:rgba(243,239,226,0.16);
  --display:'IBM Plex Sans',sans-serif;
  --body:'IBM Plex Sans',sans-serif;
  --mono:'IBM Plex Mono',monospace;
}

html {
  zoom: 1.1;
  -moz-transform: scale(1.1);
  -moz-transform-origin: top left;
}
  *{box-sizing:border-box;margin:0;padding:0;}
  html{scroll-behavior:smooth;}
  body{
    font-family:var(--body);
    background:var(--sand-2);
    color:var(--ink);
    line-height:1.5;
    overflow-x:hidden;
  }
  a{color:inherit;text-decoration:none;}
  img,svg{display:block;max-width:100%;}
  .wrap{max-width:1180px;margin:0 auto;padding:0 32px;}

  .eyebrow{
    font-family:var(--mono);
    font-size:12px;
    letter-spacing:.14em;
    text-transform:uppercase;
    display:flex;align-items:center;gap:10px;
    margin-bottom:18px;
    opacity:.75;
  }
  .eyebrow .dot{width:7px;height:7px;border-radius:50%;background:var(--ochre);flex:0 0 auto;}
  .eyebrow .dot.tq{background:var(--turquoise);}

  h1,h2,h3{font-family:var(--display);font-weight:600;letter-spacing:-.01em;}

  header{
    position:fixed;top:0;left:0;right:0;z-index:1000;
    background:rgb(251, 251, 252);
    backdrop-filter:blur(10px);
    border-bottom:1px solid var(--line-dark);
    transition:transform .35s cubic-bezier(.4,0,.2,1);
  }
  header.header-hidden{transform:translateY(-100%);}
  .rate-ticker{
    background:var(--navy);border-bottom:1px solid var(--line-dark);
    overflow-x:auto;scrollbar-width:none;
  }
  .rate-ticker::-webkit-scrollbar{display:none;}
  .rate-ticker-inner{
    display:flex;align-items:center;gap:22px;
    max-width:1180px;margin:0 auto;padding:7px 32px;
    white-space:nowrap;
  }
  .rate-item{
    font-family:var(--mono);font-size:11px;letter-spacing:.04em;
    color:var(--cream);opacity:.75;display:inline-flex;gap:7px;align-items:baseline;
  }
  .rate-label{color:#ffffff;opacity:1;}
  .rate-value{color:var(--turquoise-light);font-weight:500;}
  .rate-updated{
    font-family:var(--mono);font-size:10px;letter-spacing:.04em;
    color:var(--cream);opacity:.4;margin-left:auto;padding-left:16px;
  }
  @media(max-width:760px){
    .rate-updated{display:none;}
  }
  .nav{
    display:flex;align-items:center;justify-content:space-between;
    padding:0px 32px;max-width:1180px;margin:0 auto;
  }
  .nav-right{display:flex;align-items:center;}
  .nav-left{display:flex;align-items:center;gap:38px;}
  .logo{display:flex;align-items:center;gap:10px;}
  .logo-mark{width:34px;height:34px;flex:0 0 auto;}
  .logo-badge{position:relative;width:120px;height:120px;flex:0 0 auto;}
  .logo-badge-inner{
    position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
    width:120px;height:120px;
    display:flex;align-items:center;justify-content:center;
  }
  .logo-img{
    width:100%;height:100%;object-fit:contain;display:block;
  }
  .logo-text{font-family:var(--display);font-weight:700;font-size:17px;letter-spacing:.02em;line-height:1.1;}
  .logo-text span{display:block;font-family:var(--mono);font-weight:400;font-size:9.5px;letter-spacing:.1em;opacity:.6;text-transform:uppercase;margin-top:2px;}
  nav.links{display:flex;gap:26px;align-items:center;}
  nav.links a{font-family:var(--mono);
    font-size:12.5px;letter-spacing:.06em;
    text-transform:uppercase;
    color:#000000;
    opacity:.8;transition:opacity .2s;
  }
  nav.links a:hover{opacity:1;}
  .nav-cta{
    font-family:var(--mono);font-size:12px;letter-spacing:.06em;text-transform:uppercase;
    color:#000000;background:var(--turquoise-light);
    padding:9px 16px;border-radius:2px;white-space:nowrap;
  }
  .nav-cta-mobile{
    display:none;
    font-family:var(--mono);font-size:12px;letter-spacing:.06em;text-transform:uppercase;
    color:#000000;background:var(--turquoise-light);
    padding:12px 16px;border-radius:2px;
  }

  .nav-dropdown{position:relative;}
  .nav-dropdown-trigger{
    display:flex;flex-direction:row;align-items:center;gap:8px;
    font-family:var(--mono);font-size:12.5px;letter-spacing:.06em;text-transform:uppercase;
    color:#000000;opacity:.8;cursor:default;transition:opacity .2s;white-space:nowrap;
  }
  .nav-dropdown:hover .nav-dropdown-trigger{opacity:1;}
  .nav-dropdown-arrow{
    width:13px;height:13px;flex:0 0 auto;
    transform:rotate(0deg);
    transition:transform .45s cubic-bezier(.4,0,.2,1);
  }
  .nav-dropdown:hover .nav-dropdown-arrow{transform:rotate(180deg);}
  .nav-dropdown::after{
    content:'';position:absolute;left:50%;transform:translateX(-50%);
    top:100%;width:220px;height:18px;
  }
  .nav-dropdown-menu{
    position:absolute;top:calc(100% + 14px);left:50%;
    transform:translate(-50%,8px);
    min-width:200px;
    background:#ffffff;border:1px solid rgba(0,0,0,.1);
    box-shadow:0 18px 40px rgba(0,0,0,.25);
    opacity:0;visibility:hidden;pointer-events:none;
    transition:opacity .25s ease,transform .25s ease,visibility .25s;
    z-index:1200;
  }
  .nav-dropdown:hover .nav-dropdown-menu,
  .nav-dropdown:focus-within .nav-dropdown-menu{
    opacity:1;visibility:visible;pointer-events:auto;transform:translate(-50%,0);
  }
  .nav-dropdown-menu a{
    display:block;padding:14px 18px;
    font-family:var(--mono);font-size:12px;letter-spacing:.05em;text-transform:uppercase;
    color:#000000;opacity:.85;border-top:1px solid rgba(0,0,0,.08);
    transition:opacity .2s,background .2s;
  }
  .nav-dropdown-menu a:first-child{border-top:none;}
  .nav-dropdown-menu a:hover{opacity:1;background:rgba(0,0,0,.05);color:var(--turquoise);}
  .burger{display:none;background:none;border:none;color:#000000;cursor:pointer;}

  .hero{
    position:relative;min-height:100vh;
    background:linear-gradient(160deg, var(--navy) 0%, var(--navy-2) 55%, var(--navy) 100%);
    color:var(--cream);
    display:flex;flex-direction:column;justify-content:center;
    padding-top:168px;
    overflow:hidden;
  }
  .hero-map{position:absolute;inset:0;width:100%;height:100%;opacity:.9;transform:translateY(60px);}
  .hero-map .route{
    fill:none;stroke:var(--ochre);stroke-width:1.4;stroke-dasharray:6 3000;
    animation:draw 3.5s ease forwards;
    opacity:.55;
  }
  .hero-map .route.tq{stroke:var(--turquoise-light);}
  .hero-map .node circle{fill:var(--sand);opacity:.85;}
  .hero-map .node text{font-family:var(--mono);font-size:9px;fill:var(--cream);opacity:.5;letter-spacing:.04em;}
  @keyframes draw{ to{ stroke-dasharray:6000 6000; } }
  @media (prefers-reduced-motion: reduce){
    .hero-map .route{animation:none;stroke-dasharray:none;opacity:.4;}
  }

  .section-map{position:absolute;inset:0;width:100%;height:100%;z-index:-1;pointer-events:none;}
  .section-map .route{
    fill:none;stroke:var(--ochre);stroke-width:1.4;stroke-dasharray:6 3000;
    animation:draw 3.5s ease forwards;
    animation-play-state:paused;
    opacity:.32;
  }
  .section-map.in .route{animation-play-state:running;}
  .section-map .route.tq{stroke:var(--turquoise-light);}
  .section-map .map-silhouette{opacity:.22;stroke-width:2.6;}
  .section-map .grid-dot circle{fill:var(--ochre);opacity:.4;}
  .section-map text{font-family:var(--mono);font-size:11px;font-weight:500;fill:var(--cream);opacity:.6;letter-spacing:.06em;}
  .section-map .label-dot{fill:var(--turquoise-light);opacity:.9;}
  @media (prefers-reduced-motion: reduce){
    .section-map .route{animation:none;stroke-dasharray:none;opacity:.25;}
  }

  @media(max-width:900px){
    .section-map{display:none;}
  }

  .hero-inner{position:relative;z-index:2;}
  .hero-inner.wrap{max-width:none;margin:0;padding-left:18vw;padding-right:32px;}
  .hero-content{max-width:760px;padding:60px 0 90px;}
  .hero h1{
    font-size:clamp(38px,6vw,66px);
    line-height:1.04;
    margin-bottom:26px;
  }
  .hero h1 em{font-style:normal;color:var(--turquoise-light);}
  .hero p.lead{
    font-family:var(--body);font-size:18px;line-height:1.65;
    max-width:600px;color:rgba(243,239,226,.85);margin-bottom:38px;
  }
  .hero-actions{display:flex;gap:14px;flex-wrap:wrap;}
  .btn{
    font-family:var(--mono);font-size:12.5px;letter-spacing:.06em;text-transform:uppercase;
    padding:14px 24px;border-radius:2px;display:inline-flex;align-items:center;gap:8px;
    border:1px solid var(--line-dark);transition:all .2s;
  }
  .btn-primary{background:var(--ochre);color:var(--navy);border-color:var(--ochre);}
  .btn-primary:hover{background:#dd9a3c;}
  .btn-ghost{color:var(--cream);}
  .btn-ghost:hover{background:rgba(243,239,226,.08);}

  section{padding:110px 0;position:relative;z-index:0;}
  section.dark{background:var(--navy);color:var(--cream);}
  section.dark.section-red{background:linear-gradient(135deg, var(--red-1) 0%, var(--red-bright) 65%, var(--red-1) 130%);}
  section.dark.section-green{background:linear-gradient(135deg, var(--green-1) 0%, var(--green-bright) 65%, var(--green-1) 130%);}
  section.dark.section-red .adv-card{background:linear-gradient(150deg, var(--red-card) 0%, var(--red-card-2) 100%);border-color:rgba(243,239,226,0.16);}
  section.dark.section-green .adv-card{background:linear-gradient(150deg, var(--green-card) 0%, var(--green-card-2) 100%);border-color:rgba(243,239,226,0.16);}
  section.dark.section-red .goals-visual{background:linear-gradient(150deg, var(--red-card) 0%, var(--red-card-2) 100%);}
  section.dark.section-green .goals-visual{background:linear-gradient(150deg, var(--green-card) 0%, var(--green-card-2) 100%);}
  section.dark.section-gold{
    background:linear-gradient(135deg, var(--gold-1) 0%, var(--gold-bright) 65%, var(--gold-1) 130%);
    padding:56px 0;
  }
  section.dark.section-gold .adv-card,
  section.dark.section-gold .goals-visual{background:linear-gradient(150deg, var(--gold-card) 0%, var(--gold-card-2) 100%);border-color:rgba(243,239,226,0.16);}
  section.dark.section-amber{background:linear-gradient(150deg, var(--amber-1) 0%, var(--amber-bright) 68%, var(--amber-2) 130%);}

  .news-layout{display:grid;grid-template-columns:1.3fr 1fr;gap:24px;align-items:stretch;}

  .news-featured-col{display:flex;flex-direction:column;height:100%;}
  .news-featured{
    position:relative;
    background:var(--sand-2);border:1px solid var(--line);border-radius:3px;
    display:flex;flex-direction:column;overflow:hidden;
    flex:1;
  }
  .nf-body{padding:26px 26px 20px;display:flex;flex-direction:column;gap:12px;flex:1;}
  .nf-body h3{font-size:23px;line-height:1.32;font-weight:600;}
  .nf-body p{font-family:var(--body);font-size:15px;line-height:1.6;opacity:.75;}

  .news-arrow{
    position:absolute;bottom:14px;z-index:4;
    width:36px;height:36px;border-radius:50%;border:1px solid var(--line);
    background:var(--sand-2);color:var(--ink);display:flex;align-items:center;justify-content:center;
    cursor:pointer;transition:background .2s,border-color .2s,transform .15s,opacity .2s;
    box-shadow:0 2px 8px rgba(0,0,0,.06);
  }
  .news-arrow.news-arrow-prev{left:14px;}
  .news-arrow.news-arrow-next{right:14px;}
  .news-arrow svg{width:15px;height:15px;}
  .news-arrow:hover{background:var(--turquoise);border-color:var(--turquoise);color:#fff;}
  .news-arrow:active{transform:scale(.92);}
  .news-arrow:disabled{opacity:.35;pointer-events:none;}

  .ic-tag{
    align-self:flex-start;font-family:var(--mono);font-size:10px;letter-spacing:.08em;text-transform:uppercase;
    color:var(--turquoise);background:rgba(20,149,140,.09);border:1px solid rgba(20,149,140,.25);
    padding:4px 9px;border-radius:2px;
  }
  .ic-tag.small{font-size:8.5px;padding:3px 7px;}
  .ic-foot{
    margin-top:auto;padding:14px 54px 4px;border-top:1px solid var(--line);
    font-family:var(--mono);font-size:10.5px;letter-spacing:.03em;opacity:.5;
    display:flex;justify-content:space-between;align-items:center;gap:10px;min-height:36px;
  }

  .nf-photo{
    position:relative;aspect-ratio:16/10;width:100%;flex:0 0 auto;
    background:linear-gradient(150deg,#DED4B8 0%,#EDE7D4 100%);
    display:flex;align-items:center;justify-content:center;flex-direction:column;gap:8px;
    color:var(--ink);
  }
  .nf-photo svg{width:30px;height:30px;opacity:.35;}
  .nf-photo span{font-family:var(--mono);font-size:10px;letter-spacing:.05em;text-transform:uppercase;opacity:.4;}
  .nf-photo img{width:100%;height:100%;object-fit:cover;display:block;}

  .news-side{
    display:flex;flex-direction:column;gap:12px;
    cursor:grab;touch-action:pan-y;
    position:relative;
    height:100%;
    align-self:stretch;
  }
  .news-side.dragging{cursor:grabbing;user-select:none;}
  .news-mini{
    display:flex;flex-direction:column;gap:6px;justify-content:center;
    flex:1 1 0;
    min-height:0;
    background:var(--sand-2);border:1px solid var(--line);border-radius:3px;padding:16px 18px;
    cursor:pointer;transition:border-color .2s, opacity .2s;
  }
  .news-mini:hover{border-color:var(--turquoise);}
  .news-mini h4{font-size:13.5px;font-weight:600;line-height:1.35;}
  .nm-date{font-family:var(--mono);font-size:10px;opacity:.5;margin-top:auto;padding-top:6px;}

  @media(max-width:900px){
    .news-layout{grid-template-columns:1fr;align-items:start;}
    .news-side{cursor:auto;height:auto;}
    .news-mini{flex:0 0 auto;}
    .news-arrow{bottom:12px;}
    .news-arrow.news-arrow-prev{left:12px;}
    .news-arrow.news-arrow-next{right:12px;}
    .ic-foot{padding:12px 48px 2px;}
  }

  .grain-wrap{display:grid;grid-template-columns:1.15fr 1fr;gap:28px;align-items:stretch;}
  .grain-hero{
    background:rgba(23,15,2,.28);border:1px solid rgba(243,239,226,0.18);border-radius:4px;
    padding:34px 36px;display:flex;flex-direction:column;
  }
  .grain-hero-top{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:26px;flex-wrap:wrap;}
  .grain-crop{display:flex;align-items:center;gap:12px;}
  .grain-crop-icon{width:38px;height:38px;flex:0 0 auto;}
  .grain-crop-name{font-family:var(--display);font-size:20px;font-weight:600;color:var(--cream);}
  .grain-crop-sub{font-family:var(--mono);font-size:11px;letter-spacing:.05em;color:var(--cream);opacity:.55;margin-top:2px;}
  .demo-badge{
    font-family:var(--mono);font-size:9.5px;letter-spacing:.07em;text-transform:uppercase;
    color:var(--amber-1);background:var(--cream);padding:5px 10px;border-radius:20px;white-space:nowrap;
  }
  .grain-price-row{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:8px;}
  .grain-price{font-family:var(--display);font-size:clamp(46px,5.5vw,64px);font-weight:600;color:var(--cream);line-height:1;}
  .grain-unit{font-family:var(--mono);font-size:14px;color:var(--cream);opacity:.55;}
  .grain-change{
    display:inline-flex;align-items:center;gap:6px;font-family:var(--mono);font-size:14px;font-weight:500;
    padding:5px 11px;border-radius:20px;
  }
  .grain-change.up{color:var(--up);background:rgba(111,207,142,.14);}
  .grain-change.down{color:var(--down);background:rgba(227,128,128,.14);}
  .grain-meta{font-family:var(--mono);font-size:11.5px;color:var(--cream);opacity:.5;margin-bottom:22px;}
  .grain-spark{width:100%;height:64px;margin-top:auto;}
  .grain-source{
    font-family:var(--mono);font-size:10.5px;letter-spacing:.03em;color:var(--cream);opacity:.45;
    margin-top:16px;padding-top:16px;border-top:1px solid rgba(243,239,226,.16);
  }

  .grain-list{display:flex;flex-direction:column;gap:14px;}
  .grain-mini{
    background:linear-gradient(150deg, var(--amber-card) 0%, var(--amber-card-2) 100%);
    border:1px solid rgba(243,239,226,0.16);border-radius:3px;
    padding:18px 20px;display:flex;align-items:center;justify-content:space-between;gap:14px;
    flex:1;flex-wrap:wrap;min-width:0;
  }
  .grain-mini-name{font-family:var(--display);font-size:15px;font-weight:600;color:var(--cream);}
  .grain-mini-name span{display:block;font-family:var(--mono);font-size:10px;font-weight:400;opacity:.5;margin-top:3px;text-transform:uppercase;letter-spacing:.05em;}
  .grain-mini-demo{
    display:inline-block;margin-left:8px;font-family:var(--mono);font-size:8.5px;letter-spacing:.05em;text-transform:uppercase;
    color:var(--amber-1);background:rgba(243,239,226,.55);padding:2px 6px;border-radius:8px;vertical-align:middle;
  }
  .grain-mini-right{text-align:right;}
  .grain-mini-price{font-family:var(--mono);font-size:16px;color:var(--cream);font-weight:500;}
  .grain-mini-change{font-family:var(--mono);font-size:11.5px;margin-top:4px;}
  .grain-mini-change.up{color:var(--up);}
  .grain-mini-change.down{color:var(--down);}
  .grain-mini.soon{opacity:.45;}
  .grain-mini.soon .grain-mini-price{font-size:11px;letter-spacing:.05em;text-transform:uppercase;}

  @media(max-width:900px){
    .grain-wrap{grid-template-columns:minmax(0,1fr);}
    .grain-hero,.grain-list{min-width:0;}
  }

  .events-grid{display:grid;grid-template-columns:min(440px,42vw) 1fr;gap:56px;align-items:center;}
  .events-carousel{
    position:relative;height:400px;max-height:55vh;
    display:flex;align-items:center;justify-content:center;
    cursor:grab;user-select:none;
  }
  .events-carousel.dragging{cursor:grabbing;}
  .carousel-track{position:relative;width:100%;height:100%;}
  .carousel-item{
    position:absolute;left:50%;top:50%;width:min(440px,42vw);aspect-ratio:4/3;
    border:1px solid var(--line-dark);
    background:linear-gradient(150deg, var(--gold-card) 0%, var(--gold-card-2) 100%);
    display:flex;align-items:center;justify-content:center;text-align:center;
    transition:transform .55s cubic-bezier(.22,.7,.3,1),opacity .55s ease;
    will-change:transform,opacity;
  }
  .carousel-item span{
    font-family:var(--mono);font-size:13px;letter-spacing:.06em;text-transform:uppercase;
    color:var(--cream);opacity:.6;padding:0 14px;
  }
  .events-info{min-height:220px;position:relative;padding:6px 8px;}
  .ei-border{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;overflow:visible;}
  .ei-border rect{fill:none;stroke:var(--turquoise-light);stroke-width:1.5;opacity:.8;}
  .ei-date{font-family:var(--mono);font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;opacity:.6;margin-bottom:14px;transition:opacity .3s;}
  .ei-title{font-family:var(--display);font-size:26px;margin-bottom:16px;transition:opacity .3s;}
  .ei-desc{font-family:var(--body);font-size:16px;line-height:1.7;opacity:.9;margin-bottom:18px;transition:opacity .3s;}
  .ei-location{font-family:var(--mono);font-size:12px;opacity:.6;display:flex;align-items:center;gap:8px;transition:opacity .3s;}
  .ei-location .dot{width:6px;height:6px;border-radius:50%;background:var(--turquoise-light);flex:0 0 auto;}
  .events-info.fade{opacity:0;transform:translateY(6px);}
  .events-info{opacity:1;transform:none;transition:opacity .3s ease,transform .3s ease;}
  @media(max-width:820px){
    .events-grid{grid-template-columns:1fr;gap:36px;}
    .events-carousel{height:380px;}
    .events-carousel,.carousel-item{width:100%;}
    .carousel-item{width:min(320px,80vw);}
  }
  section.sand{background:var(--sand);}
  .section-head{max-width:640px;margin-bottom:64px;}
  .section-head h2{font-size:clamp(28px,3.4vw,42px);line-height:1.12;margin-bottom:18px;}
  .section-head p{font-family:var(--body);font-size:17px;line-height:1.7;opacity:.82;}
  section.dark .eyebrow{opacity:.6;}

  .rail{
    position:absolute;left:32px;top:0;bottom:0;width:1px;
    background:var(--line);display:none;
  }
  section.dark .rail{background:var(--line-dark);}
  @media(min-width:1100px){ .rail{display:block;} }

  .directions-grid{
    display:grid;grid-template-columns:repeat(3,1fr);gap:1px;
    background:var(--line);border:1px solid var(--line);
  }
  .dir-card{
    background:var(--sand-2);padding:34px 30px;min-height:280px;
    display:flex;flex-direction:column;
  }
  .dir-code{
    font-family:var(--mono);font-size:11px;letter-spacing:.1em;color:var(--ochre);
    margin-bottom:20px;padding-bottom:14px;border-bottom:1px solid var(--line);
    display:flex;justify-content:space-between;
  }
  .dir-card h3{font-size:19px;margin-bottom:14px;line-height:1.25;}
  .dir-card ul{list-style:none;font-family:var(--body);font-size:14.5px;line-height:1.55;opacity:.85;}
  .dir-card ul li{position:relative;padding-left:16px;margin-bottom:8px;}
  .dir-card ul li::before{content:'—';position:absolute;left:0;color:var(--turquoise);}

  @media(max-width:900px){
    .directions-grid{grid-template-columns:1fr;}
  }
  @media(min-width:901px) and (max-width:1200px){
    .directions-grid{grid-template-columns:repeat(2,1fr);}
  }

  .goals-wrap{display:grid;grid-template-columns:1.1fr 1fr;gap:70px;align-items:start;}
  .goals-list{list-style:none;}
  .goals-list li{
    display:flex;gap:20px;padding:22px 0;border-top:1px solid var(--line-dark);
    font-family:var(--body);font-size:16.5px;line-height:1.55;
  }
  .goals-list li:last-child{border-bottom:1px solid var(--line-dark);}
  .goals-list .g-num{font-family:var(--mono);font-size:12px;color:var(--turquoise-light);flex:0 0 auto;padding-top:2px;}
  .goals-visual{
    border:1px solid var(--line-dark);padding:30px;font-family:var(--mono);
    background:var(--navy-3);
  }
  .goals-visual .gv-label{font-size:11px;letter-spacing:.1em;text-transform:uppercase;opacity:.55;margin-bottom:20px;}
  .goals-visual .gv-figure{font-size:52px;font-family:var(--display);color:var(--turquoise-light);line-height:1;margin-bottom:10px;}
  .goals-visual .gv-desc{font-size:13px;line-height:1.6;opacity:.75;font-family:var(--body);}
  .goals-visual hr{border:none;border-top:1px solid var(--line-dark);margin:24px 0;}

  @media(max-width:860px){
    .goals-wrap{grid-template-columns:1fr;gap:40px;}
  }

  .adv-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:28px;}
  .adv-card{
    padding:32px 26px;background:var(--sand-2);border:1px solid var(--line);
  }
  section.dark .adv-card{background:var(--navy-2);border-color:var(--line-dark);}
  .adv-icon{width:38px;height:38px;margin-bottom:22px;}
  .adv-card h3{font-size:18px;margin-bottom:10px;}
  .adv-card p{font-family:var(--body);font-size:14.5px;line-height:1.6;opacity:.8;}
  @media(max-width:860px){ .adv-grid{grid-template-columns:1fr;} }

  .contact-grid{display:grid;grid-template-columns:1fr 1fr;gap:70px;}
  .contact-item{border-top:1px solid var(--line-dark);padding:22px 0;}
  .contact-item .ci-label{font-family:var(--mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase;opacity:.55;margin-bottom:
