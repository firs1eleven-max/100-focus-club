const menu=document.querySelector('.menu-toggle');const nav=document.querySelector('.nav');if(menu){menu.addEventListener('click',()=>{const open=nav.classList.toggle('open');menu.setAttribute('aria-expanded',open)})}document.querySelectorAll('.nav a').forEach(a=>a.addEventListener('click',()=>nav.classList.remove('open')));
async function submitForm(form,type){const status=form.querySelector('.form-status');const button=form.querySelector('button[type="submit"]');status.textContent='Submitting…';button.disabled=true;try{const data=Object.fromEntries(new FormData(form).entries());const r=await fetch('/api/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type,data})});const out=await r.json();if(!r.ok)throw new Error(out.error||'Submission failed');if(type!=='Sponsor / Donor Interest')form.reset();status.textContent=`Thank you. Your ${type.toLowerCase()} was received. Reference: ${out.reference}.`;status.style.color='#0B1F3A';if(type==='Sponsor / Donor Interest'){const support=form.querySelector('[name="support"]')?.value||'';const payable=['Donation','Financial sponsorship','Training sponsorship'].includes(support);const options=form.querySelector('.sponsor-payment-options');if(options){options.classList.toggle('is-visible',payable);if(payable)setTimeout(()=>options.scrollIntoView({behavior:'smooth',block:'nearest'}),150);}}}catch(e){status.textContent='We could not submit your information. Please try again.';status.style.color='#9b2c2c';}finally{button.disabled=false}}
document.querySelectorAll('form[data-type]').forEach(form=>form.addEventListener('submit',e=>{e.preventDefault();submitForm(form,form.dataset.type)}));
const cf=document.querySelector('#contact-form');if(cf)cf.addEventListener('submit',e=>{e.preventDefault();submitForm(cf,'Contact Message')});

function animateImpactCounters(){const counters=document.querySelectorAll('.impact-counter');if(!counters.length)return;const duration=1800;const start=performance.now();const tick=now=>{const progress=Math.min((now-start)/duration,1);counters.forEach((el,index)=>{if(progress<1){const value=Math.floor((1-Math.pow(1-progress,3))*(18+index*11));el.textContent=String(value).padStart(2,'0');}else{el.textContent=el.dataset.final||'Growing';}});if(progress<1)requestAnimationFrame(tick)};requestAnimationFrame(tick)}
const impact=document.querySelector('.impact');if(impact){const observer=new IntersectionObserver(entries=>{if(entries.some(entry=>entry.isIntersecting)){animateImpactCounters();observer.disconnect()}},{threshold:.25});observer.observe(impact)}

/* Multi-page navigation: highlight the current page and close the mobile menu after navigation. */
const currentPath=window.location.pathname.replace(/\/$/,'')||'/';
const navLinks=[...document.querySelectorAll('.nav a')];
navLinks.forEach(link=>{
  const href=link.getAttribute('href')||'';
  const target=href.split('#')[0].replace(/\/$/,'')||'/';
  const isHome=currentPath==='/'&&target==='/';
  const active=isHome||target===currentPath;
  link.classList.toggle('active',active);
  if(active)link.setAttribute('aria-current','page');
  else link.removeAttribute('aria-current');
});
document.querySelectorAll('.nav-dropdown').forEach(dropdown=>{
  const children=[...dropdown.querySelectorAll('.nav-dropdown-menu a')];
  const hasActive=children.some(link=>link.classList.contains('active'));
  if(hasActive){
    dropdown.classList.add('active-parent');
    dropdown.open=true;
  }
  const summary=dropdown.querySelector('summary');
  if(summary) summary.classList.toggle('active',hasActive);
});

/* Published website content powers the dedicated Stories page without hard-coded posts. */
(async function loadStories(){
  const posts=document.getElementById('latest-posts'), videos=document.getElementById('latest-videos'), photos=document.getElementById('latest-photos');
  if(!posts&&!videos&&!photos)return;
  try{
    const r=await fetch('/api/content?fresh='+Date.now(),{cache:'no-store'});
    if(!r.ok)throw new Error('content');
    const d=await r.json();
    const escapeHtml=s=>String(s||'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
    const embedVideo=url=>{try{const u=new URL(url);const id=u.searchParams.get('v')||u.pathname.split('/').pop();if(u.hostname.includes('youtu.be')||u.hostname.includes('youtube.com'))return '<iframe src="https://www.youtube.com/embed/'+encodeURIComponent(id)+'" title="Video" loading="lazy" allowfullscreen></iframe>';if(u.hostname.includes('vimeo.com'))return '<iframe src="https://player.vimeo.com/video/'+encodeURIComponent(id)+'" title="Video" loading="lazy" allowfullscreen></iframe>'}catch(e){}return '<a class="btn btn-primary" href="'+encodeURI(url)+'" target="_blank" rel="noopener">Watch Video</a>'};
    if(posts)posts.innerHTML=d.posts.map(p=>'<article class="content-card blog-card"><div class="content-card-header"><p class="eyebrow">BLOG</p><h3>'+escapeHtml(p.title)+'</h3></div>'+(p.image_url?'<img src="'+escapeHtml(p.image_url)+'" alt="'+escapeHtml(p.title)+'">':'')+'<div class="content-card-body"><p>'+escapeHtml(p.excerpt||String(p.body||'').slice(0,180))+'</p></div></article>').join('');
    if(videos)videos.innerHTML=d.videos.map(v=>'<article class="content-card video-card"><div class="content-card-header"><p class="eyebrow">VIDEO</p><h3>'+escapeHtml(v.title)+'</h3></div><div class="video-frame">'+embedVideo(v.url)+'</div><div class="content-card-body"><p>'+escapeHtml(v.description||'')+'</p></div></article>').join('');
    if(photos)photos.innerHTML=d.photos.map(p=>'<figure><img src="'+escapeHtml(p.url)+'" alt="'+escapeHtml(p.title)+'"><figcaption>'+escapeHtml(p.title)+'</figcaption></figure>').join('');
    if(!d.posts.length&&!d.videos.length&&!d.photos.length){const storySection=document.getElementById('stories');if(storySection)storySection.insertAdjacentHTML('beforeend','<p class="empty-content">New stories, photos and videos will appear here as they are published.</p>');}
  }catch(e){const storySection=document.getElementById('stories');if(storySection)storySection.insertAdjacentHTML('beforeend','<p class="empty-content">Stories and updates are temporarily unavailable. Please check back soon.</p>');}
})();

/* Accessibility controller — supports all display options and keeps old settings compatible. */
(function(){
  const toggle=document.querySelector('.accessibility-toggle');
  const panel=document.querySelector('#accessibility-panel');
  const close=document.querySelector('.accessibility-close');
  const controls=[...document.querySelectorAll('[data-a11y]')];
  const forms=[...document.querySelectorAll('form')];
  let generatedId=0;
  if(!toggle||!panel)return;
  const storageKey='focusclub-accessibility';
  const defaults={larger:false,contrast:false,underline:false,reduce:false,spacing:false,grayscale:false,cursor:false,focus:false};
  let state={...defaults};
  try{
    const saved=JSON.parse(localStorage.getItem(storageKey)||'{}');
    if(saved&&typeof saved==='object')state={...state,...saved};
  }catch(e){}
  const classMap={
    larger:'a11y-larger-text',contrast:'a11y-high-contrast',underline:'a11y-underline-links',
    reduce:'a11y-reduce-motion',spacing:'a11y-text-spacing',grayscale:'a11y-grayscale',
    cursor:'a11y-large-cursor',focus:'a11y-focus-highlight'
  };
  const keyForButton={
    'text-larger':'larger','high-contrast':'contrast','underline-links':'underline',
    'reduce-motion':'reduce','text-spacing':'spacing','grayscale':'grayscale',
    'large-cursor':'cursor','focus-highlight':'focus'
  };
  function enhanceForms(){
    forms.forEach(form=>{
      form.querySelectorAll('input,select,textarea').forEach(control=>{
        if(control.type==='hidden'||control.type==='checkbox'||control.dataset.a11yEnhanced)return;
        control.dataset.a11yEnhanced='true';
        const existing=control.id?form.querySelector(`label[for="${CSS.escape(control.id)}"]`):null;
        if(existing)return;
        if(!control.id)control.id=`a11y-field-${++generatedId}`;
        const label=document.createElement('label');
        label.className='sr-only';
        label.htmlFor=control.id;
        const name=control.getAttribute('name')||'';
        const placeholder=control.getAttribute('placeholder')||'';
        const fallback=name.replace(/[-_]/g,' ').replace(/\b\w/g,m=>m.toUpperCase());
        label.textContent=placeholder||fallback||'Form field';
        form.insertBefore(label,control);
        if(name)control.setAttribute('autocomplete',name==='email'?'email':name==='phone'?'tel':name==='name'?'name':name==='city'?'address-level2':'off');
      });
    });
  }
  function apply(){
    Object.entries(classMap).forEach(([key,cls])=>document.body.classList.toggle(cls,!!state[key]));
    controls.forEach(btn=>{
      const key=keyForButton[btn.dataset.a11y];
      if(key){
        btn.dataset.active=String(!!state[key]);
        btn.setAttribute('aria-pressed',String(!!state[key]));
      }else if(btn.dataset.a11y==='reset'){
        btn.dataset.active='false';
      }
    });
    try{localStorage.setItem(storageKey,JSON.stringify(state))}catch(e){}
  }
  function openPanel(){panel.hidden=false;toggle.setAttribute('aria-expanded','true');}
  function closePanel(){panel.hidden=true;toggle.setAttribute('aria-expanded','false');toggle.focus();}
  toggle.addEventListener('click',()=>panel.hidden?openPanel():closePanel());
  close?.addEventListener('click',closePanel);
  controls.forEach(btn=>btn.addEventListener('click',()=>{
    const action=btn.dataset.a11y;
    if(action==='reset') state={...defaults};
    else {
      const key=keyForButton[action];
      if(key) state[key]=!state[key];
    }
    apply();
  }));
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden)closePanel()});
  enhanceForms();
  apply();
})();


/* 100% Focus Club visitor chat */
(function(){
  const key='focusclub_chat_token';
  const escapeHtml=(v)=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const wrap=document.createElement('div'); wrap.className='chat-widget';
  wrap.innerHTML=`<button class="chat-launcher" type="button" aria-label="Open chat" aria-expanded="false" aria-controls="focus-chat-panel"><span aria-hidden="true">💬</span></button>
  <section class="chat-panel" id="focus-chat-panel" hidden aria-label="100% Focus Club chat">
    <header class="chat-header"><div><strong>100% Focus Club</strong><small>We're here to help</small></div><button type="button" class="chat-close" aria-label="Close chat">×</button></header>
    <div class="chat-messages" aria-live="polite"></div>
    <form class="chat-start-form"><div class="chat-fields">
      <input name="name" required placeholder="Your name" autocomplete="name">
      <input name="email" type="email" placeholder="Email (optional)" autocomplete="email">
      <input name="phone" placeholder="WhatsApp / phone (optional)" autocomplete="tel">
    </div><textarea name="message" required placeholder="How can we help?"></textarea>
    <button class="btn btn-primary" type="submit">Start Chat</button><p class="chat-status-message" aria-live="polite"></p></form>
    <form class="chat-reply-form" hidden><textarea name="message" required placeholder="Type your message…"></textarea>
    <button class="btn btn-primary" type="submit">Send</button><p class="chat-status-message" aria-live="polite"></p></form>
  </section>`;
  document.body.appendChild(wrap);
  const launcher=wrap.querySelector('.chat-launcher'), panel=wrap.querySelector('.chat-panel'), close=wrap.querySelector('.chat-close');
  const startForm=wrap.querySelector('.chat-start-form'), replyForm=wrap.querySelector('.chat-reply-form'), messages=wrap.querySelector('.chat-messages');
  let token=localStorage.getItem(key), lastId=0;
  function open(){panel.hidden=false;launcher.setAttribute('aria-expanded','true');if(token)load();}
  function shut(){panel.hidden=true;launcher.setAttribute('aria-expanded','false');}
  function addMessage(sender,message){const item=document.createElement('div');item.className='chat-message '+sender;item.innerHTML='<span class="chat-sender">'+escapeHtml(sender==='admin'?'Team':sender==='bot'?'100% Focus Club':'You')+'</span><p>'+escapeHtml(message)+'</p>';messages.appendChild(item);messages.scrollTop=messages.scrollHeight;}
  async function load(){if(!token)return;try{const r=await fetch('/api/chat?token='+encodeURIComponent(token)+'&after='+lastId,{cache:'no-store'});if(!r.ok){localStorage.removeItem(key);token=null;return;}const d=await r.json();if(d.status==='Closed'){localStorage.removeItem(key);token=null;return;}d.messages.forEach(m=>{lastId=Math.max(lastId,m.id);addMessage(m.sender,m.message);});}catch(e){}}
  startForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(startForm).entries()),status=startForm.querySelector('.chat-status-message');status.textContent='Connecting…';try{const r=await fetch('/api/chat/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),d=await r.json();if(!r.ok)throw new Error(d.error||'Unable to start chat');token=d.token;localStorage.setItem(key,token);startForm.hidden=true;replyForm.hidden=false;messages.innerHTML='';lastId=0;await load();status.textContent='';}catch(err){status.textContent=err.message;}});
  replyForm.addEventListener('submit',async e=>{e.preventDefault();const input=replyForm.elements.message,message=input.value.trim(),status=replyForm.querySelector('.chat-status-message');if(!message)return;input.disabled=true;status.textContent='Sending…';try{const r=await fetch('/api/chat/message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token,message})});if(!r.ok){const d=await r.json();throw new Error(d.error||'Send failed');}input.value='';status.textContent='';await load();}catch(err){status.textContent=err.message;}finally{input.disabled=false;input.focus();}});
  close.addEventListener('click',shut);launcher.addEventListener('click',open);
  if(token){startForm.hidden=true;replyForm.hidden=false;load();}
  setInterval(()=>token&&load(),8000);
})();